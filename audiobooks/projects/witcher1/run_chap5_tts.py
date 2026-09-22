#!/usr/bin/env python3
"""
Synthesizes all 49 speech segments for Chapter 5: The Voice of Reason 3.
Uses TTSDispatcher with 3 concurrent workers across the active key pool.
"""

import sys
import time
from pathlib import Path

# UTF-8 streams for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from audiobook_factory.tts_dispatcher import TTSDispatcher
from audiobook_factory.logger import logger

def main():
    project_dir = Path("audiobooks/projects/witcher1").resolve()
    script_path = project_dir / "scripts" / "chapter_005_hi_script.json"

    logger.info(f"[*] Starting Chapter 5 synthesis from {script_path.name}...")
    start_t = time.time()

    dispatcher = TTSDispatcher(
        project_dir=project_dir,
        default_backend="gemini_tts",
        max_workers=3,
        rpm=15.0,
    )

    audio_files = dispatcher.synthesize_chapter_script(
        script_path=script_path,
        chapter_num=5,
    )

    elapsed = time.time() - start_t
    print(f"\n[OK] Chapter 5 Synthesis Completed in {elapsed:.1f}s!")
    print(f"     Total Segments Synthesized: {len(audio_files)}")

if __name__ == "__main__":
    main()
