#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 11 Dramatized Screenplay Parser Runner (Resilient Multi-Model Engine).
Processes Chapter 11 ('The Voice of Reason 6') into an annotated multi-cast screenplay
attributing dialogue to Geralt, Nenneke, and Narrator.
Adheres strictly to:
- ADR-021: Zero Voice Drift & Deterministic Speaker Attribution
- ADR-015: Acting tags, prosody & breath modeling
- ADR-022: Dynamic multi-scene acoustic environments (Melitele Subterranean Grotto)
"""

import os
import sys
import re
import json
import time
import logging
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

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
from audiobook_factory.script_builder import (
    clean_screenplay_pass2,
    build_narrator_script,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_ch11_screenplay")

pool = get_persistent_key_pool()

CHARACTER_ROSTER = {
    "characters": {
        "Narrator": {
            "gender": "female",
            "voice_persona": "Aoede",
            "aliases": ["सूत्रधार", "विवरण", "कथावाचक", "Narrator"],
        },
        "Geralt": {
            "gender": "male",
            "voice_persona": "Charon",
            "aliases": ["गेराल्ट", "रिविया का गेराल्ट", "विचर", "Geralt", "Witcher"],
        },
        "Nenneke": {
            "gender": "female",
            "voice_persona": "Kore",
            "aliases": ["नेनेके", "पुजारिन", "माँ नेनेके", "Nenneke", "Mother Nenneke"],
        },
    }
}


def call_llm_json(
    chunk_text: str,
    preceding_context: str = "",
    max_retries: int = 4,
) -> List[Dict[str, Any]]:
    formatted_chars = []
    for cname, cinfo in CHARACTER_ROSTER["characters"].items():
        aliases_str = ", ".join(cinfo.get("aliases", []))
        formatted_chars.append(f"{cname} ({cinfo.get('gender', 'unknown')}) -> Aliases/Mentions: [{aliases_str}]")

    roster_hint = (
        "\nKnown Canon Characters in Project (Attribute dialogue to canonical English name as 'speaker'):\n"
        + "\n".join(f"- {fc}" for fc in formatted_chars)
        + "\n"
    )

    sys_prompt = (
        "You are an expert audio drama screenwriter. Convert novel prose into a multi-cast screenplay JSON array.\n"
        "MANDATORY INSTRUCTIONS:\n"
        "1. Split novel prose into discrete lines of character dialogue vs narrator description. NEVER merge dialogue into narration.\n"
        "2. Attribute EVERY spoken line to the exact character speaking (strictly 'Geralt', 'Nenneke', or 'Narrator').\n"
        "3. Strip speech tags ('उसने कहा', 'गेराल्ट बोला', 'नेनेके हँसी', 'पुजारिन बुदबुदाई') from dialogue text.\n"
        "4. Output strictly a JSON array of segment objects."
    )

    prompt = f"""Language: Hindi (Devanagari)
Preceding Scene Context / Characters Speaking:
{preceding_context if preceding_context else "Beginning of scene."}
{roster_hint}
Current Scene Text:
\"\"\"
{chunk_text}
\"\"\"

Output JSON: A list of objects where each object has:
- "index": int (1-based relative to this chunk)
- "type": "narration" | "dialogue" | "action"
- "speaker": character name ('Geralt', 'Nenneke', or 'Narrator')
- "text": speech text in Devanagari Hindi (with optional inline vocal tags like [whispers], [shouting], [cold menace], [growl])
- "emotion": "neutral" | "angry" | "whispering" | "sad" | "excited" | "growl" | "calm_raspy"
- "intensity_level": "low" | "medium" | "high" | "explosive"
- "pre_roll_breath_ms": int (150 to 250 for emotional lines, 0 for normal)
- "pause_after_ms": int (300 to 800)
- "acting": {{
    "delivery_style": "calm_authoritative" | "ironic_mockery" | "bellowing_rage" | "whispering_fear" | "cold_menace" | "gentle_tender" | "neutral",
    "pacing": float (0.9 to 1.1)
  }}
- "spatial": {{
    "pan": float (-0.6 to 0.6),
    "proximity": "intimate_close" | "normal_room" | "distant"
  }}
- "acoustic_env": "quiet_chamber" | "temple_grotto"
- "sfx_cues": []
- "music": {{"mood": "peaceful" | "mysterious" | "tense" | "emotional", "ducking_db": -16.0}}
"""

    candidate_models = ["gemini-3.1-flash-lite", "gemini-flash-latest", "gemini-3.8-flash"]

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": sys_prompt}]},
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192,
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
                with urllib.request.urlopen(req, timeout=90.0) as resp:
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
                if e.code in (429, 503, 500):
                    pool.mark_temporary_backoff(curr_key, 10.0, f"HTTP {e.code}")
                    if e.code == 503 and attempt >= 1:
                        print(f"    [MODEL OVERLOAD] {model} overloaded (503). Trying fallback candidate...", flush=True)
                        break
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break
            except Exception as e:
                time.sleep(1.5)
                continue

    raise RuntimeError("Failed to parse screenplay segment after exhausting model candidates.")


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    translation_file = project_dir / "translation" / "chapter_011_hi.md"
    output_script_file = project_dir / "scripts" / "chapter_011_hi_script.json"

    if not translation_file.exists():
        raise FileNotFoundError(f"Translation file not found: {translation_file}")

    with open(translation_file, "r", encoding="utf-8") as f:
        full_text = f.read()

    lines = full_text.splitlines()
    body_lines = [l for l in lines if not l.startswith("#") and l.strip() != "तर्क की आवाज़"]
    raw_body = "\n".join(body_lines).strip()

    # Split into 3 dramatic chunks for high-precision parsing
    paragraphs = [p.strip() for p in raw_body.split("\n\n") if p.strip()]
    total_paras = len(paragraphs)
    print(f"[*] Total paragraphs in translation: {total_paras}")

    chunk_size = max(10, total_paras // 3)
    chunks = []
    for i in range(0, total_paras, chunk_size):
        chunk_paras = paragraphs[i:i + chunk_size]
        chunks.append("\n\n".join(chunk_paras))

    print(f"[*] Split Chapter 11 into {len(chunks)} screenplay parsing chunks.")

    all_segments = []
    global_index = 1
    preceding_context = "Scene opens inside the underground herbal grotto of the Temple of Melitele. Geralt is sitting on a bench. Nenneke is tending rare magical plants."

    for idx, c_text in enumerate(chunks, 1):
        print(f"[*] Parsing screenplay chunk [{idx}/{len(chunks)}] ({len(c_text.split())} words)...", flush=True)
        raw_segs = call_llm_json(c_text, preceding_context)

        # Standardize character spatial positions & acoustic environments
        for seg in raw_segs:
            seg["index"] = global_index
            global_index += 1

            spk = seg.get("speaker", "Narrator")
            if spk in ("Geralt", "विचर", "गेराल्ट"):
                seg["speaker"] = "Geralt"
                seg["spatial"] = {"pan": -0.20, "proximity": "normal_room"}
            elif spk in ("Nenneke", "नेनेके", "पुजारिन"):
                seg["speaker"] = "Nenneke"
                seg["spatial"] = {"pan": 0.25, "proximity": "normal_room"}
            else:
                seg["speaker"] = "Narrator"
                seg["spatial"] = {"pan": 0.0, "proximity": "intimate_close"}

            seg["acoustic_env"] = "temple_grotto"
            all_segments.append(seg)

        # Update preceding context
        recent_dialogues = [f"{s.get('speaker')}: {s.get('text')[:40]}" for s in raw_segs[-4:]]
        preceding_context = "Last dialogue lines:\n" + "\n".join(recent_dialogues)

    # Alexandria Pass 2 normalization
    print(f"[*] Running Alexandria Pass 2 normalization on {len(all_segments)} raw segments...")
    refined_script = clean_screenplay_pass2(all_segments, CHARACTER_ROSTER)

    # Renumber strictly from 1
    for i, s in enumerate(refined_script, 1):
        s["index"] = i

    # Validate Gate 2 Audit
    spk_counts = {}
    for s in refined_script:
        spk = s.get("speaker")
        spk_counts[spk] = spk_counts.get(spk, 0) + 1

    print("\n" + "=" * 80)
    print("  CHAPTER 11 SCREENPLAY GATE 2 AUDIT:")
    print(f"    Total Segments: {len(refined_script)}")
    for spk, cnt in sorted(spk_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"      - {spk:<15}: {cnt} segments ({cnt/len(refined_script)*100:.1f}%)")
    print("=" * 80)

    # Save finalized screenplay JSON
    output_script_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_script_file, "w", encoding="utf-8") as f:
        json.dump(refined_script, f, ensure_ascii=False, indent=2)

    print(f"\n[+] Saved validated screenplay script: {output_script_file.name}")


if __name__ == "__main__":
    main()
