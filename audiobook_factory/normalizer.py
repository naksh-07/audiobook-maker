#!/usr/bin/env python3
"""
AudioBookmaker - Pillar 1: Non-Destructive Literary Normalizer.
Provides high-fidelity text normalization for speech synthesis while preserving
sacred source text unmutated in the canonical layer.
"""

from __future__ import annotations
import re
import unicodedata
from typing import Tuple, List, Dict


ZERO_WIDTH_CHARS = ("\u200b", "\u200c", "\u200d", "\ufeff", "\u2060", "\u00ad")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

PUNCTUATION_REPLACEMENTS = {
    "\u2018": "'",   # Left single quote
    "\u2019": "'",   # Right single quote
    "\u201c": '"',   # Left double quote
    "\u201d": '"',   # Right double quote
    "\u2014": " — ", # Em dash
    "\u2013": " – ", # En dash
    "\u2026": "...", # Ellipsis
    "\r\n": "\n",
    "\r": "\n",
}


def clean_book_text(text: str, preserve_literary_quotes: bool = False) -> str:
    """
    Sanitize book text non-destructively for speech reading.
    Retains 100% backward compatibility for existing callers.
    
    Operations:
    0. Unicode NFC normalization & invisible zero-width/control character hygiene.
    1. Broken hyphenated linebreak healing (e.g. "impor-\\ntant" -> "important").
    2. Smart quote & dash normalization (unless preserve_literary_quotes is True).
    3. Safe footnote reference removal (e.g. "[1]", "[23]").
    4. Running headers/page number line stripping.
    5. Excessive whitespace collapsing.
    """
    if not text:
        return ""

    # 0. Unicode NFC normalization & invisible zero-width / C0-C1 control character hygiene
    text = unicodedata.normalize("NFC", text)
    for zw in ZERO_WIDTH_CHARS:
        text = text.replace(zw, "")
    text = CONTROL_CHARS_RE.sub("", text)

    # 1. Fix broken hyphenated linebreaks across lines (ASCII, Accented Latin, Devanagari)
    text = re.sub(
        r"(\b[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F]{2,})-\n+([a-zA-Z\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F]{2,}\b)",
        r"\1\2",
        text,
    )

    # 2. Punctuation normalization
    if not preserve_literary_quotes:
        for orig, repl in PUNCTUATION_REPLACEMENTS.items():
            text = text.replace(orig, repl)
    else:
        text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Strip footnote reference marks: e.g. "[1]", "[23]"
    text = re.sub(r"\[\d{1,3}\]", "", text)

    # 4. Remove common running headers/page number lines: e.g. "Page 42 of 300", "- 42 -"
    text = re.sub(r"^[\s\-\–—]*page\s+\d+(?:\s+of\s+\d+)?[\s\-\–—]*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r"^[\s\-\–—]*\d+[\s\-\–—]*$", "", text, flags=re.IGNORECASE | re.MULTILINE)

    # 5. Collapse excessive whitespace without wiping paragraph boundaries
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_block_text(raw_text: str, preserve_literary_quotes: bool = False) -> Tuple[str, List[str]]:
    """
    Normalizes a single literary block while recording any forensic warnings.
    Returns: (normalized_text, warnings)
    """
    if not raw_text:
        return "", []

    warnings: List[str] = []
    
    # Check for unhandled control or replacement characters
    if "\ufffd" in raw_text:
        warnings.append("Block contains Unicode replacement character (\\ufffd) indicating character decode defect.")
    if CONTROL_CHARS_RE.search(raw_text):
        warnings.append("Block contained ASCII/C1 control characters which were stripped during normalization.")

    # Check for excessive broken words
    hyphen_breaks = len(re.findall(r"\b\w+-\n+\w+\b", raw_text))
    if hyphen_breaks > 3:
        warnings.append(f"Block contained {hyphen_breaks} hyphenated line breaks healed.")

    normalized = clean_book_text(raw_text, preserve_literary_quotes=preserve_literary_quotes)
    return normalized, warnings
