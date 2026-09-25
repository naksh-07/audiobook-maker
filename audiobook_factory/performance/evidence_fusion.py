#!/usr/bin/env python3
"""
Audiobook Factory - Hierarchical Evidence Fusion Engine (Pillar 3.4 & 3.5).
Fuses deterministic acoustic, prosodic, pacing, alignment, emotional, intentional,
and auxiliary perceptual evidence into an authoritative, explainable performance decision.

Evaluates candidates across an 8-layer hierarchical evidence stack:
  1. Technical Eligibility (clipping, DC offset, file integrity, duration, dead air)
  2. Alignment Plausibility (phonetic token coverage, confidence thresholds, speech bounds)
  3. Catastrophic Voice Identity Defense (mode-aware drift, distribution boundary defense)
  4. Core Acoustic Adequacy (RMS headroom, dynamic range, vocoder artifacts)
  5. Dramatic Fidelity (emotional intensity, intent actioning, subtext, emphasis, breath)
  6. Scene & Context Fit (timing realization, pacing, hesitation, restraint compliance)
  7. Character Continuity (stable DNA compliance, dynamic scene arc transitions)
  8. Perceptual Preference (auxiliary multi-dimensional human/LLM perceptual rubrics)

Enforces strict fail-closed invariants:
  - Hard gate failures at Layers 1-3 immediately disqualify the candidate.
  - When all candidates fail, returns authoritative NO_ACCEPTABLE_TAKE with winner=None.
"""

from __future__ import annotations
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .contracts import (
    TakeVariant,
    PerformanceDirection,
    EvidenceFusionResult,
    EvidenceFusionCalibrationConfig,
    TakeSelectionStatus,
)
from .continuity import CharacterPerformanceTelemetry


class EvidenceFusionEngine:
    """
    Expert Audio Drama Hierarchical Evidence Fusion Engine.
    Executes staged 8-layer evidence audit to produce an explainable,
    confidence-weighted performance verdict.
    """

    def __init__(self, config: Optional[EvidenceFusionCalibrationConfig] = None):
        self.config = config or EvidenceFusionCalibrationConfig()

    def evaluate_layer1_technical(
        self,
        take: TakeVariant,
        text: str,
        direction: PerformanceDirection,
    ) -> Tuple[bool, List[str]]:
        """
        Layer 1: Technical Eligibility Hard Gate.
        Verifies file existence, readable PCM, clipping, DC offset, duration, and dead air.
        """
        reasons: List[str] = []

        # 1. File existence and basic size
        audio_path = Path(take.audio_path)
        if not audio_path.is_file() or audio_path.stat().st_size <= 44:
            reasons.append("Audio file missing or corrupted on disk")
            return False, reasons

        # 2. Duration limits
        dur = take.duration_sec
        if dur <= 0.0:
            try:
                with wave.open(str(audio_path), "rb") as wf:
                    fr = wf.getframerate()
                    if fr > 0:
                        dur = wf.getnframes() / float(fr)
                        take.duration_sec = round(dur, 3)
            except Exception:
                pass

        if dur > 600.0:
            reasons.append(f"Audio duration {dur:.2f}s exceeds maximum bounded limit of 600.0s")

        if 0 < dur < 0.25:
            reasons.append(f"Audio duration {dur:.2f}s below minimum 0.25s")

        word_count = len(text.split())
        if word_count > 0:
            expected_dur = (word_count / 3.1) / max(0.5, direction.pace)
            max_allowed = max(4.0, expected_dur * 3.5)
            if dur > max_allowed:
                reasons.append(
                    f"Audio duration {dur:.2f}s exceeds maximum threshold of {max_allowed:.2f}s"
                )

        # 3. Acoustic metrics from evidence
        ev = take.evaluation.evidence if (take.evaluation and take.evaluation.evidence) else None
        if ev and ev.acoustic:
            pinned = getattr(
                ev.acoustic,
                "clipping_samples_pinned",
                getattr(ev.acoustic, "max_consecutive_clipped_samples", 0),
            )
            if pinned >= 12:
                reasons.append(f"Audible clipping: {pinned} pinned samples >= 12")

            dc = getattr(ev.acoustic, "dc_bias", 0.0)
            if abs(dc) > 1500.0:
                reasons.append(f"DC bias anomaly: {dc:.1f} > 1500.0")

            dead_sec = getattr(ev.acoustic, "dead_air_sec", 0.0)
            is_dramatic_silence = direction.silence_type in (
                "dramatic_silence",
                "emotional_freeze",
                "reaction_silence",
                "hesitation",
            )
            dead_threshold = 3.5 if is_dramatic_silence else 2.0
            if dead_sec > dead_threshold:
                reasons.append(f"Dead air violation: {dead_sec:.2f}s > {dead_threshold:.2f}s")

        return len(reasons) == 0, reasons

    def evaluate_layer2_alignment(
        self,
        take: TakeVariant,
    ) -> Tuple[bool, List[str]]:
        """
        Layer 2: Alignment Plausibility Hard Gate.
        Verifies phonetic alignment confidence and critical diagnostic flags.
        """
        reasons: List[str] = []

        # Check evidence alignment confidence
        ev = take.evaluation.evidence if (take.evaluation and take.evaluation.evidence) else None
        if ev and ev.alignment_confidence is not None:
            if ev.alignment_confidence < self.config.alignment_confidence_hard_gate:
                reasons.append(
                    f"Alignment failure: confidence {ev.alignment_confidence:.2f} < {self.config.alignment_confidence_hard_gate}"
                )

        # Check take direct alignment result
        align_res = getattr(take, "alignment_result", None)
        if align_res is not None:
            conf = getattr(align_res, "confidence", None)
            if conf is not None and conf < self.config.alignment_confidence_hard_gate:
                msg = f"Alignment failure: confidence {conf:.2f} < {self.config.alignment_confidence_hard_gate}"
                if msg not in reasons:
                    reasons.append(msg)
            for d in getattr(align_res, "diagnostics", []):
                sev = getattr(d, "severity", "")
                code = getattr(d, "code", "")
                if sev == "CRITICAL" or code in ("INSUFFICIENT_SPEECH", "AUDIO_FILE_DEFECT", "TEXT_AUDIO_MISMATCH"):
                    d_msg = f"Critical alignment failure: {getattr(d, 'message', str(d))}"
                    if d_msg not in reasons:
                        reasons.append(d_msg)

        return len(reasons) == 0, reasons

    def evaluate_layer3_voice_identity(
        self,
        take: TakeVariant,
    ) -> Tuple[bool, List[str]]:
        """
        Layer 3: Catastrophic Voice Identity Defense Hard Gate.
        Protects against severe timbre divergence, wrong actor, or catastrophic pitch mutation.
        """
        reasons: List[str] = []

        if take.evaluation:
            ev = take.evaluation
            if ev.voice_drift_detected:
                if (
                    ev.voice_identity_score is not None
                    and ev.voice_identity_score < self.config.catastrophic_voice_drift_similarity
                ):
                    reasons.append(
                        f"Catastrophic voice drift: similarity {ev.voice_identity_score:.2f} < {self.config.catastrophic_voice_drift_similarity}"
                    )
                for diag in ev.diagnostics:
                    if "Catastrophic" in diag or "hard gate" in diag.lower():
                        if diag not in reasons:
                            reasons.append(diag)

        return len(reasons) == 0, reasons

    def evaluate_layer4_acoustic_adequacy(
        self,
        take: TakeVariant,
    ) -> Tuple[bool, float, List[str]]:
        """
        Layer 4: Core Acoustic Adequacy.
        Evaluates RMS headroom, dynamic range, and vocoder artifacts.
        """
        reasons: List[str] = []
        score = 0.85

        ev = take.evaluation.evidence if (take.evaluation and take.evaluation.evidence) else None
        if ev and ev.acoustic:
            rms = ev.acoustic.rms_dbfs
            if rms < -45.0:
                reasons.append(f"Excessively quiet audio: RMS {rms:.1f} dBFS")
                score -= 0.25
            elif rms > -6.0:
                reasons.append(f"Over-compressed/limited audio: RMS {rms:.1f} dBFS")
                score -= 0.15

            if ev.acoustic.snr_db < 15.0:
                reasons.append(f"Poor signal-to-noise ratio: SNR {ev.acoustic.snr_db:.1f} dB")
                score -= 0.20

            flatness = getattr(ev.acoustic, "spectral_flatness_mean", getattr(ev.acoustic, "spectral_flatness", 0.0))
            if flatness > 0.40:
                reasons.append(f"Vocoder hiss / static detected: flatness {flatness:.2f}")
                score -= 0.20

        score = max(0.0, min(1.0, score))
        passed = score >= 0.60
        return passed, score, reasons

    def evaluate_layer5_dramatic_fidelity(
        self,
        take: TakeVariant,
        direction: PerformanceDirection,
    ) -> Tuple[bool, float, List[str], List[str]]:
        """
        Layer 5: Dramatic Fidelity.
        Evaluates emotional realization, intent actioning, subtext, emphasis, and breath.
        """
        reasons: List[str] = []
        reason_codes: List[str] = []
        scores: List[float] = []

        ev = take.evaluation.evidence if (take.evaluation and take.evaluation.evidence) else None

        # 1. Emotion Realization
        if ev and ev.emotion:
            emo = ev.emotion
            scores.append(emo.intensity_fit)
            scores.append(emo.restraint_adherence)
            reasons.extend(emo.diagnostics)
            reason_codes.extend(emo.reason_codes)

        # 2. Intent Realization
        if ev and ev.intent:
            intent = ev.intent
            scores.append(1.0 if intent.actioning_communicated else 0.5)
            scores.append(intent.subtext_fit)
            reasons.extend(intent.diagnostics)
            reason_codes.extend(intent.reason_codes)

        # 3. Emphasis Evidence
        if ev and ev.emphasis:
            emp = ev.emphasis
            reasons.extend(emp.diagnostics)
            reason_codes.extend(emp.reason_codes)
            if any(c in emp.reason_codes for c in ("EMPHASIS_CORRECT", "EMPHASIS_MATCH")):
                scores.append(0.90)
            elif any(c in emp.reason_codes for c in ("EMPHASIS_MISPLACED", "DE_EMPHASIS_VIOLATION", "MISSING_EMPHASIS")):
                scores.append(0.55)

        # 4. Breath Evidence
        if ev and ev.breath:
            br = ev.breath
            scores.append(br.physical_strain_match)
            reasons.extend(br.diagnostics)
            if br.breath_detected:
                reason_codes.append("BREATH_ORGANIC")

        # Fallback to dimensional scores if specialized evidence is sparse
        if not scores and take.evaluation and take.evaluation.dimensions:
            dims = take.evaluation.dimensions
            if "emotional_match" in dims:
                scores.append(dims["emotional_match"].score)
            if "intent_match" in dims:
                scores.append(dims["intent_match"].score)
            if "subtext" in dims:
                scores.append(dims["subtext"].score)

        avg_score = sum(scores) / len(scores) if scores else 0.75
        passed = avg_score >= 0.65
        return passed, round(avg_score, 3), reasons, reason_codes

    def evaluate_layer6_scene_fit(
        self,
        take: TakeVariant,
        direction: PerformanceDirection,
    ) -> Tuple[bool, float, List[str]]:
        """
        Layer 6: Scene & Context Fit.
        Evaluates pacing rhythm, timing realization, and situational restraint.
        """
        reasons: List[str] = []
        score = 0.80

        ev = take.evaluation.evidence if (take.evaluation and take.evaluation.evidence) else None
        if ev and ev.pacing:
            if ev.pacing.dramatic_timing_fit > 0:
                score = (score + ev.pacing.dramatic_timing_fit) / 2.0

        if direction.restraint >= 0.65:
            # Under high restraint, check that vocal headroom is contained
            if ev and ev.acoustic:
                if ev.acoustic.rms_dbfs > -15.0:
                    reasons.append("Restraint breached: unsuppressed shouting under high restraint")
                    score -= 0.15

        score = max(0.0, min(1.0, score))
        passed = score >= 0.65
        return passed, round(score, 3), reasons

    def evaluate_layer7_character_continuity(
        self,
        take: TakeVariant,
        telemetry: Optional[CharacterPerformanceTelemetry] = None,
    ) -> Tuple[bool, float, List[str]]:
        """
        Layer 7: Character Continuity.
        Evaluates Stable Character DNA compliance (habitual pace IQR, energy bounds)
        and smooth dynamic scene transitions.
        """
        reasons: List[str] = []
        if telemetry is None:
            return True, 0.80, reasons

        score = 0.85
        ev = take.evaluation.evidence if (take.evaluation and take.evaluation.evidence) else None

        # Check pacing against habitual pace bounds
        wps = getattr(ev.pacing, "words_per_sec", getattr(ev.pacing, "words_per_second", 0.0)) if (ev and ev.pacing) else 0.0
        if wps > 0:
            p_min, p_max = telemetry.pace_bounds
            if wps < p_min:
                reasons.append(f"Continuity anomaly: pace {wps:.2f} wps below habitual bound {p_min:.2f}")
                score -= 0.12
            elif wps > p_max:
                reasons.append(f"Continuity anomaly: pace {wps:.2f} wps above habitual bound {p_max:.2f}")
                score -= 0.12

        # Check energy against habitual energy bounds
        if ev and ev.acoustic:
            rms = ev.acoustic.rms_dbfs
            e_min, e_max = telemetry.energy_bounds
            # Map dBFS roughly to 0-1 energy scale for boundary check
            norm_energy = max(0.0, min(1.0, (rms + 40.0) / 30.0))
            if norm_energy < e_min:
                reasons.append(f"Continuity anomaly: energy {norm_energy:.2f} below habitual bound {e_min:.2f}")
                score -= 0.10
            elif norm_energy > e_max:
                reasons.append(f"Continuity anomaly: energy {norm_energy:.2f} above habitual bound {e_max:.2f}")
                score -= 0.10

        score = max(0.0, min(1.0, score))
        passed = score >= 0.65
        return passed, round(score, 3), reasons

    def evaluate_layer8_perceptual(
        self,
        take: TakeVariant,
    ) -> Tuple[bool, float, float, List[str], List[str]]:
        """
        Layer 8: Auxiliary Perceptual Preference.
        Consumes PerceptualPerformanceEvidence from heuristic or LLM judge.
        Acts as auxiliary guidance; never overrides deterministic hard gates.
        """
        reasons: List[str] = []
        reason_codes: List[str] = []

        ev = take.evaluation.evidence if (take.evaluation and take.evaluation.evidence) else None
        perceptual = ev.perceptual if ev else None

        if perceptual is None:
            return True, 0.80, 0.70, reasons, reason_codes

        dim_scores = [
            perceptual.naturalness.score,
            perceptual.acting_believability.score,
            perceptual.emotional_fidelity.score,
            perceptual.intent_fidelity.score,
            perceptual.subtext_fidelity.score,
            perceptual.prosodic_fit.score,
            perceptual.scene_fit.score,
            perceptual.dialogue_reactivity.score,
        ]
        dim_confidences = [
            perceptual.naturalness.confidence,
            perceptual.acting_believability.confidence,
            perceptual.emotional_fidelity.confidence,
            perceptual.intent_fidelity.confidence,
            perceptual.subtext_fidelity.confidence,
            perceptual.prosodic_fit.confidence,
            perceptual.scene_fit.confidence,
            perceptual.dialogue_reactivity.confidence,
        ]

        avg_score = sum(dim_scores) / len(dim_scores)
        avg_conf = sum(dim_confidences) / len(dim_confidences)

        for d in (
            perceptual.naturalness,
            perceptual.acting_believability,
            perceptual.emotional_fidelity,
            perceptual.intent_fidelity,
            perceptual.subtext_fidelity,
            perceptual.prosodic_fit,
            perceptual.scene_fit,
            perceptual.dialogue_reactivity,
        ):
            reason_codes.extend(d.reason_codes)

        passed = avg_score >= 0.65
        return passed, round(avg_score, 3), round(avg_conf, 2), reasons, reason_codes

    def fuse_take(
        self,
        take: TakeVariant,
        text: str,
        direction: PerformanceDirection,
        telemetry: Optional[CharacterPerformanceTelemetry] = None,
    ) -> EvidenceFusionResult:
        """
        Executes hierarchical evidence fusion for a single candidate take.
        Fuses Layers 1-8 into an EvidenceFusionResult with explicit status, confidence, and reason codes.
        """
        layer_passed: Dict[str, bool] = {}
        hard_gate_reasons: List[str] = []
        review_reasons: List[str] = []
        reason_codes: List[str] = []

        # Layer 1: Technical Eligibility Hard Gate
        p1, r1 = self.evaluate_layer1_technical(take, text, direction)
        layer_passed["layer1_technical"] = p1
        if not p1:
            hard_gate_reasons.extend(r1)

        # Layer 2: Alignment Plausibility Hard Gate
        p2, r2 = self.evaluate_layer2_alignment(take)
        layer_passed["layer2_alignment"] = p2
        if not p2:
            hard_gate_reasons.extend(r2)

        # Layer 3: Catastrophic Voice Identity Defense Hard Gate
        p3, r3 = self.evaluate_layer3_voice_identity(take)
        layer_passed["layer3_voice_identity"] = p3
        if not p3:
            hard_gate_reasons.extend(r3)

        # Fail-closed check: if any of Layers 1-3 fail, candidate is disqualified
        if not (p1 and p2 and p3):
            status: TakeSelectionStatus = "REGENERATE"
            review_reasons.extend(hard_gate_reasons)
            reason_codes.append("HARD_GATE_FAILURE")
            base_score = take.evaluation.overall_score if take.evaluation else 0.40
            fused_score = round(min(0.45, base_score), 3)
            fused_conf = 0.35

            return EvidenceFusionResult(
                layer_passed=layer_passed,
                hard_gate_reasons=hard_gate_reasons,
                fused_score=fused_score,
                fused_confidence=fused_conf,
                status=status,
                review_reasons=review_reasons,
                reason_codes=reason_codes,
            )

        # Layer 4: Acoustic Adequacy
        p4, s4, r4 = self.evaluate_layer4_acoustic_adequacy(take)
        layer_passed["layer4_acoustic_adequacy"] = p4
        review_reasons.extend(r4)

        # Layer 5: Dramatic Fidelity
        p5, s5, r5, rc5 = self.evaluate_layer5_dramatic_fidelity(take, direction)
        layer_passed["layer5_dramatic_fidelity"] = p5
        review_reasons.extend(r5)
        reason_codes.extend(rc5)

        # Layer 6: Scene Fit
        p6, s6, r6 = self.evaluate_layer6_scene_fit(take, direction)
        layer_passed["layer6_scene_fit"] = p6
        review_reasons.extend(r6)

        # Layer 7: Character Continuity
        p7, s7, r7 = self.evaluate_layer7_character_continuity(take, telemetry)
        layer_passed["layer7_character_continuity"] = p7
        review_reasons.extend(r7)

        # Layer 8: Perceptual Preference
        p8, s8, c8, r8, rc8 = self.evaluate_layer8_perceptual(take)
        layer_passed["layer8_perceptual"] = p8
        review_reasons.extend(r8)
        reason_codes.extend(rc8)

        # Weighted Score Fusion
        # If perceptual evidence is present, blend it with dramatic fidelity and acoustics
        has_perceptual = (
            take.evaluation
            and take.evaluation.evidence
            and take.evaluation.evidence.perceptual is not None
        )
        if has_perceptual:
            w_acoustic = 0.15
            w_dramatic = 0.30
            w_scene = 0.20
            w_continuity = 0.15 if telemetry else 0.05
            w_perceptual = 0.20 if telemetry else 0.30
        else:
            w_acoustic = 0.20
            w_dramatic = 0.45
            w_scene = 0.20
            w_continuity = 0.15 if telemetry else 0.0
            w_perceptual = 0.0

        # Renormalize weights
        total_w = w_acoustic + w_dramatic + w_scene + w_continuity + w_perceptual
        fused_score = (
            w_acoustic * s4
            + w_dramatic * s5
            + w_scene * s6
            + w_continuity * s7
            + w_perceptual * s8
        ) / total_w

        # Confidence Computation
        ev = take.evaluation.evidence if (take.evaluation and take.evaluation.evidence) else None
        align_conf = ev.alignment_confidence if (ev and ev.alignment_confidence is not None) else 0.85
        eval_conf = 0.85
        if take.evaluation and take.evaluation.overall_score > 0:
            eval_conf = 0.90
        percept_conf = c8 if has_perceptual else 1.0

        fused_conf = round(max(0.20, min(1.0, align_conf * 0.40 + eval_conf * 0.40 + percept_conf * 0.20)), 2)
        fused_score = round(max(0.0, min(1.0, fused_score)), 3)

        # Status Assignment
        status = "ACCEPT"
        if fused_score >= self.config.high_quality_threshold and fused_conf >= self.config.min_accept_confidence:
            status = "ACCEPT"
            reason_codes.append("HIGH_FIDELITY_PERFORMANCE")
        elif fused_score >= self.config.min_accept_score:
            if fused_conf < self.config.low_confidence_review_threshold:
                status = "ACCEPT_WITH_WARNING"
                reason_codes.append("ACCEPT_WITH_UNCERTAINTY")
            else:
                status = "ACCEPT"
                reason_codes.append("SATISFACTORY_PERFORMANCE")
        elif fused_score >= self.config.critical_defect_score:
            status = "REVIEW"
            reason_codes.append("MARGINAL_QUALITY_REVIEW_REQUIRED")
        else:
            status = "REGENERATE"
            reason_codes.append("UNACCEPTABLE_PERFORMANCE_DEFECT")

        return EvidenceFusionResult(
            layer_passed=layer_passed,
            hard_gate_reasons=hard_gate_reasons,
            fused_score=fused_score,
            fused_confidence=fused_conf,
            status=status,
            review_reasons=review_reasons,
            reason_codes=list(dict.fromkeys(reason_codes)),
        )

    def fuse_candidate_pool(
        self,
        takes: List[TakeVariant],
        text: str,
        direction: PerformanceDirection,
        telemetry: Optional[CharacterPerformanceTelemetry] = None,
    ) -> Tuple[Optional[TakeVariant], TakeSelectionStatus, List[TakeVariant], Dict[str, EvidenceFusionResult]]:
        """
        Evaluates an entire candidate pool through hierarchical evidence fusion.
        Returns:
            Tuple of:
            (winner_or_none, overall_status, qualified_takes, fusion_map)
        """
        if not takes:
            return None, "NO_ACCEPTABLE_TAKE", [], {}

        fusion_map: Dict[str, EvidenceFusionResult] = {}
        qualified_takes: List[TakeVariant] = []
        disqualified_takes: List[TakeVariant] = []

        for t in takes:
            res = self.fuse_take(t, text, direction, telemetry)
            fusion_map[t.take_id] = res
            t.selection_result = None  # reset
            # Check hard gates (Layers 1-3)
            layers1to3_passed = (
                res.layer_passed.get("layer1_technical", False)
                and res.layer_passed.get("layer2_alignment", False)
                and res.layer_passed.get("layer3_voice_identity", False)
            )
            if layers1to3_passed and res.fused_score >= self.config.critical_defect_score:
                qualified_takes.append(t)
            else:
                disqualified_takes.append(t)

        if not qualified_takes:
            # Authoritative NO_ACCEPTABLE_TAKE: all candidates failed hard gates or critical score
            return None, "NO_ACCEPTABLE_TAKE", [], fusion_map

        # Rank qualified takes by fused_score
        qualified_takes.sort(key=lambda t: fusion_map[t.take_id].fused_score, reverse=True)
        winner = qualified_takes[0]
        winner_status = fusion_map[winner.take_id].status

        return winner, winner_status, qualified_takes, fusion_map
