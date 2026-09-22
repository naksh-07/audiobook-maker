#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 6 Autonomous Speech Synthesis Runner.
Runs Gate 4 synthesis using the persistent SQLite key pool (92 keys) in strictly 1-worker
Stealth Human Cadence mode with TokenBucket rate limiting, SDK header emulation,
and instant fast-forward resume checkpointing.
"""

import sys
import time
import json
from pathlib import Path

# Ensure UTF-8 output on Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.key_manager import get_persistent_key_pool


def main():
    project_dir = Path("audiobooks/projects/witcher1").resolve()
    script_path = project_dir / "scripts" / "chapter_006_hi_script.json"
    audio_dir = project_dir / "audio_chunks"

    if not script_path.exists():
        print(f"[!] Script file not found: {script_path}")
        sys.exit(1)

    with open(script_path, "r", encoding="utf-8") as f:
        script = json.load(f)

    total_segments = len(script)
    cached_chunks = list(audio_dir.glob("c006_s*.wav"))

    print(f"=== Chapter 6 Stealth Speech Synthesis (Gate 4: 1-Worker Invariant) ===")
    print(f"  Script: {script_path.name} ({total_segments} segments)")
    print(f"  Target Audio Dir: {audio_dir}")
    print(f"  Already Cached on Disk: {len(cached_chunks)} / {total_segments} chunks ({len(cached_chunks)*100/total_segments:.1f}%)")

    pool = get_persistent_key_pool()
    pool_summary = pool.get_status_summary()
    print(f"  Persistent Key Pool: {pool_summary.get('active_keys', 0)} active keys, {pool_summary.get('exhausted_today', 0)} exhausted today")

    start_time = time.time()
    dispatcher = TTSDispatcher(
        project_dir=project_dir,
        max_workers=1,
        rpm=15.0,
    )

    print(f"[*] Starting speech synthesis in strictly 1-worker mode (Stealth Human Cadence)...")
    sys.stdout.flush()

    try:
        results = dispatcher.synthesize_chapter_script(script_path, chapter_num=6)
    except Exception as e:
        print(f"[!] Synthesis interrupted or quota paused: {e}")
        sys.stdout.flush()

    elapsed = time.time() - start_time
    chunks = list(audio_dir.glob("c006_s*.wav"))
    print(f"\n=== Synthesis Milestone ===")
    print(f"  Elapsed Time: {elapsed / 60.0:.2f} minutes")
    print(f"  Total Chunks on Disk: {len(chunks)} / {total_segments}")

    if len(chunks) == total_segments:
        print(f"[SUCCESS] 100% of Chapter 6 speech chunks synthesized ({len(chunks)}/{total_segments})!")
    else:
        missing = total_segments - len(chunks)
        print(f"[!] Checkpoint: {missing} chunks remaining ({len(chunks)}/{total_segments} ready).")

    sys.stdout.flush()


if __name__ == "__main__":
    main()
