#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
p = ROOT_DIR / "audiobooks" / "projects" / "witcher1" / "scripts"

ROMAN_MAP = {
    "I": "भाग एक",
    "II": "भाग दो",
    "III": "भाग तीन",
    "IV": "भाग चार",
    "V": "भाग पाँच",
    "VI": "भाग छह",
    "VII": "भाग सात",
    "VIII": "भाग आठ",
    "IX": "भाग नौ",
    "X": "भाग दस",
    "XI": "भाग ग्यारह",
    "XII": "भाग बारह",
    "XIII": "भाग तेरह",
    "XIV": "भाग चौदह",
    "XV": "भाग पंद्रह",
    "XVI": "भाग सोलह",
    "XVII": "भाग सत्रह",
    "XVIII": "भाग अठारह",
    "XIX": "भाग उन्नीस",
    "XX": "भाग बीस",
}

# Only update unstarted chapters 6, 8, 10, 12
for ch in [6, 8, 10, 12]:
    sf = p / f"chapter_{ch:03d}_hi_script.json"
    if not sf.exists():
        continue
    data = json.loads(sf.read_text(encoding="utf-8"))
    modified = False
    for s in data:
        t = s.get("text", "").strip()
        if t in ROMAN_MAP:
            s["text"] = ROMAN_MAP[t]
            print(f"Chapter {ch}: Segment {s.get('index')} '{t}' -> '{s['text']}'")
            modified = True
    if modified:
        sf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[+] Saved updated {sf.name}")
