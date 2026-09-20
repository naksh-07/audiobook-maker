#!/usr/bin/env python3
"""
Audiobook Factory - Autonomous Overnight Multi-Chapter Production Pipeline.
Orchestrates autonomous synthesis and studio mastering across Chapters 4-13:
1. Waits for currently running Chapter 4 to finish (if active).
2. Sequentially processes Chapters 5 through 13 with single-worker Stealth Human Cadence.
3. STRICT USER INVARIANT: If all segments of a chapter cannot be generated (e.g. keys exhaust),
   DO NOT run FFmpeg mastering/ducking on the partial chapter; leave audio chunks cached
   and wait for tomorrow's quota. Only 100% synthesized chapters are mastered and ducked.
4. Pauses cleanly when all keys in the pool are exhausted for the day.
"""

import os
import sys
import time
import json
import hashlib
from pathlib import Path

# Configure Windows UTF-8 stdout
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent

# Load .env file
env_file = ROOT_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.soundscape import (
    render_chapter_soundscape,
    apply_dynamic_sidechain_ducking,
    get_audio_duration,
)

PROJECT_DIR = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
SCRIPTS_DIR = PROJECT_DIR / "scripts"
SOUNDSCAPES_DIR = PROJECT_DIR / "soundscapes"
AUDIO_CHUNKS_DIR = PROJECT_DIR / "audio_chunks"
MASTERED_DIR = PROJECT_DIR / "mastered"


def wait_for_chapter_4():
    """Wait for Chapter 4 to finish if currently running."""
    ch4_cinematic = MASTERED_DIR / "chapter_004_cinematic.m4a"
    if ch4_cinematic.exists() and ch4_cinematic.stat().st_size > 50000:
        logger.info("[+] Chapter 4 is already finished and mastered.")
        return

    logger.info("[*] Chapter 4 production is in progress. Waiting for completion...")
    last_reported_count = -1
    while True:
        if ch4_cinematic.exists() and ch4_cinematic.stat().st_size > 50000:
            logger.info("[+] Chapter 4 production completed successfully!")
            break

        # Log chunk progress periodically
        ch4_chunks = list(AUDIO_CHUNKS_DIR.glob("c004_s*.wav"))
        if len(ch4_chunks) != last_reported_count:
            last_reported_count = len(ch4_chunks)
            logger.info(f"    ... Chapter 4 progress: {last_reported_count}/44 segments generated.")

        time.sleep(15.0)


def produce_chapter(ch_num: int) -> bool:
    """
    Produce a single chapter with full speech synthesis + vocal mastering + soundscape ducking.
    Returns True if chapter was 100% completed and mastered.
    Returns False if halted due to key quota exhaustion (incomplete chapter NOT mastered).
    """
    script_path = SCRIPTS_DIR / f"chapter_{ch_num:03d}_hi_script.json"
    if not script_path.exists():
        logger.error(f"Script not found: {script_path}")
        return False

    cinematic_m4a = MASTERED_DIR / f"chapter_{ch_num:03d}_cinematic.m4a"
    if cinematic_m4a.exists() and cinematic_m4a.stat().st_size > 50000:
        logger.info(f"[+] Chapter {ch_num} is already fully produced and mastered: {cinematic_m4a.name}")
        return True

    with open(script_path, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    total_segments = len(script_data)
    total_chars = sum(len(s.get("text", "")) for s in script_data)

    logger.info("\n" + "=" * 75)
    logger.info(f"🎙️  STARTING PRODUCTION: CHAPTER {ch_num:02d} ({total_segments} segments, {total_chars:,} chars)")
    logger.info("   Mode: Stealth Human Cadence (Single-Worker, Content-Aware Pacing)")
    logger.info("=" * 75)

    pool = get_persistent_key_pool()
    summary = pool.get_status_summary()
    active_keys = summary.get("active_keys", 0)
    logger.info(f"[*] Persistent Key Pool Status: {active_keys} active keys available.")

    if active_keys == 0:
        logger.critical(f"[QUOTA HALT] Zero active keys remaining in pool for date {summary['date']}.")
        return False

    # 1. Initialize TTS Dispatcher in Stealth Human Cadence Mode
    dispatcher = TTSDispatcher(
        project_dir=PROJECT_DIR,
        default_voice="Charon",
        max_workers=1,  # Strict single-thread sequential pacing
    )

    # 2. Synthesize Chapter Speech Segments
    synth_success = True
    try:
        audio_files = dispatcher.synthesize_chapter_script(script_path, chapter_num=ch_num)
    except Exception as e:
        logger.warning(f"Synthesis paused or encountered error for Chapter {ch_num}: {e}")
        synth_success = False

    # 3. VERIFY 100% COMPLETION BEFORE ANY FFMPEG PROCESSING
    # User Strict Invariant: "agar ksi chapters ka sara audio generate na ho paya ho
    # to usko ffmpeg m process krna mat puri generate krne ka wait krenge kl ki limits ka"
    all_segments_present = True
    valid_audio_files = []

    for seg in script_data:
        s_idx = seg.get("index", 1)
        text = seg.get("text", "")
        voice_cfg = dispatcher.voice_map.get(seg.get("speaker", "Narrator"), dispatcher.voice_map.get("Narrator", {}))
        voice = voice_cfg.get("voice", dispatcher.default_voice) if isinstance(voice_cfg, dict) else dispatcher.default_voice
        cache_key = f"{text}|{voice}".encode("utf-8")
        seg_hash = hashlib.md5(cache_key).hexdigest()[:8]
        seg_file = AUDIO_CHUNKS_DIR / f"c{ch_num:03d}_s{s_idx:04d}_{seg_hash}.wav"

        if seg_file.exists() and seg_file.stat().st_size > 1000:
            valid_audio_files.append(seg_file)
        else:
            all_segments_present = False
            break

    if not all_segments_present or len(valid_audio_files) < total_segments:
        logger.warning("=" * 75)
        logger.warning(
            f"⏸️  INCOMPLETE CHAPTER: Chapter {ch_num:02d} has {len(valid_audio_files)}/{total_segments} "
            f"segments generated."
        )
        logger.warning(
            "   [USER INVARIANT ENFORCED] Skipping FFmpeg mastering & ducking until 100% of segments "
            "are generated."
        )
        logger.warning("   Audio chunks safely cached in audio_chunks/. Pausing until quota resets tomorrow.")
        logger.warning("=" * 75)
        return False

    # 4. Concatenate and Master Vocals with 5-Stage DSP
    logger.info(f"\n[*] All {total_segments} segments verified! Applying 5-Stage Studio Vocal Mastering...")
    vocal_m4a = MASTERED_DIR / f"chapter_{ch_num:03d}_mastered.m4a"
    concatenate_and_master_chapter(valid_audio_files, vocal_m4a)
    vocal_dur = get_audio_duration(vocal_m4a)
    logger.info(f"[+] Mastered Vocal Stem: {vocal_m4a.name} ({vocal_dur:.1f}s / {vocal_dur/60.0:.1f} mins)")

    # 5. Render Atmospheric Soundscape Bed from SoundBank
    logger.info(f"\n[*] Rendering Atmospheric Soundscape Bed from SoundBank...")
    soundscape_plan_path = SOUNDSCAPES_DIR / f"chapter_{ch_num:03d}_hi_soundscape.json"
    if soundscape_plan_path.exists():
        with open(soundscape_plan_path, "r", encoding="utf-8") as f:
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
                    "ambient_volume": 0.25,
                    "description": "Atmospheric ambient bed"
                }
            ],
            "sfx_cues": []
        }

    bgm_raw = SOUNDSCAPES_DIR / f"chapter_{ch_num:03d}_bgm.wav"

    seg_durations = {}
    for seg in script_data:
        s_idx = seg.get("index", 1)
        matches = sorted(AUDIO_CHUNKS_DIR.glob(f"c{ch_num:03d}_s{s_idx:04d}_*.wav"))
        if matches:
            seg_durations[s_idx] = get_audio_duration(matches[0])

    render_chapter_soundscape(plan, vocal_dur, bgm_raw, segment_durations=seg_durations)
    logger.info(f"[+] Atmospheric Bed Ready: {bgm_raw.name}")

    # 6. Apply -16dB Dynamic Sidechain Ducking & Broadcast Release
    logger.info(f"\n[*] Applying -16dB Dynamic Sidechain Compression & Broadcast Limiter...")
    apply_dynamic_sidechain_ducking(
        vocal_file=vocal_m4a,
        bgm_file=bgm_raw,
        output_file=cinematic_m4a,
        duck_attenuation_db=-16.0,
        attack_ms=150,
        release_ms=850,
    )

    final_dur = get_audio_duration(cinematic_m4a)
    logger.info("=" * 75)
    logger.info(f"🎉 CHAPTER {ch_num:02d} PRODUCTION COMPLETE!")
    logger.info(f"   Deliverable Audio : {cinematic_m4a.name}")
    logger.info(f"   Audio Duration   : {final_dur:.1f}s ({final_dur/60.0:.1f} minutes)")
    logger.info("=" * 75)

    return True


def main():
    logger.info("=" * 80)
    logger.info("🚀 AUDIOBOOK FACTORY - AUTONOMOUS OVERNIGHT PRODUCTION ENGINE")
    logger.info("   Novel: The Last Wish (Witcher 1)")
    logger.info("   Strategy: Sequential processing until all API keys exhaust.")
    logger.info("   Invariant: Only 100% complete chapters are mastered with FFmpeg.")
    logger.info("=" * 80)

    # Step 1: Wait for Chapter 4 to complete
    wait_for_chapter_4()

    # Inter-chapter breather (60 seconds)
    logger.info("\n[INTER-CHAPTER BREATHER] Cooling off for 60s before next chapter session...")
    time.sleep(60.0)

    # Step 2: Loop through Chapters 5 to 13
    for ch_num in range(5, 14):
        pool = get_persistent_key_pool()
        active_keys = pool.get_status_summary().get("active_keys", 0)

        if active_keys == 0:
            logger.critical(
                f"\n[ALL KEYS EXHAUSTED] All 40 keys reached daily quota. "
                f"Halting overnight pipeline cleanly at Chapter {ch_num}. Goodnight!"
            )
            break

        logger.info(f"\n>>> Advancing to Chapter {ch_num:02d} with {active_keys} active keys remaining in pool.")
        success = produce_chapter(ch_num)

        if not success:
            logger.warning(
                f"\n[PIPELINE PAUSED] Chapter {ch_num:02d} could not be 100% completed today due to quota limits."
            )
            logger.warning(
                "Incomplete chapter was NOT mastered with FFmpeg per user instruction."
            )
            logger.warning("All generated segments are safely checkpointed in SQLite and disk. Pausing pipeline.")
            break

        # Natural studio break between finished chapters
        logger.info(f"\n[STUDIO BREATHER] Chapter {ch_num} mastered! Pausing 75s before opening next chapter...")
        time.sleep(75.0)

    logger.info("\n" + "=" * 80)
    logger.info("🏁 AUTONOMOUS PRODUCTION RUN FINISHED OR PAUSED FOR TODAY.")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
