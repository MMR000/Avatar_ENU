# utils/merge.py
import subprocess, tempfile, os

def concat_videos(video_paths, output_path):
    """用 ffmpeg 按顺序合并 mp4，无重新编码."""
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        for p in video_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
        list_path = f.name
    try:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            output_path,
        ]
        subprocess.check_call(cmd)
    finally:
        os.remove(list_path)
