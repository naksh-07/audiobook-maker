#!/usr/bin/env python3
"""
Audiobook Factory - Script Engine: Speech Normalizer & Narrator Script Builder.
Handles symbol expansion, abbreviations, Devanagari normalization, and basic narration chunking.
"""

from __future__ import annotations
import re
from typing import List, Dict, Any


def normalize_speech_text(text: str, is_hindi: bool = False) -> str:
    """Normalize symbols, abbreviations, and numbers for natural TTS reading."""
    if not text:
        return ""

    text = text.strip()

    # Restrict % to numbers only (e.g. 50% -> 50 प्रतिशत / 50 percent)
    # Standalone % (corrupted dashes/colons from legacy fonts) are converted to em-dash
    if is_hindi:
        text = re.sub(r"(\d+)\s*%", r"\1 प्रतिशत", text)
        text = re.sub(r"(?<!\d)%(?!\d)", " — ", text)
    else:
        text = re.sub(r"(\d+)\s*%", r"\1 percent", text)
        text = re.sub(r"(?<!\d)%(?!\d)", " — ", text)

    # Universal symbol replacements
    symbols = {
        "&": " and " if not is_hindi else " और ",
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
