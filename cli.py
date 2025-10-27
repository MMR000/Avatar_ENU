# cli.py — Edge-TTS + Wav2Lip пакет режимі (қос JSONL лог)
# --------------------------------------------------------------------
# ① Ұзын мәтінді енгізіңіз → бос жол (Enter) → аяқтау
# ② Аватар жынысын таңдаңыз (m – ер, f – әйел)
# ③ Әр сегментке бірегей action (1-20) тағайындау, алдын-ала кесте көрсету
# ④ MAX_WORKERS (3) ағынмен:
#      • Edge-TTS (16 kHz WAV)
#      • Wav2Lip (ауыз қимылы) — stdout прогрессі префикспен
#      • clip біткенде OutputLogger-ге жазу
# ⑤ static/logs/ ішінде екі файл:
#      session_*_ids.jsonl     — API деңгейіндегі ID-лер
#      session_*_clips.jsonl   — дайын клип ақпараты
# ⑥ Клиптер жойылмайды; қаласаңыз ffmpeg біріктіру ұсынылады
# --------------------------------------------------------------------

import os, sys, subprocess, pathlib, concurrent.futures
from typing import List, Optional

from utils.nlp import parse_text
from utils.tts import synthesize_speech
from utils.video_utils import TEMPLATE_DIR, OUTPUT_DIR, WAV2LIP_DIR
from utils.merge import concat_videos
from utils.classify import classify_sentence_structure
from utils.api_id import IDLogger
from utils.output_id import OutputLogger

AUDIO_DIR = pathlib.Path("static/audio").resolve(); AUDIO_DIR.mkdir(exist_ok=True)
LOG_DIR   = pathlib.Path("static/logs").resolve();  LOG_DIR.mkdir(exist_ok=True)
MAX_WORKERS = 3

# ------------------------------------------------------------------ helpers
def assign_actions(sentences: List[str], gender: str):
    """[(idx, sentence, action_id, template)]"""
    mapping = []
    for idx, sent in enumerate(sentences, 1):
        action_id, _ = classify_sentence_structure(None)
        mapping.append((idx, sent, action_id, f"{gender}_{action_id}.mp4"))
    return mapping


def run_clip(idx: int, sentence: str, gender: str, action_id: int,
             clip_logger: OutputLogger) -> str:
    """TTS + Wav2Lip for single clip; write clip log when ready."""
    # ---------- 1) Edge-TTS
    audio_path = AUDIO_DIR / f"seg_{idx:03d}.wav"
    synthesize_speech(sentence, str(audio_path), voice_gender=gender)

    # ---------- 2) Wav2Lip
    template  = TEMPLATE_DIR / f"{gender}_{action_id}.mp4"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path  = OUTPUT_DIR / f"vid_{idx:03d}.mp4"

    cmd = [
        "python", str(WAV2LIP_DIR / "inference.py"),
        "--checkpoint_path", str(WAV2LIP_DIR / "checkpoints/wav2lip_gan.pth"),
        "--segmentation_path", str(WAV2LIP_DIR / "checkpoints/face_segmentation.pth"),
        "--enhance_face", "gfpgan",
        "--face", str(template),
        "--audio", str(audio_path),
        "--outfile", str(out_path),
    ]
    print(f"[{idx:02d}] 🎞️  Lip Sync басталды (action {action_id})")
    proc = subprocess.Popen(cmd, cwd=str(WAV2LIP_DIR),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"})
    assert proc.stdout
    for line in proc.stdout:
        print(f"[{idx:02d}] {line.rstrip()}")
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Wav2Lip {idx} клипі қате ({proc.returncode})")

    print(f"[{idx:02d}] ✓ Дайын → {out_path}")

    # ---------- 3) Clip-level log
    clip_logger.add_entry(
        text_clip_id   = idx,
        video_path     = str(out_path),
        avatar_action_id = action_id
    )
    return str(out_path)

# ------------------------------------------------------------------ main
def main():
    # 1. Мәтін енгізу (бос жол – тоқтату)
    print("Ұзын мәтінді енгізіңіз (аяқтау үшін бос жолда Enter басыңыз):")
    lines: List[str] = []
    while True:
        ln = input()
        if ln.strip() == "":
            break
        lines.append(ln)
    text = "\n".join(lines)

    # 2. Сегменттеу
    sentences, _ = parse_text(text)

    # 3. Аватар жынысын таңдау
    while True:
        gender = input("Аватар жынысы (m – ер, f – әйел): ").strip().lower()
        if gender in {"m", "f"}:
            break

    # 4. Action тағайындау және кесте
    mapping = assign_actions(sentences, gender)
    print("\n=== Клип – Шаблон сәйкестігі ===")
    for idx, sent, aid, tpl in mapping:
        print(f"{idx:02d}: {sent}  →  {tpl}")
    input("\nБастау үшін Enter басыңыз…")

    # 5. Логгерлер
    api_logger   = IDLogger(LOG_DIR)
    clip_logger  = OutputLogger(LOG_DIR)
    avatar_gender_id = 1 if gender == "m" else 2
    voice_gender_id  = avatar_gender_id

    #   5-a. Алдын-ала API-ID жазу
    for idx, _s, aid, _tpl in mapping:
        api_logger.add_entry(
            text_clip_id      = idx,
            orig_voice_id     = 1000 + idx,
            avatar_action_id  = aid,
            avatar_gender_id  = avatar_gender_id,
            voice_gender_id   = voice_gender_id,
            target_voice_id   = None,
            after_voice_id    = None,
        )

    # 6. Клиптерді параллель генерациялау
    videos: List[Optional[str]] = [None] * len(mapping)
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        fut_map = {
            pool.submit(run_clip, idx, sent, gender, aid, clip_logger): idx
            for idx, sent, aid, _tpl in mapping
        }
        for fut in concurrent.futures.as_completed(fut_map):
            idx = fut_map[fut]
            try:
                videos[idx-1] = fut.result()
            except Exception as exc:
                print(f"[{idx:02d}] ✗ Қате: {exc}")

    # 7. Лог файлдары
    print(f"\nAPI ID логы  → {api_logger.file_path()}")
    print(f"Клип логы    → {clip_logger.file_path()}")

    # 8. Біріктіру сұрау
    if input("\nБарлық клиптерді бір бейнеге біріктіруді қалайсыз ба? (y/n): ").lower() == "y":
        ready = [v for v in videos if v]
        if not ready:
            print("Біріктіруге жарамды клип жоқ!")
            return
        final_mp4 = "static/video_output/final_merged.mp4"
        print("🔗 ffmpeg арқылы біріктіру …")
        concat_videos(ready, final_mp4)
        print(f"🎬 Дайын бейне → {final_mp4}")
    else:
        print("Жеке клиптер static/video_output/ директориясында сақталды.")


if __name__ == "__main__":
    main()
