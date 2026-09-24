#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 13 Fast & Robust Screenplay Builder (Batch Engine).
Converts Chapter 13 ('The Voice of Reason 7' / 'तर्क की आवाज़ 7') translation into an annotated
multi-cast screenplay JSON attributing dialogue to:
- Geralt (algenib)
- Narrator (Aoede)
- Dandelion (Puck)
- Falwick (Fenrir)
- Dennis_Cranmer (Fenrir)
- Tailles (Puck)
- Nenneke (Kore)
- Iola (Kore)
"""

import os
import sys
import re
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

# Ensure UTF-8 I/O for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers
from audiobook_factory.gate_auditor import audit_gate2_script

pool = get_persistent_key_pool()

CANONICAL_SPEAKERS = {
    "Narrator",
    "Geralt",
    "Dandelion",
    "Falwick",
    "Dennis_Cranmer",
    "Tailles",
    "Nenneke",
    "Iola",
}

SPEAKER_ALIAS_MAP = {
    "विचर": "Geralt",
    "गेराल्ट": "Geralt",
    "रिविया का गेराल्ट": "Geralt",
    "geralt": "Geralt",
    "geralt of rivia": "Geralt",
    "witcher": "Geralt",
    "डैंडेलियन": "Dandelion",
    "कवि": "Dandelion",
    "भाट": "Dandelion",
    "dandelion": "Dandelion",
    "jaskier": "Dandelion",
    "फ़ाल्विक": "Falwick",
    "काउंट फ़ाल्विक": "Falwick",
    "काउंट": "Falwick",
    "falwick": "Falwick",
    "count falwick": "Falwick",
    "डेनिस क्रैनमर": "Dennis_Cranmer",
    "डेनिस": "Dennis_Cranmer",
    "क्रैनमर": "Dennis_Cranmer",
    "कप्तान क्रैनमर": "Dennis_Cranmer",
    "बौना": "Dennis_Cranmer",
    "dennis": "Dennis_Cranmer",
    "cranmer": "Dennis_Cranmer",
    "dennis cranmer": "Dennis_Cranmer",
    "dennis_cranmer": "Dennis_Cranmer",
    "dwarf": "Dennis_Cranmer",
    "तैलिस": "Tailles",
    "टेल्स": "Tailles",
    "tailles": "Tailles",
    "sir tailles": "Tailles",
    "नेनेके": "Nenneke",
    "पुजारिन": "Nenneke",
    "माँ नेनेके": "Nenneke",
    "मदर नेनेके": "Nenneke",
    "nenneke": "Nenneke",
    "mother nenneke": "Nenneke",
    "इओला": "Iola",
    "iola": "Iola",
    "कथावाचक": "Narrator",
    "सूत्रधार": "Narrator",
    "विवरण": "Narrator",
    "narrator": "Narrator",
}


def call_llm_batch(
    batch_text: str,
    batch_idx: int,
    total_batches: int,
    preceding_context: str = "",
    max_retries: int = 15,
) -> List[Dict[str, Any]]:
    candidate_models = ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-flash-latest"]

    sys_prompt = """You are a Hollywood Audio Drama Screenwriter.
Convert Hindi novel prose into an annotated multi-cast screenplay JSON array for audio synthesis.

MANDATORY RULES:
1. Split into discrete lines of character dialogue vs narrator description. NEVER merge dialogue into narration.
2. Attribute EVERY line to one of these EXACT canonical character names:
   - 'Narrator' (narrative prose, descriptions)
   - 'Geralt' (Witcher Geralt / गेराल्ट)
   - 'Dandelion' (poet / डैंडेलियन)
   - 'Falwick' (Count Falwick / फ़ाल्विक)
   - 'Dennis_Cranmer' (Dwarf captain / डेनिस क्रैनमर)
   - 'Tailles' (Young knight / तैलिस)
   - 'Nenneke' (Mother Nenneke / नेनेके)
   - 'Iola' (Novice priestess / इओला)
3. Strip speech tags from dialogue ('उसने कहा', 'गेराल्ट बोला', 'फ़ाल्विक दहाड़ा') when spoken.
4. Keep the text 100% complete and verbatim in Devanagari Hindi. Do NOT skip or summarize.
5. In 'text', you may prepend expressive tags: [whispers], [shouting], [cold menace], [growl], [sighs], [choked gasp].
6. Output MUST be a valid JSON array of segment objects."""

    prompt = f"""Language: Hindi (Devanagari)
Preceding Context: {preceding_context if preceding_context else "Continuing chapter scene."}

Text to Convert to Screenplay JSON:
\"\"\"
{batch_text}
\"\"\"

Output format: Return ONLY a JSON list of objects:
[
  {{
    "type": "narration" | "dialogue",
    "speaker": "Narrator" | "Geralt" | "Dandelion" | "Falwick" | "Dennis_Cranmer" | "Tailles" | "Nenneke" | "Iola",
    "text": "verbatim Devanagari text",
    "emotion": "neutral" | "angry" | "whispering" | "sad" | "excited" | "growl" | "calm_raspy",
    "intensity_level": "low" | "medium" | "high",
    "pre_roll_breath_ms": 0 or 150,
    "pause_after_ms": 400,
    "acting": {{"delivery_style": "neutral" | "cold_menace" | "ironic_mockery" | "bellowing_rage", "pacing": 1.0}},
    "spatial": {{"pan": 0.0, "proximity": "normal_room"}},
    "acoustic_env": "forest_glade",
    "sfx_cues": []
  }}
]"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": sys_prompt}]},
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 4096,
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }
    data_bytes = json.dumps(payload).encode("utf-8")

    for model in candidate_models:
        for attempt in range(max_retries):
            curr_key = pool.get_key(service="text")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={curr_key}"
            headers = get_stealth_sdk_headers(curr_key)
            req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

            try:
                with urllib.request.urlopen(req, timeout=35.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if not candidates:
                        continue
                    candidate = candidates[0]
                    parts = candidate.get("content", {}).get("parts", [])
                    if not parts:
                        continue
                    raw_json = "".join(p.get("text", "") for p in parts if "text" in p).strip()

                    match = re.search(r"```(?:json)?\s*(.*?)```", raw_json, re.DOTALL)
                    if match:
                        raw_json = match.group(1).strip()
                    elif raw_json.startswith("```"):
                        raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json)
                        raw_json = re.sub(r"\s*```$", "", raw_json).strip()

                    parsed = json.loads(raw_json)
                    if isinstance(parsed, list):
                        return parsed
                    elif isinstance(parsed, dict) and "segments" in parsed:
                        return parsed["segments"]
            except urllib.error.HTTPError as e:
                err_msg = e.read().decode("utf-8", errors="ignore")
                if e.code in (429, 503, 500):
                    pool.mark_temporary_backoff(curr_key, 10.0, f"HTTP {e.code}")
                    print(f"    [Pacing] HTTP {e.code} on {model}. Retrying...", flush=True)
                    time.sleep(2.0)
                    continue
                else:
                    print(f"    [HTTP {e.code}] {err_msg[:80]}", flush=True)
                    break
            except TimeoutError:
                print(f"    [Timeout] Request on {model} timed out after 35s. Switching key/retry...", flush=True)
                time.sleep(1.0)
                continue
            except Exception as e:
                print(f"    [Err] {e}", flush=True)
                time.sleep(1.0)
                continue

    raise RuntimeError(f"Failed batch {batch_idx}/{total_batches} on all candidate models.")


def normalize_segment_speaker(seg: Dict[str, Any], env_default: str = "forest_glade") -> Dict[str, Any]:
    raw_spk = str(seg.get("speaker", "Narrator")).strip()
    norm_spk = SPEAKER_ALIAS_MAP.get(raw_spk.lower(), SPEAKER_ALIAS_MAP.get(raw_spk, raw_spk))

    if norm_spk not in CANONICAL_SPEAKERS:
        if "geralt" in raw_spk.lower() or "विचर" in raw_spk or "गेराल्ट" in raw_spk:
            norm_spk = "Geralt"
        elif "dandelion" in raw_spk.lower() or "कवि" in raw_spk or "भाट" in raw_spk or "डैंडेलियन" in raw_spk:
            norm_spk = "Dandelion"
        elif "falwick" in raw_spk.lower() or "फ़ाल्विक" in raw_spk:
            norm_spk = "Falwick"
        elif "cranmer" in raw_spk.lower() or "dennis" in raw_spk.lower() or "बौना" in raw_spk or "क्रैनमर" in raw_spk:
            norm_spk = "Dennis_Cranmer"
        elif "tailles" in raw_spk.lower() or "तैलिस" in raw_spk:
            norm_spk = "Tailles"
        elif "nenneke" in raw_spk.lower() or "नेनेके" in raw_spk:
            norm_spk = "Nenneke"
        elif "iola" in raw_spk.lower() or "इओला" in raw_spk:
            norm_spk = "Iola"
        else:
            norm_spk = "Narrator"

    seg["speaker"] = norm_spk

    spatial_presets = {
        "Narrator": {"pan": 0.0, "proximity": "intimate_close"},
        "Geralt": {"pan": -0.20, "proximity": "normal_room"},
        "Dandelion": {"pan": -0.35, "proximity": "normal_room"},
        "Falwick": {"pan": 0.30, "proximity": "normal_room"},
        "Dennis_Cranmer": {"pan": 0.10, "proximity": "normal_room"},
        "Tailles": {"pan": 0.40, "proximity": "normal_room"},
        "Nenneke": {"pan": 0.25, "proximity": "normal_room"},
        "Iola": {"pan": 0.15, "proximity": "intimate_close"},
    }
    if norm_spk in spatial_presets:
        seg["spatial"] = spatial_presets[norm_spk]

    if "acoustic_env" not in seg or not seg["acoustic_env"]:
        seg["acoustic_env"] = env_default

    return seg


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    translation_file = project_dir / "translation" / "chapter_013_hi.md"
    output_script_file = project_dir / "scripts" / "chapter_013_hi_script.json"
    cache_dir = project_dir / "scripts" / ".cache_ch13_batches"
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not translation_file.exists():
        raise FileNotFoundError(f"Translation file not found: {translation_file}")

    with open(translation_file, "r", encoding="utf-8") as f:
        full_text = f.read()

    # Split into paragraphs
    raw_paras = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    
    # Identify environment switch at Section II
    paras = []
    for p in raw_paras:
        if p.startswith("# तर्क की आवाज़ 7") or p == "## I":
            continue
        paras.append(p)

    # Group into lean batches of 10 paragraphs each
    BATCH_SIZE = 10
    batches = []
    for i in range(0, len(paras), BATCH_SIZE):
        chunk = paras[i:i + BATCH_SIZE]
        env = "temple_courtyard" if any("## II" in p or "मंदिर" in p or "इओला" in p for p in chunk) else "forest_glade"
        # clean header markers from chunk text
        clean_chunk = [p.replace("## II", "").strip() for p in chunk if p.replace("## II", "").strip()]
        batches.append(("\n\n".join(clean_chunk), env))

    print(f"[*] Sliced Chapter 13 into {len(batches)} lean batches (~10 paragraphs each).")

    all_segments = []
    global_index = 1
    prev_context = "Scene in forest clearing outside Ellander."

    for idx, (b_text, b_env) in enumerate(batches, 1):
        cache_file = cache_dir / f"batch_{idx:02d}.json"
        if cache_file.exists():
            print(f"[*] Restoring [{idx}/{len(batches)}] from cache ({cache_file.name})...")
            with open(cache_file, "r", encoding="utf-8") as cf:
                segs = json.load(cf)
        else:
            w_cnt = len(b_text.split())
            print(f"\n[*] Parsing [{idx}/{len(batches)}] ({w_cnt} words, env={b_env})...", flush=True)
            t0 = time.time()
            segs = call_llm_batch(b_text, idx, len(batches), prev_context)
            t_el = time.time() - t0
            print(f"[+] Batch {idx} parsed in {t_el:.1f}s ({len(segs)} segments).")
            with open(cache_file, "w", encoding="utf-8") as cf:
                json.dump(segs, cf, ensure_ascii=False, indent=2)

        for seg in segs:
            seg["index"] = global_index
            global_index += 1
            seg = normalize_segment_speaker(seg, env_default=b_env)
            all_segments.append(seg)

        if segs:
            prev_context = segs[-1].get("text", "")[-200:]
        time.sleep(1.0)

    print(f"\n[*] Assembled {len(all_segments)} total screenplay segments across {len(batches)} batches.")

    script_data = {
        "metadata": {
            "project_id": "witcher1",
            "chapter_id": "chapter_013",
            "title": "तर्क की आवाज़ 7",
            "total_segments": len(all_segments),
            "language": "hi",
            "parser_version": "3.8_sota_lean"
        },
        "segments": all_segments
    }

    with open(output_script_file, "w", encoding="utf-8") as out_f:
        json.dump(script_data, out_f, ensure_ascii=False, indent=2)

    print(f"[+] Screenplay saved to: {output_script_file.name}")

    # Audit Gate 2
    print("\n[*] Auditing Gate 2 (Screenplay Schema & Canonical Speakers)...")
    audit_res = audit_gate2_script(output_script_file, project_dir=project_dir)
    print(f"[OK] Gate 2 Audit Passed: {audit_res}")


if __name__ == "__main__":
    main()
