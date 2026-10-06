#!/usr/bin/env python3
"""
Audiobook Factory - Offline Screenplay & Super-Chunking Engine.
Provides 100% offline rule-based dialogue/narration parsing and narrator super-chunking
without external LLM calls.
"""

import re
from typing import Dict, Any, List, Optional
from audiobook_factory.script_builder import (
    clean_screenplay_pass2,
    build_narrator_script,
    normalize_speech_text,
)


def build_narrator_superchunks(
    text: str,
    is_hindi: bool = False,
    max_words: int = 550,
) -> List[Dict[str, Any]]:
    """
    Quota-Efficient Narrator Super-Chunking Engine.
    Consolidates entire novel chapters (all dialogues + narration) into maximum-capacity
    speech blocks (up to ~550 words per chunk) voiced entirely by Narrator.
    Minimizes API requests by 85-90% while preserving natural breathing pauses.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    # Hindi dialogue dash normalization: turns 'कहा- दीदी...' into 'कहा, "... दीदी...'
    hindi_dialogue_dash = re.compile(
        r"([^।?!.\n]{1,35}?(?:ने\s*(?:कहा|पूछा|जवाब\s*दिया|बोला|बोली)|कहता\s*है|कहती\s*है|कहता|कहती|पूछता|पूछती|बोला|बोली|कहा\s*था|कहा|जवाब\s*दिया|जवाब\s*देती|कह\s*देती\s*थी|हंसते\s*हुए\s*कहता|हंसते\s*हुए\s*कहा|हंसकर\s*कहा))\s*[-—:]\s*",
        re.DOTALL,
    )

    raw_paragraphs = clean_text.split("\n\n")
    paragraphs = []

    # Pre-process paragraphs: split mega-paragraphs if any single paragraph > max_words
    for p in raw_paragraphs:
        p_strip = p.strip()
        if not p_strip:
            continue
        p_words = len(p_strip.split())
        if p_words <= max_words:
            paragraphs.append(p_strip)
        else:
            sentence_delims = r"([।?!.\n])\s*"
            parts = re.split(sentence_delims, p_strip)
            temp_p = ""
            for i in range(0, len(parts) - 1, 2):
                sent = parts[i] + parts[i + 1]
                if len((temp_p + " " + sent).split()) > max_words and temp_p:
                    paragraphs.append(temp_p.strip())
                    temp_p = sent
                else:
                    temp_p = (temp_p + " " + sent).strip()
            if len(parts) % 2 == 1 and parts[-1].strip():
                temp_p = (temp_p + " " + parts[-1]).strip()
            if temp_p:
                paragraphs.append(temp_p)

    chunks = []
    curr_paras = []
    curr_words = 0

    for p in paragraphs:
        # Chapter header detection
        if p.startswith("#"):
            if curr_paras:
                chunks.append(("\n\n".join(curr_paras), 800))
                curr_paras = []
                curr_words = 0
            chunks.append((p.lstrip("#").strip(), 1200))
            continue

        # Scene break detection
        if p in ("---", "* * *", "***", "— — —", "___"):
            if curr_paras:
                chunks.append(("\n\n".join(curr_paras), 1200))
                curr_paras = []
                curr_words = 0
            continue

        # Format Hindi dialogue dashes to natural spoken pauses
        if is_hindi or any("\u0900" <= ch <= "\u097f" for ch in p):
            p_formatted = hindi_dialogue_dash.sub(r'\1, "... ', p)
        else:
            p_formatted = p

        words_in_p = len(p_formatted.split())

        if curr_words + words_in_p > max_words and curr_paras:
            chunks.append(("\n\n".join(curr_paras), 800))
            curr_paras = [p_formatted]
            curr_words = words_in_p
        else:
            curr_paras.append(p_formatted)
            curr_words += words_in_p

    if curr_paras:
        chunks.append(("\n\n".join(curr_paras), 1000))

    segments = []
    for idx, (chunk_text, pause_ms) in enumerate(chunks, 1):
        cleaned = normalize_speech_text(chunk_text, is_hindi=is_hindi)
        cleaned = re.sub(r"\[(?:whispers|whispering)\]", "<whisper>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[(?:sighs|sigh)\]", "<sigh>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[(?:gasp|gasps)\]", "<gasp>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[(?:pause|silence)\]", "<short pause>", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\[(?:laugh|chuckle)\]", "<laugh>", cleaned, flags=re.IGNORECASE)

        segments.append({
            "index": idx,
            "type": "narration",
            "speaker": "Narrator",
            "text": cleaned,
            "emotion": "neutral",
            "style": "master cinematic audiobook narration with expressive emotional dialogue modulations and atmospheric suspense",
            "pause_after_ms": pause_ms,
        })

    return segments


def parse_literature_offline(
    literature_text: str,
    is_hindi: bool = False,
    mode: str = "narrator",
    max_chunk_words: int = 550,
    character_roster: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    100% OFFLINE Screenplay Generator.
    Converts raw novel prose or script text into standard Screenplay JSON segments
    without making any external LLM/API calls. Zero keys, zero rate limits, sub-second speed.
    """
    clean_text = literature_text.strip()
    if not clean_text:
        return []

    mode = (mode or "narrator").lower()

    if mode in ("narrator", "superchunk", "auto"):
        return build_narrator_superchunks(clean_text, is_hindi=is_hindi, max_words=max_chunk_words)

    if mode == "screenplay":
        raw_items = []
        lines = clean_text.splitlines()
        script_pattern = re.compile(r"^([A-Za-z0-9_\u0900-\u097F\s]{2,25})[:–—\-]\s*(.+)$")
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            m = script_pattern.match(line_str)
            if m:
                spk = m.group(1).strip()
                dia = m.group(2).strip()
                spk_lower = spk.lower()
                if spk_lower in ("narrator", "narration", "विवरण", "सूत्रधार"):
                    raw_items.append({
                        "index": len(raw_items) + 1,
                        "type": "narration",
                        "speaker": "Narrator",
                        "text": dia,
                        "emotion": "neutral",
                        "pause_after_ms": 600,
                    })
                else:
                    raw_items.append({
                        "index": len(raw_items) + 1,
                        "type": "dialogue",
                        "speaker": spk,
                        "text": dia,
                        "emotion": "neutral",
                        "pause_after_ms": 450,
                    })
            else:
                raw_items.append({
                    "index": len(raw_items) + 1,
                    "type": "narration",
                    "speaker": "Narrator",
                    "text": line_str,
                    "emotion": "neutral",
                    "pause_after_ms": 700,
                })
        return clean_screenplay_pass2(raw_items, is_hindi=is_hindi, character_roster=character_roster)

    # mode == 'dialogue'
    hindi_cue_pattern = re.compile(
        r"(?:^|[।?!.\n])\s*([^।?!.\n]{0,35}?(?:ने\s*(?:कहा|पूछा|जवाब\s*दिया|बोला|बोली)|कहता\s*है|कहती\s*है|कहता|कहती|पूछता|पूछती|बोला|बोली|कहा\s*था|कहा|जवाब\s*दिया|जवाब\s*देती|कह\s*देती\s*थी|हंसते\s*हुए\s*कहता|हंसते\s*हुए\s*कहा|हंसकर\s*कहा)\s*[-—:])\s*",
        re.DOTALL,
    )
    eng_quote_pat = re.compile(r'["“]([^"”]+)["”]')

    active_characters = []
    if character_roster and "characters" in character_roster:
        chars = character_roster["characters"]
        if isinstance(chars, dict):
            active_characters = list(chars.keys())
        elif isinstance(chars, list):
            active_characters = [c.get("english_name", "") for c in chars if isinstance(c, dict)]

    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    raw_items = []
    recent_dialogue_speakers = []

    for p_clean in paragraphs:
        if p_clean.startswith("#"):
            raw_items.append({
                "index": len(raw_items) + 1,
                "type": "chapter_header",
                "speaker": "Narrator",
                "text": p_clean.lstrip("#").strip(),
                "emotion": "neutral",
                "pause_after_ms": 1200,
            })
            continue

        if p_clean in ("---", "* * *", "***", "— — —", "___"):
            if raw_items:
                raw_items[-1]["pause_after_ms"] = max(raw_items[-1].get("pause_after_ms", 600), 1200)
            continue

        h_matches = list(hindi_cue_pattern.finditer(p_clean)) if (is_hindi or any("\u0900" <= ch <= "\u097f" for ch in p_clean)) else []

        if h_matches:
            first_start = h_matches[0].start()
            if first_start > 0:
                lead_narr = p_clean[:first_start].strip()
                if len(lead_narr.split()) > 2:
                    raw_items.append({
                        "index": len(raw_items) + 1,
                        "type": "narration",
                        "speaker": "Narrator",
                        "text": lead_narr,
                        "emotion": "neutral",
                        "pause_after_ms": 500,
                    })

            for i, m in enumerate(h_matches):
                cue_text = m.group(1).strip()
                body_start = m.end()
                body_end = h_matches[i + 1].start() if i + 1 < len(h_matches) else len(p_clean)
                dia_text = p_clean[body_start:body_end].strip()
                if not dia_text:
                    continue

                detected_spk = "Narrator"
                if any(w in cue_text for w in ("मैंने", "मैं", "कहती", "बोली", "देती")):
                    detected_spk = "Protagonist"
                elif any(w in cue_text for w in ("वह", "उसने")):
                    detected_spk = recent_dialogue_speakers[-1] if recent_dialogue_speakers else "He"
                else:
                    words = [w.strip("-—: ।?!,.`'\"") for w in cue_text.split()]
                    stop_words = {
                        "इस", "पर", "तो", "जैसे", "अक्सर", "मुझसे", "ने", "भी", "हंसते", "हुए",
                        "कहता", "कहती", "पूछता", "पूछती", "बोला", "बोली", "कहा", "था", "थी", "है",
                        "जवाब", "दिया", "देती", "देता", "कर", "हंसकर"
                    }
                    clean_words = [w for w in words if w and w not in stop_words]
                    if clean_words:
                        detected_spk = clean_words[-1]
                    else:
                        detected_spk = recent_dialogue_speakers[-1] if recent_dialogue_speakers else "Narrator"

                if detected_spk not in ("Narrator", "Foley") and detected_spk not in active_characters:
                    active_characters.append(detected_spk)

                if detected_spk != "Narrator":
                    if not recent_dialogue_speakers or recent_dialogue_speakers[-1] != detected_spk:
                        recent_dialogue_speakers.append(detected_spk)
                    if len(recent_dialogue_speakers) > 4:
                        recent_dialogue_speakers = recent_dialogue_speakers[-4:]

                emo = "neutral"
                if "?" in dia_text or "क्या" in dia_text or "क्यों" in dia_text:
                    emo = "curious"
                elif "!" in dia_text:
                    emo = "excited"
                elif "हंस" in cue_text:
                    emo = "happy"
                elif "फुसफुसा" in cue_text:
                    emo = "whispering"

                raw_items.append({
                    "index": len(raw_items) + 1,
                    "type": "dialogue",
                    "speaker": detected_spk,
                    "text": dia_text,
                    "emotion": emo,
                    "pause_after_ms": 450,
                })
            continue

        quotes = eng_quote_pat.findall(p_clean)
        if quotes:
            parts = eng_quote_pat.split(p_clean)
            for p_idx, part in enumerate(parts):
                part_strip = part.strip()
                if not part_strip:
                    continue
                if p_idx % 2 == 1:
                    prev_part = parts[p_idx - 1] if p_idx > 0 else ""
                    next_part = parts[p_idx + 1] if p_idx + 1 < len(parts) else ""
                    context_tag = (prev_part[-60:] + " " + next_part[:60]).strip()

                    spk = "Character"
                    for ac in active_characters:
                        if ac.lower() in context_tag.lower():
                            spk = ac
                            break
                    if spk == "Character":
                        spk = recent_dialogue_speakers[-1] if recent_dialogue_speakers else "Narrator"

                    emo = "neutral"
                    if "?" in part_strip:
                        emo = "curious"
                    elif "!" in part_strip:
                        emo = "excited"

                    raw_items.append({
                        "index": len(raw_items) + 1,
                        "type": "dialogue",
                        "speaker": spk,
                        "text": part_strip,
                        "emotion": emo,
                        "pause_after_ms": 450,
                    })
                else:
                    if len(part_strip.split()) > 3:
                        raw_items.append({
                            "index": len(raw_items) + 1,
                            "type": "narration",
                            "speaker": "Narrator",
                            "text": part_strip,
                            "emotion": "neutral",
                            "pause_after_ms": 600,
                        })
            continue

        w_count = len(p_clean.split())
        if w_count > 350:
            sub_chunks = build_narrator_script(p_clean, is_hindi=is_hindi)
            raw_items.extend(sub_chunks)
        else:
            raw_items.append({
                "index": len(raw_items) + 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": p_clean,
                "emotion": "neutral",
                "pause_after_ms": 600,
            })

    cleaned = clean_screenplay_pass2(raw_items, is_hindi=is_hindi, character_roster=character_roster)
    return cleaned
