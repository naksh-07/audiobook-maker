import sys
import urllib.request
import json
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers

pool = get_persistent_key_pool()
with pool._connection() as conn:
    rows = conn.execute("SELECT status, count(*) FROM key_quota_ledger GROUP BY status").fetchall()
    print("Database key status summary:", [dict(r) for r in rows], flush=True)

k = pool.get_key("text")
print(f"Acquired text key: ...{k[-6:]}", flush=True)

models = ["gemini-2.5-flash", "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash"]

for m in models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
    data = json.dumps({"contents": [{"parts": [{"text": "Say namaste in Hindi"}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_stealth_sdk_headers(k), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read())
            txt = res["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"[OK] {m}: {txt}", flush=True)
    except Exception as e:
        print(f"[ERR] {m}: {e}", flush=True)
