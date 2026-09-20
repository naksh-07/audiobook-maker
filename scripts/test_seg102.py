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
for line in env_file.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

import json
from audiobook_factory.tts_dispatcher import synthesize_gemini_tts

script = json.loads(Path("audiobooks/projects/witcher1/scripts/chapter_006_hi_script.json").read_text(encoding="utf-8"))
seg102 = [s for s in script if s.get("index") == 102][0]

text = seg102["text"]
out_file = Path("test_seg102.wav")

print(f"Testing segment 102 ({len(text)} chars)...")
try:
    path, dur = synthesize_gemini_tts(text, out_file, voice="Charon")
    print(f"SUCCESS: Generated {path} ({dur:.2f}s)")
except Exception as e:
    print(f"FAILED: {e}")
