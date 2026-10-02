#!/usr/bin/env python3
"""
Audiobook Factory - Alignment Engine: Text & Transliteration Utilities.
Converts Devanagari, Hinglish, and Latin dialogue into clean phonetic Roman tokens for MMS_FA CTC.
"""

from __future__ import annotations
import re
import unicodedata
from typing import List, Tuple

# Complete Devanagari to Roman transliteration table for MMS_FA acoustic alignment
DEVA_TO_ROMAN_MAP = {
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo', 'ऋ': 'ri',
    'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'अं': 'an', 'अः': 'ah', 'ँ': 'n',
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny', 'ज्ञ': 'gy',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    'क़': 'q', 'ख़': 'kh', 'ग़': 'gh', 'ज़': 'z', 'ड़': 'd', 'ढ़': 'dh', 'फ़': 'f',
    'ा': 'a', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo', 'ृ': 'ri',
    'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ं': 'n', '्': '',
    '़': '', '।': ' ', '॥': ' ', '’': "'", '‘': "'"
}


def transliterate_devanagari_to_roman(text: str) -> str:
    """
    Converts Devanagari and Latin dialogue into clean romanized tokens for MMS_FA CTC.
    Handles Hindi conjuncts, aspirated consonants, nuktas, matras, and acting cues.
    Strictly preserves MMS_FA vocabulary: [a-z'\\-\\s].
    """
    if not text:
        return ""

    # 1. Strip bracketed acting tags like [whispers], [gasp], [sigh]
    clean = re.sub(r"\[[^\]]+\]", " ", text)
    # 2. Unicode NFC normalization
    clean = unicodedata.normalize("NFC", clean)
    # Pre-map multi-character Devanagari ligatures / conjuncts
    clean = clean.replace("ज्ञ", "gy").replace("क्ष", "ksh").replace("त्र", "tr").replace("श्र", "shr")

    res = []
    for char in clean:
        res.append(DEVA_TO_ROMAN_MAP.get(char, char))
    roman = "".join(res)
    # Strip non-alphanumeric except spaces and apostrophes
    roman = re.sub(r"[^a-zA-Z'\s\-]", " ", roman).lower()
    return " ".join(roman.split())


def normalize_text_for_alignment(text: str) -> Tuple[List[str], List[str]]:
    """
    Produces paired raw source tokens and normalized Roman phonetic tokens.
    Guarantees 1:1 token correspondence for downstream WordAlignment contracts.
    """
    # Strip bracketed acting cues
    no_cues = re.sub(r"\[[^\]]+\]", " ", text).strip()
    raw_tokens = [w for w in no_cues.split() if w]

    if not raw_tokens:
        return (["[speech]"], ["aa"])

    roman_tokens = []
    paired_raw = []

    for raw in raw_tokens:
        target_raw = raw
        m_dig = re.search(r"\d+", raw)
        if m_dig:
            from audiobook_factory.pronunciation.resolver import number_to_hindi_words
            try:
                target_raw = re.sub(r"\d+", lambda m: number_to_hindi_words(int(m.group(0))), raw)
            except Exception:
                target_raw = raw
        rom = transliterate_devanagari_to_roman(target_raw)
        # If token stripped completely (e.g. pure punctuation like "---" or "..."), provide anchor
        if not rom:
            rom = "aa"
        roman_tokens.append(rom)
        paired_raw.append(raw)

    return paired_raw, roman_tokens
