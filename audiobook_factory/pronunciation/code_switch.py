#!/usr/bin/env python3
"""
Audiobook Factory - Code-Switching & Spoken Register Handler.
Preserves intentional artistic and dramatic code-switching without forcing every foreign token
into literal phonetic assimilation. Implements Option 1A Hybrid Mode.
"""

from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple
from .contracts import SpokenLanguage, PronunciationPolicy


# Common English loanwords naturally integrated into colloquial Hindustani speech
NATURAL_HINDUSTANI_LOANWORDS = {
    "doctor", "hospital", "police", "station", "captain", "sir", "madam",
    "lord", "lady", "major", "colonel", "sergeant", "whiskey", "brandy",
    "beer", "glass", "bottle", "road", "gate", "coat", "boots", "gun",
    "pistol", "office", "report", "file", "minute", "second", "time"
}


class CodeSwitchEngine:
    """
    Manages language transitions inside dramatic dialogue and narration lines.
    Ensures natural spoken prosody without corrupting literary intentionality.
    """

    @staticmethod
    def is_intentional_code_switch(
        token: str,
        sentence_context: str,
        character_profile: Optional[Any] = None,
    ) -> bool:
        """
        Determines whether an English/foreign token inside Hindi dialogue is intentional code-switching
        rather than untranslated leakage.
        """
        clean = token.strip().lower()
        if clean in NATURAL_HINDUSTANI_LOANWORDS:
            return True

        # Check character sociolinguistic profile quirks or vocabulary preferences
        if character_profile is not None:
            # Modern, scholastic, or aristocrat sociolects naturally code-switch titles or technical terms
            tier = getattr(character_profile, "vocabulary_tier", "balanced")
            if tier in ("scholastic", "techno", "courtly"):
                return True
            # Check speech quirks
            quirks = str(getattr(character_profile, "speech_quirks", "")).lower()
            if "english" in quirks or "bilingual" in quirks or "code-switch" in quirks:
                return True

        return False

    @staticmethod
    def determine_pronunciation_policy(
        token: str,
        sentence_lang: SpokenLanguage,
        token_lang: SpokenLanguage,
        is_proper_noun: bool = False,
    ) -> PronunciationPolicy:
        """
        Selects the appropriate PronunciationPolicy according to Option 1A (Hybrid):
        - Proper nouns in foreign languages: PHONETIC_RESPELLED or CODE_SWITCH_NATIVE
        - Natural integrated loanwords: DESI_COLLOQUIAL
        - Pure target language tokens: STRICT_CANONICAL
        """
        if token_lang == SpokenLanguage.ENGLISH and sentence_lang == SpokenLanguage.HINDI:
            if is_proper_noun:
                # Option 1A Hybrid: Phonetic Devanagari guide for Hindi TTS synthesis,
                # preserving authentic acoustic delivery while literary prose remains in English
                return PronunciationPolicy.PHONETIC_RESPELLED
            elif token.lower() in NATURAL_HINDUSTANI_LOANWORDS:
                return PronunciationPolicy.DESI_COLLOQUIAL
            else:
                return PronunciationPolicy.CODE_SWITCH_NATIVE

        if token_lang == SpokenLanguage.URDU or token_lang == SpokenLanguage.SANSKRIT:
            return PronunciationPolicy.STRICT_CANONICAL

        return PronunciationPolicy.STRICT_CANONICAL
