#!/usr/bin/env python3
"""
Audiobook Factory - Kruti Dev 010 to Unicode Devanagari Transcoder.
Provides high-precision deterministic transcoding of legacy 8-bit Kruti Dev 010
typeset text into standard Unicode Devanagari (U+0900..U+097F).
Zero-dependency, thread-safe, and non-destructive.
"""

from __future__ import annotations
import re
from typing import Dict, Tuple

# Legacy Kruti Dev signature character combinations for detection
KRUTIDEV_SIGNATURES = (
    "gSjh", "ikWVj", "vkSj", "iRFkj", "D;k", "gS", "Fkk", "Fkh", "Fks",
    "ugha", "fd;k", "x;k", "ysfdu", "mlds", "mldh", "vius", "viuh"
)

# Core Kruti Dev 010 character and matra substitution mapping
KRUTIDEV_MAPPINGS: Tuple[Tuple[str, str], ...] = (
    ("ñ", "र्"),
    ("ò", "रु"),
    ("ó", "रू"),
    ("ô", "ह्न"),
    ("õ", "हृ"),
    ("ù", "ह्र"),
    ("ú", "ह्ल"),
    ("û", "ह्म"),
    ("ü", "ह्म्"),
    ("ý", "ह्य"),
    ("þ", "ह्"),
    (" ", " "),
    ("अा", "आ"),
    ("अो", "ओ"),
    ("अौ", "औ"),
    ("अे", "ए"),
    ("अै", "ऐ"),
    ("ाे", "ो"),
    ("ाै", "ौ"),
    ("ाे", "ो"),
    ("ाै", "ौ"),
    ("ा", "ा"),
    ("ी", "ी"),
    ("ु", "ु"),
    ("ू", "ू"),
    ("ृ", "ृ"),
    ("े", "े"),
    ("ै", "ै"),
    ("ं", "ं"),
    ("ँ", "ँ"),
    ("ः", "ः"),
    ("्", "्"),
    ("़", "़"),
    ("ऽ", "ऽ"),
    ("।", "।"),
    ("॥", "॥"),
    ("०", "०"),
    ("१", "१"),
    ("२", "२"),
    ("३", "३"),
    ("४", "४"),
    ("५", "५"),
    ("६", "६"),
    ("७", "७"),
    ("८", "८"),
    ("९", "९"),
    ("kS", "ौ"),
    ("ks", "ो"),
    ("k", "ा"),
    ("h", "ी"),
    ("q", "ु"),
    ("w", "ू"),
    ("`", "ृ"),
    ("s", "े"),
    ("S", "ै"),
    ("a", "ं"),
    ("W", "ॉ"),
    ("A", "ँ"),
    ("%", "ः"),
    ("~", "्"),
    ("+", "़"),
    ("vks", "ओ"),
    ("vkS", "औ"),
    ("vk", "आ"),
    ("v", "अ"),
    ("b", "इ"),
    ("bZ", "ई"),
    ("m", "उ"),
    ("Å", "ऊ"),
    (",s", "ऐ"),
    (",", "ए"),
    ("d", "क"),
    ("D", "क्"),
    ("[k", "ख"),
    ("[", "ख्"),
    ("x", "ग"),
    ("X", "ग्"),
    ("?k", "घ"),
    ("?", "घ्"),
    ("³", "ङ"),
    ("p", "च"),
    ("P", "च्"),
    ("N", "छ"),
    ("t", "ज"),
    ("T", "ज्"),
    (">k", "झ"),
    (">", "झ्"),
    ("¥", "ञ"),
    ("V", "ट"),
    ("B", "ठ"),
    ("M", "ड"),
    ("<", "ढ"),
    (".", "ड़"),
    ("/", "ढ़"),
    (".k", "ण"),
    ("T", "ण्"),
    ("r", "त"),
    ("R", "त्"),
    ("Fk", "थ"),
    ("F", "थ्"),
    ("n", "द"),
    ("èk", "ध"),
    ("è", "ध्"),
    ("/k", "ध"),
    ("/", "ध्"),
    ("u", "न"),
    ("U", "न्"),
    ("i", "प"),
    ("I", "प्"),
    ("Q", "फ"),
    ("b", "ब"),
    ("B", "ब्"),
    ("Hk", "भ"),
    ("H", "भ्"),
    ("e", "म"),
    ("E", "म्"),
    (";k", "य"),
    (";", "य्"),
    ("j", "र"),
    ("y", "ल"),
    ("Y", "ल्"),
    ("o", "व"),
    ("O", "व्"),
    ("'k", "श"),
    ("'", "श्"),
    ("\"k", "ष"),
    ("\"", "ष्"),
    ("l", "स"),
    ("L", "स्"),
    ("g", "ह"),
    ("G", "ह्"),
    ("K", "ज्ञ"),
    ("=", "त्र"),
    ("«", "्र"),
    ("}", "द्व"),
    ("{", "द्ध"),
    ("`", "द्य"),
    ("]", "द्द"),
    ("[", "द्ब"),
    ("~", "द्भ"),
    ("|", "द्य"),
)


def is_krutidev_text(sample: str, threshold: float = 0.05) -> bool:
    """
    Detects if raw ASCII text contains Kruti Dev 010 font encoding signatures.
    """
    if not sample or len(sample) < 20:
        return False

    tokens = sample.split()
    if not tokens:
        return False

    sig_count = sum(1 for t in tokens if any(sig in t for sig in KRUTIDEV_SIGNATURES))
    return (sig_count / len(tokens)) >= threshold


def transcode_krutidev_to_devanagari(text: str) -> str:
    """
    Transcodes Kruti Dev 010 text to Unicode Devanagari.
    Handles choti-ee matra reversal ('f' placed before consonant).
    """
    if not text:
        return ""

    out = text

    # Pre-pass: Handle 'f' matra (choti-ee) which in Kruti Dev is typeset BEFORE consonant
    # e.g., 'fd' -> 'कि'
    out = re.sub(r"f([a-zA-Z\u00C0-\u024F]+)", r"\1f", out)

    # Core substitutions
    for k, v in KRUTIDEV_MAPPINGS:
        out = out.replace(k, v)

    # Convert trailing 'f' to 'ि'
    out = out.replace("f", "ि")

    # Post-pass: Clean double matras or formatting artifacts
    out = out.replace("ाे", "ो").replace("ाै", "ौ").replace("अा", "आ")

    return out
