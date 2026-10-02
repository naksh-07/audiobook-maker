#!/usr/bin/env python3
"""
Audiobook Factory - Alignment Engine: Multi-Signal Calibrated Confidence & Diagnostics.
Computes calibrated confidence score from 5 distinct acoustic and structural signals:
Phonetic (C_phonetic), Coverage (C_coverage), Timing (C_timing), Speech Ratio (C_speech), Boundary (C_boundary).
"""

from __future__ import annotations
import numpy as np
from typing import List, Tuple

from audiobook_factory.alignment_contracts import (
    WordAlignment,
    PauseInterval,
    SpeechRegion,
    AlignmentDiagnostic,
    AlignmentCalibrationConfig,
    AlignmentConfidenceCategory,
)


def calculate_confidence_and_diagnostics(
    words: List[WordAlignment],
    pauses: List[PauseInterval],
    speech_regions: List[SpeechRegion],
    total_audio_ms: int,
    text: str,
    method: str,
    config: AlignmentCalibrationConfig,
) -> Tuple[float, AlignmentConfidenceCategory, List[AlignmentDiagnostic]]:
    """
    Computes calibrated confidence score from 5 distinct acoustic and structural signals.
    Attaches actionable diagnostics.
    """
    cfg = config
    diagnostics: List[AlignmentDiagnostic] = []

    if not words or total_audio_ms <= 0:
        diagnostics.append(
            AlignmentDiagnostic(
                code="INSUFFICIENT_SPEECH",
                severity="CRITICAL",
                message="No aligned words or zero audio duration",
            )
        )
        return 0.0, "FAILED_REVIEW_REQUIRED", diagnostics

    # Signal 1: Phonetic Alignment Confidence (C_phonetic)
    raw_scores = [w.confidence for w in words]
    mean_score = float(np.mean(raw_scores)) if raw_scores else 0.0
    c_phonetic = min(1.0, mean_score * 5.0) if mean_score < 0.20 else min(1.0, 0.70 + mean_score * 0.30)

    # Signal 2: Word Coverage (C_coverage)
    expected_words = max(1, len(text.split()))
    aligned_words = len(words)
    coverage_ratio = aligned_words / float(expected_words)
    c_coverage = max(0.0, 1.0 - abs(1.0 - coverage_ratio))

    # Signal 3: Timing Plausibility (C_timing)
    durations = [w.duration_ms for w in words]
    impossible_durations = [
        d for d in durations
        if d < cfg.min_word_duration_ms or d > cfg.max_word_duration_ms
    ]
    c_timing = max(0.0, 1.0 - (len(impossible_durations) / float(len(words))))

    if impossible_durations:
        diagnostics.append(
            AlignmentDiagnostic(
                code="IMPOSSIBLE_WORD_DURATION",
                severity="WARNING",
                message=f"{len(impossible_durations)} words have implausible duration (<{cfg.min_word_duration_ms}ms or >{cfg.max_word_duration_ms}ms)",
                evidence={"impossible_count": len(impossible_durations)},
            )
        )

    # Signal 4: Speech Activity Ratio (C_speech)
    total_speech_ms = sum(durations)
    speech_ratio = total_speech_ms / float(max(total_audio_ms, 1))
    if speech_ratio < 0.25:
        c_speech = 0.40
        diagnostics.append(
            AlignmentDiagnostic(
                code="INSUFFICIENT_SPEECH",
                severity="WARNING",
                message=f"Speech ratio ({speech_ratio:.2f}) is abnormally low for dialogue line",
                evidence={"speech_ratio": speech_ratio},
            )
        )
    else:
        c_speech = 1.0

    # Signal 5: Boundary Stability (C_boundary)
    boundary_violations = 0
    for i in range(1, len(words)):
        if words[i].start_ms < words[i - 1].end_ms:
            boundary_violations += 1
    c_boundary = max(0.0, 1.0 - (boundary_violations / float(len(words))))
    if boundary_violations > 0:
        diagnostics.append(
            AlignmentDiagnostic(
                code="UNSTABLE_BOUNDARY",
                severity="WARNING",
                message=f"Detected {boundary_violations} overlapping word boundaries",
            )
        )

    # Dead air detection
    dead_air_pauses = [p for p in pauses if p.classification == "dead_air"]
    if dead_air_pauses:
        diagnostics.append(
            AlignmentDiagnostic(
                code="UNEXPECTED_LONG_SILENCE",
                severity="WARNING",
                message=f"Detected {len(dead_air_pauses)} instances of suspicious dead air (> {cfg.dead_air_min_ms}ms)",
                evidence={"max_pause_ms": max(p.duration_ms for p in dead_air_pauses)},
            )
        )

    # Text-audio mismatch check
    if abs(aligned_words - expected_words) >= 3 and expected_words > 4:
        diagnostics.append(
            AlignmentDiagnostic(
                code="TEXT_AUDIO_MISMATCH",
                severity="CRITICAL",
                message=f"Severe token count mismatch: text has {expected_words} words, aligned {aligned_words}",
                evidence={"expected": expected_words, "aligned": aligned_words},
            )
        )

    # Composite Calibrated Confidence Formula
    conf = (
        cfg.weight_phonetic * c_phonetic
        + cfg.weight_coverage * c_coverage
        + cfg.weight_timing * c_timing
        + cfg.weight_speech_activity * c_speech
        + cfg.weight_boundary * c_boundary
    )

    conf = max(0.0, min(1.0, conf))

    # Categorization
    if any(d.severity == "CRITICAL" for d in diagnostics) or conf < cfg.low_confidence_threshold:
        category: AlignmentConfidenceCategory = "FAILED_REVIEW_REQUIRED"
    elif conf >= cfg.high_confidence_threshold:
        category = "HIGH"
    elif conf >= cfg.medium_confidence_threshold:
        category = "MEDIUM"
    else:
        category = "LOW"

    if not diagnostics:
        diagnostics.append(
            AlignmentDiagnostic(
                code="ALIGNMENT_OK",
                severity="INFO",
                message="High-quality phonetic and structural alignment verified",
            )
        )

    return conf, category, diagnostics
