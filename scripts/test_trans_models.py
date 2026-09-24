import sys
import json
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers

pool = get_persistent_key_pool()
k = pool.get_key("text")

test_prompt = "Translate this paragraph into literary Hindustani: The silver sword was forged under the dying moon. Geralt gripped the leather hilt, his cat-like eyes narrowing against the mist."

test_models = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
    "gemini-pro-latest"
]

for m in test_models:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={k}"
    data = json.dumps({
        "contents": [{"parts": [{"text": test_prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=get_stealth_sdk_headers(k), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read())
            out = res["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"[OK] {m}: {out[:60]}...", flush=True)
            break
    except Exception as e:
        print(f"[ERR] {m}: {e}", flush=True)
