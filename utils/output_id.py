"""
OutputLogger —— 记录 **每个小 clip 完成后** 才知道的结果
写入 JSON Lines：static/logs/session_<ts>_clips.jsonl
"""

from __future__ import annotations
import json, datetime
from pathlib import Path
from typing import Any

class OutputLogger:
    def __init__(self, log_dir: Path):
        log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self._path = log_dir / f"session_{ts}_clips.jsonl"

    def add_entry(self, **payload: Any) -> None:
        with self._path.open("a", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False)
            fp.write("\n")

    def file_path(self) -> str:
        return str(self._path)
