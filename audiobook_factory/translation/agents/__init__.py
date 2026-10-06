#!/usr/bin/env python3
"""
Audiobook Factory - Room 2: Multi-Agent Dramatic Translation Collective.
Deconstructs literary translation into 4 specialized collaborative agents:
1. LiteraryDraftTranslator: Sense-for-sense dramatic prose & scene mode translation.
2. HindustaniCadenceSpecialist: Spoken audio drama prosody, breath pauses & honorifics.
3. SubtextAndIdiomDramaturge: Earthy Hindustani metaphors, rustic grit & 19-to-21 amplification.
4. TranslationQualityCritic: Independent canon terminology verification & reflection repair.
"""

from .draft_translator import LiteraryDraftTranslator
from .cadence_specialist import HindustaniCadenceSpecialist
from .idiom_dramaturge import SubtextAndIdiomDramaturge
from .translation_critic import TranslationQualityCritic
from .collective import MultiAgentTranslationCollective, get_translation_collective

__all__ = [
    "LiteraryDraftTranslator",
    "HindustaniCadenceSpecialist",
    "SubtextAndIdiomDramaturge",
    "TranslationQualityCritic",
    "MultiAgentTranslationCollective",
    "get_translation_collective",
]
