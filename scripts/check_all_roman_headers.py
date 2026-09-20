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

ROMAN_REGEX = re.compile(r"^[IVXLCDMivxlcdm]+$")

HINDI_NUMS = {
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
}

found = []
for sf in sorted(p.glob("chapter_*_hi_script.json")):
    data = json.loads(sf.read_text(encoding="utf-8"))
    for s in data:
        t = s.get("text", "").strip()
        if ROMAN_REGEX.match(t):
            found.append((sf.name, s.get("index"), t))

print(f"Found {len(found)} Roman numeral segments across all scripts:")
for f in found:
    print(f"  {f[0]}: Segment {f[1]} -> '{f[2]}'")
