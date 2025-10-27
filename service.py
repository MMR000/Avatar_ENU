# service.py  —— FastAPI + WebSocket + 全文件上传
# =========================================================
import os, uuid, pathlib, threading, asyncio, json
from celery_app import start_rabbitmq_listener

from dotenv import load_dotenv

# --- ① 立即加载 .env，并取出配置 ----------------------------
load_dotenv()
UPLOAD_URL   = os.getenv("FILE_SERVER_UPLOAD_URL", "").strip()      # 必填
SUB_FOLDER   = os.getenv("UPLOAD_SUBFOLDER", "avatar_pipe").strip() # 可自定义
AUTH_TOKEN   = os.getenv("FILE_SERVER_TOKEN", "").strip()           # 若需鉴权
start_rabbitmq_listener()
import requests, logging
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from utils.nlp      import parse_text
from utils.tts      import synthesize_speech
from utils.video_utils import generate_batch_lip_sync
from utils.merge    import concat_videos
from utils.classify import classify_sentence_structure
from utils.api_id   import IDLogger
from utils.output_id import OutputLogger

# ---------- 全局常量 ----------
MEDIA_ROOT   = pathlib.Path("static").resolve(); MEDIA_ROOT.mkdir(exist_ok=True)
MAX_WORKERS  = 3
request_lock = threading.Lock()                  # 串行不同请求
progress_queues: dict[str, asyncio.Queue] = {}

# ---------- FastAPI ----------
app = FastAPI(title="Edge-TTS + Wav2Lip API")

class LipReq(BaseModel):
    text  : str
    gender: str = "m"   # 'm' / 'f'
    merge : bool = True

# ---------- 上传助手 ----------
def upload_file(file_path: str) -> str | None:
    if not UPLOAD_URL:
        logging.warning("[UPLOAD] UPLOAD_URL 未配置，跳过上传")
        return None
    try:
        with open(file_path, "rb") as fp:
            resp = requests.post(
                UPLOAD_URL,
                files={"file": (os.path.basename(file_path), fp, "video/mp4")},
                data ={"subrootfolder": SUB_FOLDER},
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"} if AUTH_TOKEN else {},
                timeout=120
            )
        if resp.status_code != 200:
            logging.error(f"[UPLOAD] HTTP {resp.status_code}: {resp.text[:120]}")
            return None

        # 纯文本
        ctype = resp.headers.get("content-type","")
        if ctype.startswith("text/") or ctype.startswith("application/octet-stream") or ctype.startswith("application/json"):
            try:
                logging.error(f"[UPLOAD] Status 200: {json.loads(resp.text)}")
                return json.loads(resp.text)
            except json.JSONDecodeError:
                return resp.text.strip().strip('"')

        return None
    except Exception as e:
        logging.exception(f"[UPLOAD] Exception: {e}")
        return None

# ---------- 进度推送 ----------
def push(job_id: str, msg: dict):
    q = progress_queues.get(job_id)
    if q:
        try: q.put_nowait(msg)
        except asyncio.QueueFull: pass

# ---------- WebSocket ----------
@app.websocket("/ws/lipsync/{job_id}")
async def ws_lipsync(ws: WebSocket, job_id: str):
    await ws.accept()
    q = progress_queues.setdefault(job_id, asyncio.Queue(maxsize=100))
    try:
        while True:
            data = await q.get()
            await ws.send_json(data)
            if data.get("stage") == "done":
                break
    except WebSocketDisconnect:
        pass
    finally:
        progress_queues.pop(job_id, None)

# ---------- 主接口 ----------
@app.post("/lipsync")
def lipsync(req: LipReq):

    if not req.text.strip():
        raise HTTPException(400, "text 不能为空")

    with request_lock:                   # 保证批次串行
        job_id = uuid.uuid4().hex

        # ---- 目录 / 日志 ----
        job_dir  = MEDIA_ROOT / job_id
        audio_d  = job_dir / "audio"; audio_d.mkdir(parents=True, exist_ok=True)
        video_d  = job_dir / "video"; video_d.mkdir()
        log_d    = job_dir / "logs" ; log_d.mkdir()
        api_log  = IDLogger(log_d)
        clip_log = OutputLogger(log_d)

        # ---- 1) 文本分句 ----
        sentences, _ = parse_text(req.text)
        total = len(sentences)
        push(job_id, {"stage":"start","total":total})

        # ---- 2) 动作随机 + API 日志 ----
        mapping = []
        for idx, sent in enumerate(sentences, 1):
            aid, _ = classify_sentence_structure(None)
            mapping.append((idx, sent, aid))
            api_log.add_entry(
                text_clip_id     = idx,
                orig_voice_id    = 1000+idx,
                avatar_action_id = aid,
                avatar_gender_id = 1 if req.gender=="m" else 2,
                voice_gender_id  = 1 if req.gender=="m" else 2,
                target_voice_id  = None,
                after_voice_id   = None,
            )

        # ---- 3) 生成 wav + 任务 ----
        tasks = []
        for idx, sent, aid in mapping:
            wav = audio_d / f"{idx:03d}.wav"
            synthesize_speech(sent, str(wav), voice_gender=req.gender)
            push(job_id, {"stage":"tts","index":idx,"total":total})
            tasks.append((str(wav), req.gender, aid))

        # ---- 4) 并发口型同步 ----
        clips_local = generate_batch_lip_sync(
            tasks, MAX_WORKERS, video_dir=video_d,
            on_done=lambda k: push(job_id, {"stage":"wav2lip","index":k,"total":total})
        )

        # ---- 5) 上传每个 clip ----
        clips_remote = []
        for mp4_path in clips_local:
            remote = upload_file(mp4_path) or mp4_path   # 上传失败则保留本地
            clips_remote.append(remote)

        for (idx, _s, aid), url in zip(mapping, clips_remote):
            clip_log.add_entry(text_clip_id=idx, video_path=url, avatar_action_id=aid)

        # ---- 6) 合并 & 上传 ----
        merged_url = None
        if req.merge and len(clips_local) > 1:
            push(job_id, {"stage":"merge"})
            merged_local = str(video_d / f"{job_id}.mp4")
            concat_videos(clips_local, merged_local)
            filepath = upload_file(merged_local)
            print(filepath)
            merged_url = filepath or merged_local

        # ---- 7) 完成 ----
        push(job_id, {"stage":"done","merged": merged_url or ""})

        return JSONResponse({
            "job_id"  : job_id,
            "clips"   : clips_remote,
            "merged"  : merged_url,
            "api_log" : api_log.file_path(),
            "clip_log": clip_log.file_path()
        })

# ---------- (可选) 下载本地合并文件 ----------
@app.get("/video/{job_id}.mp4")
def download(job_id: str):
    path = MEDIA_ROOT / job_id / "video" / f"{job_id}.mp4"
    if not path.exists():
        raise HTTPException(404, "未找到本地合并视频")
    return FileResponse(path, media_type="video/mp4", filename=path.name)
