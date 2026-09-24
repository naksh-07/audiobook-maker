#!/usr/bin/env python3
"""
Audiobook Factory - Chapter 10 Dramatized Screenplay Parser Runner (Resilient Multi-Model Engine).
Processes Chapter 10 ('The Edge of the World') into an annotated multi-cast screenplay
attributing dialogue to Geralt, Dandelion, Alderman, Nettly, Dhun, Old_Woman, Torque, Toruviel, Filavandrel, Galarr, and Narrator.
Adheres strictly to:
- ADR-021: Zero Voice Drift & Deterministic Speaker Attribution
- ADR-015: Acting tags, prosody & breath modeling
- ADR-022: Dynamic multi-scene acoustic environments
- Resilient model switching (gemini-flash-latest -> gemini-3.1-flash-lite) with persistent key backoff
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
logger = logging.getLogger("build_ch10_screenplay")

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
        "Dandelion": {
            "gender": "male",
            "voice_persona": "Puck",
            "aliases": ["डैंडेलियन", "कवि", "भाट", "शायर", "Jaskier", "Dandelion"],
        },
        "Alderman": {
            "gender": "male",
            "voice_persona": "Fenrir",
            "aliases": ["मुखिया", "अपर पोसाडा का मुखिया", "Alderman"],
        },
        "Nettly": {
            "gender": "male",
            "voice_persona": "Puck",
            "aliases": ["नेटली", "गाड़ीवान", "किसान", "Nettly"],
        },
        "Dhun": {
            "gender": "male",
            "voice_persona": "Fenrir",
            "aliases": ["धुन", "गाँव का प्रधान", "वृद्ध धुन", "Dhun"],
        },
        "Old_Woman": {
            "gender": "female",
            "voice_persona": "Kore",
            "aliases": ["बूढ़ी औरत", "नानी", "दादी", "किताब वाली औरत", "Old Woman", "Grandmother"],
        },
        "Torque": {
            "gender": "male",
            "voice_persona": "Puck",
            "aliases": ["टॉर्क", "सिल्वन", "बकरा", "सींगों वाला", "शैतान", "Torque", "Sylvan", "Deovel"],
        },
        "Toruviel": {
            "gender": "female",
            "voice_persona": "Kore",
            "aliases": ["तोरूविएल", "एलवेन योद्धा", "लड़की", "Toruviel"],
        },
        "Galarr": {
            "gender": "male",
            "voice_persona": "Puck",
            "aliases": ["गलार", "एल्व", "Galarr"],
        },
        "Filavandrel": {
            "gender": "male",
            "voice_persona": "Fenrir",
            "aliases": ["फ़िलावांड्रेल", "राजकुमार", "एल्व्स का राजा", "फ़िलावंद्रेइल", "Filavandrel"],
        },
        "Villager": {
            "gender": "male",
            "voice_persona": "Puck",
            "aliases": ["ग्रामीण", "किसान", "पहला ग्रामीण", "दूसरा ग्रामीण", "सिपाही", "Villager"],
        },
    }
}


def parse_dramatized_chunk_resilient(
    chunk_text: str,
    preceding_context: str = "",
    character_roster: Optional[Dict[str, Any]] = None,
    max_retries: int = 6,
) -> List[Dict[str, Any]]:
    """Robustly parses a chunk into dramatized segments using key rotation and multi-model fallback."""
    chars = character_roster.get("characters", {}) if character_roster else {}
    formatted_chars = []
    for cname, details in chars.items():
        if cname in ("Narrator", "Foley"):
            continue
        gender = details.get("gender", "neutral")
        aliases = details.get("aliases", [])
        alias_str = f", aliases: {', '.join(aliases[:4])}" if aliases else ""
        formatted_chars.append(f"{cname} [{gender}{alias_str}]")

    roster_hint = (
        "\nKnown Canon Characters in Project (Attribute dialogue to canonical English name as 'speaker'):\n"
        + "\n".join(f"- {fc}" for fc in formatted_chars)
        + "\n"
    )

    sys_prompt = (
        "You are an expert audio drama screenwriter. Convert novel prose into a multi-cast screenplay JSON array.\n"
        "MANDATORY INSTRUCTIONS:\n"
        "1. Split novel prose into discrete lines of character dialogue vs narrator description. NEVER merge dialogue into narration.\n"
        "2. Attribute EVERY spoken line to the exact character speaking (Geralt, Dandelion, Alderman, Nettly, Dhun, Old_Woman, Torque, Toruviel, Filavandrel, Galarr).\n"
        "3. Strip speech tags ('उसने कहा', 'गेराल्ट बोला', 'डैंडेलियन हँसा') from dialogue text.\n"
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
- "speaker": character name (Geralt, Dandelion, Alderman, Nettly, Dhun, Old_Woman, Torque, Toruviel, Filavandrel, Galarr, Villager, Narrator, or Foley)
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
- "acoustic_env": "tavern_interior" | "quiet_chamber" | "open_road" | "hemp_field" | "mountain_clearing"
- "sfx_cues": []
- "music": {{"mood": "peaceful" | "mysterious" | "tense" | "emotional" | "epic", "ducking_db": -16.0}}
"""

    candidate_models = ["gemini-3.1-flash-lite", "gemini-flash-latest"]

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
                    if isinstance(parsed, list) and len(parsed) > 0:
                        return parsed
                    elif isinstance(parsed, dict) and "segments" in parsed:
                        return parsed["segments"]
                    elif isinstance(parsed, dict) and "script" in parsed:
                        return parsed["script"]
            except urllib.error.HTTPError as e:
                if e.code == 503:
                    # Model overload, do not blame key; switch model immediately
                    break
                elif e.code == 429:
                    pool.mark_temporary_backoff(curr_key, 12.0, "RPM rate limit in script parsing")
                    time.sleep(1.0)
                else:
                    time.sleep(1.0)
                continue
            except Exception as ex:
                time.sleep(1.5)
                continue

    logger.warning("  [!] Screenplay LLM parsing exhausted all attempts. Falling back to narrator.")
    return build_narrator_script(chunk_text, is_hindi=True)


def main():
    project_dir = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
    hi_file = project_dir / "translation" / "chapter_010_hi.md"
    out_file = project_dir / "scripts" / "chapter_010_hi_script.json"
    cache_file = project_dir / "scripts" / "chapter_010_raw_chunks_cache.json"

    logger.info(f"Reading Hindi chapter text from {hi_file}...")
    if not hi_file.exists():
        raise FileNotFoundError(f"Hindi translation not found at {hi_file}")

    with open(hi_file, "r", encoding="utf-8") as f:
        full_text = f.read().strip()

    paragraphs = [p.strip() for p in full_text.split("\n\n") if p.strip()]
    logger.info(f"Total paragraphs in chapter 10: {len(paragraphs)}")

    # Chunk into semantic ~900-1,000 word blocks
    chunks = []
    cur = []
    cur_words = 0
    for p in paragraphs:
        w = len(p.split())
        cur.append(p)
        cur_words += w
        if cur_words >= 900:
            chunks.append("\n\n".join(cur))
            cur = []
            cur_words = 0
    if cur:
        chunks.append("\n\n".join(cur))

    logger.info(f"Divided chapter into {len(chunks)} semantic chunks for LLM parsing.")

    cached_items_by_chunk = {}
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_items_by_chunk = json.load(f)
            logger.info(f"Loaded existing checkpoint with {len(cached_items_by_chunk)}/{len(chunks)} chunks.")
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}. Starting fresh.")

    all_raw_items = []
    rolling_context = ""

    for idx, chunk_str in enumerate(chunks, 1):
        idx_str = str(idx)
        if idx_str in cached_items_by_chunk:
            logger.info(f"[{idx:02d}/{len(chunks):02d}] Loading chunk from checkpoint cache ({len(cached_items_by_chunk[idx_str])} items)...")
            chunk_items = cached_items_by_chunk[idx_str]
        else:
            logger.info(f"[{idx:02d}/{len(chunks):02d}] Parsing chunk ({len(chunk_str)} chars, ~{len(chunk_str.split())} words)...")
            chunk_items = parse_dramatized_chunk_resilient(
                chunk_text=chunk_str,
                preceding_context=rolling_context,
                character_roster=CHARACTER_ROSTER,
                max_retries=6,
            )

            cached_items_by_chunk[idx_str] = chunk_items
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cached_items_by_chunk, f, ensure_ascii=False, indent=2)

        all_raw_items.extend(chunk_items)
        recent_speakers = [it.get("speaker", "Narrator") for it in chunk_items[-2:]]
        rolling_context = f"Scene chunk {idx} ended with speakers: {', '.join(recent_speakers)}."

    logger.info(f"Assembled {len(all_raw_items)} raw screenplay items. Running Alexandria Pass 2 cleanup...")
    cleaned_script = clean_screenplay_pass2(
        all_raw_items,
        is_hindi=True,
        character_roster=CHARACTER_ROSTER,
    )

    logger.info(f"Cleaned screenplay generated: {len(cleaned_script)} final segments.")

    # Speaker distribution stats
    speakers = {}
    for s in cleaned_script:
        spk = s.get("speaker", "Unknown")
        speakers[spk] = speakers.get(spk, 0) + 1
    for spk, count in sorted(speakers.items(), key=lambda x: -x[1]):
        logger.info(f"  - {spk}: {count} segments")

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(cleaned_script, f, ensure_ascii=False, indent=2)

    logger.info(f"[+] Screenplay written to {out_file} successfully!")


if __name__ == "__main__":
    main()
