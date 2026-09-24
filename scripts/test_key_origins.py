import sqlite3
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
conn = sqlite3.connect(ROOT_DIR / "audiobooks" / "key_pool_state.db")
c = conn.cursor()

keys = c.execute("SELECT key_preview, api_key FROM key_quota_ledger").fetchall()
print(f"Total keys in ledger: {len(keys)}")

# Let's test a sample of 5 AIza keys and 5 AQ keys to see their success rate
import urllib.request
from audiobook_factory.cadence import get_stealth_sdk_headers

sample_aiza = [k for prev, k in keys if prev.startswith("AIza")][:5]
sample_aq = [k for prev, k in keys if prev.startswith("AQ.")][:10]

print("\n--- Testing AIza keys ---")
for k in sample_aiza:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={k}"
    data = json.dumps({"contents": [{"parts": [{"text": "Hi"}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_stealth_sdk_headers(k), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            print(f"AIza ...{k[-6:]}: OK")
    except Exception as e:
        print(f"AIza ...{k[-6:]}: {e}")

print("\n--- Testing AQ keys ---")
for k in sample_aq:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={k}"
    data = json.dumps({"contents": [{"parts": [{"text": "Hi"}]}]}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_stealth_sdk_headers(k), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            print(f"AQ ...{k[-6:]}: OK")
    except Exception as e:
        print(f"AQ ...{k[-6:]}: {e}")
