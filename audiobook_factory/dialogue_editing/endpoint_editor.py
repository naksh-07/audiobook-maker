#!/usr/bin/env python3
"""
Audiobook Factory - Intelligent Endpoint Editor (DE-02).
Distinguishes hard technical boundaries (artifacts, digital dead air) from
natural performance boundaries (inhales, exhales, emotional resonance tails, whispered releases).
Operates deterministically without destructive silence-stripping.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

from audiobook_factory.forensic_analyzer import MathematicalAcousticAnalyzer
from audiobook_factory.alignment_contracts import AlignmentResult
from audiobook_factory.performance.contracts import PerformanceDirection, PerformanceEvidence
from .contracts import EndpointClassification, DialogueEditorialConfig


class EndpointEditor:
    """
    Intelligent Waveform Endpoint Editor.
    Analyzes segment boundaries using alignment, acoustic telemetry, and dramatic intent.
    Preserves organic performance elements while removing synthetic or dead artifacts.
    """

    def __init__(
        self,
        config: Optional[DialogueEditorialConfig] = None,
        analyzer: Optional[MathematicalAcousticAnalyzer] = None,
        sample_rate: int = 24000,
    ):
        self.config = config or DialogueEditorialConfig()
        self.sample_rate = sample_rate
        self.analyzer = analyzer or MathematicalAcousticAnalyzer(sample_rate=sample_rate)

    def analyze_endpoints(
        self,
        samples: np.ndarray,
        sample_rate: int,
        alignment: Optional[AlignmentResult] = None,
        direction: Optional[PerformanceDirection] = None,
        evidence: Optional[PerformanceEvidence] = None,
    ) -> Dict[str, Any]:
        """
        Deterministically evaluates head and tail boundaries for a dialogue segment.

        Returns:
            Dict containing:
                - speech_start_ms: int
                - speech_end_ms: int
                - head_trim_ms: int
                - tail_trim_ms: int
                - head_classification: EndpointClassification
                - tail_classification: EndpointClassification
                - crossfade_in_ms: float
                - crossfade_out_ms: float
                - decision_reasons: List[str]
        """
        total_samples = len(samples)
        total_dur_ms = int(total_samples / sample_rate * 1000.0) if sample_rate > 0 else 0

        if total_dur_ms <= 100:
            return {
                "speech_start_ms": 0,
                "speech_end_ms": total_dur_ms,
                "head_trim_ms": 0,
                "tail_trim_ms": 0,
                "head_classification": "TECHNICAL_BOUNDARY",
                "tail_classification": "TECHNICAL_BOUNDARY",
                "crossfade_in_ms": self.config.default_declick_fade_ms,
                "crossfade_out_ms": self.config.default_declick_fade_ms,
                "decision_reasons": ["Very short segment (<100ms); bypassed endpoint trimming"],
            }

        # ---------------------------------------------------------------------
        # 1. Resolve Reference Speech Boundaries
        # ---------------------------------------------------------------------
        ref_start_ms, ref_end_ms = self._resolve_speech_bounds(samples, sample_rate, alignment)
        reasons: List[str] = []

        # ---------------------------------------------------------------------
        # 2. Head Boundary Analysis
        # ---------------------------------------------------------------------
        head_trim_ms, head_cls, fade_in_ms, head_reasons = self._analyze_head(
            samples=samples,
            sample_rate=sample_rate,
            speech_start_ms=ref_start_ms,
            total_dur_ms=total_dur_ms,
            direction=direction,
            evidence=evidence,
        )
        reasons.extend(head_reasons)

        # ---------------------------------------------------------------------
        # 3. Tail Boundary Analysis
        # ---------------------------------------------------------------------
        tail_trim_ms, tail_cls, fade_out_ms, tail_reasons = self._analyze_tail(
            samples=samples,
            sample_rate=sample_rate,
            speech_end_ms=ref_end_ms,
            total_dur_ms=total_dur_ms,
            direction=direction,
            evidence=evidence,
        )
        reasons.extend(tail_reasons)

        # ---------------------------------------------------------------------
        # 4. Safeguard: Bound total trim to preserve core speech
        # ---------------------------------------------------------------------
        head_trim_ms = min(head_trim_ms, self.config.max_endpoint_trim_ms)
        tail_trim_ms = min(tail_trim_ms, self.config.max_endpoint_trim_ms)

        # Guarantee at least 60ms of speech remains
        if head_trim_ms + tail_trim_ms >= total_dur_ms - 60:
            reasons.append("Safety guard engaged: Trims exceeded safety margin; clamped to safe boundaries")
            head_trim_ms = 0
            tail_trim_ms = 0

        # Adjust trim points to nearest zero-crossings
        head_trim_ms = self._snap_trim_to_zero_crossing(samples, sample_rate, head_trim_ms, is_head=True)
        tail_trim_ms = self._snap_trim_to_zero_crossing(samples, sample_rate, tail_trim_ms, is_head=False)

        return {
            "speech_start_ms": ref_start_ms,
            "speech_end_ms": ref_end_ms,
            "head_trim_ms": head_trim_ms,
            "tail_trim_ms": tail_trim_ms,
            "head_classification": head_cls,
            "tail_classification": tail_cls,
            "crossfade_in_ms": fade_in_ms,
            "crossfade_out_ms": fade_out_ms,
            "decision_reasons": reasons,
        }

    def _resolve_speech_bounds(
        self,
        samples: np.ndarray,
        sample_rate: int,
        alignment: Optional[AlignmentResult],
    ) -> Tuple[int, int]:
        """Resolves authoritative or acoustic onset and offset in milliseconds."""
        total_dur_ms = int(len(samples) / sample_rate * 1000.0)

        # 1. Alignment contract has highest precision
        if alignment and alignment.words:
            first_w_start = min(w.start_ms for w in alignment.words)
            last_w_end = max(w.end_ms for w in alignment.words)
            return max(0, first_w_start), min(total_dur_ms, last_w_end)

        # 2. Check for silence valleys and isolated trailing bursts
        flen = int(sample_rate * 0.01)  # 10ms frame
        if len(samples) < flen:
            return 0, total_dur_ms

        rms_arr = []
        times = []
        for i in range(0, len(samples) - flen, flen):
            w = samples[i:i + flen]
            rms = np.sqrt(np.mean(w ** 2))
            rms_db = 20.0 * math.log10(max(rms, 1e-5) / 32768.0)
            rms_arr.append(rms_db)
            times.append(i / sample_rate)

        # Dynamic speech floor: allows whispered dialogue down to -52 dBFS while holding baseline -45 dBFS
        speech_dbs = [db for db in rms_arr if db > -48.0]
        mean_speech_db = float(np.mean(speech_dbs)) if speech_dbs else -30.0
        speech_floor_db = max(-52.0, min(-42.0, mean_speech_db - 12.0))

        # Forward scan for speech onset (> -45 dBFS or dynamic floor)
        speech_start_ms = 0
        for idx, db in enumerate(rms_arr):
            if db >= speech_floor_db:
                speech_start_ms = max(0, int(times[idx] * 1000.0))
                break

        # Find continuous silence valleys (RMS < -48 dBFS for >= 100ms)
        valleys = []
        in_v = False
        v_start = 0
        for idx, db in enumerate(rms_arr):
            if db < -48.0 and not in_v:
                in_v = True
                v_start = idx
            elif db >= -48.0 and in_v:
                in_v = False
                v_dur = times[idx] - times[v_start]
                if v_dur >= 0.10:
                    valleys.append((times[v_start], times[idx], v_dur))

        # If a late valley exists and the audio after it is an isolated short burst (<0.35s)
        is_synthetic_burst = False
        if valleys and (times[-1] - valleys[-1][1]) < 0.35 and valleys[-1][0] > 0.2:
            valley_dur = valleys[-1][2]
            # Plosive stop closures are 40-90ms. If silence valley >= 100ms, it is a disconnected late burst.
            is_synthetic_burst = (valley_dur >= 0.10)
            # If alignment is present and the final word's timestamp reaches into/past the valley, trust alignment
            if alignment and getattr(alignment, "words", None):
                last_word = alignment.words[-1]
                if last_word.end_ms > int(valleys[-1][0] * 1000.0):
                    is_synthetic_burst = False

        if is_synthetic_burst:
            speech_end_ms = int(valleys[-1][0] * 1000.0)
        else:
            # Backward scan looking for speech energy drop below speech_floor_db
            speech_end_ms = total_dur_ms
            for idx in range(len(rms_arr) - 1, -1, -1):
                if rms_arr[idx] >= speech_floor_db:
                    speech_end_ms = min(total_dur_ms, int((times[idx] + 0.05) * 1000.0))
                    break

        if speech_end_ms <= speech_start_ms:
            speech_end_ms = total_dur_ms

        return speech_start_ms, speech_end_ms

    def _analyze_head(
        self,
        samples: np.ndarray,
        sample_rate: int,
        speech_start_ms: int,
        total_dur_ms: int,
        direction: Optional[PerformanceDirection],
        evidence: Optional[PerformanceEvidence],
    ) -> Tuple[int, EndpointClassification, float, List[str]]:
        """Evaluates leading silence, inhalations, and technical artifacts."""
        reasons: List[str] = []
        fade_in_ms = self.config.default_declick_fade_ms  # 5ms technical baseline

        if speech_start_ms <= self.config.head_speech_safety_buffer_ms:
            # Clean immediate speech onset
            return 0, "NATURAL_SPEECH", fade_in_ms, ["Head has immediate natural speech onset"]

        pre_dur_ms = speech_start_ms

        # Check for natural respiratory intake
        has_directed_pre_breath = bool(direction and direction.pre_roll_breath_ms > 0)
        has_detected_pre_breath = bool(evidence and evidence.breath and evidence.breath.pre_roll_breath_detected)
        is_strained_or_emotional = bool(
            direction and (
                direction.physical_state in ("combat_strain", "exhausted", "wounded")
                or direction.surface_emotion in ("fear", "panic", "grief", "shock", "intimacy")
                or direction.breath_behavior in ("labored", "sharp_intake", "exhausted", "trembling")
            )
        )

        if has_directed_pre_breath or has_detected_pre_breath or is_strained_or_emotional:
            # Preserving natural breath intake before speech
            reasons.append("Preserved natural pre-speech breath intake")
            return 0, "NATURAL_BREATH", fade_in_ms, reasons

        # Inspect pre-speech acoustic energy
        pre_samples = samples[:int(speech_start_ms / 1000.0 * sample_rate)]
        if len(pre_samples) > 0:
            pre_rms = float(np.sqrt(np.mean(pre_samples ** 2)))
            pre_db = 20.0 * math.log10(max(pre_rms, 1e-5) / 32768.0)
        else:
            pre_db = -90.0

        # Unwanted dead air (low acoustic energy running longer than head threshold)
        if pre_dur_ms > self.config.max_unwanted_silence_head_ms and pre_db <= -48.0:
            # Trim excess leading silence, retaining a comfortable safety buffer
            trim_ms = max(0, pre_dur_ms - self.config.head_speech_safety_buffer_ms)
            reasons.append(f"Trimmed {trim_ms}ms of unwanted leading dead air ({pre_db:.1f} dBFS)")
            return trim_ms, "UNWANTED_SILENCE", fade_in_ms, reasons

        # Audio artifact check (elevated energy in pre-speech region without breath justification)
        if pre_dur_ms > 60 and pre_db > -35.0:
            trim_ms = max(0, pre_dur_ms - self.config.head_speech_safety_buffer_ms)
            reasons.append(f"Trimmed leading acoustic artifact ({pre_db:.1f} dBFS)")
            return trim_ms, "AUDIO_ARTIFACT", fade_in_ms, reasons

        return 0, "NATURAL_SPEECH", fade_in_ms, ["Leading boundary within normal natural limits"]

    def _analyze_tail(
        self,
        samples: np.ndarray,
        sample_rate: int,
        speech_end_ms: int,
        total_dur_ms: int,
        direction: Optional[PerformanceDirection],
        evidence: Optional[PerformanceEvidence],
    ) -> Tuple[int, EndpointClassification, float, List[str]]:
        """Evaluates trailing dead air, vocoder bursts, and emotional releases."""
        reasons: List[str] = []
        fade_out_ms = self.config.default_declick_fade_ms  # 5ms technical baseline
        post_dur_ms = total_dur_ms - speech_end_ms

        if post_dur_ms <= self.config.tail_speech_safety_buffer_ms:
            return 0, "NATURAL_SPEECH", fade_out_ms, ["Tail speech boundary within natural margin"]

        # Check for emotional release / post-roll breath
        has_directed_post_breath = bool(direction and direction.post_roll_breath_ms > 0)
        has_detected_post_breath = bool(evidence and evidence.breath and evidence.breath.post_roll_breath_detected)
        is_emotional_release = bool(
            direction and (
                direction.silence_type in ("emotional_freeze", "dramatic_silence")
                or getattr(direction, "silence_intent", None) in ("grief", "emotional_absorption", "realization")
                or direction.character_state in ("grief", "exhausted", "wounded")
                or direction.surface_emotion in ("grief", "despair", "shock")
            )
        )

        if has_directed_post_breath or has_detected_post_breath or is_emotional_release:
            # Preserving emotional release / trailing breath with organic gentle fade (50ms)
            fade_out_ms = max(self.config.editorial_transition_fade_ms, 50.0)
            reasons.append("Preserved emotional vocal release / trailing exhale")
            # If excessive dead air sits beyond the emotional release (e.g. > 800ms), trim only beyond 600ms
            if post_dur_ms > 800:
                excess_trim_ms = post_dur_ms - 600
                reasons.append(f"Trimmed {excess_trim_ms}ms of dead air beyond emotional release window")
                return excess_trim_ms, "EMOTIONAL_TAIL", fade_out_ms, reasons
            return 0, "EMOTIONAL_TAIL", fade_out_ms, reasons

        # Forensic anomaly check (Layer 1 detect_speech_endpoint + local late burst detection)
        post_samples = samples[int(speech_end_ms / 1000.0 * sample_rate):]
        has_burst = False
        if len(post_samples) > int(0.12 * sample_rate):
            late_chunk = post_samples[-int(0.1 * sample_rate):]
            valley_chunk = post_samples[:int(0.1 * sample_rate)]
            late_peak = float(np.max(np.abs(late_chunk))) if len(late_chunk) > 0 else 0.0
            valley_rms = float(np.sqrt(np.mean(valley_chunk ** 2))) if len(valley_chunk) > 0 else 0.0
            valley_db = 20.0 * math.log10(max(valley_rms, 1e-5) / 32768.0)
            if late_peak > 15000.0 and valley_db < -42.0:
                has_burst = True


        _, dead_air_sec, anomalies = self.analyzer.detect_speech_endpoint(samples)
        has_burst_anomaly = has_burst or any("BURST" in a.get("type", "") for a in anomalies)
        if has_burst_anomaly:
            trim_ms = max(0, post_dur_ms - self.config.tail_speech_safety_buffer_ms)
            reasons.append("Surgically removed trailing vocoder/C2PA acoustic burst anomaly")
            return trim_ms, "AUDIO_ARTIFACT", fade_out_ms, reasons

        # Unwanted trailing dead air (vocoder silence carrier)
        if post_dur_ms > self.config.max_unwanted_silence_tail_ms:
            post_samples = samples[int(speech_end_ms / 1000.0 * sample_rate):]
            post_rms = float(np.sqrt(np.mean(post_samples ** 2))) if len(post_samples) > 0 else 0.0
            post_db = 20.0 * math.log10(max(post_rms, 1e-5) / 32768.0)
            if post_db <= -45.0:
                trim_ms = max(0, post_dur_ms - self.config.tail_speech_safety_buffer_ms)
                reasons.append(f"Trimmed {trim_ms}ms of trailing dead air ({post_db:.1f} dBFS)")
                return trim_ms, "UNWANTED_SILENCE", fade_out_ms, reasons

        return 0, "NATURAL_SPEECH", fade_out_ms, ["Trailing duration within natural acoustic decay"]

    def _snap_trim_to_zero_crossing(
        self,
        samples: np.ndarray,
        sample_rate: int,
        trim_ms: float,
        is_head: bool,
    ) -> float:
        """Surgically snaps the trim point to the nearest zero-crossing sample with sub-millisecond precision."""
        if trim_ms <= 0:
            return 0.0

        target_idx = int(round(trim_ms / 1000.0 * sample_rate)) if is_head else len(samples) - int(round(trim_ms / 1000.0 * sample_rate))
        target_idx = max(0, min(len(samples) - 1, target_idx))

        # Search window: ±3ms
        win = int(sample_rate * 0.003)
        start_search = max(0, target_idx - win)
        end_search = min(len(samples) - 1, target_idx + win)

        best_idx = target_idx
        min_dist = float("inf")

        for idx in range(start_search, end_search):
            if samples[idx] * samples[idx + 1] <= 0.0:
                dist = abs(idx - target_idx)
                if dist < min_dist:
                    min_dist = dist
                    best_idx = idx

        if min_dist == float("inf"):
            min_abs = abs(samples[target_idx])
            for idx in range(start_search, end_search):
                if abs(samples[idx]) < min_abs:
                    min_abs = abs(samples[idx])
                    best_idx = idx

        if is_head:
            return max(0.0, float(best_idx / sample_rate * 1000.0))
        else:
            return max(0.0, float((len(samples) - best_idx) / sample_rate * 1000.0))

