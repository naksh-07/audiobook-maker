#!/usr/bin/env python3
"""
Audiobook Factory - Alignment Engine: Pause & Breath Intelligence Classifier.
Classifies non-speech intervals into dramatic, respiratory, grammatical, or defect silences.
"""

from __future__ import annotations
import math
import numpy as np
from typing import Optional, Any

from audiobook_factory.alignment_contracts import (
    PauseInterval,
    PauseClassification,
    AlignmentCalibrationConfig,
)


def classify_pause(
    start_ms: int,
    end_ms: int,
    samples: np.ndarray,
    sample_rate: int,
    config: AlignmentCalibrationConfig,
    direction: Optional[Any] = None,
    is_initial: bool = False,
    is_terminal: bool = False,
) -> PauseInterval:
    """
    Classifies non-speech intervals into dramatic, respiratory, grammatical, or defect silences.
    """
    dur_ms = max(0, end_ms - start_ms)
    cfg = config

    # Extract samples in pause window
    if len(samples) > 0 and sample_rate > 0:
        s_idx = (start_ms * sample_rate) // 1000
        e_idx = (end_ms * sample_rate) // 1000
        pause_samples = samples[s_idx:e_idx]
        rms = float(np.sqrt(np.mean(pause_samples ** 2))) if len(pause_samples) > 0 else 0.0
        rms_dbfs = 20.0 * math.log10(max(rms, 1e-6) / 32768.0)
    else:
        rms_dbfs = -60.0

    classification: PauseClassification = "natural_pause"

    # 1. Trailing or intra-line dead air check (long unmotivated silence)
    if dur_ms >= cfg.dead_air_min_ms:
        # Check if direction explicitly requested high restraint or dramatic silence
        prio = getattr(direction, "performance_priority", "standard") if direction else "standard"
        restraint = getattr(direction, "restraint", 0.5) if direction else 0.5
        if prio == "climactic" or restraint >= 0.80:
            classification = "dramatic_pause"
        else:
            classification = "dead_air"

    # 2. Digital zero step discontinuity check (short dropout between words)
    elif rms_dbfs < cfg.synthetic_gap_rms_dbfs and dur_ms >= 50:
        classification = "synthetic_gap"

    # 3. Initial breath intake check
    elif is_initial and dur_ms <= cfg.breath_pause_max_ms:
        classification = "breath_pause"

    # 4. Interruption / abrupt cutoff check
    elif dur_ms <= 100 and direction and getattr(direction, "interruption_behavior", "none") != "none":
        classification = "interruption_gap"

    # 5. Dramatic pause vs natural pause
    elif dur_ms >= cfg.dramatic_pause_min_ms:
        classification = "dramatic_pause"

    elif dur_ms < cfg.natural_pause_min_ms and not is_initial and not is_terminal:
        classification = "hesitation"

    else:
        classification = "natural_pause"

    return PauseInterval(
        start_ms=start_ms,
        end_ms=end_ms,
        duration_ms=dur_ms,
        classification=classification,
        confidence=0.90,
    )
