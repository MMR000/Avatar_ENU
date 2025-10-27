"""
Celery worker-side logic: TTS → Wav2Lip → upload.
"""
import pathlib, logging
from app.celery_app import celery_app
from app.service   import upload_file, push, LipReq

from utils.nlp          import parse_text
from utils.tts          import synthesize_speech
from utils.video_utils  import generate_batch_lip_sync
from utils.merge        import concat_videos
from utils.classify     import classify_sentence_structure
from utils.api_id       import IDLogger
from utils.output_id    import OutputLogger

MEDIA_ROOT  = pathlib.Path("static").resolve()
MAX_WORKERS = 3

@celery_app.task(bind=True, name="app.tasks.lipsync_job")
def lipsync_job(self, req_dict: dict):
    req    = LipReq(**req_dict)
    job_id = req_dict["job_id"]

    jd       = MEDIA_ROOT / job_id
    audio_d  = jd / "audio"; audio_d.mkdir(parents=True, exist_ok=True)
    video_d  = jd / "video"; video_d.mkdir()
    log_d    = jd / "logs" ; log_d.mkdir()

    api_log  = IDLogger(log_d)
    clip_log = OutputLogger(log_d)

    # 1) 解析文本
    sentences, _ = parse_text(req.text)
    total = len(sentences)
    push(job_id, {"stage": "start", "total": total})

    # 2) 记录动作
    mapping = []
    for idx, sent in enumerate(sentences, 1):
        aid, _ = classify_sentence_structure(None)
        mapping.append((idx, sent, aid))
        api_log.add_entry(
            text_clip_id=idx, orig_voice_id=1000+idx,
            avatar_action_id=aid, avatar_gender_id=1 if req.gender=="m" else 2,
            voice_gender_id=1 if req.gender=="m" else 2,
        )

    # 3) TTS
    for idx, sent, _ in mapping:
        wav = audio_d / f"{idx:03d}.wav"
        synthesize_speech(sent, str(wav), voice_gender=req.gender)
        push(job_id, {"stage": "tts", "index": idx, "total": total})

    # 4) 口型
    clips_local = generate_batch_lip_sync(
        [(str(audio_d/f"{i:03d}.wav"), req.gender, aid) for i, _, aid in mapping],
        MAX_WORKERS, video_dir=video_d,
        on_done=lambda k: push(job_id, {"stage":"wav2lip","index":k,"total":total})
    )

    # 5) 上传
    clips_remote=[]
    for mp4 in clips_local:
        clips_remote.append(upload_file(mp4) or mp4)
    for (i, _s, aid), url in zip(mapping, clips_remote):
        clip_log.add_entry(text_clip_id=i, video_path=url, avatar_action_id=aid)

    # 6) 合并
    merged_url=None
    if req.merge and len(clips_local)>1:
        push(job_id, {"stage":"merge"})
        merged_local=str(video_d/f"{job_id}.mp4")
        concat_videos(clips_local, merged_local)
        merged_url=upload_file(merged_local) or merged_local

    # 7) 完成
    push(job_id, {"stage":"done","merged": merged_url or ""})
    return {"clips": clips_remote, "merged": merged_url,
            "api_log": api_log.file_path(), "clip_log": clip_log.file_path()}
