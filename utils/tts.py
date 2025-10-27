# utils/tts.py — Multilingual Edge‑TTS integration
# -----------------------------------------------
# Generates **16‑kHz mono WAV** files compatible with Wav2Lip.
#
# • synthesize_speech(text, output_path, gender="m", lang="kk")
#     gender: "m" / "f" → 根据语言选择 Edge-TTS 声音
#     lang: "kk" / "ru" / "en"
#
# • Also supports full Edge-TTS voice ID directly as gender argument.
#
# Requirements (pip):  edge-tts  pydub  ffmpeg/avlib in PATH.

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Literal, Union

import edge_tts
from pydub import AudioSegment

# ---------------------------------------------------------------------------
# 多语言 Voice 映射
# ---------------------------------------------------------------------------

VOICE_MAP = {
    "kk": {
        "m": "kk-KZ-DauletNeural",
        "f": "kk-KZ-AigulNeural",
    },
    "ru": {
        "m": "ru-RU-DmitryNeural",
        "f": "ru-RU-SvetlanaNeural",
    },
    "en": {
        "m": "en-US-GuyNeural",
        "f": "en-US-JennyNeural",
    }
}


async def _edge_tts_to_mp3(text: str, voice: str, mp3_path: Path):
    """Asynchronously fetch TTS and write MP3 to *mp3_path*."""
    comm = edge_tts.Communicate(text, voice)
    await comm.save(str(mp3_path))


def synthesize_speech(
    text: str,
    output_path: Union[str, Path],
    voice_gender: Literal["m", "f"] | str = "m",
    lang: Literal["kk", "ru", "en"] = "kk"
):
    """
    Generate speech in selected language and save as 16‑kHz mono WAV.

    Parameters
    ----------
    text : str
        Text to be synthesised (Kazakh, Russian, or English).
    output_path : str | Path
        Destination *.wav* filename.
    voice_gender : "m" | "f" | str
        • "m" / "f" → gender selection for given language.
        • Or pass a full Edge‑TTS voice ID directly.
    lang : "kk" | "ru" | "en"
        Language of the voice. Default: "kk"
    """
    lang = lang.lower()
    gender = str(voice_gender).lower()
    voice_id = VOICE_MAP.get(lang, {}).get(gender, voice_gender)

    # 1) Fetch MP3 via Edge TTS (async) into temp file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_mp3:
        mp3_path = Path(tmp_mp3.name)
    asyncio.run(_edge_tts_to_mp3(text, voice_id, mp3_path))

    # 2) Convert MP3 → WAV (16 kHz mono) using pydub
    wav_path = Path(output_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    audio = AudioSegment.from_file(mp3_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(wav_path, format="wav")

    # 3) Cleanup temp
    mp3_path.unlink(missing_ok=True)

    return str(wav_path)  # convenient for callers
