import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from audiobook_factory.key_manager import get_persistent_key_pool

pool = get_persistent_key_pool()
k = pool.get_key("text")
tts_k = pool.get_key("tts")

print(f"[*] Probing with active key ...{k[-6:]}:", flush=True)

# 1. Fetch live models list from Google API
list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={k}"
try:
    with urllib.request.urlopen(list_url, timeout=10.0) as r:
        data = json.loads(r.read())
        all_models = [m["name"].split("/")[-1] for m in data.get("models", [])]
        gen_models = [m["name"].split("/")[-1] for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        print(f"[+] Total models found on API: {len(all_models)}", flush=True)
        print(f"[+] Models supporting generateContent: {gen_models}\n", flush=True)
except Exception as e:
    print(f"[!] Failed to list models: {e}", flush=True)
    gen_models = ["gemini-flash-latest", "gemini-flash-lite-latest", "gemini-pro-latest", "gemini-2.5-flash"]

# 2. Test candidate models
target_models = [
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-pro-latest",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-3.1-flash-tts-preview",
]

for model in target_models:
    is_tts = "tts" in model
    key_to_use = tts_k if is_tts else k
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key_to_use}"
    
    if is_tts:
        payload = {
            "contents": [{"parts": [{"text": "Hello"}]}],
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
            "contents": [{"parts": [{"text": "Respond strictly with: LIVE"}]}],
            "generationConfig": {"maxOutputTokens": 5}
        }
        
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            cand = res.get("candidates", [{}])[0]
            if is_tts:
                print(f"  [ONLINE]  {model:<30} -> TTS Audio Generated Successfully (finishReason: {cand.get('finishReason')})", flush=True)
            else:
                txt = cand.get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                print(f"  [ONLINE]  {model:<30} -> Responded: \"{txt}\" (finishReason: {cand.get('finishReason')})", flush=True)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")[:100].replace("\n", " ")
        print(f"  [OFFLINE] {model:<30} -> HTTP {e.code}: {body}", flush=True)
    except Exception as ex:
        print(f"  [ERROR]   {model:<30} -> {ex}", flush=True)
