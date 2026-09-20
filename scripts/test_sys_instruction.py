#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env
env_file = ROOT_DIR / ".env"
for line in env_file.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from audiobook_factory.key_manager import get_persistent_key_pool

pool = get_persistent_key_pool()
api_key = pool.get_key()
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-tts-preview:generateContent?key={api_key}"

payload_with_sys = {
    "contents": [{"parts": [{"text": "परीक्षण वाक्य।"}]}],
    "systemInstruction": {"parts": [{"text": "Speak expressively."}]},
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Charon"}}}
    }
}

try:
    req = urllib.request.Request(url, data=json.dumps(payload_with_sys).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        print("With systemInstruction: SUCCESS")
except urllib.error.HTTPError as e:
    print("With systemInstruction: FAILED ->", e.read().decode("utf-8")[:120])

payload_without_sys = {
    "contents": [{"parts": [{"text": "परीक्षण वाक्य।"}]}],
    "generationConfig": {
        "responseModalities": ["AUDIO"],
        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Charon"}}}
    }
}

try:
    req = urllib.request.Request(url, data=json.dumps(payload_without_sys).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        print("Without systemInstruction: SUCCESS")
except urllib.error.HTTPError as e:
    print("Without systemInstruction: FAILED ->", e.read().decode("utf-8")[:120])
