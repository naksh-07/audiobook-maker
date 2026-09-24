#!/usr/bin/env python3
"""
Audiobook Factory - Terminology Consistency Auditor (Gate T5 & T1).
Executes deterministic validation against Book Bible canonical forms
to eliminate spelling drift and forbidden variants without LLM latency.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from pydantic import BaseModel, Field

from .book_bible import BookBible


class TerminologyAuditResult(BaseModel):
    is_valid: bool
    status: str  # PASS, WARN, FAIL
    forbidden_variants_found: List[str] = Field(default_factory=list)
    missing_canonical_terms: List[str] = Field(default_factory=list)
    leaked_latin_terms: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


# Default generic forbidden variant anti-patterns across novels (novel-agnostic)
COMMON_FORBIDDEN_VARIANTS: Dict[str, str] = {}


def audit_terminology(
    devanagari_text: str,
    book_bible: BookBible,
    source_text: str = "",
    forbidden_variants: Optional[Dict[str, str]] = None,
) -> TerminologyAuditResult:
    """
    Deterministic audit of target Hindi text against Book Bible canonical forms and forbidden variants.
    """
    forbidden_hits: List[str] = []
    warnings: List[str] = []

    # 1. Combine project-level variants with any passed variants
    active_variants: Dict[str, str] = dict(COMMON_FORBIDDEN_VARIANTS)
    if hasattr(book_bible, "terminology_variants") and book_bible.terminology_variants:
        active_variants.update(book_bible.terminology_variants)
    if forbidden_variants:
        active_variants.update(forbidden_variants)

    for pattern, canonical in active_variants.items():
        if re.search(pattern, devanagari_text):
            matches = re.findall(pattern, devanagari_text)
            forbidden_hits.append(f"Forbidden variant '{matches[0]}' -> must be canonical '{canonical}'")

    # 2. Check canonical terms in Book Bible
    lexicon = book_bible.get_canonical_lexicon()
    missing_canon: List[str] = []

    for eng, hi in lexicon.items():
        # If English term appeared heavily in source, check that Devanagari translation is present
        if source_text and re.search(rf"\b{re.escape(eng)}\b", source_text, re.IGNORECASE):
            # Check if canonical Devanagari exists in target
            if hi not in devanagari_text:
                # Check if it was an alias
                warnings.append(f"Expected canonical term '{hi}' for '{eng}' was not explicitly matched in target text.")

    # 3. Check for leaked Latin character names in Hindi text
    leaked_latin: List[str] = []
    for eng_name in book_bible.characters.keys():
        if len(eng_name) >= 4 and re.search(rf"\b{re.escape(eng_name)}\b", devanagari_text):
            leaked_latin.append(f"Leaked English name '{eng_name}' found in Hindi text; should be Devanagari.")

    is_valid = len(forbidden_hits) == 0 and len(leaked_latin) == 0
    status = "PASS" if is_valid and not warnings else ("WARN" if is_valid else "FAIL")

    return TerminologyAuditResult(
        is_valid=is_valid,
        status=status,
        forbidden_variants_found=forbidden_hits,
        missing_canonical_terms=missing_canon,
        leaked_latin_terms=leaked_latin,
        warnings=warnings,
    )
