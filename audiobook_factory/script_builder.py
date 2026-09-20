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
    api_key: str = "",
    model: str = "gemini-3-flash-preview",
    max_retries: int = 3,
) -> List[Dict[str, Any]]:
    """Helper to parse a single chunk of chapter text into screenplay JSON."""
    import json
    import time
    import urllib.request
    import urllib.error
    from audiobook_factory.tts_dispatcher import global_key_pool

    sys_prompt = (
        "You are an expert audio drama director. Convert this book chapter scene into an annotated screenplay JSON script. "
        "Split into narration segments and character dialogue segments. Attribute each dialogue to the correct character. "
        "Remove redundant dialogue tags like 'he said', 'she replied' when spoken by the character."
    )

    prompt = f"""Language: {"Hindi (Devanagari)" if is_hindi else "English"}
Preceding Scene Context / Characters Speaking:
{preceding_context if preceding_context else "Beginning of scene."}

Current Scene Text:
\"\"\"
{chunk_text}
\"\"\"

Output JSON: A list of objects where each object has:
- "index": int (1-based relative to this chunk)
- "type": "narration" | "dialogue"
- "speaker": character name (e.g. "Harry", "Ron") or "Narrator"
- "text": speech text (clean spoken content in {"Devanagari Hindi" if is_hindi else "English"})
- "emotion": "neutral" | "angry" | "whispering" | "sad" | "excited"
- "pause_after_ms": int (300 to 800)
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": sys_prompt}]},
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json",
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }

    data_bytes = json.dumps(payload).encode("utf-8")

    for attempt in range(max_retries):
        curr_key = api_key or global_key_pool.get_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={curr_key}"
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": curr_key,
                "User-Agent": "AudiobookFactory/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_json = data["candidates"][0]["content"]["parts"][0]["text"].strip()

                # Strip markdown code blocks ```json ... ```
                if raw_json.startswith("```"):
                    raw_json = re.sub(r"^```(?:json)?\s*", "", raw_json)
                    raw_json = re.sub(r"\s*```$", "", raw_json).strip()

                try:
                    parsed = json.loads(raw_json)
                except json.JSONDecodeError:
                    # Regex fallback for outermost list [...] or object {...}
                    match = re.search(r"(\[.*\]|\{.*\})", raw_json, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group(1))
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
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait_sec = 3.5 * (attempt + 1)
                time.sleep(wait_sec)
                continue
            break
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2.0)
                continue
            break

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
    from audiobook_factory.tts_dispatcher import global_key_pool
    api_key = global_key_pool.get_key()
    if not api_key:
        return build_narrator_script(chapter_text, is_hindi)

    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3-flash-preview")

    # If chapter is within safe token budget (~7,500 chars), process directly
    if len(chapter_text) <= 7500:
        raw_items = _parse_dramatized_chunk_llm(
            chunk_text=chapter_text,
            is_hindi=is_hindi,
            api_key=api_key,
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
                api_key=api_key,
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

    # Normalize aliases and assign continuous 1-based indexing
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

    # Pass 2 (Alexandria Pattern): Two-pass pronoun disambiguation & alias resolution
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

        # Update active cast trackers
        if speaker != "Narrator":
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

        final_script.append({
            "index": len(final_script) + 1,
            "type": sanitized_item.get("type", "narration"),
            "speaker": speaker,
            "text": cleaned_text,
            "emotion": sanitized_item.get("emotion", "neutral"),
            "pause_after_ms": int(sanitized_item.get("pause_after_ms", 600)),
        })

    return final_script


def generate_project_scripts(
    project_dir: Path,
    use_hindi: bool = False,
    dramatized: bool = False,
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
        if script_file.exists() and script_file.stat().st_size > 50:
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
