import sys
import json
import sqlite3
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

conn = sqlite3.connect(REPO_ROOT / "audiobooks" / "key_pool_state.db")
c = conn.cursor()
total_keys = c.execute("SELECT COUNT(*) FROM key_quota_ledger").fetchone()[0]
active_keys = c.execute("SELECT COUNT(*) FROM key_quota_ledger WHERE status='ACTIVE'").fetchone()[0]
print(f"[*] Keys in Database: Total={total_keys}, Active={active_keys}")

rows = c.execute("SELECT api_key, status, total_calls_today, key_preview FROM key_quota_ledger").fetchall()

# Let's test which models respond across active keys
test_models = [
    "gemini-flash-latest",
    "gemini-pro-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-tts-preview"
]

print("\n[*] Testing model availability across active keys in pool:\n")

working_keys = [r[0] for r in rows if r[1] == "ACTIVE"]

for model in test_models:
    model_passed = False
    details = ""
    for k in working_keys[:5]: # test first few active keys
        is_tts = "tts" in model
        if is_tts:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k}"
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
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={k}"
            payload = {
                "contents": [{"parts": [{"text": "Hello, respond with ONE word: OK"}]}],
                "generationConfig": {"maxOutputTokens": 5}
            }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                cand = res.get("candidates", [{}])[0]
                if is_tts:
                    parts = cand.get("content", {}).get("parts", [{}])
                    has_audio = any("inlineData" in p for p in parts)
                    details = f"TTS Audio Generated (inlineData={has_audio})"
                else:
                    txt = cand.get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    details = f"Text Response: '{txt}'"
                model_passed = True
                break
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore")[:100].replace("\n", " ")
            details = f"HTTP {e.code}: {err_body}"
        except Exception as ex:
            details = f"Error: {ex}"
            
    status_tag = "[WORKING]" if model_passed else "[UNAVAILABLE]"
    print(f"  {status_tag:<14} {model:<30} -> {details}")
