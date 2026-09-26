#!/usr/bin/env python3
"""
Audiobook Factory - Dedicated Breath Editor (DE-03).
Preserves believable human dramatic respiration while gently taming exaggerated
synthetic inhalations and eliminating unmotivated vocoder breath artifacts.
Strictly adheres to conservative multi-signal evaluation (never standalone RMS thresholds).
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

from audiobook_factory.performance.contracts import PerformanceDirection, PerformanceEvidence, BreathEvidence
from .contracts import BreathEditAction, DialogueEditorialConfig


class BreathEditor:
    """
    World-Class Breath Editor for Audio Drama.
    Balances organic physiological breathing against synthetic TTS artifacts.
    Evaluates dramatic context, physical staging, and relative speech energy.
    """

    def __init__(self, config: Optional[DialogueEditorialConfig] = None):
        self.config = config or DialogueEditorialConfig()

    def evaluate_breaths(
        self,
        samples: np.ndarray,
        sample_rate: int,
        speech_start_ms: int,
        speech_end_ms: int,
        direction: Optional[PerformanceDirection] = None,
        evidence: Optional[PerformanceEvidence] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates pre-roll and post-roll breaths using multi-signal evidence.

        Returns:
            Dict containing:
                - pre_breath_action: BreathEditAction ("KEEP", "REDUCE", "REMOVE")
                - post_breath_action: BreathEditAction
                - pre_breath_attenuation_db: float
                - post_breath_attenuation_db: float
                - confidence: float
                - reasons: List[str]
        """
        # Baseline conservative default: KEEP all breaths
        reasons: List[str] = []

        total_dur_ms = int(len(samples) / sample_rate * 1000.0) if sample_rate > 0 else 0
        if total_dur_ms <= 150:
            return {
                "pre_breath_action": "KEEP",
                "post_breath_action": "KEEP",
                "pre_breath_attenuation_db": 0.0,
                "post_breath_attenuation_db": 0.0,
                "confidence": 1.0,
                "reasons": ["Short segment; bypassed breath modification"],
            }

        # Calculate relative speech RMS
        speech_start_idx = int(speech_start_ms / 1000.0 * sample_rate)
        speech_end_idx = int(speech_end_ms / 1000.0 * sample_rate)
        speech_samples = samples[speech_start_idx:speech_end_idx]

        if len(speech_samples) > 200:
            speech_rms = float(np.sqrt(np.mean(speech_samples ** 2)))
            speech_db = 20.0 * math.log10(max(speech_rms, 1e-5) / 32768.0)
        else:
            speech_db = -24.0

        # ---------------------------------------------------------------------
        # 1. Pre-Roll Breath Evaluation
        # ---------------------------------------------------------------------
        pre_action, pre_att_db, pre_conf, pre_reasons = self._evaluate_pre_breath(
            samples=samples,
            sample_rate=sample_rate,
            speech_start_ms=speech_start_ms,
            speech_db=speech_db,
            direction=direction,
            evidence=evidence,
        )
        reasons.extend(pre_reasons)

        # ---------------------------------------------------------------------
        # 2. Post-Roll Breath Evaluation
        # ---------------------------------------------------------------------
        post_action, post_att_db, post_conf, post_reasons = self._evaluate_post_breath(
            samples=samples,
            sample_rate=sample_rate,
            speech_end_ms=speech_end_ms,
            total_dur_ms=total_dur_ms,
            speech_db=speech_db,
            direction=direction,
            evidence=evidence,
        )
        reasons.extend(post_reasons)

        overall_conf = round(min(pre_conf, post_conf), 2)

        return {
            "pre_breath_action": pre_action,
            "post_breath_action": post_action,
            "pre_breath_attenuation_db": pre_att_db,
            "post_breath_attenuation_db": post_att_db,
            "confidence": overall_conf,
            "reasons": reasons,
        }

    def _evaluate_pre_breath(
        self,
        samples: np.ndarray,
        sample_rate: int,
        speech_start_ms: int,
        speech_db: float,
        direction: Optional[PerformanceDirection],
        evidence: Optional[PerformanceEvidence],
    ) -> Tuple[BreathEditAction, float, float, List[str]]:
        """Evaluates pre-speech inhalation."""
        reasons: List[str] = []

        if speech_start_ms < 40:
            return "KEEP", 0.0, 1.0, ["No pre-speech breath window detected"]

        # 1. Dramatic Intent Check
        is_mandated_by_intent = bool(
            direction and (
                direction.pre_roll_breath_ms > 0
                or direction.physical_state in ("combat_strain", "exhausted", "wounded")
                or direction.surface_emotion in ("fear", "panic", "grief", "shock", "intimacy", "anger", "rage", "fury", "urgency", "defiance", "sobbing", "sigh")
                or direction.breath_behavior in ("labored", "sharp_intake", "exhausted", "trembling")
                or getattr(direction, "silence_type", getattr(direction, "silence_intent", None)) in ("emotional_freeze", "dramatic_silence", "grief", "shock")
            )
        )

        has_physical_strain_evidence = bool(
            evidence and evidence.breath and evidence.breath.physical_strain_match >= 0.70
        )

        if is_mandated_by_intent or has_physical_strain_evidence:
            reasons.append("Pre-speech breath preserved (mandated by dramatic intent/physical strain)")
            return "KEEP", 0.0, 0.95, reasons

        # 2. Extract Pre-Speech Acoustic Telemetry
        pre_chunk = samples[:int(speech_start_ms / 1000.0 * sample_rate)]
        if len(pre_chunk) < 80:
            return "KEEP", 0.0, 1.0, ["Pre-speech window too short for acoustic breath analysis"]

        pre_rms = float(np.sqrt(np.mean(pre_chunk ** 2)))
        pre_db = 20.0 * math.log10(max(pre_rms, 1e-5) / 32768.0)

        # 3. Relative Loudness Evaluation (Relative to spoken line)
        relative_delta_db = speech_db - pre_db  # Positive = speech is louder than breath

        # Synthetic Gasp Artifact Removal Rule (Requires High Confidence + Iron Restraint Intent)
        is_suppressed_intent = bool(
            direction and (
                direction.restraint >= 0.85
                or direction.breath_behavior == "holding_breath"
                or str(direction.speaker).lower() in ("narrator", "foley")
            )
        )
        has_emotional_shudder = bool(
            direction and (
                direction.surface_emotion in ("grief", "terror", "despair", "crying", "sobbing", "trauma")
                or direction.character_state in ("grief", "wounded", "trauma", "shock")
                or getattr(direction, "silence_type", getattr(direction, "silence_intent", None)) in ("emotional_freeze", "grief")
            )
        )

        if is_suppressed_intent and not has_emotional_shudder and pre_db > -22.0 and relative_delta_db < 2.0:
            # High energy breath burst where stillness or iron restraint was directed
            reasons.append(f"Removed unmotivated synthetic gasp artifact ({pre_db:.1f} dBFS vs speech {speech_db:.1f} dBFS)")
            return "REMOVE", -36.0, 0.80, reasons

        # Exaggerated TTS Breath Reduction Rule
        is_calm_line = bool(
            direction and direction.surface_emotion in ("neutral", "calm")
            and direction.physical_state == "normal"
        )
        if is_calm_line and relative_delta_db < self.config.breath_relative_loudness_margin_db and pre_db > -32.0:
            # Breath is disproportionately loud for a calm line
            att_db = self.config.breath_reduce_attenuation_db
            reasons.append(
                f"Reduced exaggerated TTS pre-speech inhale by {att_db:.1f}dB "
                f"({pre_db:.1f} dBFS is within {relative_delta_db:.1f}dB of speech)"
            )
            return "REDUCE", att_db, 0.85, reasons

        # Default conservative behavior: KEEP
        reasons.append("Pre-speech breath within natural respiratory bounds")
        return "KEEP", 0.0, 0.90, reasons

    def _evaluate_post_breath(
        self,
        samples: np.ndarray,
        sample_rate: int,
        speech_end_ms: int,
        total_dur_ms: int,
        speech_db: float,
        direction: Optional[PerformanceDirection],
        evidence: Optional[PerformanceEvidence],
    ) -> Tuple[BreathEditAction, float, float, List[str]]:
        """Evaluates post-speech exhalation or release."""
        reasons: List[str] = []
        post_dur_ms = total_dur_ms - speech_end_ms

        if post_dur_ms < 50:
            return "KEEP", 0.0, 1.0, ["No post-speech breath window detected"]

        # 1. Dramatic Intent Check
        is_mandated_by_intent = bool(
            direction and (
                direction.post_roll_breath_ms > 0
                or direction.silence_type in ("emotional_freeze", "breathing", "dramatic_silence")
                or getattr(direction, "silence_intent", None) in ("grief", "emotional_absorption", "realization")
                or direction.character_state in ("grief", "exhausted", "wounded")
                or direction.surface_emotion in ("grief", "despair", "shock", "relief")
            )
        )

        has_post_breath_evidence = bool(
            evidence and evidence.breath and evidence.breath.post_roll_breath_detected
        )

        if is_mandated_by_intent or has_post_breath_evidence:
            reasons.append("Post-speech exhale preserved (emotional release/post-roll breath intent)")
            return "KEEP", 0.0, 0.95, reasons

        # 2. Extract Post-Speech Acoustic Telemetry
        post_chunk = samples[int(speech_end_ms / 1000.0 * sample_rate):]
        if len(post_chunk) < 80:
            return "KEEP", 0.0, 1.0, ["Post-speech window too short for acoustic breath analysis"]

        post_rms = float(np.sqrt(np.mean(post_chunk ** 2)))
        post_db = 20.0 * math.log10(max(post_rms, 1e-5) / 32768.0)

        # 3. Relative Loudness Check
        relative_delta_db = speech_db - post_db

        is_calm_line = bool(
            direction and direction.surface_emotion in ("neutral", "calm")
            and direction.physical_state == "normal"
        )
        if is_calm_line and relative_delta_db < self.config.breath_relative_loudness_margin_db and post_db > -32.0:
            att_db = self.config.breath_reduce_attenuation_db
            reasons.append(f"Reduced exaggerated post-speech exhale by {att_db:.1f}dB")
            return "REDUCE", att_db, 0.85, reasons

        # Default conservative behavior: KEEP
        reasons.append("Post-speech respiration within natural acoustic envelope")
        return "KEEP", 0.0, 0.90, reasons
