#!/usr/bin/env python3
"""
Audiobook Factory - Alignment Package.
Modular decomposition of Pillar 4: Workstation Superpower Local Forced Aligner (Alignment 2.0).
"""

from __future__ import annotations

from audiobook_factory.alignment.text_utils import (
    DEVA_TO_ROMAN_MAP,
    transliterate_devanagari_to_roman,
    normalize_text_for_alignment,
)
from audiobook_factory.alignment.audio_io import (
    _load_wav_tensor_safely,
    _read_pcm_samples,
    _get_wav_duration_ms,
)
from audiobook_factory.alignment.pause_classifier import (
    classify_pause,
)
from audiobook_factory.alignment.diagnostics import (
    calculate_confidence_and_diagnostics,
)
from audiobook_factory.alignment.energy_fallback import (
    align_with_energy_fallback,
    align_single_with_energy_fallback,
    align_batch_detailed_with_energy_fallback,
)
from audiobook_factory.alignment.mms_aligner import (
    WorkstationForcedAligner,
)

__all__ = [
    "WorkstationForcedAligner",
    "DEVA_TO_ROMAN_MAP",
    "transliterate_devanagari_to_roman",
    "normalize_text_for_alignment",
    "_load_wav_tensor_safely",
    "_read_pcm_samples",
    "_get_wav_duration_ms",
    "classify_pause",
    "calculate_confidence_and_diagnostics",
    "align_with_energy_fallback",
    "align_single_with_energy_fallback",
    "align_batch_detailed_with_energy_fallback",
]
