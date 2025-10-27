#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os, json, uuid, pathlib, logging, time, functools, threading
import concurrent.futures as futures
import datetime
from typing import Any

import pika, requests

# ──────────────────── внешние утилиты ────────────────────
from utils.nlp import parse_text
from utils.tts import synthesize_speech
from utils.video_utils import generate_batch_lip_sync, make_video_with_green_background
from utils.merge import concat_videos
from utils.classify import classify_sentence_structure
from utils.api_id import IDLogger
from utils.output_id import OutputLogger

# ──────────────────── конфиг ────────────────────
RABBIT_HOST = os.getenv("RABBIT_HOST")
RABBIT_USER = os.getenv("RABBITMQ_USER")
RABBIT_PASS = os.getenv("RABBITMQ_PASS")

FILE_UPLOAD = os.getenv("FILE_SERVER_UPLOAD_URL", "http://10.255.161.3:9090/sendfile").strip()
SUB_FOLDER  = os.getenv("UPLOAD_SUBFOLDER", "avatar_pipe")
AUTH_TOKEN  = os.getenv("FILE_SERVER_TOKEN", "").strip()

QUEUE_IN        = os.getenv("RMQ_QUEUE_IN", "avatar_generated_tasks")
QUEUE_DONE_DEF  = os.getenv("RMQ_QUEUE_DONE", "avatar_generated_done")
QUEUE_ERROR     = os.getenv("RMQ_ERROR_QUEUE", "avatar_generated_errors")
MAX_RETRIES     = int(os.getenv("RMQ_MAX_RETRIES", 3))

# Если во входной очереди в брокере уже настроен DLX — укажи то же имя, чтобы избежать 406
DLX_NAME = os.getenv("RMQ_EXISTING_DLX", "retry_exchange").strip()  # оставь пустым, если у брокера DLX не стоит
DLK_NAME = os.getenv("RMQ_EXISTING_DLK", "").strip()                # если был задан x-dead-letter-routing-key

MEDIA_ROOT  = pathlib.Path("static/video_output").resolve()
MEDIA_ROOT.mkdir(exist_ok=True)
MAX_WORKERS = int(os.getenv("MAX_WORKERS", 1))
HEARTBEAT   = int(os.getenv("RMQ_HEARTBEAT", 60))
BLOCK_TOUT  = int(os.getenv("RMQ_BLOCK_TIMEOUT", 120))

# Опционально ограничим GPU-конкурентность (если используешь Wav2Lip на CUDA)
GPU_SEMAPHORE = threading.Semaphore(1)

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_file = os.path.join(LOG_DIR, f"celery_app_{timestamp}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),            # вывод в консоль
        logging.FileHandler(log_file, mode="w", encoding="utf-8")  # отдельный файл для этого запуска
    ]
)

# ──────────────────── helpers ────────────────────
def upload_file(fp: str) -> str | None:
    if not FILE_UPLOAD:
        return None
    try:
        headers = {}
        if AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
        with open(fp, "rb") as f:
            r = requests.post(
                FILE_UPLOAD,
                files={"file": (os.path.basename(fp), f, "video/mp4")},
                data={"subrootfolder": SUB_FOLDER},
                headers=headers,
                timeout=120,
            )
        if r.status_code != 200:
            logging.error("UPLOAD HTTP %s %s", r.status_code, r.text[:200])
            return None
        ctype = r.headers.get("content-type", "")
        if ctype.startswith(("text/", "application/json")):
            try:
                return json.loads(r.text)
            except json.JSONDecodeError:
                return r.text.strip().strip('"')
    except Exception as e:
        logging.error("UPLOAD exception: %s", e)
    return None


def lipsync_pipeline(text: str, gender: str, lang: str, use_avatar: bool, merge: bool,
                     page_id: int, content_id: int, text_id: int | None) -> dict[str, Any]:
    job_id = uuid.uuid4().hex
    job_dir = MEDIA_ROOT / job_id
    audio_d = job_dir / "audio"; audio_d.mkdir(parents=True, exist_ok=True)
    video_d = job_dir / "video"; video_d.mkdir()
    log_d   = job_dir / "logs";  log_d.mkdir()

    api_log  = IDLogger(log_d)
    clip_log = OutputLogger(log_d)

    sentences, _ = parse_text(text)

    # 2) TTS
    tasks = []
    for idx, sent in enumerate(sentences, 1):
        aid, _ = classify_sentence_structure(None)
        wav = audio_d / f"{idx:03d}.wav"
        synthesize_speech(sent, str(wav), voice_gender=gender, lang=lang)
        tasks.append((str(wav), gender, aid))
        api_log.add_entry(
            text_clip_id=idx, orig_voice_id=1000 + idx,
            avatar_action_id=aid, avatar_gender_id=1 if gender == "m" else 2,
            voice_gender_id=1 if gender == "m" else 2,
        )

    # 3) Видео
    clips_local: list[str] = []
    if use_avatar:
        for idx, (sentence, (wav_path, gender, aid)) in enumerate(zip(sentences, tasks), 1):
            logging.info("🔊 Wav2Lip task %d: text='%s', wav='%s', gender='%s', action_id=%s",
                         idx, sentence.strip(), wav_path, gender, aid)
            # если есть риск OOM — снимаем семафор
            with GPU_SEMAPHORE:
                clip_path = generate_batch_lip_sync([(str(wav_path), gender, aid)], 1, video_dir=video_d)[0]
                clips_local.append(clip_path)
                try:
                    import torch, gc
                    gc.collect(); torch.cuda.empty_cache()
                except Exception:
                    pass
    else:
        for idx, (wav_path, _, _) in enumerate(tasks, 1):
            out_path = video_d / f"{idx:03d}.mp4"
            make_video_with_green_background(str(wav_path), str(out_path))
            clips_local.append(str(out_path))

    # 4) Загрузка
    clips_remote = [upload_file(mp4) or mp4 for mp4 in clips_local]
    for (idx, _wav, aid), url in zip(tasks, clips_remote):
        clip_log.add_entry(text_clip_id=idx, video_path=url, avatar_action_id=aid)

    # 5) Сшивка
    merged_url = None
    if merge and clips_local:
        merged_local = video_d / f"{job_id}.mp4"
        concat_videos(clips_local, str(merged_local))
        merged_url = upload_file(str(merged_local)) or str(merged_local)

    return {
        "job_id": job_id,
        "clips": clips_remote,
        "merged": merged_url,
        "api_log": api_log.file_path(),
        "clip_log": clip_log.file_path(),
        "page_id": page_id,
        "content_id": content_id,
        "text_id": text_id,
        "use_avatar": use_avatar,
        "lang": lang,
    }

# ──────────────────── AMQP glue ────────────────────
POOL = futures.ThreadPoolExecutor(max_workers=MAX_WORKERS)

def conn_params() -> pika.ConnectionParameters:
    return pika.ConnectionParameters(
        host=RABBIT_HOST,
        credentials=pika.PlainCredentials(RABBIT_USER, RABBIT_PASS),
        heartbeat=HEARTBEAT,
        blocked_connection_timeout=BLOCK_TOUT,
        connection_attempts=10,
        retry_delay=5,
    )

def _declare_incoming(ch: pika.BlockingChannel):
    """Декларируем входную очередь, повторяя DLX-аргументы, если заданы через env."""
    args = {}
    if DLX_NAME:
        args["x-dead-letter-exchange"] = DLX_NAME
    if DLK_NAME:
        args["x-dead-letter-routing-key"] = DLK_NAME
    ch.queue_declare(queue=QUEUE_IN, durable=True, arguments=args or None)

def _declare_passive_or_create(ch: pika.BlockingChannel, qname: str):
    """Стараемся не портить чужие аргументы: сначала passive, иначе создаём простую durable."""
    try:
        ch.queue_declare(queue=qname, passive=True)
    except Exception:
        ch.queue_declare(queue=qname, durable=True)

def _publish(ch: pika.BlockingChannel, routing_key: str, body: dict[str, Any]):
    """Безопасная публикация: для входной очереди — совместимая декларация, для остальных — passive."""
    if routing_key == QUEUE_IN:
        _declare_incoming(ch)
    else:
        _declare_passive_or_create(ch, routing_key)

    ch.basic_publish(
        exchange="",
        routing_key=routing_key,
        body=json.dumps(body).encode(),
        properties=pika.BasicProperties(content_type="application/json", delivery_mode=2),
    )

def worker_job(ch: pika.BlockingChannel, tag: int, payload: dict[str, Any]):
    start_time = time.time()
    done_q = payload.get("done_queue", QUEUE_DONE_DEF)

    try:
        logging.info("🚀 START processing task: %s", payload)
        result = lipsync_pipeline(
            text=payload["text"],
            gender=payload.get("gender", "m"),
            lang=payload.get("lang", "kk"),
            use_avatar=bool(payload.get("useAvatar", True)),
            merge=bool(payload.get("merge", True)),
            page_id=payload["page_id"],
            content_id=payload["content_id"],
            text_id=payload.get("text_id"),
        )
        duration = time.time() - start_time
        logging.info("✅ FINISHED task page_id=%s in %.2f sec", payload.get("page_id"), duration)

        result["status"] = "done"

        def _ok():
            _declare_passive_or_create(ch, done_q)
            _publish(ch, done_q, result)

        ch.connection.add_callback_threadsafe(_ok)

    except Exception as exc:
        logging.exception("❌ Ошибка обработки таска: %s", exc)

        attempt = int(payload.get("retry", 0)) + 1
        retry_payload = payload.copy()
        retry_payload["retry"] = attempt
        retry_payload["last_error"] = str(exc)

        logging.info("🔁 Возврат в исходную очередь %s (попытка %s) для page_id=%s",
                     QUEUE_IN, attempt, payload.get("page_id"))

        def _republish():
            _publish(ch, QUEUE_IN, retry_payload)

        ch.connection.add_callback_threadsafe(_republish)
        time.sleep(5)

    # Подтверждаем текущее сообщение (копия уже опубликована либо результат отправлен)
    ch.connection.add_callback_threadsafe(lambda: ch.basic_ack(tag))

def consumer_cb(ch: pika.BlockingChannel, method, props, body: bytes):
    try:
        payload = json.loads(body)
        logging.info("📥 Received task: page_id=%s, content_id=%s, retry=%s",
                     payload.get("page_id"), payload.get("content_id"), payload.get("retry"))
    except Exception as e:
        logging.error("⛔️ Bad JSON: %s", e)
        ch.basic_ack(method.delivery_tag)
        return
    POOL.submit(worker_job, ch, method.delivery_tag, payload)

def consume_forever():
    while True:
        try:
            connection = pika.BlockingConnection(conn_params())
            channel = connection.channel()

            _declare_incoming(channel)  # совместимая декларация входной очереди

            channel.basic_qos(prefetch_count=MAX_WORKERS)
            channel.basic_consume(queue=QUEUE_IN, on_message_callback=consumer_cb)
            logging.info("🔌 Подключён к %s, слушаю %s", RABBIT_HOST, QUEUE_IN)
            channel.start_consuming()
        except KeyboardInterrupt:
            logging.info("👋 Stopped by user")
            break
        except Exception as e:
            logging.warning("⚠️ Connection error: %s – retrying in 5 sec", e)
            time.sleep(5)

if __name__ == "__main__":
    consume_forever()
