import sqlite3
import urllib.request
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.cadence import get_stealth_sdk_headers

conn = sqlite3.connect("audiobooks/key_pool_state.db")
c = conn.cursor()
aiza_keys = [r[0] for r in c.execute("SELECT api_key FROM key_quota_ledger WHERE key_preview LIKE 'AIzaSy%'").fetchall()]

print(f"Testing {len(aiza_keys)} AIza keys on gemini-3.8-flash...", flush=True)

for i, k in enumerate(aiza_keys, 1):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={k}"
    data = json.dumps({"contents": [{"parts": [{"text": "Translate to Hindi: The river was dark and deep."}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_stealth_sdk_headers(k), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            res = json.loads(r.read())
            txt = res["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"[OK] Key {i} ({k[:12]}...): {txt}", flush=True)
    except Exception as e:
        print(f"[ERR] Key {i} ({k[:12]}...): {e}", flush=True)
