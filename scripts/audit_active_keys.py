import sqlite3
import urllib.request
import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.cadence import get_stealth_sdk_headers
from audiobook_factory.key_manager import get_persistent_key_pool

pool = get_persistent_key_pool()
conn = sqlite3.connect(ROOT_DIR / "audiobooks" / "key_pool_state.db")
c = conn.cursor()

keys = c.execute("SELECT api_key, key_preview FROM key_quota_ledger WHERE status='ACTIVE'").fetchall()
print(f"Auditing {len(keys)} ACTIVE keys on gemini-3.6-flash...", flush=True)

working_keys = []
exhausted_keys = []
overloaded_keys = []

for idx, (k, prev) in enumerate(keys, 1):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={k}"
    data = json.dumps({"contents": [{"parts": [{"text": "Hi"}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_stealth_sdk_headers(k), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            working_keys.append(k)
            print(f"[{len(working_keys)} OK] Key {idx}/{len(keys)} {prev} WORKING!", flush=True)
            if len(working_keys) >= 15:
                print("Found 15 active healthy keys! Stopping early.", flush=True)
                break
    except urllib.error.HTTPError as e:
        err_b = e.read().decode("utf-8", errors="ignore")
        if e.code == 429:
            exhausted_keys.append((k, err_b))
            print(f"[429] Key {idx}/{len(keys)} {prev} (429)", flush=True)
        elif e.code == 503:
            overloaded_keys.append((k, err_b))
            print(f"[503] Key {idx}/{len(keys)} {prev} (503)", flush=True)
        else:
            print(f"[{e.code}] Key {idx}/{len(keys)} {prev}", flush=True)
    except Exception as e:
        print(f"[ERR] Key {idx}/{len(keys)} {prev}: {e}", flush=True)

print(f"\nAudit complete: {len(working_keys)} working keys found!")
