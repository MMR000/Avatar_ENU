# utils/video_utils.py

# ===========================================================

# ① generate_lip_sync — Calls Wav2Lip once to get a single MP4 segment

# ② generate_batch_lip_sync — ThreadPool concurrent, sequential return

# - Supports on_done(idx) callback, facilitating WebSocket progress pushing

# ③ make_video_with_green_background — Static green background + audio to synthesize MP4

# ============================================================

from __future__ import annotations
import pathlib, subprocess, os, uuid, threading, concurrent.futures
from typing import Sequence, Tuple, List, Callable, Optional

# --- Path constants -------------------------------------------
TEMPLATE_DIR = pathlib.Path("static/video_templates").resolve()
WAV2LIP_DIR  = pathlib.Path("./wav2lip").resolve()
OUTPUT_DIR   = pathlib.Path("static/video_output").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Single-segment lip-sync video generation -----------------
def generate_lip_sync(
    audio_path : str,
    gender     : str,
    action_id  : int,
    video_dir  : pathlib.Path | None = None,
    use_gpu    : bool = False,
    gpu_id     : int | None = None
) -> str:
    """
Generate a lip-synced video based on the audio and template, and return the absolute path of the mp4 file.
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

# --- Batch concurrent lip-sync -----------------------------------------
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
`max_workers`: Concurrency level

`on_done(k)`: Callback after the completion of the k-th segment (1-based), which can be used to push progress.

Return value: A list of mp4 paths in the same order as the tasks.
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

# --- Green background + audio-generated video-----------------------------------
GREEN_BG_PATH = TEMPLATE_DIR / "green_bg.png"

def make_video_with_green_background(wav_path: str, out_path: str):
    """
Create a static video using a pure green background image and audio (for scenarios where useAvatar=False).
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
