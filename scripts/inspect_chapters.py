#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("audiobooks/projects/witcher1")
scripts = sorted((p / "scripts").glob("chapter_*_hi_script.json"))

print(f"{'CHAPTER':<12} {'SEGMENTS':<10} {'SOUNDSCAPE PLAN':<18} {'MASTERED M4A':<15}")
print("-" * 60)

total_segs = 0
for s in scripts:
    with open(s, "r", encoding="utf-8") as f:
        data = json.load(f)
    ch_num = int(s.name.split("_")[1])
    segs = len(data)
    total_segs += segs
    soundscape = (p / "soundscapes" / f"chapter_{ch_num:03d}_hi_soundscape.json").exists()
    mastered = (p / "mastered" / f"chapter_{ch_num:03d}_cinematic.m4a").exists()
    print(f"Chapter {ch_num:02d}   {segs:<10} {str(soundscape):<18} {str(mastered):<15}")

print("-" * 60)
print(f"Total Speech Segments: {total_segs}")
