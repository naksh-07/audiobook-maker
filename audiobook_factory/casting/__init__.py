#!/usr/bin/env python3
"""
Audiobook Factory - Casting Subsystem & Voice Allocation Engine.
Provides character casting profiles, candidate discovery, voice auditions,
multi-dimensional evaluation, and immutable cast locking.
"""

from .contracts import (
    CharacterCastingProfile,
    VoiceCandidateScore,
    AuditionScene,
    AuditionResult,
    CastingEvaluationRecord,
    CastLock,
    CastLockManifest,
)
from .candidate_engine import VoiceCandidateEngine
from .audition_engine import VoiceAuditionEngine
from .casting_evaluator import CastingEvaluator
from .cast_lock import CastLockManager

__all__ = [
    "CharacterCastingProfile",
    "VoiceCandidateScore",
    "AuditionScene",
    "AuditionResult",
    "CastingEvaluationRecord",
    "CastLock",
    "CastLockManifest",
    "VoiceCandidateEngine",
    "VoiceAuditionEngine",
    "CastingEvaluator",
    "CastLockManager",
]
