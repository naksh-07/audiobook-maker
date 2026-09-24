import urllib.request
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from audiobook_factory.key_manager import get_persistent_key_pool

pool = get_persistent_key_pool()
text_key = pool.get_key("text")
tts_key = pool.get_key("tts")

models_to_test = [
    ("gemini-pro-latest", "text", text_key),
    ("gemini-flash-latest", "text", text_key),
    ("gemini-flash-lite-latest", "text", text_key),
    ("gemini-2.5-pro", "text", text_key),
    ("gemini-2.5-flash-lite", "text", text_key),
    ("gemini-3.1-flash-tts-preview", "tts", tts_key),
]

print(f"[*] Testing candidate models against live Gemini API:\n")

for model_name, service, key in models_to_test:
    if service == "text":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": 'Respond strictly with the word "ONLINE_OK"'}]}],
            "generationConfig": {"maxOutputTokens": 10},
        }
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": "Hello"}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}},
            },
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            cand = res_data.get("candidates", [{}])[0]
            if service == "text":
                out = cand.get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                print(f"  [PASS] {model_name:<30} -> Responded: \"{out}\"")
            else:
                has_audio = "inlineData" in cand.get("content", {}).get("parts", [{}])[0]
                print(f"  [PASS] {model_name:<30} -> Audio Synthesized: {has_audio}")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="ignore")[:140].replace("\n", " ")
        print(f"  [FAIL] {model_name:<30} -> HTTP {e.code}: {err}")
    except Exception as ex:
        print(f"  [FAIL] {model_name:<30} -> Error: {ex}")
