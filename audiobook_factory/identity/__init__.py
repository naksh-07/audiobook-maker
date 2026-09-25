#!/usr/bin/env python3
"""
Audiobook Factory - Character Voice Identity & Drift Defense Subsystem (Wave 2).
Provides Voice DNA, Reference Voice Banks, and Acoustic Voice Identity / Drift Analysis.
"""

from .voice_dna import (
    VoiceDNAIdentityLayer,
    VoiceDNABehaviorLayer,
    VoiceDNAEmotionalLayer,
    VoiceDNAForbiddenLayer,
    VoiceDNA,
    VoiceDNABank,
)
from .reference_bank import (
    AcousticSignature,
    ReferenceVoiceBank,
)
from .voice_drift_analyzer import (
    VoiceIdentityDriftResult,
    VoiceIdentityAnalyzer,
)

__all__ = [
    "VoiceDNAIdentityLayer",
    "VoiceDNABehaviorLayer",
    "VoiceDNAEmotionalLayer",
    "VoiceDNAForbiddenLayer",
    "VoiceDNA",
    "VoiceDNABank",
    "AcousticSignature",
    "ReferenceVoiceBank",
    "VoiceIdentityDriftResult",
    "VoiceIdentityAnalyzer",
]
