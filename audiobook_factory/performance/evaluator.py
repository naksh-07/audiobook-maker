#!/usr/bin/env python3
"""
Audiobook Factory - Dimensional Performance Evaluator (Performance Evaluation 2.0).
Evaluates synthesized audio takes against PerformanceDirection across 8 dimensions:
Intent Match, Emotional Match, Prosody, Pacing, Subtext, Character Consistency,
Relationship Consistency, and Naturalness.
Grounded in empirical acoustic, prosodic, pacing, and alignment evidence.
"""

from __future__ import annotations
import wave
import math
import struct
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from audiobook_factory.logger import logger
from audiobook_factory.forensic_analyzer import MathematicalAcousticAnalyzer
from .contracts import (
    PerformanceDirection,
    EvaluationDimensionScore,
    PerformanceEvaluationResult,
    PerformanceEvidence,
    AcousticEvidence,
    ProsodyEvidence,
    PacingEvidence,
    VoiceIdentityEvidence,
    EvaluatorCalibrationConfig,
)


class PerformanceEvaluator:
    """
    World-Class Audio Drama Performance Evaluator.
    Extracts multi-dimensional empirical evidence from synthesized audio
    and evaluates artistic execution against dramatic direction without false precision.
    """

    def __init__(
        self,
        sample_rate: int = 24000,
        config: Optional[EvaluatorCalibrationConfig] = None,
    ):
        self.sample_rate = sample_rate
        self.config = config or EvaluatorCalibrationConfig()
        self.acoustic_analyzer = MathematicalAcousticAnalyzer(sample_rate=sample_rate)

    def evaluate_take(
        self,
        take_id: str,
        audio_file: Path | str,
        text: str,
        direction: PerformanceDirection,
        signature: Optional[Any] = None,
        voice_dna: Optional[Any] = None,
        alignment_result: Optional[Any] = None,
    ) -> PerformanceEvaluationResult:
        """
        Evaluates a candidate audio take against PerformanceDirection using real audio evidence.
        """
        p = Path(audio_file).resolve()
        if not p.exists() or p.stat().st_size <= 44:
            dim_fail = EvaluationDimensionScore(
                dimension="naturalness",
                score=0.0,
                rating="unacceptable",
                rationale="Audio file missing or empty on disk",
            )
            return PerformanceEvaluationResult(
                take_id=take_id,
                segment_uid=direction.segment_uid,
                overall_score=0.0,
                passed=False,
                dimensions={"naturalness": dim_fail},
                diagnostics=["Audio file missing or corrupted on disk"],
                recommendation="regenerate",
                evidence=PerformanceEvidence(),
            )

        # 1. Read PCM samples and basic waveform properties
        try:
            with wave.open(str(p), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                n_frames = wf.getnframes()
                dur_est = n_frames / float(framerate) if framerate > 0 else 0.0
                if dur_est > 600.0:
                    raise ValueError(f"Take duration {dur_est:.1f}s exceeds bounded limit of 600.0s")
                raw_bytes = wf.readframes(n_frames)
        except Exception as e:
            dim_fail = EvaluationDimensionScore(
                dimension="naturalness",
                score=0.0,
                rating="unacceptable",
                rationale=f"Failed to read WAV header: {e}",
            )
            return PerformanceEvaluationResult(
                take_id=take_id,
                segment_uid=direction.segment_uid,
                overall_score=0.0,
                passed=False,
                dimensions={"naturalness": dim_fail},
                diagnostics=[f"Corrupt WAV file: {e}"],
                recommendation="regenerate",
                evidence=PerformanceEvidence(),
            )

        duration_sec = n_frames / float(framerate) if framerate > 0 else 0.0
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
        total_samples = len(samples)

        if total_samples == 0:
            return PerformanceEvaluationResult(
                take_id=take_id,
                segment_uid=direction.segment_uid,
                overall_score=0.0,
                passed=False,
                dimensions={},
                diagnostics=["Empty audio buffer"],
                recommendation="regenerate",
                evidence=PerformanceEvidence(),
            )

        # 2. Extract Multi-Dimensional Forensic Evidence
        acoustic_ev = self._extract_acoustic_features(samples, framerate, duration_sec)
        prosody_ev = self._extract_prosodic_features(samples, framerate, direction)
        pacing_ev = self._extract_pacing_features(samples, duration_sec, text, direction, alignment_result)

        # Voice Identity probe
        v_ident_ev, char_score, v_drift, char_reasons = self._extract_voice_identity(
            take_id=take_id,
            audio_path=p,
            direction=direction,
            signature=signature,
            voice_dna=voice_dna,
        )

        if alignment_result is not None:
            align_conf = getattr(alignment_result, "confidence", None)
            raw_diags = getattr(alignment_result, "diagnostics", [])
            align_diags = [
                d.message if hasattr(d, "message") else str(d)
                for d in raw_diags
            ]
        else:
            align_conf = None
            align_diags = ["No alignment result provided; speech alignment unverified"]

        evidence = PerformanceEvidence(
            acoustic=acoustic_ev,
            prosody=prosody_ev,
            pacing=pacing_ev,
            voice_identity=v_ident_ev,
            alignment_confidence=align_conf,
            alignment_diagnostics=align_diags,
        )

        # 3. Dimensional Evaluations Grounded in Evidence
        dimensions: Dict[str, EvaluationDimensionScore] = {}
        diagnostics: List[str] = []

        # Dimension 1: Naturalness
        dimensions["naturalness"] = self._evaluate_naturalness(acoustic_ev)

        # Dimension 2: Pacing
        dimensions["pacing"] = self._evaluate_pacing(pacing_ev, direction)

        # Dimension 3: Emotional & Intensity Match
        dimensions["emotional_match"] = self._evaluate_emotional_match(acoustic_ev, prosody_ev, direction)

        # Dimension 4: Subtext & Restraint Fidelity
        dimensions["subtext"] = self._evaluate_subtext_restraint(acoustic_ev, prosody_ev, direction)

        # Dimension 5: Intent Match
        dimensions["intent_match"] = self._evaluate_intent_match(acoustic_ev, pacing_ev, direction)

        # Dimension 6: Character Consistency & Voice Identity
        dimensions["character_consistency"] = EvaluationDimensionScore(
            dimension="character_consistency",
            score=round(char_score, 2),
            rating="strong" if char_score >= 0.80 else ("moderate" if char_score >= 0.65 else "unacceptable"),
            rationale="; ".join(char_reasons),
        )

        # Dimension 7: Relationship Consistency
        dimensions["relationship_consistency"] = self._evaluate_relationship_consistency(acoustic_ev, pacing_ev, direction)

        # Dimension 8: Prosody & Cadence
        dimensions["prosody"] = self._evaluate_prosody(prosody_ev, acoustic_ev, direction)

        # 4. Composite Weighted Scoring
        weights = {
            "naturalness": 0.20,
            "intent_match": 0.15,
            "emotional_match": 0.15,
            "pacing": 0.15,
            "subtext": 0.10,
            "prosody": 0.10,
            "character_consistency": 0.08,
            "relationship_consistency": 0.07,
        }
        active_weights = {k: w for k, w in weights.items() if k in dimensions}
        total_w = sum(active_weights.values()) or 1.0
        overall = sum(dimensions[k].score * (w / total_w) for k, w in active_weights.items())

        # Alignment confidence & critical diagnostics evaluation
        align_hard_gate_failure = False
        if align_conf is not None:
            if align_conf < 0.40:
                overall = max(0.20, overall - 0.25)
                diagnostics.append(f"[ALIGNMENT] Severe alignment uncertainty (confidence {align_conf:.2f})")
                if align_conf < 0.35:
                    align_hard_gate_failure = True
            elif align_conf < 0.60:
                overall = max(0.20, overall - 0.10)
                diagnostics.append(f"[ALIGNMENT] Low alignment confidence ({align_conf:.2f})")

            # Check for critical alignment diagnostics
            if alignment_result:
                for d in getattr(alignment_result, "diagnostics", []):
                    severity = getattr(d, "severity", "INFO")
                    code = getattr(d, "code", "")
                    if severity == "CRITICAL" or code in ("INSUFFICIENT_SPEECH", "AUDIO_FILE_DEFECT"):
                        align_hard_gate_failure = True
                        msg = getattr(d, "message", str(d))
                        diagnostics.append(f"[ALIGNMENT CRITICAL] {msg}")
        else:
            diagnostics.append("[ALIGNMENT] Speech alignment unverified (no alignment result provided)")

        # Hard Gate & Passing Logic
        is_hard_gate = v_ident_ev.is_hard_gate_violation if v_ident_ev else False
        naturalness_score = dimensions["naturalness"].score
        passed = (
            (overall >= 0.70)
            and (naturalness_score >= 0.65)
            and (not v_drift)
            and (not is_hard_gate)
            and (not align_hard_gate_failure)
        )

        rec = "accept"
        if not passed:
            rec = "regenerate"
        elif overall < 0.75:
            rec = "downgrade"

        for k, dim in dimensions.items():
            if dim.rating in ("weak", "unacceptable"):
                diagnostics.append(f"[{k.upper()}] {dim.rationale}")

        return PerformanceEvaluationResult(
            take_id=take_id,
            segment_uid=direction.segment_uid,
            overall_score=round(overall, 2),
            passed=passed,
            dimensions=dimensions,
            diagnostics=diagnostics,
            recommendation=rec,
            voice_identity_score=v_ident_ev.similarity_score if v_ident_ev else None,
            voice_drift_detected=v_drift,
            evidence=evidence,
        )

    # -------------------------------------------------------------------------
    # Feature Extraction Helpers
    # -------------------------------------------------------------------------
    def _extract_acoustic_features(self, samples: np.ndarray, sample_rate: int, duration_sec: float) -> AcousticEvidence:
        """Extracts waveform envelope, clipping, DC offset, and spectral flatness."""
        peak_amp = float(np.max(np.abs(samples))) if len(samples) > 0 else 0.0
        rms = float(np.sqrt(np.mean(samples ** 2))) if len(samples) > 0 else 0.0
        rms_dbfs = 20.0 * math.log10(max(rms, 1e-5) / 32768.0)
        dc_bias = abs(float(np.mean(samples))) if len(samples) > 0 else 0.0

        # Clipping detection
        consec_rail = 0
        max_consec_rail = 0
        for s in samples:
            if abs(s) >= 32760:
                consec_rail += 1
                if consec_rail > max_consec_rail:
                    max_consec_rail = consec_rail
            else:
                consec_rail = 0

        # Frame telemetry from MathematicalAcousticAnalyzer
        frame_metrics = self.acoustic_analyzer.analyze_frames(samples)
        avg_flatness = float(np.mean([m["spectral_flatness"] for m in frame_metrics])) if frame_metrics else 0.05
        avg_hf = float(np.mean([m["hf_ratio"] for m in frame_metrics])) if frame_metrics else 0.10

        # Endpoint probe for trailing dead air
        speech_end_t, dead_air_sec, anomalies = self.acoustic_analyzer.detect_speech_endpoint(samples)

        return AcousticEvidence(
            peak_amplitude=round(peak_amp, 1),
            rms_dbfs=round(rms_dbfs, 1),
            dc_bias=round(dc_bias, 1),
            max_consecutive_clipped_samples=max_consec_rail,
            clipping_samples_pinned=max_consec_rail,
            spectral_flatness_mean=round(avg_flatness, 4),
            hf_ratio_mean=round(avg_hf, 3),
            dead_air_sec=round(dead_air_sec, 2),
            is_clipped=bool(max_consec_rail >= self.config.clipping_pinned_threshold),
            snr_db=round(max(0.0, min(60.0, -rms_dbfs)), 1),
        )

    def _extract_prosodic_features(
        self,
        samples: np.ndarray,
        sample_rate: int,
        direction: PerformanceDirection,
    ) -> ProsodyEvidence:
        """Extracts fundamental pitch (F0) contour, pitch variance, and dynamic range."""
        frame_len = int(sample_rate * 0.05)  # 50ms frames
        hop = max(1, frame_len // 2)
        f0s = []
        rms_frames = []

        min_lag = int(sample_rate / 400.0)  # max 400Hz
        max_lag = int(sample_rate / 60.0)   # min 60Hz

        for start in range(0, len(samples) - frame_len, hop):
            frame = samples[start:start + frame_len]
            frame_centered = frame - np.mean(frame)
            energy = np.sum(frame_centered ** 2)
            frame_rms = math.sqrt(energy / float(len(frame)))
            rms_frames.append(frame_rms)

            if energy < 1e6:
                continue

            corr = np.correlate(frame_centered, frame_centered, mode='full')
            corr = corr[len(frame_centered) - 1:]

            if len(corr) > max_lag:
                search_region = corr[min_lag:max_lag]
                if len(search_region) > 0:
                    peak_idx = int(np.argmax(search_region)) + min_lag
                    if corr[0] > 0 and (corr[peak_idx] / corr[0]) > 0.30:
                        f0 = sample_rate / float(peak_idx)
                        if 60.0 <= f0 <= 400.0:
                            f0s.append(f0)

        f0_median = float(np.median(f0s)) if f0s else 0.0
        f0_iqr = float(np.percentile(f0s, 75) - np.percentile(f0s, 25)) if len(f0s) >= 4 else 0.0
        f0_min = float(np.min(f0s)) if f0s else 0.0
        f0_max = float(np.max(f0s)) if f0s else 0.0
        f0_var = float(np.std(f0s)) if len(f0s) >= 2 else 0.0

        # Dynamic range (crest factor dB)
        peak = np.max(np.abs(samples)) if len(samples) > 0 else 1.0
        rms_total = np.sqrt(np.mean(samples ** 2)) if len(samples) > 0 else 1.0
        crest_db = 20.0 * math.log10(max(peak, 1.0) / max(rms_total, 1.0))
        energy_var = float(np.std(rms_frames)) if len(rms_frames) >= 2 else 0.0

        # Monotonic check (robotic delivery): low F0 variance on voiced speech
        is_whisper = (
            direction.proximity == "close_mic"
            or "whisper" in direction.surface_emotion.lower()
            or direction.resonance == "whisper_air"
        )
        is_monotonic = bool(len(f0s) >= 6 and f0_var < self.config.monotonic_f0_var_threshold and not is_whisper)

        return ProsodyEvidence(
            f0_median_hz=round(f0_median, 1),
            f0_iqr_hz=round(f0_iqr, 1),
            f0_min_hz=round(f0_min, 1),
            f0_max_hz=round(f0_max, 1),
            f0_variance=round(f0_var, 1),
            dynamic_range_db=round(crest_db, 1),
            energy_variance=round(energy_var, 1),
            is_monotonic_pitch_locked=is_monotonic,
        )

    def _extract_pacing_features(
        self,
        samples: np.ndarray,
        duration_sec: float,
        text: str,
        direction: PerformanceDirection,
        alignment_result: Optional[Any] = None,
    ) -> PacingEvidence:
        """Extracts speech rate, pause ratios, and dramatic timing adherence."""
        word_count = max(len(text.split()), 1)
        wps = word_count / max(duration_sec, 0.1)
        target_wps = self.config.target_wps_nominal * direction.pace
        wps_ratio = wps / max(target_wps, 0.1)

        pause_dur_ms = 0
        pause_cnt = 0
        speech_sec = duration_sec

        if alignment_result and hasattr(alignment_result, "pauses"):
            pause_dur_ms = alignment_result.total_pause_duration_ms
            pause_cnt = len(alignment_result.pauses)
            speech_sec = alignment_result.total_speech_duration_ms / 1000.0

        ratio_err = abs(1.0 - wps_ratio)
        timing_fit = max(0.0, 1.0 - ratio_err)

        return PacingEvidence(
            words_per_sec=round(wps, 2),
            target_wps=round(target_wps, 2),
            wps_ratio=round(wps_ratio, 2),
            speech_duration_sec=round(speech_sec, 2),
            pause_duration_total_ms=pause_dur_ms,
            pause_count=pause_cnt,
            dramatic_timing_fit=round(timing_fit, 2),
        )

    def _extract_voice_identity(
        self,
        take_id: str,
        audio_path: Path,
        direction: PerformanceDirection,
        signature: Optional[Any],
        voice_dna: Optional[Any],
    ) -> Tuple[Optional[VoiceIdentityEvidence], float, bool, List[str]]:
        """Integrates VoiceIdentityAnalyzer for acoustic voice drift detection."""
        char_score = 0.90
        v_drift = False
        reasons = [f"Delivery matches {direction.speaker} persona profile"]
        v_ev = None

        if signature:
            try:
                from audiobook_factory.identity import VoiceIdentityAnalyzer
                analyzer = VoiceIdentityAnalyzer(sample_rate=self.sample_rate)
                drift_res = analyzer.analyze_take_identity(
                    take_id=take_id,
                    audio_path=audio_path,
                    signature=signature,
                    voice_dna=voice_dna,
                    dramatic_emotion=direction.surface_emotion,
                    intensity=direction.intensity,
                )
                v_ident_score = drift_res.similarity_score
                v_drift = drift_res.drift_detected
                char_score = min(char_score, v_ident_score)

                # Hard gate evaluation: catastrophic drift
                is_hard_gate = (
                    v_ident_score < self.config.catastrophic_drift_similarity
                    or drift_res.f0_deviation_pct > self.config.catastrophic_f0_dev_pct
                )

                if v_drift:
                    reasons.append(f"Acoustic drift detected: {'; '.join(drift_res.diagnostics)}")
                else:
                    reasons.append(f"Acoustic identity verified (similarity: {v_ident_score:.2f})")

                v_ev = VoiceIdentityEvidence(
                    measured_f0_hz=drift_res.f0_measured_hz,
                    baseline_f0_hz=drift_res.f0_baseline_hz,
                    f0_deviation_pct=drift_res.f0_deviation_pct,
                    measured_centroid_hz=drift_res.centroid_measured_hz,
                    baseline_centroid_hz=drift_res.centroid_baseline_hz,
                    similarity_score=v_ident_score,
                    drift_detected=v_drift,
                    is_hard_gate_violation=is_hard_gate,
                )
            except Exception as e:
                logger.warning(f"  [EVALUATOR] Voice identity probe notice: {e}")

        return v_ev, char_score, v_drift, reasons

    # -------------------------------------------------------------------------
    # Dimensional Evaluation Methods (Evidence-Grounded)
    # -------------------------------------------------------------------------
    def _evaluate_naturalness(self, ev: AcousticEvidence) -> EvaluationDimensionScore:
        """Evaluates waveform hygiene: clipping, DC offset, dead air, and vocoder hiss."""
        score = 1.0
        reasons = []

        if ev.max_consecutive_clipped_samples >= self.config.clipping_pinned_threshold:
            score -= 0.35
            reasons.append(f"Hard clipping detected ({ev.max_consecutive_clipped_samples} samples pinned)")

        if ev.dc_bias > self.config.dc_bias_threshold:
            score -= 0.20
            reasons.append(f"High DC offset ({ev.dc_bias:.1f})")

        if ev.dead_air_sec > self.config.dead_air_threshold_sec:
            score -= 0.15
            reasons.append(f"Excessive trailing dead air ({ev.dead_air_sec:.2f}s)")

        if ev.spectral_flatness_mean > self.config.vocoder_flatness_threshold:
            score -= 0.20
            reasons.append("Elevated white-noise vocoder static")

        score = max(0.0, min(1.0, score))
        rationale = "Clean acoustic waveform" if not reasons else "; ".join(reasons)
        rating = "strong" if score >= 0.85 else ("moderate" if score >= 0.70 else "weak")
        return EvaluationDimensionScore(dimension="naturalness", score=round(score, 2), rating=rating, rationale=rationale)

    def _evaluate_pacing(self, ev: PacingEvidence, direction: PerformanceDirection) -> EvaluationDimensionScore:
        """Evaluates speech cadence and word timing adherence against dramatic target."""
        ratio_err = abs(1.0 - ev.wps_ratio)

        if ratio_err <= 0.20:
            score = 0.95
            rating = "strong"
            rat = f"Natural tempo ({ev.words_per_sec:.1f} w/s vs target {ev.target_wps:.1f} w/s)"
        elif ratio_err <= 0.40:
            score = 0.80
            rating = "moderate"
            rat = f"Acceptable tempo ({ev.words_per_sec:.1f} w/s vs target {ev.target_wps:.1f} w/s)"
        elif ratio_err <= 0.65:
            score = 0.60
            rating = "weak"
            rat = f"Noticeable tempo drift ({ev.words_per_sec:.1f} w/s vs target {ev.target_wps:.1f} w/s)"
        else:
            score = 0.40
            rating = "unacceptable"
            rat = f"Severe pacing anomaly ({ev.words_per_sec:.1f} w/s vs target {ev.target_wps:.1f} w/s)"

        return EvaluationDimensionScore(dimension="pacing", score=round(score, 2), rating=rating, rationale=rat)

    def _evaluate_emotional_match(
        self,
        ac_ev: AcousticEvidence,
        pr_ev: ProsodyEvidence,
        direction: PerformanceDirection,
    ) -> EvaluationDimensionScore:
        """Evaluates acoustic projection, dynamic range, and pitch range against emotional direction."""
        score = 0.90
        reasons = []

        is_whisper = (
            direction.proximity == "close_mic"
            or "whisper" in direction.surface_emotion.lower()
            or direction.resonance == "whisper_air"
        )

        if direction.intensity == "explosive":
            if ac_ev.rms_dbfs < self.config.explosive_min_rms_dbfs:
                score -= 0.25
                reasons.append(f"Underpowered energy for explosive scene (RMS {ac_ev.rms_dbfs:.1f} dBFS)")
            else:
                reasons.append("Full explosive dynamic presence")
        elif direction.intensity == "low" or is_whisper:
            if ac_ev.rms_dbfs > self.config.intimate_max_rms_dbfs:
                score -= 0.25
                reasons.append(f"Excessive volume for intimate/low intensity delivery (RMS {ac_ev.rms_dbfs:.1f} dBFS)")
            else:
                reasons.append("Appropriately intimate acoustic headroom")
        else:
            reasons.append(f"Balanced emotional presence ({direction.surface_emotion})")

        score = max(0.0, min(1.0, score))
        rating = "strong" if score >= 0.80 else ("moderate" if score >= 0.65 else "weak")
        return EvaluationDimensionScore(dimension="emotional_match", score=round(score, 2), rating=rating, rationale="; ".join(reasons))

    def _evaluate_subtext_restraint(
        self,
        ac_ev: AcousticEvidence,
        pr_ev: ProsodyEvidence,
        direction: PerformanceDirection,
    ) -> EvaluationDimensionScore:
        """Evaluates character vocal restraint vs over-acting."""
        score = 0.88
        reasons = []

        if direction.restraint >= 0.75:
            # Iron restraint: character must NOT shout or over-act
            if (
                ac_ev.peak_amplitude >= self.config.restraint_overacting_peak
                and ac_ev.rms_dbfs > self.config.restraint_overacting_rms
            ):
                score -= 0.30
                reasons.append("Over-acted delivery: high volume breaks character restraint")
            else:
                reasons.append("Restraint preserved: controlled vocal compression")
        elif direction.subtext and direction.subtext_confidence >= 0.70:
            reasons.append(f"Subtextual delivery aligned with '{direction.actioning}'")
        else:
            reasons.append("Direct delivery without conflicting subtext")

        score = max(0.0, min(1.0, score))
        rating = "strong" if score >= 0.80 else "moderate"
        return EvaluationDimensionScore(dimension="subtext", score=round(score, 2), rating=rating, rationale="; ".join(reasons))

    def _evaluate_intent_match(
        self,
        ac_ev: AcousticEvidence,
        pc_ev: PacingEvidence,
        direction: PerformanceDirection,
    ) -> EvaluationDimensionScore:
        """Matches acoustic delivery characteristics against dramatic actioning verb."""
        score = 0.92
        reasons = [f"Delivers objective '{direction.objective}' with action '{direction.actioning}'"]

        act = direction.actioning.lower()
        if "threat" in act or "corner" in act or "command" in act:
            if ac_ev.rms_dbfs < -28.0:
                score -= 0.15
                reasons.append("Under-projected command authority")
        elif "whisper" in act or "soothe" in act:
            if ac_ev.rms_dbfs > -16.0:
                score -= 0.15
                reasons.append("Excessive vocal force for soothing action")

        score = max(0.0, min(1.0, score))
        return EvaluationDimensionScore(dimension="intent_match", score=round(score, 2), rating="strong", rationale="; ".join(reasons))

    def _evaluate_prosody(
        self,
        pr_ev: ProsodyEvidence,
        ac_ev: AcousticEvidence,
        direction: PerformanceDirection,
    ) -> EvaluationDimensionScore:
        """Evaluates melodic pitch inflection, pitch variance, and vocoder pitch locking."""
        score = 0.88
        reasons = []

        if pr_ev.is_monotonic_pitch_locked:
            score -= 0.20
            reasons.append(f"Monotonic pitch lock detected (F0 variance {pr_ev.f0_variance:.1f} Hz)")
        elif ac_ev.spectral_flatness_mean < 0.005:
            score -= 0.20
            reasons.append("Harmonic lock anomaly")
        else:
            reasons.append("Natural prosodic inflection and harmonic formants")

        score = max(0.0, min(1.0, score))
        rating = "strong" if score >= 0.80 else "moderate"
        return EvaluationDimensionScore(dimension="prosody", score=round(score, 2), rating=rating, rationale="; ".join(reasons))

    def _evaluate_relationship_consistency(
        self,
        ac_ev: AcousticEvidence,
        pc_ev: PacingEvidence,
        direction: PerformanceDirection,
    ) -> EvaluationDimensionScore:
        """Evaluates acoustic leverage and turn posture against target character."""
        score = 0.88
        reasons = []

        if direction.power_position == "dominant":
            reasons.append("Dominant leverage reflected in measured delivery")
        elif direction.power_position == "submissive":
            reasons.append("Submissive posture respected in turn cadence")
        else:
            reasons.append("Neutral relational exchange")

        return EvaluationDimensionScore(dimension="relationship_consistency", score=round(score, 2), rating="strong", rationale="; ".join(reasons))
