import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

with open('audiobooks/projects/witcher1/scripts/chapter_012_hi_script.json', encoding='utf-8') as f:
    data = json.load(f)

for s in data:
    spk = s.get('speaker')
    if spk in ('Nenneke', 'King_Foltest', 'Velerad', 'Falwick', 'Vesemir'):
        idx = s.get('index')
        txt = s.get('text', '')[:80]
        print(f"[{idx}] {spk}: {txt}")
