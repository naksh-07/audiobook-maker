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
aiza_keys = [r[0] for r in c.execute("SELECT api_key FROM key_quota_ledger WHERE key_preview LIKE 'AIzaSy%' AND status='ACTIVE'").fetchall()]
aq_keys = [r[0] for r in c.execute("SELECT api_key FROM key_quota_ledger WHERE key_preview LIKE 'AQ.Ab%' AND status='ACTIVE'").fetchall()][:3]

for name, k in [("AIza key", aiza_keys[0])] + [("AQ key " + str(i), k) for i, k in enumerate(aq_keys)]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={k}"
    data = json.dumps({"contents": [{"parts": [{"text": "Hello"}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_stealth_sdk_headers(k), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(f"{name} ({k[:10]}...): SUCCESS", flush=True)
    except Exception as e:
        print(f"{name} ({k[:10]}...): FAILED ({e})", flush=True)
