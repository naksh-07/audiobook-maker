#!/usr/bin/env python3
"""
Audiobook Factory - Pronunciation & Spoken Language QA Subsystem.
Provides canonical pronunciation lexicon management, deterministic multi-tier resolution,
code-switch detection, spoken text transformation, audio-level verification with forced alignment,
targeted single-take repairs, and cross-chapter consistency tracking.
"""

from .contracts import (
    PronunciationStatus,
    PronunciationSource,
    SpokenLanguage,
    PronunciationPolicy,
    PronunciationEntry,
    PronunciationResolutionResult,
    SpokenTextResult,
    PronunciationAudioQAResult,
    CrossChapterPronunciationDrift,
    PronunciationProvenanceRecord,
)
from .lexicon import PronunciationLexicon
from .language_detector import detect_token_language, classify_sentence_language
from .code_switch import CodeSwitchEngine
from .resolver import PronunciationResolver, number_to_hindi_words
from .spoken_text import SpokenTextEngine
from .auditor import PronunciationAudioQA
from .repair import PronunciationRepairEngine
from .consistency import CrossChapterConsistencyAuditor
from .provenance import PronunciationProvenanceTracker
from .golden_set import GOLDEN_PRONUNCIATION_CASES, run_golden_pronunciation_suite

__all__ = [
    "PronunciationStatus",
    "PronunciationSource",
    "SpokenLanguage",
    "PronunciationPolicy",
    "PronunciationEntry",
    "PronunciationResolutionResult",
    "SpokenTextResult",
    "PronunciationAudioQAResult",
    "CrossChapterPronunciationDrift",
    "PronunciationProvenanceRecord",
    "PronunciationLexicon",
    "detect_token_language",
    "classify_sentence_language",
    "CodeSwitchEngine",
    "PronunciationResolver",
    "number_to_hindi_words",
    "SpokenTextEngine",
    "PronunciationAudioQA",
    "PronunciationRepairEngine",
    "CrossChapterConsistencyAuditor",
    "PronunciationProvenanceTracker",
    "GOLDEN_PRONUNCIATION_CASES",
    "run_golden_pronunciation_suite",
]
