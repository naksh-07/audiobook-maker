#!/usr/bin/env python3
"""
Audiobook Factory - Spoken Language & Script Detection Engine.
Identifies script characteristics, language identity, and code-switching boundaries
for spoken audio synthesis (distinct from literary text classification).
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Tuple
from .contracts import SpokenLanguage


DEVANAGARI_RANGE = re.compile(r"[\u0900-\u097F]")
LATIN_RANGE = re.compile(r"[a-zA-Z]")

# Phonetic / lexical markers for Urdu / Persian loanwords in Hindustani
NUKTA_CHAR = "\u093c"
URDU_NUKTA_PATTERNS = ["क़", "ख़", "ग़", "ज़", "फ़", "\u0915\u093c", "\u0916\u093c", "\u0917\u093c", "\u091c\u093c", "\u092b\u093c"]
URDU_LEXICAL_MARKERS = {
    "ख़ुद", "ज़िंदगी", "मौत", "इश्क़", "हुस्न", "ग़म", "वक़्त", "शराब", "साकी",
    "अजीब", "सलाम", "जनाब", "हुज़ूर", "साहब", "मुल्क", "दिल", "नज़र", "शौक़",
    "क़रीब", "फ़र्क़", "तस्वीर", "तारीफ़", "महफ़िल", "इरादा", "अंदाज़", "ख़ुशबू"
}

# Sanskrit tatsama conjunct markers
SANSKRIT_CONJUNCT_PATTERNS = ["क्ष", "त्र", "ज्ञ", "श्र", "ऋ", "ष"]
SANSKRIT_LEXICAL_MARKERS = {
    "प्रतीक्षा", "दृष्टि", "क्षण", "समस्त", "कर्म", "धर्म", "आत्मा", "मोक्ष",
    "अस्तित्व", "सृष्टि", "हृदय", "मृत्यु", "ज्ञान", "यज्ञ", "विद्या", "ऋषि"
}


def detect_token_language(token: str) -> SpokenLanguage:
    """
    Classifies a single word/token into a SpokenLanguage category.
    """
    if not token or not token.strip():
        return SpokenLanguage.UNKNOWN

    clean = re.sub(r"^[^\w\u0900-\u097F]+|[^\w\u0900-\u097F]+$", "", token.strip())
    if not clean:
        return SpokenLanguage.UNKNOWN

    has_deva = bool(DEVANAGARI_RANGE.search(clean))
    has_latn = bool(LATIN_RANGE.search(clean))

    if has_deva and has_latn:
        return SpokenLanguage.HINDUSTANI

    if has_latn and not has_deva:
        return SpokenLanguage.ENGLISH

    # Devanagari token - classify dialectal/origin texture
    if has_deva:
        if clean in URDU_LEXICAL_MARKERS or any(p in clean for p in URDU_NUKTA_PATTERNS):
            return SpokenLanguage.URDU
        if clean in SANSKRIT_LEXICAL_MARKERS or any(p in clean for p in SANSKRIT_CONJUNCT_PATTERNS):
            return SpokenLanguage.SANSKRIT
        return SpokenLanguage.HINDI

    return SpokenLanguage.UNKNOWN


def classify_sentence_language(text: str) -> Dict[str, Any]:
    """
    Analyzes an entire sentence or line for script dominance, code-switching, and language composition.
    """
    tokens = re.findall(r"[\w\u0900-\u097F]+", text)
    if not tokens:
        return {
            "primary_language": SpokenLanguage.UNKNOWN,
            "is_code_switched": False,
            "devanagari_count": 0,
            "latin_count": 0,
            "tokens_by_language": {},
        }

    deva_count = sum(1 for t in tokens if DEVANAGARI_RANGE.search(t))
    latn_count = sum(1 for t in tokens if LATIN_RANGE.search(t))
    total = len(tokens)

    # Token language distribution
    tokens_by_lang: Dict[str, List[str]] = {}
    for t in tokens:
        lang = detect_token_language(t).value
        tokens_by_lang.setdefault(lang, []).append(t)

    # Primary language determination
    if deva_count > 0 and latn_count > 0:
        is_code_switched = True
        primary = SpokenLanguage.HINDI if deva_count >= latn_count else SpokenLanguage.ENGLISH
    elif deva_count > 0:
        is_code_switched = False
        primary = SpokenLanguage.HINDI
    elif latn_count > 0:
        is_code_switched = False
        primary = SpokenLanguage.ENGLISH
    else:
        is_code_switched = False
        primary = SpokenLanguage.UNKNOWN

    return {
        "primary_language": primary,
        "is_code_switched": is_code_switched,
        "devanagari_count": deva_count,
        "latin_count": latn_count,
        "total_tokens": total,
        "latin_ratio": round(latn_count / total, 3),
        "tokens_by_language": tokens_by_lang,
    }
