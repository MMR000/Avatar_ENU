# utils/video_utils.py
# =========================================================
# ① generate_lip_sync        —— 调一次 Wav2Lip 得到单段 MP4
# ② generate_batch_lip_sync  —— ThreadPool 并发、顺序返回
#    - 支持 on_done(idx) 回调，便于推送 WebSocket 进度
# ③ make_video_with_green_background —— 静态绿色背景 + 音频合成 MP4
# =========================================================

from __future__ import annotations
import pathlib, subprocess, os, uuid, threading, concurrent.futures
from typing import Sequence, Tuple, List, Callable, Optional

# --- 路径常量 -------------------------------------------------
TEMPLATE_DIR = pathlib.Path("static/video_templates").resolve()
WAV2LIP_DIR  = pathlib.Path("./wav2lip").resolve()
OUTPUT_DIR   = pathlib.Path("static/video_output").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- 单段口型同步视频生成 -------------------------------------
def generate_lip_sync(
    audio_path : str,
    gender     : str,
    action_id  : int,
    video_dir  : pathlib.Path | None = None,
    use_gpu    : bool = False,
    gpu_id     : int | None = None
) -> str:
    """
    根据 audio + 模板生成一段口型同步视频，返回 mp4 绝对路径
    gender: 'm' / 'f'
    """
    video_dir = video_dir or OUTPUT_DIR
    video_dir.mkdir(parents=True, exist_ok=True)

    template = TEMPLATE_DIR / f"{gender}_{action_id}.mp4"
    if not template.exists():
        raise FileNotFoundError(template)

    out_path = video_dir / f"{uuid.uuid4().hex}.mp4"

    cmd = [
        "python", str(WAV2LIP_DIR / "inference.py"),
        "--checkpoint_path", str(WAV2LIP_DIR / "checkpoints/wav2lip_gan.pth"),
        "--face", str(template),
        "--audio", str(audio_path),
        "--outfile", str(out_path),
        "--resize_factor", "3"
    ]
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = "0"        # CPU

    subprocess.check_call(cmd, cwd=str(WAV2LIP_DIR), env=env)
    return str(out_path)

# --- 批量并发口型同步 -----------------------------------------
Task = Tuple[str, str, int]  # (audio_path, gender, action_id)

_global_executor: concurrent.futures.ThreadPoolExecutor | None = None
_executor_lock  = threading.Lock()

def _get_executor(max_workers: int) -> concurrent.futures.ThreadPoolExecutor:
    global _global_executor
    with _executor_lock:
        if _global_executor is None or _global_executor._max_workers != max_workers:
            if _global_executor:
                _global_executor.shutdown(wait=False)
            _global_executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    return _global_executor

def generate_batch_lip_sync(
    tasks      : Sequence[Task],
    max_workers: int = 3,
    video_dir  : pathlib.Path | None = None,
    on_done    : Optional[Callable[[int], None]] = None
) -> List[str]:
    """
    tasks:       [(wav, gender, action_id), ...]
    max_workers: 并发数
    on_done(k):  每完成第 k 段（1-based）回调，可用于推送进度
    返回值:       与 tasks 顺序一致的 mp4 路径列表
    """
    results: List[str | None] = [None] * len(tasks)

    def _wrap(idx: int, t: Task):
        wav, g, aid = t
        path = generate_lip_sync(wav, g, aid, video_dir)
        if on_done:
            on_done(idx + 1)  # 1-based
        return idx, path

    exe = _get_executor(max_workers)
    futs = {exe.submit(_wrap, i, t): i for i, t in enumerate(tasks)}
    for fut in concurrent.futures.as_completed(futs):
        idx, path = fut.result()
        results[idx] = path
    return results  # type: ignore

# --- 绿色背景 + 音频合成视频 -----------------------------------
GREEN_BG_PATH = TEMPLATE_DIR / "green_bg.png"

def make_video_with_green_background(wav_path: str, out_path: str):
    """
    用纯绿色背景图 + 音频合成静态视频（用于 useAvatar=False 的场景）
    """
    if not GREEN_BG_PATH.exists():
        raise FileNotFoundError(f"Green background image not found: {GREEN_BG_PATH}")

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(GREEN_BG_PATH),
        "-i", wav_path,
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(out_path)
    ]
    subprocess.run(cmd, check=True)
