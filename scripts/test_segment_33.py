#!/usr/bin/env python3
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env
env_file = ROOT_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from audiobook_factory.tts_dispatcher import synthesize_gemini_tts

for cand in ["भाग पाँच", "अध्याय 5", "पाँच", "भाग 5"]:
    try:
        path, dur = synthesize_gemini_tts(cand, Path("test_cand.wav"), voice="Charon")
        print(f"Candidate '{cand}' SUCCESS: {dur:.2f}s")
        break
    except Exception as e:
        print(f"Candidate '{cand}' FAILED: {e}")
