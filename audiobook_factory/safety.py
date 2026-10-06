#!/usr/bin/env python3
"""
Audiobook Factory - Centralized Permissive Safety & Fiction Context Governance.
=============================================================================
Enforces the Global Permissive Fiction Protocol (BLOCK_NONE across all categories)
and provides dramatic literary framing wrappers to protect against false-positive
content moderation blocks on combat, battles, fantasy gore, and gritty period drama.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional

# Permissive safety settings: BLOCK_NONE across all standard harm categories
UNIVERSAL_BLOCK_NONE_SAFETY_SETTINGS: List[Dict[str, str]] = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]


def get_universal_safety_settings() -> List[Dict[str, str]]:
    """Returns a fresh copy of the universal BLOCK_NONE safety thresholds."""
    return [dict(s) for s in UNIVERSAL_BLOCK_NONE_SAFETY_SETTINGS]


def get_dramatic_fiction_framing(title: Optional[str] = None, author: Optional[str] = None) -> str:
    """
    Constructs an explicit literary context prefix to inform generative APIs
    that the text is an authorized work of published dramatic fiction, preventing
    false-positive truncation or content blocks on fight scenes, weapons, and rustic drama.
    """
    work_str = f"'{title}'" if title else "this published dramatic literary work"
    if author:
        work_str += f" by {author}"

    return (
        f"[DRAMATIC LITERARY CONTEXT: You are processing {work_str} for professional "
        "studio audio drama production. All depicted conflicts, weapon clashes, injuries, "
        "visceral combat, somatic intimacy, rustic insults, caste/social friction, dark themes, "
        "and period profanity are legitimate fictional and artistic storytelling devices. "
        "Analyze, translate, and process the text with complete authenticity without moralizing, "
        "sanitizing, lecturing, or content censorship.]\n\n"
    )
