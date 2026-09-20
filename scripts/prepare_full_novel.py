#!/usr/bin/env python3
"""
Full Novel Pre-Production Pipeline Runner:
1. Translates all remaining 12 chapters into dramatic literary Hindustani using Witcher Lore Glossary.
2. Generates dramatized screenplay script JSONs with multi-voice character attribution for all 13 chapters.
3. Generates Director Soundscape JSON Plans for all 13 chapters.
Zero audio generation (saving TTS quotas).
"""

import sys
import time
from pathlib import Path

# Configure UTF-8 for Devanagari logging
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.translator import translate_book_project
from audiobook_factory.script_builder import generate_project_scripts
from audiobook_factory.soundscape import generate_project_soundscapes

PROJECT_DIR = WORKSPACE_DIR / "audiobooks" / "projects" / "witcher1"

def main():
    print("=======================================================", flush=True)
    print("   THE WITCHER: NOVEL PRE-PRODUCTION ENGINE           ", flush=True)
    print("   Target: All 13 Chapters (90,654 Words)              ", flush=True)
    print("   Mode  : Hindi Translation + Scripts + Soundscapes  ", flush=True)
    print("=======================================================\n", flush=True)

    # Step 1: Translate all chapters to Hindi
    print("\n[STEP 1/3] Translating all chapters into literary Hindustani...", flush=True)
    trans_dir = translate_book_project(PROJECT_DIR, model="gemini-3-flash-preview")
    print(f"[OK] Hindi translation complete at: {trans_dir}\n", flush=True)

    # Step 2: Generate dramatized screenplay scripts
    print("[STEP 2/3] Generating screenplay scripts with multi-voice attribution...", flush=True)
    scripts_dir = generate_project_scripts(PROJECT_DIR, use_hindi=True, dramatized=True)
    print(f"[OK] Scripts generated at: {scripts_dir}\n", flush=True)

    # Step 3: Generate director soundscape plans
    print("[STEP 3/3] Generating Soundscape JSON plans...", flush=True)
    soundscapes_dir = generate_project_soundscapes(PROJECT_DIR)
    print(f"[OK] Soundscape plans ready at: {soundscapes_dir}\n", flush=True)

    print("=======================================================", flush=True)
    print("   [SUCCESS] FULL NOVEL PRE-PRODUCTION COMPLETE!      ", flush=True)
    print("   All 13 chapters translated, scripted & primed.     ", flush=True)
    print("=======================================================", flush=True)

if __name__ == "__main__":
    main()
