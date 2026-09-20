#!/usr/bin/env python3
"""
Produce Chapter 2: The Witcher (विचर - Geralt vs Striga)
Full-cast Gemini 3.1 Flash TTS speech synthesis + 5-stage DSP vocal mastering +
SoundBank ambient score + -16dB dynamic sidechain ducking + EBU R128 broadcast release.
"""

import os
import sys
import time
import json
from pathlib import Path

# Configure Windows UTF-8 stdout
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent

# Load .env file manually
env_file = ROOT_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# Add project root to sys.path
sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.logger import logger
from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.soundscape import (
    render_chapter_soundscape,
    apply_dynamic_sidechain_ducking,
    get_audio_duration,
)

PROJECT_DIR = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
SCRIPT_PATH = PROJECT_DIR / "scripts" / "chapter_002_hi_script.json"
SOUNDSCAPE_PLAN = PROJECT_DIR / "soundscapes" / "chapter_002_hi_soundscape.json"
AUDIO_CHUNKS_DIR = PROJECT_DIR / "audio_chunks"
MASTERED_DIR = PROJECT_DIR / "mastered"
SOUNDSCAPES_DIR = PROJECT_DIR / "soundscapes"


def main():
    start_time = time.time()
    logger.info("=" * 70)
    logger.info("⚔️ PRODUCING CHAPTER 2: THE WITCHER (विचर - गेराल्ट और स्ट्रिगा)")
    logger.info("   Engine: Gemini 3.1 Flash TTS Pool (8 API Keys Rotating)")
    logger.info("   Lead Voice: Charon (Deep Gritty Baritone)")
    logger.info("=" * 70)

    if not SCRIPT_PATH.exists():
        raise FileNotFoundError(f"Script not found: {SCRIPT_PATH}")

    with open(SCRIPT_PATH, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    total_segments = len(script_data)
    total_chars = sum(len(s.get("text", "")) for s in script_data)
    logger.info(f"Loaded {total_segments} screenplay segments ({total_chars:,} characters).")

    # 1. Initialize TTS Dispatcher
    dispatcher = TTSDispatcher(
        project_dir=PROJECT_DIR,
        default_voice="Charon",
        max_workers=3,
        rpm=24.0,  # 3 workers with smooth pacing across 8 rotated keys
    )

    # 2. Synthesize Chapter 2 Audio Segments
    logger.info(f"\n[*] Starting speech synthesis for Chapter 2...")
    audio_files = dispatcher.synthesize_chapter_script(SCRIPT_PATH, chapter_num=2)
    logger.info(f"[+] All {len(audio_files)} audio segments ready in {AUDIO_CHUNKS_DIR.name}/")

    # 3. Concatenate and Master Vocals with 5-Stage DSP
    logger.info(f"\n[*] Applying 5-Stage Studio Vocal Mastering...")
    vocal_m4a = MASTERED_DIR / "chapter_002_mastered.m4a"
    concatenate_and_master_chapter(audio_files, vocal_m4a)
    vocal_dur = get_audio_duration(vocal_m4a)
    logger.info(f"[+] Mastered Vocal Stem: {vocal_m4a.name} ({vocal_dur:.1f}s / {vocal_dur/60.0:.1f} mins)")

    # 4. Render Soundscape Bed from SoundBank
    logger.info(f"\n[*] Rendering Atmospheric Soundscape Bed from SoundBank...")
    if SOUNDSCAPE_PLAN.exists():
        with open(SOUNDSCAPE_PLAN, "r", encoding="utf-8") as f:
            plan = json.load(f)
    else:
        plan = {
            "primary_mood": "tense",
            "ducking_attenuation_db": -16.0,
            "scenes": [
                {
                    "scene_id": 1,
                    "segment_start": 1,
                    "segment_end": total_segments,
                    "mood": "tense",
                    "ambient_volume": 0.35,
                    "description": "The Witcher dark fantasy atmosphere"
                }
            ],
            "sfx_cues": []
        }

    bgm_raw = SOUNDSCAPES_DIR / "chapter_002_bgm.wav"

    # Map segment durations for dynamic soundscape cue placement
    seg_durations = {}
    for seg in script_data:
        s_idx = seg.get("index", 1)
        matches = sorted(AUDIO_CHUNKS_DIR.glob(f"c002_s{s_idx:04d}_*.wav"))
        if matches:
            seg_durations[s_idx] = get_audio_duration(matches[0])

    render_chapter_soundscape(plan, vocal_dur, bgm_raw, segment_durations=seg_durations)
    logger.info(f"[+] Atmospheric Bed Ready: {bgm_raw.name}")

    # 5. Apply -16dB Dynamic Sidechain Ducking & Broadcast Release
    logger.info(f"\n[*] Applying -16dB Dynamic Sidechain Compression & Broadcast Limiter...")
    cinematic_m4a = MASTERED_DIR / "chapter_002_cinematic.m4a"
    apply_dynamic_sidechain_ducking(
        vocal_file=vocal_m4a,
        bgm_file=bgm_raw,
        output_file=cinematic_m4a,
        duck_attenuation_db=-16.0,
        attack_ms=150,
        release_ms=850,
    )

    elapsed_min = round((time.time() - start_time) / 60.0, 1)
    final_dur = get_audio_duration(cinematic_m4a)

    logger.info("=" * 70)
    logger.info("🎉 CHAPTER 2 PRODUCTION COMPLETE!")
    logger.info(f"   Deliverable Audio : {cinematic_m4a}")
    logger.info(f"   Audio Duration   : {final_dur:.1f}s ({final_dur/60.0:.1f} minutes)")
    logger.info(f"   Total Segments   : {len(audio_files)}/{total_segments}")
    logger.info(f"   Elapsed Time     : {elapsed_min} minutes")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
