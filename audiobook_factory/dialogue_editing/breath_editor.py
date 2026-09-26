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

from audiobook_factory.alignment_contracts import AlignmentResult
from audiobook_factory.performance.contracts import PerformanceDirection, PerformanceEvidence, BreathEvidence
from .contracts import BreathEditAction, DialogueEditorialConfig, MidLineBreathEdit


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
        alignment: Optional[AlignmentResult] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates pre-roll, post-roll, and mid-line breaths using multi-signal evidence.

        Returns:
            Dict containing:
                - pre_breath_action: BreathEditAction ("KEEP", "REDUCE", "REMOVE")
                - post_breath_action: BreathEditAction
                - pre_breath_attenuation_db: float
                - post_breath_attenuation_db: float
                - mid_breath_edits: List[MidLineBreathEdit]
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
                "mid_breath_edits": [],
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

        # ---------------------------------------------------------------------
        # 3. Mid-Line Breath Evaluation (DE-07)
        # ---------------------------------------------------------------------
        mid_edits = self.evaluate_mid_line_breaths(
            samples=samples,
            sample_rate=sample_rate,
            speech_start_ms=speech_start_ms,
            speech_end_ms=speech_end_ms,
            speech_db=speech_db,
            direction=direction,
            evidence=evidence,
            alignment=alignment,
        )
        for me in mid_edits:
            if me.action != "KEEP":
                reasons.append(f"Mid-line breath at {me.start_ms}-{me.end_ms}ms: {me.action} ({me.reason})")

        overall_conf = round(min(pre_conf, post_conf), 2)

        return {
            "pre_breath_action": pre_action,
            "post_breath_action": post_action,
            "pre_breath_attenuation_db": pre_att_db,
            "post_breath_attenuation_db": post_att_db,
            "mid_breath_edits": mid_edits,
            "confidence": overall_conf,
            "reasons": reasons,
        }

    def evaluate_mid_line_breaths(
        self,
        samples: np.ndarray,
        sample_rate: int,
        speech_start_ms: int,
        speech_end_ms: int,
        speech_db: float,
        direction: Optional[PerformanceDirection] = None,
        evidence: Optional[PerformanceEvidence] = None,
        alignment: Optional[AlignmentResult] = None,
    ) -> List[MidLineBreathEdit]:
        """
        Detects and evaluates mid-line breath events within dialogue (DE-07).
        Uses alignment pause/word intervals or acoustic energy dips.
        Preserves emotional/performance-critical breaths; reduces exaggerated gasps on calm lines.
        """
        mid_edits: List[MidLineBreathEdit] = []
        if speech_end_ms - speech_start_ms < 600:
            return mid_edits

        # 1. Discover Candidate Mid-Line Gaps
        candidate_gaps: List[Tuple[int, int]] = []

        if alignment and alignment.pauses:
            for p in alignment.pauses:
                # Must be strictly internal to speech bounds
                if p.start_ms >= speech_start_ms + 80 and p.end_ms <= speech_end_ms - 80:
                    dur = p.end_ms - p.start_ms
                    if 80 <= dur <= 1200:
                        candidate_gaps.append((p.start_ms, p.end_ms))

        elif alignment and alignment.words and len(alignment.words) > 1:
            sorted_words = sorted(alignment.words, key=lambda w: w.start_ms)
            for k in range(len(sorted_words) - 1):
                gap_s = sorted_words[k].end_ms
                gap_e = sorted_words[k + 1].start_ms
                dur = gap_e - gap_s
                if 100 <= dur <= 1000 and gap_s >= speech_start_ms + 80 and gap_e <= speech_end_ms - 80:
                    candidate_gaps.append((gap_s, gap_e))

        # Fallback acoustic energy dip detection if no alignment provided
        if not candidate_gaps and len(samples) > 0 and sample_rate > 0:
            frame_ms = 40
            frame_samples = int(sample_rate * (frame_ms / 1000.0))
            hop_samples = frame_samples // 2

            start_sample = int((speech_start_ms + 150) / 1000.0 * sample_rate)
            end_sample = int((speech_end_ms - 150) / 1000.0 * sample_rate)

            in_gap = False
            gap_start_sm = 0
            for pos in range(start_sample, max(start_sample, end_sample - frame_samples), hop_samples):
                frm = samples[pos : pos + frame_samples]
                rms = float(np.sqrt(np.mean(frm ** 2))) if len(frm) > 0 else 0.0
                f_db = 20.0 * math.log10(max(rms, 1e-5) / 32768.0)

                # Gap threshold: 14dB below speech RMS
                is_low = (speech_db - f_db) > 14.0
                if is_low and not in_gap:
                    in_gap = True
                    gap_start_sm = pos
                elif not is_low and in_gap:
                    in_gap = False
                    dur_ms = int((pos - gap_start_sm) / sample_rate * 1000.0)
                    if 120 <= dur_ms <= 900:
                        candidate_gaps.append((
                            int(gap_start_sm / sample_rate * 1000.0),
                            int(pos / sample_rate * 1000.0)
                        ))

        # 2. Check Dramatic Intent Protections (Emotional / Strain Safeguards)
        is_mandated_emotional_breath = bool(
            direction and (
                direction.physical_state in ("combat_strain", "exhausted", "wounded")
                or direction.surface_emotion in (
                    "fear", "panic", "grief", "shock", "intimacy", "anger", "rage",
                    "fury", "urgency", "defiance", "sobbing", "sigh", "despair", "crying"
                )
                or direction.breath_behavior in ("labored", "sharp_intake", "exhausted", "trembling")
                or getattr(direction, "silence_type", getattr(direction, "silence_intent", None)) in (
                    "emotional_freeze", "dramatic_silence", "grief", "shock"
                )
                or direction.character_state in ("grief", "wounded", "trauma", "shock")
            )
        )
        has_physical_strain = bool(
            evidence and evidence.breath and evidence.breath.physical_strain_match >= 0.70
        )
        is_suppressed_restraint = bool(
            direction and direction.restraint >= 0.85
            and getattr(direction, "character_state", "") in ("grief", "wounded", "trauma", "shock")
        )

        # 3. Evaluate each candidate mid-line gap
        for gap_s, gap_e in candidate_gaps:
            s_idx = int(gap_s / 1000.0 * sample_rate)
            e_idx = int(gap_e / 1000.0 * sample_rate)
            gap_chunk = samples[s_idx:e_idx]

            if len(gap_chunk) < 60:
                continue

            gap_rms = float(np.sqrt(np.mean(gap_chunk ** 2)))
            gap_db = 20.0 * math.log10(max(gap_rms, 1e-5) / 32768.0)
            rel_delta_db = speech_db - gap_db

            # Emotional / Physical strain protection (Always KEEP)
            if is_mandated_emotional_breath or has_physical_strain or is_suppressed_restraint:
                mid_edits.append(
                    MidLineBreathEdit(
                        start_ms=gap_s,
                        end_ms=gap_e,
                        action="KEEP",
                        attenuation_db=0.0,
                        confidence=0.95,
                        reason="Preserved emotional/physical-strain mid-line breath",
                    )
                )
                continue

            # Pure silence floor (No breath present)
            if gap_db < -52.0:
                mid_edits.append(
                    MidLineBreathEdit(
                        start_ms=gap_s,
                        end_ms=gap_e,
                        action="KEEP",
                        attenuation_db=0.0,
                        confidence=1.0,
                        reason="Natural ambient pause floor",
                    )
                )
                continue

            # Exaggerated TTS Mid-line Inhale on Calm Line
            is_calm_line = bool(
                direction is None
                or (
                    direction.surface_emotion in ("neutral", "calm")
                    and direction.physical_state == "normal"
                )
            )
            if is_calm_line and gap_db > -34.0 and rel_delta_db < self.config.mid_line_breath_relative_loudness_margin_db:
                att_db = self.config.breath_reduce_attenuation_db
                mid_edits.append(
                    MidLineBreathEdit(
                        start_ms=gap_s,
                        end_ms=gap_e,
                        action="REDUCE",
                        attenuation_db=att_db,
                        confidence=0.85,
                        reason=f"Reduced exaggerated mid-line TTS inhale by {att_db:.1f}dB ({gap_db:.1f} dBFS vs speech {speech_db:.1f} dBFS)",
                    )
                )
                continue

            # Default: Keep natural respiration
            mid_edits.append(
                MidLineBreathEdit(
                    start_ms=gap_s,
                    end_ms=gap_e,
                    action="KEEP",
                    attenuation_db=0.0,
                    confidence=0.90,
                    reason="Natural mid-line respiration",
                )
            )

        return mid_edits

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
