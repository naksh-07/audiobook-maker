import sys
import json
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from audiobook_factory.key_manager import get_persistent_key_pool

pool = get_persistent_key_pool()

models_to_test = [
    ("gemini-3.8-flash", "text"),
    ("gemini-3.7-flash", "text"),
    ("gemini-3.5-flash", "text"),
    ("gemini-3.1-pro-preview", "text"),
    ("gemini-3.1-flash-lite", "text"),
    ("gemini-3.1-flash-tts-preview", "tts"),
    ("gemini-3.8-flash-tts", "tts"),
]

print("[*] Testing Modern Gemini Models against Key Pool:\n", flush=True)

for model, service in models_to_test:
    is_tts = service == "tts"
    success = False
    last_err = ""
    # Try with up to 3 keys from pool
    for attempt in range(3):
        k = pool.get_key(service)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k}"
        
        if is_tts:
            payload = {
                "contents": [{"parts": [{"text": "Testing voice synthesis."}]}],
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}
                },
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
                ]
            }
        else:
            payload = {
                "contents": [{"parts": [{"text": "Reply strictly with: SUCCESS"}]}],
                "generationConfig": {"maxOutputTokens": 5}
            }
            
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                cand = res.get("candidates", [{}])[0]
                if is_tts:
                    parts = cand.get("content", {}).get("parts", [{}])
                    has_audio = any("inlineData" in p for p in parts)
                    print(f"  [ONLINE]  {model:<30} -> TTS Audio Generated: {has_audio}", flush=True)
                else:
                    txt = cand.get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    print(f"  [ONLINE]  {model:<30} -> Response: '{txt}'", flush=True)
                success = True
                break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")[:100].replace("\n", " ")
            last_err = f"HTTP {e.code}: {err_body}"
            if e.code == 429:
                pool.mark_temporary_backoff(k, 15.0, "RPM probe")
            continue
        except Exception as ex:
            last_err = str(ex)
            continue
            
    if not success:
        print(f"  [FAILED]  {model:<30} -> {last_err}", flush=True)
