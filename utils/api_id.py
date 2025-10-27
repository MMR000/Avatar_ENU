# utils/api_id.py — ID logging without circular imports
# ----------------------------------------------------
# Provides an `IDLogger` to collect per‑segment metadata and stream it to
# a JSON‑lines file (one JSON object per line). Front‑end can tail or fetch the
# file to monitor progress.

from __future__ import annotations

import json
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class IDLogger:
    """Log segment‑level IDs to a JSONL file (no external dependencies)."""

    def __init__(self, output_dir: Path):
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self._path = output_dir / f"session_{timestamp}_ids.jsonl"
        output_dir.mkdir(parents=True, exist_ok=True)
        self._entries: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_entry(
        self,
        *,
        text_clip_id: int,
        orig_voice_id: int,
        avatar_action_id: int,
        avatar_gender_id: int,
        voice_gender_id: int,
        target_voice_id: Optional[int] = None,
        after_voice_id: Optional[int] = None,
    ) -> None:
        """Append a new entry and write it immediately to disk."""
        entry: Dict[str, Any] = {
            "text_clip_id": text_clip_id,
            "orig_voice_id": orig_voice_id,
            "avatar_action_id": avatar_action_id,
            "avatar_gender_id": avatar_gender_id,
            "target_voice_id": target_voice_id,
            "after_voice_id": after_voice_id,
            "voice_gender_id": voice_gender_id,
        }
        self._entries.append(entry)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Convenience getters
    # ------------------------------------------------------------------

    def entries(self) -> List[Dict[str, Any]]:
        return self._entries

    def file_path(self) -> str:
        return str(self._path)
