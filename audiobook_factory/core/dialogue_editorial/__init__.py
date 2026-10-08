#!/usr/bin/env python3
"""
Audiobook Factory - Dialogue Editorial DSP Package (DE-01 - DE-07).
Standard: v6.0-ENTERPRISE-DAG
"""

from .dsp import (
    apply_hann_fades,
    trim_silence_speech_floor,
    apply_highpass_filter,
    generate_silence_padding,
)
from .editor import DialogueEditorialEngine, EditorialPlan

__all__ = [
    "apply_hann_fades",
    "trim_silence_speech_floor",
    "apply_highpass_filter",
    "generate_silence_padding",
    "DialogueEditorialEngine",
    "EditorialPlan",
]
