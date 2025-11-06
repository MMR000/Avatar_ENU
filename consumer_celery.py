#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, uuid, pathlib, logging
import time
import pika, requests


from dotenv import load_dotenv

load_dotenv()

from utils.nlp          import parse_text
from utils.tts          import synthesize_speech
from utils.video_utils  import generate_batch_lip_sync
from utils.merge        import concat_videos
from utils.classify     import classify_sentence_structure
from utils.api_id       import IDLogger
from utils.output_id    import OutputLogger


RABBIT_HOST  = os.getenv("RABBIT_HOST")
RABBIT_USER  = os.getenv("RABBITMQ_USER")
RABBIT_PASS  = os.getenv("RABBITMQ_PASS")

FILE_UPLOAD  = os.getenv("FILE_SERVER_UPLOAD_URL", "").strip()
SUB_FOLDER   = os.getenv("UPLOAD_SUBFOLDER", "avatar_pipe").strip()
AUTH_TOKEN   = os.getenv("FILE_SERVER_TOKEN", "").strip()

QUEUE_IN     = "avatar_generated_task"
QUEUE_OUT_DEF= "avatar_generated_done"

MEDIA_ROOT   = pathlib.Path("static").resolve(); MEDIA_ROOT.mkdir(exist_ok=True)
MAX_WORKERS  = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)


def upload_file(fp: str) -> str | None:
    if not FILE_UPLOAD:
        logging.warning("FILE_SERVER_UPLOAD_URL is not configured, and the local path is returned directly.")
        return None
    try:
        with open(fp, "rb") as f:
            r = requests.post(
                FILE_UPLOAD,
                files={"file": (os.path.basename(fp), f, "video/mp4")},
                data={"subrootfolder": SUB_FOLDER},
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"} if AUTH_TOKEN else {},
                timeout=120
            )
        if r.status_code != 200:
            logging.error("UPLOAD HTTP %s %s", r.status_code, r.text[:120])
            return None

        ctype = r.headers.get("content-type", "")

        if ctype.startswith(("application/json", "text/")):
            try:
                data = json.loads(r.text)

                for k in ("url", "fileUrl", "path"):
                    if k in data:
                        return data[k]

                if isinstance(data.get("data"), dict):
                    for k in ("url", "fileUrl", "path"):
                        if k in data["data"]:
                            return data["data"][k]
            except json.JSONDecodeError:
                return r.text.strip().strip('"')

        return r.text.strip().strip('"')
    except Exception as e:
        logging.exception("UPLOAD exception: %s", e)
        return None

def lipsync_pipeline(text: str, gender: str = "m", merge: bool = True) -> dict:
    job_id   = uuid.uuid4().hex
    job_dir  = MEDIA_ROOT / job_id
    audio_d  = job_dir / "audio"; audio_d.mkdir(parents=True, exist_ok=True)
    video_d  = job_dir / "video"; video_d.mkdir()
    log_d    = job_dir / "logs" ; log_d.mkdir()

    api_log  = IDLogger(log_d)
    clip_log = OutputLogger(log_d)

    sentences, _ = parse_text(text)

    tasks = []
    for idx, sent in enumerate(sentences, 1):
        aid, _ = classify_sentence_structure(None)
        wav = audio_d / f"{idx:03d}.wav"
        synthesize_speech(sent, str(wav), voice_gender=gender)
        tasks.append((str(wav), gender, aid))
        api_log.add_entry(
            text_clip_id=idx,
            orig_voice_id=1000 + idx,
            avatar_action_id=aid,
            avatar_gender_id=1 if gender == "m" else 2,
            voice_gender_id=1 if gender == "m" else 2,
        )

    clips_local = generate_batch_lip_sync(tasks, MAX_WORKERS, video_dir=video_d)

    clips_remote = []
    for mp4 in clips_local:
        clips_remote.append(upload_file(mp4) or mp4)
    for (idx, _wav, aid), url in zip(tasks, clips_remote):
        clip_log.add_entry(text_clip_id=idx, video_path=url, avatar_action_id=aid)

    merged_url = None
    if merge and len(clips_local) > 1:
        merged_local = str(video_d / f"{job_id}.mp4")
        concat_videos(clips_local, merged_local)
        merged_url = upload_file(merged_local) or merged_local

    return {
        "job_id": job_id,
        "clips": clips_remote,
        "merged": merged_url,
        "api_log": api_log.file_path(),
        "clip_log": clip_log.file_path()
    }

def callback(ch, method, properties, body: bytes):
    try:
        payload = json.loads(body.decode())
        logging.info("🎫 Received task: %s", payload)

        text   = payload["text"]
        gender = payload.get("gender", "m")
        merge  = bool(payload.get("merge", True))
        done_q = payload.get("done_queue", QUEUE_OUT_DEF)

        result = lipsync_pipeline(text, gender, merge)
        result["status"] = "done"

        ch.queue_declare(queue=done_q, durable=True)
        ch.basic_publish(
            exchange="",
            routing_key=done_q,
            body=json.dumps(result).encode(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2)
        )
        logging.info("✅ The result has been sent to %s", done_q)

    except Exception as e:
        logging.exception("❌ Processing failure")
        err = {"status": "error", "error": str(e)}
        done_q = payload.get("done_queue", QUEUE_OUT_DEF) if "payload" in locals() else QUEUE_OUT_DEF
        ch.basic_publish(
            exchange="",
            routing_key=done_q,
            body=json.dumps(err).encode(),
            properties=pika.BasicProperties(content_type="application/json", delivery_mode=2)
        )
    finally:
        ch.basic_ack(delivery_tag=method.delivery_tag)

def main():
    credentials = pika.PlainCredentials(RABBIT_USER, RABBIT_PASS)
    params = pika.ConnectionParameters(host=RABBIT_HOST, credentials=credentials)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE_IN, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE_IN, on_message_callback=callback)

    logging.info("🔌 Connected %s, listening queue %s", RABBIT_HOST, QUEUE_IN)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logging.info("⏹️  Manual termination")
        channel.stop_consuming()

if __name__ == "__main__":
    main()
