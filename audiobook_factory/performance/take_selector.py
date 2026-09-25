#!/usr/bin/env python3
"""
Audiobook Factory - Intelligent Take Selector & Scene Director (Pillar 3.4 & 3.5).
Performs staged, explainable multi-dimensional comparison of candidate takes
to select the best dramatic performance rather than blindly choosing the loudest.
Features:
- Stage 1-3 Hard Gates: Technical audio integrity, alignment plausibility, catastrophic voice drift defense
- Stage 4 Contextual Dimensional Scoring: Mode-specific dynamic weight allocation
- Stage 5 Pairwise Take Judging: Acoustic evidence deliberation for close margins and climactic beats
- Stage 6 First-Class Result: TakeSelectionResult with reason codes, runner-up provenance, and review flags
- Scene-Level Take Selection: Dramatic arc tracking (energy, pace, tension) and conversational chemistry
"""

from __future__ import annotations
import os
import wave
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from audiobook_factory.logger import logger
from .contracts import (
    TakeVariant,
    PerformanceDirection,
    PerformanceEvaluationResult,
    TakeSelectionResult,
    TakeSelectorCalibrationConfig,
    EvaluationDimensionScore,
)
from .evaluator import PerformanceEvaluator
from .chemistry import ConversationalChemistry
from .continuity import PerformanceContinuityTracker


class PairwiseTakeJudge:
    """
    Expert Audio Drama Take Judge.
    Performs forensic pairwise comparison when candidates are closely matched
    or at climactic scene moments, breaking ties using acoustic & dramatic evidence.
    """

    @classmethod
    def deliberate(
        cls,
        cand_a: TakeVariant,
        score_a: float,
        cand_b: TakeVariant,
        score_b: float,
        direction: PerformanceDirection,
        text: str,
        config: TakeSelectorCalibrationConfig,
        chemistry_scores: Optional[Dict[str, float]] = None,
    ) -> Tuple[TakeVariant, TakeVariant, float, float, List[str], str]:
        """
        Conducts forensic deliberation between top two competing candidate takes.

        Returns:
            Tuple of:
            (winner, runner_up, winner_score, runner_up_score, reason_codes, explainable_rationale)
        """
        reason_codes: List[str] = []
        adj_a = 0.0
        adj_b = 0.0

        ev_a = cand_a.evaluation
        ev_b = cand_b.evaluation
        dims_a = ev_a.dimensions if ev_a else {}
        dims_b = ev_b.dimensions if ev_b else {}

        sub_a = dims_a.get("subtext").score if "subtext" in dims_a else 0.80
        sub_b = dims_b.get("subtext").score if "subtext" in dims_b else 0.80

        emo_a = dims_a.get("emotional_match").score if "emotional_match" in dims_a else 0.80
        emo_b = dims_b.get("emotional_match").score if "emotional_match" in dims_b else 0.80

        nat_a = dims_a.get("naturalness").score if "naturalness" in dims_a else 0.80
        nat_b = dims_b.get("naturalness").score if "naturalness" in dims_b else 0.80

        intent_a = dims_a.get("intent_match").score if "intent_match" in dims_a else 0.80
        intent_b = dims_b.get("intent_match").score if "intent_match" in dims_b else 0.80

        pace_a = dims_a.get("pacing").score if "pacing" in dims_a else 0.80
        pace_b = dims_b.get("pacing").score if "pacing" in dims_b else 0.80

        v_id_a = ev_a.voice_identity_score if (ev_a and ev_a.voice_identity_score is not None) else 0.85
        v_id_b = ev_b.voice_identity_score if (ev_b and ev_b.voice_identity_score is not None) else 0.85

        # 1. Restraint vs Over-Acting Deliberation
        is_restraint_moment = direction.restraint >= 0.65 or "restraint" in direction.actioning.lower()
        if is_restraint_moment:
            # Under high restraint, shouting or excessive projection is penalized
            if sub_a > sub_b + 0.03:
                adj_a += 0.04
                reason_codes.append("BETTER_RESTRAINT")
            elif sub_b > sub_a + 0.03:
                adj_b += 0.04
                reason_codes.append("BETTER_RESTRAINT")

            # Check acoustic clipping / headroom
            clip_a = 0
            clip_b = 0
            if ev_a and ev_a.evidence and ev_a.evidence.acoustic:
                clip_a = getattr(ev_a.evidence.acoustic, "clipping_samples_pinned", getattr(ev_a.evidence.acoustic, "max_consecutive_clipped_samples", 0))
            if ev_b and ev_b.evidence and ev_b.evidence.acoustic:
                clip_b = getattr(ev_b.evidence.acoustic, "clipping_samples_pinned", getattr(ev_b.evidence.acoustic, "max_consecutive_clipped_samples", 0))
            if clip_a == 0 and clip_b > 0:
                adj_a += 0.03
                if "LOWER_ARTIFACT_RISK" not in reason_codes:
                    reason_codes.append("LOWER_ARTIFACT_RISK")
            elif clip_b == 0 and clip_a > 0:
                adj_b += 0.03
                if "LOWER_ARTIFACT_RISK" not in reason_codes:
                    reason_codes.append("LOWER_ARTIFACT_RISK")

        # 2. Dramatic Pause vs Dead Air
        dead_a = ev_a.evidence.acoustic.dead_air_sec if (ev_a and ev_a.evidence and ev_a.evidence.acoustic) else 0.0
        dead_b = ev_b.evidence.acoustic.dead_air_sec if (ev_b and ev_b.evidence and ev_b.evidence.acoustic) else 0.0
        if dead_a > 1.2 and dead_b <= 0.6:
            adj_b += 0.04
            reason_codes.append("BETTER_DRAMATIC_PAUSE")
        elif dead_b > 1.2 and dead_a <= 0.6:
            adj_a += 0.04
            reason_codes.append("BETTER_DRAMATIC_PAUSE")

        # 3. Subtextual Reality vs Surface Reading
        if abs(sub_a - sub_b) >= 0.05:
            if sub_a > sub_b:
                adj_a += 0.03
                if "BETTER_SUBTEXT" not in reason_codes:
                    reason_codes.append("BETTER_SUBTEXT")
            else:
                adj_b += 0.03
                if "BETTER_SUBTEXT" not in reason_codes:
                    reason_codes.append("BETTER_SUBTEXT")

        # 4. Emotional Delivery & Intent Match
        if abs(emo_a - emo_b) >= 0.05:
            if emo_a > emo_b:
                adj_a += 0.03
                if "BETTER_EMOTIONAL_DELIVERY" not in reason_codes:
                    reason_codes.append("BETTER_EMOTIONAL_DELIVERY")
            else:
                adj_b += 0.03
                if "BETTER_EMOTIONAL_DELIVERY" not in reason_codes:
                    reason_codes.append("BETTER_EMOTIONAL_DELIVERY")

        if abs(intent_a - intent_b) >= 0.05:
            if intent_a > intent_b:
                adj_a += 0.03
                if "STRONGER_INTENT_MATCH" not in reason_codes:
                    reason_codes.append("STRONGER_INTENT_MATCH")
            else:
                adj_b += 0.03
                if "STRONGER_INTENT_MATCH" not in reason_codes:
                    reason_codes.append("STRONGER_INTENT_MATCH")

        # 5. Voice Identity Stability
        if abs(v_id_a - v_id_b) >= 0.06:
            if v_id_a > v_id_b:
                adj_a += 0.04
                if "BETTER_VOICE_CONTINUITY" not in reason_codes:
                    reason_codes.append("BETTER_VOICE_CONTINUITY")
            else:
                adj_b += 0.04
                if "BETTER_VOICE_CONTINUITY" not in reason_codes:
                    reason_codes.append("BETTER_VOICE_CONTINUITY")

        # 6. Pacing & Timing Fit
        if abs(pace_a - pace_b) >= 0.06:
            if pace_a > pace_b:
                adj_a += 0.02
                if "BETTER_PACING" not in reason_codes:
                    reason_codes.append("BETTER_PACING")
            else:
                adj_b += 0.02
                if "BETTER_PACING" not in reason_codes:
                    reason_codes.append("BETTER_PACING")

        # 7. Chemistry Bonus (if available)
        if chemistry_scores:
            c_a = chemistry_scores.get(cand_a.take_id, 0.70)
            c_b = chemistry_scores.get(cand_b.take_id, 0.70)
            if abs(c_a - c_b) >= 0.05:
                if c_a > c_b:
                    adj_a += 0.05
                    if "BETTER_CHEMISTRY" not in reason_codes:
                        reason_codes.append("BETTER_CHEMISTRY")
                else:
                    adj_b += 0.05
                    if "BETTER_CHEMISTRY" not in reason_codes:
                        reason_codes.append("BETTER_CHEMISTRY")

        # 8. Alignment Uncertainty & Artifacts
        align_a = ev_a.evidence.alignment_confidence if (ev_a and ev_a.evidence and ev_a.evidence.alignment_confidence is not None) else None
        align_b = ev_b.evidence.alignment_confidence if (ev_b and ev_b.evidence and ev_b.evidence.alignment_confidence is not None) else None
        if align_a is not None and align_b is not None:
            if abs(align_a - align_b) >= 0.10:
                if align_a > align_b:
                    adj_a += 0.02
                    if "LOWER_ALIGNMENT_UNCERTAINTY" not in reason_codes:
                        reason_codes.append("LOWER_ALIGNMENT_UNCERTAINTY")
                else:
                    adj_b += 0.02
                    if "LOWER_ALIGNMENT_UNCERTAINTY" not in reason_codes:
                        reason_codes.append("LOWER_ALIGNMENT_UNCERTAINTY")

        final_a = round(min(1.0, max(0.0, score_a + adj_a)), 3)
        final_b = round(min(1.0, max(0.0, score_b + adj_b)), 3)

        if final_a >= final_b:
            winner = cand_a
            runner_up = cand_b
            win_score = final_a
            ru_score = final_b
        else:
            winner = cand_b
            runner_up = cand_a
            win_score = final_b
            ru_score = final_a

        # If reason_codes is empty, assign strongest evidential dimension
        if not reason_codes:
            if sub_a != sub_b:
                reason_codes.append("BETTER_SUBTEXT")
            elif emo_a != emo_b:
                reason_codes.append("BETTER_EMOTIONAL_DELIVERY")
            else:
                reason_codes.append("STRONGER_INTENT_MATCH")

        w_ev = winner.evaluation
        ru_ev = runner_up.evaluation
        w_sub = w_ev.dimensions.get("subtext").score if (w_ev and "subtext" in w_ev.dimensions) else 0.80
        ru_sub = ru_ev.dimensions.get("subtext").score if (ru_ev and "subtext" in ru_ev.dimensions) else 0.80

        rationale_bits = [
            f"Selected Take '{winner.variant_type}' (overall: {win_score:.2f}) via Pairwise Deliberation"
        ]
        if "BETTER_RESTRAINT" in reason_codes:
            rationale_bits.append(f"superior dramatic restraint (subtext {w_sub:.2f} vs {ru_sub:.2f})")
        elif "BETTER_CHEMISTRY" in reason_codes:
            rationale_bits.append("superior conversational chemistry and turn coupling")
        elif "BETTER_SUBTEXT" in reason_codes:
            rationale_bits.append(f"superior subtext control ({w_sub:.2f} vs {ru_sub:.2f})")
        if direction.target_character:
            rationale_bits.append(f"better relationship dynamic toward {direction.target_character}")
        rationale_bits.append(f"preferred over '{runner_up.variant_type}' ({ru_score:.2f})")

        rationale = "; ".join(rationale_bits)
        return winner, runner_up, win_score, ru_score, reason_codes, rationale


class IntelligentTakeSelector:
    """
    World-Class Performance Take Selector & Scene Director.
    Selects the optimal performance take based on staged hard gates,
    multi-dimensional evidence, pairwise judicial deliberation, and scene continuity.
    """

    def __init__(
        self,
        evaluator: Optional[PerformanceEvaluator] = None,
        config: Optional[TakeSelectorCalibrationConfig] = None,
        aligner: Optional[Any] = None,
    ):
        self.evaluator = evaluator or PerformanceEvaluator()
        self.config = config or TakeSelectorCalibrationConfig()
        self.aligner = aligner

    def _audit_technical_hard_gates(
        self,
        take: TakeVariant,
        text: str,
        direction: PerformanceDirection,
    ) -> Tuple[bool, List[str]]:
        """Stage 1: Audits raw audio integrity, DC offset, duration, and clipping."""
        reasons: List[str] = []
        p = Path(take.audio_path)
        if not p.exists() or p.stat().st_size <= 44:
            return False, ["Audio file missing or unreadable header"]

        dur = take.duration_sec
        if dur <= 0.0:
            try:
                with wave.open(str(p), "rb") as wf:
                    dur = wf.getnframes() / float(wf.getframerate())
                    take.duration_sec = round(dur, 3)
            except Exception as e:
                return False, [f"Failed to read WAV audio header: {e}"]

        if dur < self.config.min_duration_sec:
            reasons.append(f"Truncated audio: duration {dur:.2f}s < {self.config.min_duration_sec}s")

        words = len(text.split()) if text else 0
        if words > 0:
            target_dur = words / max(0.5, direction.pace * 2.8)
            if dur > target_dur * self.config.max_duration_multiplier and dur > 4.0:
                reasons.append(
                    f"Excessive duration: {dur:.2f}s exceeds {self.config.max_duration_multiplier}x target ({target_dur:.2f}s)"
                )

        if take.evaluation and take.evaluation.evidence:
            ev = take.evaluation.evidence
            if ev.acoustic:
                pinned = getattr(ev.acoustic, "clipping_samples_pinned", getattr(ev.acoustic, "max_consecutive_clipped_samples", 0))
                if pinned >= self.config.clipping_pinned_hard_gate:
                    reasons.append(
                        f"Audible clipping: {pinned} pinned samples >= {self.config.clipping_pinned_hard_gate}"
                    )
                dc = getattr(ev.acoustic, "dc_bias", 0.0)
                if abs(dc) > self.config.dc_bias_hard_gate:
                    reasons.append(f"DC bias anomaly: {dc:.1f} > {self.config.dc_bias_hard_gate}")
                dead_sec = getattr(ev.acoustic, "dead_air_sec", 0.0)
                if dead_sec > self.config.dead_air_hard_gate_sec:
                    reasons.append(f"Dead air violation: {dead_sec:.2f}s > {self.config.dead_air_hard_gate_sec}s")

        return len(reasons) == 0, reasons

    def _audit_alignment_hard_gates(
        self,
        take: TakeVariant,
    ) -> Tuple[bool, List[str]]:
        """Stage 2: Audits speech alignment confidence and word omissions."""
        reasons: List[str] = []
        if take.evaluation and take.evaluation.evidence:
            ev = take.evaluation.evidence
            if ev.alignment_confidence is not None:
                if ev.alignment_confidence < self.config.alignment_confidence_hard_gate:
                    reasons.append(
                        f"Alignment failure: confidence {ev.alignment_confidence:.2f} < {self.config.alignment_confidence_hard_gate}"
                    )
        # Also check take's direct alignment_result or diagnostics if present
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
                if sev == "CRITICAL" or code in ("INSUFFICIENT_SPEECH", "AUDIO_FILE_DEFECT"):
                    d_msg = f"Critical alignment failure: {getattr(d, 'message', str(d))}"
                    if d_msg not in reasons:
                        reasons.append(d_msg)
        return len(reasons) == 0, reasons

    def _audit_voice_identity_gate(
        self,
        take: TakeVariant,
    ) -> Tuple[bool, List[str]]:
        """Stage 3: Audits catastrophic voice drift and timbre divergence."""
        reasons: List[str] = []
        if take.evaluation:
            ev = take.evaluation
            if ev.voice_drift_detected:
                if ev.voice_identity_score is not None and ev.voice_identity_score < 0.45:
                    reasons.append(f"Catastrophic voice drift: similarity {ev.voice_identity_score:.2f} < 0.45")
                for diag in ev.diagnostics:
                    if "Catastrophic" in diag or "hard gate" in diag.lower():
                        reasons.append(diag)
        return len(reasons) == 0, reasons

    def _score_contextual(
        self,
        take: TakeVariant,
        direction: PerformanceDirection,
        chemistry_context: Optional[Dict[str, float]] = None,
        arc_context: Optional[Dict[str, float]] = None,
    ) -> float:
        """Stage 4: Context-aware weighted scoring based on dramatic mode."""
        ev = take.evaluation
        if not ev:
            return 0.50

        base_score = ev.overall_score
        dims = ev.dimensions

        sub_score = dims.get("subtext").score if "subtext" in dims else base_score
        rel_score = dims.get("relationship_consistency").score if "relationship_consistency" in dims else base_score
        nat_score = dims.get("naturalness").score if "naturalness" in dims else base_score
        emo_score = dims.get("emotional_match").score if "emotional_match" in dims else base_score
        pros_score = dims.get("prosody").score if "prosody" in dims else base_score
        pace_score = dims.get("pacing").score if "pacing" in dims else base_score
        intent_score = dims.get("intent_match").score if "intent_match" in dims else base_score

        is_whisper = (
            direction.proximity == "close_mic"
            or direction.intimacy_level == "intimate"
            or "whisper" in direction.surface_emotion.lower()
        )
        is_climax = (
            direction.intensity in ("high", "explosive")
            or direction.performance_priority in ("high", "climactic")
        )
        is_exposition = (
            direction.narrative_mode == "narrator_exposition"
            or direction.speaker in ("Narrator", "Foley")
        )
        is_anger = any(w in direction.surface_emotion.lower() for w in ("anger", "rage", "fury", "hostile", "menace", "combat"))
        is_grief = any(w in direction.surface_emotion.lower() for w in ("grief", "sorrow", "despair", "weeping", "mourning")) or direction.vulnerability >= 0.70

        bonus = 0.0

        # 1. Voice Identity & Drift Enforcement
        if ev.voice_drift_detected:
            bonus -= self.config.voice_drift_penalty
        elif ev.voice_identity_score is not None and ev.voice_identity_score >= 0.85:
            bonus += self.config.voice_match_bonus

        # 2. Context-Aware Weighting
        if is_exposition:
            if nat_score >= 0.85:
                bonus += 0.08
            if pace_score >= 0.85:
                bonus += 0.04
        elif is_climax:
            if emo_score >= 0.85:
                bonus += 0.08
            if direction.restraint >= 0.70 and sub_score >= 0.85:
                bonus += 0.06
        elif is_whisper:
            if take.variant_type in ("more_intimate", "vulnerable", "restraint"):
                bonus += 0.08
            if nat_score >= 0.80:
                bonus += 0.04
        elif is_anger:
            if intent_score >= 0.85:
                bonus += 0.06
            if direction.restraint >= 0.70 and sub_score >= 0.85:
                bonus += 0.06
        elif is_grief:
            if emo_score >= 0.85:
                bonus += 0.06
            if sub_score >= 0.80:
                bonus += 0.05
        else:
            # Standard Dialogue
            if direction.restraint >= 0.70 and sub_score >= 0.85:
                bonus += 0.05
            if rel_score >= 0.85:
                bonus += 0.04

        # 3. Naturalness prerequisite
        if nat_score < self.config.unnaturalness_threshold:
            bonus -= self.config.unnaturalness_penalty

        # 4. Chemistry Context Bonus (Wave D)
        if chemistry_context and take.take_id in chemistry_context:
            chem = chemistry_context[take.take_id]
            bonus += (chem - 0.70) * self.config.chemistry_weight

        # 5. Scene Arc Context Bonus (Wave D)
        if arc_context and take.take_id in arc_context:
            bonus += arc_context[take.take_id]

        effective_score = max(0.0, min(1.0, base_score + bonus))
        return effective_score

    def select_take_with_result(
        self,
        takes: List[TakeVariant],
        text: str,
        direction: PerformanceDirection,
        signature: Optional[Any] = None,
        voice_dna: Optional[Any] = None,
        chemistry_context: Optional[Dict[str, float]] = None,
        arc_context: Optional[Dict[str, float]] = None,
    ) -> TakeSelectionResult:
        """
        Executes the full staged take selection pipeline:
        Stage 1-3 Hard Gates -> Stage 4 Contextual Scoring -> Stage 5 Pairwise Deliberation -> Stage 6 Result.
        """
        if not takes:
            raise ValueError(f"No candidate takes provided for segment {direction.segment_uid}")

        # Ensure all takes are evaluated and aligned
        for t in takes:
            # If take does not have an alignment result and aligner is provided, run alignment
            if getattr(t, "alignment_result", None) is None and self.aligner is not None:
                try:
                    t.alignment_result = self.aligner.align_segment(
                        audio_path=t.audio_path,
                        text=text,
                        segment_uid=direction.segment_uid,
                        direction=direction,
                    )
                except Exception as e:
                    logger.warning(f"Failed to align take {t.take_id}: {e}")

            if t.evaluation is None:
                t.evaluation = self.evaluator.evaluate_take(
                    take_id=t.take_id,
                    audio_file=t.audio_path,
                    text=text,
                    direction=direction,
                    signature=signature,
                    voice_dna=voice_dna,
                    alignment_result=getattr(t, "alignment_result", None),
                )
            elif (
                t.evaluation.evidence is not None
                and t.evaluation.evidence.alignment_confidence is None
                and getattr(t, "alignment_result", None) is not None
            ):
                t.evaluation = self.evaluator.evaluate_take(
                    take_id=t.take_id,
                    audio_file=t.audio_path,
                    text=text,
                    direction=direction,
                    signature=signature,
                    voice_dna=voice_dna,
                    alignment_result=t.alignment_result,
                )

        # Single candidate take path
        if len(takes) == 1:
            sole = takes[0]
            sole.is_selected = True
            ev = sole.evaluation

            all_reasons: List[str] = []
            p_tech, r_tech = self._audit_technical_hard_gates(sole, text, direction)
            if not p_tech:
                all_reasons.extend(r_tech)

            p_align, r_align = self._audit_alignment_hard_gates(sole)
            if not p_align:
                all_reasons.extend(r_align)

            p_voice, r_voice = self._audit_voice_identity_gate(sole)
            if not p_voice:
                all_reasons.extend(r_voice)

            gates_passed = (len(all_reasons) == 0)
            score = ev.overall_score if ev else 0.80
            eval_passed = ev.passed if ev else True

            if gates_passed and eval_passed:
                reason = (
                    f"Selected sole candidate ({sole.variant_type}): overall score {score:.2f} "
                    f"satisfies performance and technical standards."
                )
                review_req = False
                confidence = 1.0
                reason_codes = ["STRONGER_INTENT_MATCH"]
            else:
                reason = (
                    f"Selected sole candidate ({sole.variant_type}) as degraded baseline (score: {score:.2f})."
                )
                if not gates_passed:
                    reason += f" [HARD GATE FAILURE: {'; '.join(all_reasons)}]"
                if not eval_passed and ev:
                    failed_dims = [k for k, d in ev.dimensions.items() if d.rating in ("weak", "unacceptable")]
                    if failed_dims:
                        reason += f" [EVALUATION DEFECTS: {', '.join(failed_dims)}]"
                    elif ev.voice_drift_detected:
                        reason += " [VOICE DRIFT DETECTED]"
                review_req = True
                confidence = 0.35
                reason_codes = ["REVIEW_REQUIRED_GATE_FAILURE"] if not gates_passed else ["REVIEW_REQUIRED_LOW_QUALITY"]

            sole.selection_reason = reason
            result = TakeSelectionResult(
                winner=sole,
                runner_up=None,
                winner_score=round(score, 3),
                runner_up_score=None,
                margin=0.0,
                confidence=confidence,
                reason_codes=reason_codes,
                evidence={
                    "gate_passed": gates_passed,
                    "gate_reasons": all_reasons,
                    "eval_passed": eval_passed,
                },
                review_required=review_req,
            )
            sole.selection_result = result
            return result

        # Stage 1 - 3: Hard Gates Audit
        qualified_takes: List[TakeVariant] = []
        disqualified_takes: List[Tuple[TakeVariant, List[str]]] = []

        for t in takes:
            t_reasons: List[str] = []
            p_tech, r_tech = self._audit_technical_hard_gates(t, text, direction)
            if not p_tech:
                t_reasons.extend(r_tech)

            p_align, r_align = self._audit_alignment_hard_gates(t)
            if not p_align:
                t_reasons.extend(r_align)

            p_voice, r_voice = self._audit_voice_identity_gate(t)
            if not p_voice:
                t_reasons.extend(r_voice)

            if t_reasons:
                disqualified_takes.append((t, t_reasons))
                t.is_selected = False
                t.selection_reason = f"Disqualified by Hard Gate: {'; '.join(t_reasons)}"
            else:
                qualified_takes.append(t)

        all_violated = False
        if not qualified_takes:
            # All candidates violated hard gates - compete among all with review_required
            competing_takes = takes
            all_violated = True
        else:
            competing_takes = qualified_takes

        # Stage 4: Contextual Dimensional Scoring
        scored_candidates: List[Tuple[float, TakeVariant]] = []
        for t in competing_takes:
            s = self._score_contextual(t, direction, chemistry_context, arc_context)
            scored_candidates.append((s, t))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        cand_1_score, cand_1 = scored_candidates[0]
        cand_2_score, cand_2 = scored_candidates[1] if len(scored_candidates) > 1 else (None, None)

        # Stage 5: Pairwise Take Judging
        should_pairwise = False
        if cand_2 is not None and cand_2_score is not None:
            margin = cand_1_score - cand_2_score
            is_close = margin <= self.config.pairwise_margin_threshold
            is_climactic = direction.performance_priority in ("climactic", "high") or direction.intensity in ("high", "explosive")
            is_restraint = direction.restraint >= 0.65 or "restraint" in direction.actioning.lower()

            ev1 = cand_1.evaluation
            ev2 = cand_2.evaluation
            emo_diff = abs(
                (ev1.dimensions.get("emotional_match").score if (ev1 and "emotional_match" in ev1.dimensions) else 0.8)
                - (ev2.dimensions.get("emotional_match").score if (ev2 and "emotional_match" in ev2.dimensions) else 0.8)
            )
            nat_diff = abs(
                (ev1.dimensions.get("naturalness").score if (ev1 and "naturalness" in ev1.dimensions) else 0.8)
                - (ev2.dimensions.get("naturalness").score if (ev2 and "naturalness" in ev2.dimensions) else 0.8)
            )
            has_divergence = emo_diff >= 0.12 and nat_diff >= 0.12

            if is_close or is_climactic or is_restraint or has_divergence:
                should_pairwise = True

        if should_pairwise and cand_2 is not None and cand_2_score is not None:
            winner, runner_up, win_score, ru_score, reason_codes, rationale = PairwiseTakeJudge.deliberate(
                cand_a=cand_1,
                score_a=cand_1_score,
                cand_b=cand_2,
                score_b=cand_2_score,
                direction=direction,
                text=text,
                config=self.config,
                chemistry_scores=chemistry_context,
            )
            final_margin = round(win_score - ru_score, 3)
            confidence = round(max(0.20, min(1.0, 0.60 + (final_margin / 0.10) * 0.40)), 2)
        else:
            winner = cand_1
            runner_up = cand_2
            win_score = round(cand_1_score, 3)
            ru_score = round(cand_2_score, 3) if cand_2_score is not None else None
            final_margin = round(win_score - (ru_score or 0.0), 3)
            confidence = round(min(1.0, 0.70 + final_margin), 2)
            reason_codes = []

            # Populate explainable rationale and reason codes
            w_ev = winner.evaluation
            ru_ev = runner_up.evaluation if runner_up else None
            reason_parts = [
                f"Selected Take '{winner.variant_type}' (overall: {w_ev.overall_score:.2f})" if w_ev else f"Selected Take '{winner.variant_type}'"
            ]

            if ru_ev:
                w_sub = w_ev.dimensions.get("subtext").score if (w_ev and "subtext" in w_ev.dimensions) else None
                ru_sub = ru_ev.dimensions.get("subtext").score if (ru_ev and "subtext" in ru_ev.dimensions) else None
                if w_sub and ru_sub and w_sub > ru_sub:
                    reason_parts.append(f"superior subtext control ({w_sub:.2f} vs {ru_sub:.2f})")
                    reason_codes.append("BETTER_SUBTEXT")
                    if direction.restraint >= 0.65:
                        reason_codes.append("BETTER_RESTRAINT")

                w_emo = w_ev.dimensions.get("emotional_match").score if (w_ev and "emotional_match" in w_ev.dimensions) else None
                ru_emo = ru_ev.dimensions.get("emotional_match").score if (ru_ev and "emotional_match" in ru_ev.dimensions) else None
                if w_emo and ru_emo and w_emo > ru_emo:
                    reason_codes.append("BETTER_EMOTIONAL_DELIVERY")

                if direction.target_character:
                    reason_parts.append(f"better relationship dynamic toward {direction.target_character}")

                reason_parts.append(f"preferred over '{runner_up.variant_type}' ({ru_ev.overall_score:.2f})")
            else:
                reason_codes.append("STRONGER_INTENT_MATCH")

            rationale = "; ".join(reason_parts)

        # Flag review required if all violated or confidence too low
        review_required = all_violated or (confidence < self.config.min_confidence_review_threshold)
        if all_violated:
            rationale = "[REVIEW REQUIRED - ALL TAKES FAILED HARD GATES] " + rationale

        # Finalize winner and candidates state
        winner.is_selected = True
        winner.selection_reason = rationale

        result = TakeSelectionResult(
            winner=winner,
            runner_up=runner_up,
            winner_score=win_score,
            runner_up_score=ru_score,
            margin=final_margin,
            confidence=confidence,
            reason_codes=reason_codes,
            evidence={
                "all_violated": all_violated,
                "disqualified_count": len(disqualified_takes),
                "pairwise_triggered": should_pairwise,
            },
            review_required=review_required,
        )
        winner.selection_result = result

        for t in takes:
            if t.take_id != winner.take_id:
                t.is_selected = False
                if not t.selection_reason:
                    t.selection_reason = f"Outperformed by winning take '{winner.variant_type}'."

        logger.info(
            f"  [TAKE SELECTION] Segment {direction.index} ({direction.speaker}): {winner.selection_reason}"
        )
        return result

    def select_best_take(
        self,
        takes: List[TakeVariant],
        text: str,
        direction: PerformanceDirection,
        signature: Optional[Any] = None,
        voice_dna: Optional[Any] = None,
    ) -> TakeVariant:
        """
        Evaluates and selects the winning take from a list of candidate TakeVariants.
        Sets is_selected=True, selection_reason, and selection_result on the chosen take.
        Fully backward-compatible API returning winning TakeVariant.
        """
        result = self.select_take_with_result(
            takes=takes,
            text=text,
            direction=direction,
            signature=signature,
            voice_dna=voice_dna,
        )
        return result.winner

    def select_scene_takes(
        self,
        scene_takes: List[List[TakeVariant]],
        directions: List[PerformanceDirection],
        texts: List[str],
        chemistry: Optional[ConversationalChemistry] = None,
        continuity_tracker: Optional[PerformanceContinuityTracker] = None,
        signatures: Optional[Dict[str, Any]] = None,
        voice_dnas: Optional[Dict[str, Any]] = None,
    ) -> List[TakeVariant]:
        """
        Evaluates and selects takes across an entire scene simultaneously (Wave D).
        Tracks dramatic performance arc (energy, pace, tension) and interpersonal chemistry
        between consecutive dialogue turns.
        """
        if not scene_takes:
            return []

        selected_takes: List[TakeVariant] = []
        chem_eval = chemistry or ConversationalChemistry()
        total_segments = len(directions)

        for i, (cand_takes, direction) in enumerate(zip(scene_takes, directions)):
            if not cand_takes:
                continue

            text_i = texts[i] if i < len(texts) else ""
            sig_i = signatures.get(direction.speaker, None) if signatures else None
            dna_i = voice_dnas.get(direction.speaker, None) if voice_dnas else None

            # 1. Interpersonal Chemistry Context
            chemistry_context: Optional[Dict[str, float]] = None
            if selected_takes:
                prev_winner = selected_takes[-1]
                prev_spk = prev_winner.direction.speaker
                curr_spk = direction.speaker
                if prev_spk not in ("Narrator", "Foley") and curr_spk not in ("Narrator", "Foley") and prev_spk != curr_spk:
                    chem_map: Dict[str, float] = {}
                    for cand in cand_takes:
                        c_res = chem_eval.evaluate_dialogue_chemistry(
                            prev_winner, cand, actual_gap_ms=cand.direction.pause_before_ms
                        )
                        chem_map[cand.take_id] = c_res.composite_chemistry_score
                    chemistry_context = chem_map

            # 2. Dramatic Performance Arc Context
            arc_context: Dict[str, float] = {}
            progress = i / max(1, total_segments - 1)

            # Detect fatigue: if 3+ prior lines maintained high energy (> 0.80)
            recent_high_energy = 0
            for st in selected_takes[-3:]:
                if st.direction.energy >= 0.80:
                    recent_high_energy += 1

            for cand in cand_takes:
                cand_bonus = 0.0

                # Fatigue defense: give dynamic breathing room
                if recent_high_energy >= 2:
                    if cand.direction.energy >= 0.80 or cand.variant_type == "exposed":
                        cand_bonus -= 0.06
                    else:
                        cand_bonus += 0.04

                # Premature climax defense
                if progress < 0.35 and direction.intensity not in ("high", "explosive") and direction.performance_priority not in ("climactic", "high"):
                    if cand.direction.energy >= 0.85 or cand.variant_type == "exposed":
                        cand_bonus -= 0.05

                # Climactic release reward
                if progress >= 0.70 and direction.performance_priority == "climactic":
                    if cand.variant_type in ("more_restrained", "vulnerable", "exposed", "restraint"):
                        cand_bonus += 0.04

                # Continuity check with character telemetry
                if continuity_tracker and direction.speaker in continuity_tracker.characters:
                    telem = continuity_tracker.characters[direction.speaker]
                    if len(telem.paces) >= 3:
                        pace_delta = abs(cand.direction.pace - telem.average_pace)
                        if pace_delta < 0.15:
                            cand_bonus += 0.03
                        elif pace_delta > 0.40 and direction.performance_priority == "standard":
                            cand_bonus -= 0.04

                arc_context[cand.take_id] = round(cand_bonus, 3)

            # Select winner for current segment
            result = self.select_take_with_result(
                takes=cand_takes,
                text=text_i,
                direction=direction,
                signature=sig_i,
                voice_dna=dna_i,
                chemistry_context=chemistry_context,
                arc_context=arc_context,
            )
            winner = result.winner
            selected_takes.append(winner)

            # Update continuity tracker
            if continuity_tracker:
                continuity_tracker.record_direction(direction, duration_sec=winner.duration_sec)
                continuity_tracker.record_take(
                    speaker=direction.speaker,
                    take_id=winner.take_id,
                    duration_sec=winner.duration_sec,
                    voice_identity_score=winner.evaluation.voice_identity_score if winner.evaluation else None,
                )

        return selected_takes
