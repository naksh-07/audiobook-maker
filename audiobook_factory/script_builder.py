#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.1: Screenplay Script Builder & Speech Normalizer.
Converts raw novel prose (English or Hindi) into an annotated Screenplay Script JSON.
Handles dialogue vs. narration segmentation, text normalization, and pause timing.
"""

import os
import re
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional


def normalize_speech_text(text: str, is_hindi: bool = False) -> str:
    """Normalize symbols, abbreviations, and numbers for natural TTS reading."""
    if not text:
        return ""

    text = text.strip()

    # Universal symbol replacements
    symbols = {
        "&": " and " if not is_hindi else " और ",
        "%": " percent" if not is_hindi else " प्रतिशत",
        "$": " dollars " if not is_hindi else " डॉलर ",
        "₹": " rupees " if not is_hindi else " रुपये ",
        "@": " at ",
        "#": " number " if not is_hindi else " नंबर ",
        "+": " plus " if not is_hindi else " प्लस ",
        "=": " equals " if not is_hindi else " बराबर ",
    }
    for sym, word in symbols.items():
        text = text.replace(sym, word)

    if not is_hindi:
        # Common English honorifics and abbreviations
        abbrevs = {
            r"\bMr\.\s*": "Mister ",
            r"\bMrs\.\s*": "Missus ",
            r"\bMs\.\s*": "Miss ",
            r"\bDr\.\s*": "Doctor ",
            r"\bProf\.\s*": "Professor ",
            r"\bSt\.\s*": "Saint ",
            r"\bvs\.\s*": "versus ",
            r"\betc\.\s*": "et cetera ",
            r"\bi\.e\.\s*": "that is ",
            r"\be\.g\.\s*": "for example ",
        }
        for pat, repl in abbrevs.items():
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)

    # Strip formatting artifacts
    text = re.sub(r"[\*\_~`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_narrator_script(chapter_text: str, is_hindi: bool = False) -> List[Dict[str, Any]]:
    """
    Standard Audiobook Mode: Groups text into optimal speech chunks (200 - 500 words).
    Maintains dramatic pauses at paragraph boundaries and scene breaks.
    """
    paragraphs = chapter_text.split("\n\n")
    script = []
    chunk_index = 1

    current_chunk = []
    current_words = 0

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue

        # Skip chapter headers like "# Chapter 1"
        if p.startswith("#"):
            header_text = p.lstrip("#").strip()
            script.append({
                "index": chunk_index,
                "type": "chapter_header",
                "speaker": "Narrator",
                "text": normalize_speech_text(header_text, is_hindi),
                "emotion": "neutral",
                "pause_after_ms": 1200,
            })
            chunk_index += 1
            continue

        # Scene breaks
        if p in ("---", "* * *", "***", "— — —"):
            if current_chunk:
                script.append({
                    "index": chunk_index,
                    "type": "narration",
                    "speaker": "Narrator",
                    "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
                    "emotion": "neutral",
                    "pause_after_ms": 800,
                })
                chunk_index += 1
                current_chunk = []
                current_words = 0
            continue

        words = len(p.split())

        # If adding this paragraph exceeds ~350 words, flush the chunk
        if current_words + words > 350 and current_chunk:
            script.append({
                "index": chunk_index,
                "type": "narration",
                "speaker": "Narrator",
                "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
                "emotion": "neutral",
                "pause_after_ms": 600,
            })
            chunk_index += 1
            current_chunk = [p]
            current_words = words
        else:
            current_chunk.append(p)
            current_words += words

    if current_chunk:
        script.append({
            "index": chunk_index,
            "type": "narration",
            "speaker": "Narrator",
            "text": normalize_speech_text("\n\n".join(current_chunk), is_hindi),
            "emotion": "neutral",
            "pause_after_ms": 1000,
        })

    return script


def _parse_dramatized_chunk_llm(
    chunk_text: str,
    preceding_context: str = "",
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
    api_key: str = "",
    model: str = "gemini-flash-lite-latest",
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """Helper to parse a single chunk of chapter text into screenplay JSON."""
    import json
    import time
    import urllib.request
    import urllib.error
    from audiobook_factory.key_manager import get_persistent_key_pool
    from audiobook_factory.cadence import get_stealth_sdk_headers

    pool = get_persistent_key_pool()

    sys_prompt = (
        "You are a Hollywood Audio Drama Director (GraphicAudio / BBC Radio 4 / HBO standard). "
        "Convert this book chapter scene into an annotated multi-cast screenplay with deep cinematic audio direction.\n\n"
        "Core Dramaturgy Invariants:\n"
        "1. UNFILTERED ADULT DIALOGUE MANDATE: Never sanitize, soften, or omit coarse curses ('गांड', 'भोसड़ीके', 'लंड', 'रांड', 'मादरचोद'), "
        "tavern obscenities, or intimate bedroom dialogue. Preserve 100% of explicit dramatic truth.\n"
        "2. MULTI-CAST ATTRIBUTION: Split into narration segments and character dialogue segments. Attribute each dialogue to the correct character by name. "
        "Remove redundant dialogue tags like 'he said', 'she replied', 'उसने कहा' when spoken by the character.\n"
        "3. NEURAL VOCAL TAGS: Gemini 3.1 Flash TTS is steered using inline English audio tags in square brackets. Prepend vocal tags directly inside the 'text' field "
        "when dialogue or dramatic narration demands it: `[whispers]`, `[shouting]`, `[cold menace]`, `[intimate, breathy]`, `[trembling voice]`, `[sighs]`, "
        "`[gasp]`, `[growl]`, `[groan]`, `[spits]`, `[bellowing rage]`, `[breathless_exhaustion]`, `[mocking chuckle]`. Do NOT emit non-vocal action tags in text.\n"
        "4. CYNICAL PROTAGONIST GRUNT ENGINE & PROSODY: When a brooding, cynical protagonist reacts with skepticism, weary resignation, or menacing brevity, "
        "prepend `[growl] हूँ...` or `[sighs] हम्म...` and set 'pause_after_ms' to 1000-1400ms to enforce the iconic 1.2s pregnant pause prosody.\n"
        "5. DURAANGI ZUBAAN (INNER MONOLOGUES): When a character thinks an unfiltered thought or aside (contrasting with polite outward speech), "
        "tag the text with `[whispers] (मन में: ...)` and set spatial.proximity: 'intimate_close' and acoustic_env: 'binaural_whisper'.\n"
        "6. INTIMATE SCENES & ASMR STAGING: For romantic, sensual, or passionate scenes, set spatial.proximity: 'intimate_close', spatial.pan: 0.0, "
        "intensity_level: 'low', pre_roll_breath_ms: 200-250, and music.ducking_db: -22.0 ('The Erotic Silence'). Use ellipses ('...') for breathless pauses.\n"
        "7. TAVERN SHOCK BEAT & COMBAT IMPACT: When a climactic death threat or filthy curse drops in a tavern, set pause_after_ms: 800-1200ms with a solitary "
        "coin_clink or tankard_slam cue for an acoustic shock drop. For physical combat, emit dedicated segments with type: 'action', speaker: 'Foley', text: '[ACTION]'.\n"
        "8. For EVERY segment, assign audio direction: acting delivery & pacing, spatial stereo panning, acoustic environment, inline Foley SFX cues, and musical mood."
    )

    roster_hint = ""
    if character_roster:
        chars = character_roster.get("characters", {})
        if isinstance(chars, dict):
            names = list(chars.keys())
            roster_hint = f"\nKnown Canon Characters in Project: {', '.join(names)}\n"
        elif isinstance(chars, list):
            names = [c.get("english_name", "") for c in chars if isinstance(c, dict)]
            roster_hint = f"\nKnown Canon Characters in Project: {', '.join(names)}\n"

    prompt = f"""Language: {"Hindi (Devanagari)" if is_hindi else "English"}
Preceding Scene Context / Characters Speaking:
{preceding_context if preceding_context else "Beginning of scene."}
{roster_hint}
Current Scene Text:
\"\"\"
{chunk_text}
\"\"\"

Output JSON: A list of objects where each object has:
- "index": int (1-based relative to this chunk)
- "type": "narration" | "dialogue" | "action" (emit "action" for dedicated physical action beats, sword unsheathed, door kick, tankard slam, body impact, explosion)
- "speaker": character name (e.g. "Alice", "Bob"), "Narrator", or "Foley" (for action segments)
- "text": speech text (clean spoken content in {"Devanagari Hindi" if is_hindi else "English"}, with optional inline vocal tags like [whispers], [shouting], [cold menace] where emotionally appropriate, or "[ACTION]" for action segments)
- "emotion": "neutral" | "angry" | "whispering" | "sad" | "excited" | "growl" | "calm_raspy"
- "intensity_level": "low" | "medium" | "high" | "explosive" (DSP dynamic headroom: "low" for whispered/intimate, "medium" for standard dialogue/narration, "high" for intense confrontation/shouts, "explosive" for climactic battle cries)
- "pre_roll_breath_ms": int (150 to 250 for intimate/terrified lines, 0 for standard delivery)
- "pause_after_ms": int (300 to 800)
- "acting": {{
    "delivery_style": "whispering_fear" | "cold_menace" | "breathless_exhaustion" | "ironic_mockery" | "bellowing_rage" | "calm_authoritative" | "gentle_tender" | "neutral",
    "pacing": float (0.88 to 1.15, e.g. 0.92 for slow/bassy/deliberate, 1.0 for normal, 1.10 for fast action)
  }}
- "spatial": {{
    "pan": float (-0.4 to 0.4, e.g. 0.0 for Narrator, -0.22 for protagonist, +0.22 for other speakers),
    "proximity": "intimate_close" | "normal_room" | "distant"
  }}
- "acoustic_env": "tavern_interior" | "stone_crypt" | "royal_hall" | "damp_dungeon" | "dense_forest_night" | "quiet_chamber" | "open_road"
- "sfx_cues": [
    {{
      "tag": "sword_draw" | "sword_clash" | "body_fall" | "blood_impact" | "beer_pour" | "tankard_slam" | "coin_clink" | "chair_scrape" | "door_creak" | "footsteps_wood" | "boots_gravel" | "cloak_rustle" | "sign_magic" | "fire_crackle" | "horse_gallop",
      "timing": "before" | "under" | "after",
      "offset_ms": int (-200 to 600),
      "volume": float (0.25 to 0.55),
      "description": "Short explanation of physical sound"
    }}
  ]
- "music": {{
    "mood": "peaceful" | "mysterious" | "tense" | "emotional" | "epic",
    "ducking_db": float (-18.0 to -10.0)
  }}
"""

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
    from audiobook_factory.logger import logger

    max_retries = max(max_retries, 4)
    for attempt in range(max_retries):
        curr_key = pool.get_key(service="text") if (attempt > 0 or not api_key) else api_key
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={curr_key}"
        headers = get_stealth_sdk_headers(curr_key)
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    logger.warning(f"  [!] Screenplay LLM returned no candidates: {data.get('promptFeedback', {})}")
                    continue
                candidate = candidates[0]
                parts = candidate.get("content", {}).get("parts", [])
                if not parts:
                    continue
                text_parts = [p.get("text", "") for p in parts if "text" in p]
                raw_json = "".join(text_parts).strip()

                # Strip markdown code blocks ```json ... ```
                match = re.search(r"```(?:json)?\s*(.*?)```", raw_json, re.DOTALL)
                if match:
                    raw_json = match.group(1).strip()
                elif raw_json.startswith("```"):
                    raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json)
                    raw_json = re.sub(r"\s*```$", "", raw_json).strip()

                parsed = None
                try:
                    parsed = json.loads(raw_json)
                except json.JSONDecodeError:
                    # [AGENTIC SHIFT] LLM-based Truncation Recovery Loop
                    if (raw_json.startswith("[") or raw_json.startswith("{")) and candidate.get("finishReason") == "MAX_TOKENS":
                        logger.info("  [*] JSON truncated (MAX_TOKENS). Invoking Data Healer Agent...")
                        healer_prompt = f"The following JSON array was truncated. Please continue outputting valid JSON exactly from where it left off, closing the array properly. Only return the continued JSON without markdown.\n\nTruncated JSON end:\n{raw_json[-1000:]}"
                        healer_payload = {
                            "contents": [{"parts": [{"text": healer_prompt}]}],
                            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 4096},
                        }
                        try:
                            h_req = urllib.request.Request(
                                url,  # Reusing the same URL with current key
                                data=json.dumps(healer_payload).encode("utf-8"),
                                headers=headers,
                                method="POST",
                            )
                            with urllib.request.urlopen(h_req, timeout=90.0) as h_resp:
                                h_data = json.loads(h_resp.read().decode("utf-8"))
                                h_parts = h_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                continuation = "".join([p.get("text", "") for p in h_parts if "text" in p]).strip()
                                if continuation.startswith("```"):
                                    continuation = re.sub(r"^```(?:json)?\s*", "", continuation)
                                    continuation = re.sub(r"\s*```$", "", continuation).strip()
                                
                                repaired_json = raw_json + continuation
                                parsed = json.loads(repaired_json)
                                logger.info("  [+] Data Healer Agent successfully repaired the truncated JSON.")
                        except Exception as e:
                            logger.warning(f"  [!] Data Healer failed: {e}. Falling back to last safe brace.")
                            repaired = raw_json.strip()
                            last_brace = repaired.rfind("}")
                            if last_brace != -1 and not repaired.endswith("]"):
                                candidate_str = repaired[:last_brace + 1].rstrip() + "\n]"
                                try:
                                    parsed = json.loads(candidate_str)
                                except Exception:
                                    raise
                            else:
                                raise
                    else:
                        # Fallback for incomplete JSON array with safe closing brace
                        repaired = raw_json.strip()
                        last_brace = repaired.rfind("}")
                        if last_brace != -1 and repaired.startswith("[") and not repaired.endswith("]"):
                            candidate_str = repaired[:last_brace + 1].rstrip() + "\n]"
                            parsed = json.loads(candidate_str)
                        else:
                            raise

                if isinstance(parsed, list):
                    return parsed
                elif isinstance(parsed, dict) and "script" in parsed and isinstance(parsed["script"], list):
                    return parsed["script"]
                elif isinstance(parsed, dict) and "segments" in parsed and isinstance(parsed["segments"], list):
                    return parsed["segments"]
                else:
                    raise ValueError(f"Unexpected JSON structure: {type(parsed)}")

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            logger.warning(f"  [!] Screenplay LLM HTTP {e.code} on key ...{curr_key[-6:]}: {err_body[:120]}")
            if e.code == 429:
                pool.mark_temporary_backoff(curr_key, 12.0, "RPM rate limit in script parsing")
            time.sleep(1.5)
            continue
        except Exception as ex:
            logger.warning(f"  [!] Screenplay LLM parse error: {ex}")
            time.sleep(1.5)
            continue

    logger.warning("  [!] All screenplay retries exhausted. Falling back to narrator chunks.")
    # Guaranteed Zero Text Drop: Fall back to narrator script for this chunk instead of returning []
    return build_narrator_script(chunk_text, is_hindi)


def build_dramatized_script_llm(
    chapter_text: str,
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Dramatized Screenplay Mode with Sliding-Window Chunking:
    Converts entire chapter of arbitrary length into screenplay JSON without truncation.
    """
    from audiobook_factory.key_manager import get_persistent_key_pool
    pool = get_persistent_key_pool()
    api_key = pool.get_key(service="text")
    if not api_key:
        return build_narrator_script(chapter_text, is_hindi)

    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-flash-lite-latest")

    # If chapter is within safe token budget (~7,500 chars), process directly
    if len(chapter_text) <= 7500:
        raw_items = _parse_dramatized_chunk_llm(
            chunk_text=chapter_text,
            is_hindi=is_hindi,
            character_roster=character_roster,
            api_key="",
            model=model,
        )
        if not raw_items:
            return build_narrator_script(chapter_text, is_hindi)
    else:
        # Novel-Scale: Split into semantic ~1,500 word chunks on paragraph boundaries
        paragraphs = chapter_text.split("\n\n")
        chunks = []
        cur_chunk = []
        cur_words = 0

        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            w = len(p.split())
            cur_chunk.append(p)
            cur_words += w
            if cur_words >= 1200:
                chunks.append("\n\n".join(cur_chunk))
                cur_chunk = []
                cur_words = 0
        if cur_chunk:
            chunks.append("\n\n".join(cur_chunk))

        raw_items = []
        rolling_context = ""

        for c_idx, chunk_str in enumerate(chunks, 1):
            chunk_items = _parse_dramatized_chunk_llm(
                chunk_text=chunk_str,
                preceding_context=rolling_context,
                is_hindi=is_hindi,
                character_roster=character_roster,
                api_key="",
                model=model,
            )
            if chunk_items:
                raw_items.extend(chunk_items)
                # Form rolling context from the last 2 items
                recent_speakers = [it.get("speaker", "Narrator") for it in chunk_items[-2:]]
                rolling_context = f"Scene chunk {c_idx} ended with speakers: {', '.join(recent_speakers)}."
            else:
                # Fallback on this chunk
                fallback_chunk = build_narrator_script(chunk_str, is_hindi)
                raw_items.extend(fallback_chunk)

    if not raw_items:
        return build_narrator_script(chapter_text, is_hindi)

    return clean_screenplay_pass2(raw_items, is_hindi=is_hindi, character_roster=character_roster)


def clean_screenplay_pass2(
    raw_items: List[Dict[str, Any]],
    is_hindi: bool = False,
    character_roster: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Pass 2 (Alexandria Pattern): Two-pass pronoun disambiguation, alias resolution,
    unknown speaker fallback, text normalization, and continuous 1-based indexing.
    """
    alias_map = {}
    gender_map = {}
    if character_roster and "characters" in character_roster:
        chars = character_roster["characters"]
        if isinstance(chars, dict):
            for canon_name, details in chars.items():
                alias_map[canon_name.lower()] = canon_name
                if isinstance(details, dict):
                    gender_map[canon_name] = details.get("gender", "neutral").lower()
                    for alias in details.get("aliases", []):
                        alias_map[alias.lower()] = canon_name
        elif isinstance(chars, list):
            for c in chars:
                if isinstance(c, dict):
                    c_name = c.get("hindi_name") if is_hindi and c.get("hindi_name") else c.get("english_name", "")
                    if c_name:
                        alias_map[c_name.lower()] = c_name
                        gender_map[c_name] = c.get("gender", "neutral").lower()
                        eng = c.get("english_name", "")
                        if eng:
                            alias_map[eng.lower()] = c_name

    last_male_character = "Narrator"
    last_female_character = "Narrator"
    last_active_character = "Narrator"

    final_script = []
    for idx, item in enumerate(raw_items, 1):
        speaker = item.get("speaker", "Narrator").strip()
        speaker_lower = speaker.lower()
        if speaker_lower in alias_map:
            speaker = alias_map[speaker_lower]

        # Disambiguate pronouns if LLM attributed dialogue to a pronoun
        if item.get("type") == "dialogue":
            if speaker_lower in ("he", "him", "the man", "the boy", "the lad", "his voice", "उसने", "वह", "आदमी"):
                speaker = last_male_character if last_male_character != "Narrator" else last_active_character
            elif speaker_lower in ("she", "her", "the woman", "the girl", "the lady", "her voice", "लड़की", "महिला"):
                speaker = last_female_character if last_female_character != "Narrator" else last_active_character
            elif speaker_lower in ("unknown", "someone", "voice", "a voice", "stranger"):
                speaker = last_active_character

        # Dedicated action beat support: keep Foley speaker and action type intact
        is_action_beat = item.get("type") == "action" or speaker_lower == "foley"
        if is_action_beat:
            speaker = "Foley"
        elif not speaker or speaker_lower in ("narrator", "narration", "header", "chapter_header"):
            speaker = "Narrator"

        # Update active cast trackers
        if speaker not in ("Narrator", "Foley"):
            last_active_character = speaker
            g = gender_map.get(speaker, "neutral")
            if g == "male":
                last_male_character = speaker
            elif g == "female":
                last_female_character = speaker

        from audiobook_factory.sanitizer import sanitize_screenplay_segment
        sanitized_item = sanitize_screenplay_segment(item, is_hindi)
        if not sanitized_item:
            continue

        cleaned_text = normalize_speech_text(sanitized_item.get("text", ""), is_hindi)
        if not cleaned_text:
            continue

        seg_type = "action" if is_action_beat else sanitized_item.get("type", "narration")
        entry = {
            "index": len(final_script) + 1,
            "type": seg_type,
            "speaker": speaker,
            "text": cleaned_text,
            "emotion": sanitized_item.get("emotion", "neutral"),
            "pause_after_ms": int(sanitized_item.get("pause_after_ms", 600)),
        }
        for field in ("acting", "spatial", "acoustic_env", "sfx_cues", "music", "intensity_level", "pre_roll_breath_ms"):
            if field in sanitized_item:
                entry[field] = sanitized_item[field]

        final_script.append(entry)

    return final_script


def generate_project_scripts(
    project_dir: Path,
    use_hindi: bool = False,
    dramatized: bool = False,
    overwrite: bool = False,
) -> Path:
    """Generates JSON screenplay scripts for all chapters in project."""
    project_dir = Path(project_dir).resolve()
    input_dir = project_dir / ("translation" if use_hindi else "extracted")
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    target_files = sorted(input_dir.glob("*.md"))
    if not target_files:
        raise FileNotFoundError(f"No markdown chapters found in {input_dir}")

    # Load character roster from translation glossary or project registry if available
    roster = None
    roster_file = project_dir / "character_roster.json"
    glossary_file = project_dir / "translation" / "glossary.json"
    if roster_file.exists():
        try:
            with open(roster_file, "r", encoding="utf-8") as f:
                roster = json.load(f)
        except Exception:
            pass
    elif glossary_file.exists():
        try:
            with open(glossary_file, "r", encoding="utf-8") as f:
                glossary = json.load(f)
                roster = {"characters": {c["hindi_name"] if use_hindi and "hindi_name" in c else c.get("english_name", ""): {"aliases": [c.get("english_name", "")]} for c in glossary.get("characters", [])}}
        except Exception:
            pass

    print(f"[*] Building audiobook scripts for {len(target_files)} chapters (Mode: {'Dramatized' if dramatized else 'Narrator'})...")

    for chap_file in target_files:
        script_file = scripts_dir / f"{chap_file.stem}_script.json"
        if not overwrite and script_file.exists() and script_file.stat().st_size > 50:
            print(f"[-] Script already exists: {script_file.name} (Skipping)")
            continue

        with open(chap_file, "r", encoding="utf-8") as f:
            content = f.read()

        if dramatized:
            script = build_dramatized_script_llm(content, is_hindi=use_hindi, character_roster=roster)
        else:
            script = build_narrator_script(content, is_hindi=use_hindi)

        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script, f, ensure_ascii=False, indent=2)

        print(f"[+] Built script for {chap_file.name} -> {len(script)} audio segments")

    print(f"[DONE] All chapter scripts built -> {scripts_dir}")
    return scripts_dir
