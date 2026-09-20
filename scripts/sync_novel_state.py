#!/usr/bin/env python3
"""
Sync all 13 chapter screenplay scripts into the SQLite ProjectStateLedger.
Provides 100% accurate global tracking across the entire novel.
"""

import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.state import ProjectStateLedger
PROJECT_DIR = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
SCRIPTS_DIR = PROJECT_DIR / "scripts"

ledger = ProjectStateLedger(PROJECT_DIR)

# Load voice registry if available
voice_registry = {}
v_file = PROJECT_DIR / "voice_registry.json"
if v_file.exists():
    voice_registry = json.loads(v_file.read_text(encoding="utf-8"))

total_scripts_registered = 0
for ch in range(1, 14):
    s_path = SCRIPTS_DIR / f"chapter_{ch:03d}_hi_script.json"
    if s_path.exists():
        script = json.loads(s_path.read_text(encoding="utf-8"))
        ledger.register_script_segments(ch, script, voice_registry, "Charon")
        total_scripts_registered += 1

progress = ledger.get_progress()

print("=" * 60)
print("  THE WITCHER 1: ACCURATE FULL NOVEL STATE TELEMETRY")
print("=" * 60)
print(f"  Total Canonical Chapters : 13")
print(f"  Chapters Registered      : {total_scripts_registered}")
print(f"  Total Speech Segments    : {progress['total_segments']}")
print(f"  Completed Audio Segments : {progress['completed']}")
print(f"  Pending Audio Segments   : {progress['pending']}")
print(f"  Novel Audio Completion   : {progress['progress_percent']}%")
print("=" * 60)
