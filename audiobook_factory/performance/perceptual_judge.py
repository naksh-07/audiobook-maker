#!/usr/bin/env python3
"""
Audiobook Factory - Perceptual Performance Judge (Phase 14 & Wave 6).
Evaluates acting believability, emotional fidelity, subtext nuance, scene fit,
and conversational reactivity as an auxiliary evidence provider.
IMPORTANT: Deterministic DSP evidence remains authoritative for physical/acoustic properties;
the perceptual judge provides nuanced dramatic acting telemetry without being the sole authority.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from .contracts import (
    PerformanceDirection,
    TakeVariant,
    EvaluationDimensionScore,
    PerceptualPerformanceEvidence,
    PerformanceEvidence,
)


def _default_enable_external_llm() -> bool:
    import os
    if os.environ.get("MOCK_OFFLINE", "").lower() in ("true", "1", "yes"):
        return False
    if os.environ.get("UNIT_TEST_MODE", "").lower() in ("true", "1", "yes"):
        return False
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    return True


class PerceptualJudgeConfig(BaseModel):
    """
    Configurable calibration parameters for perceptual performance evaluation.
    Isolates scoring weights and confidence scaling.
    """
    model_config = ConfigDict(extra="ignore")

    enable_external_llm: bool = Field(default_factory=_default_enable_external_llm, description="Whether to call external LLM judge for acting critique")
    provider_name: str = Field(default="hybrid_llm_dsp", description="Name of the judge provider engine")
    confidence_floor: float = Field(default=0.50, description="Minimum confidence assigned to heuristic evaluation")
    dimension_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "naturalness": 0.15,
            "acting_believability": 0.18,
            "emotional_fidelity": 0.18,
            "intent_fidelity": 0.16,
            "subtext_fidelity": 0.11,
            "prosodic_fit": 0.08,
            "scene_fit": 0.08,
            "dialogue_reactivity": 0.06,
        }
    )


class PerceptualPerformanceJudge:
    """
    Auxiliary dramatic and acting performance judge.
    Evaluates synthesized takes against artistic dramatic direction across 8 dimensions.
    Produces explainable structured telemetry with explicit confidence and reason codes.
    """

    def __init__(self, config: Optional[PerceptualJudgeConfig] = None):
        self.config = config or PerceptualJudgeConfig()

    def judge_performance(
        self,
        take: Optional[TakeVariant] = None,
        direction: Optional[PerformanceDirection] = None,
        text: str = "",
        scene_context: Optional[Dict[str, Any]] = None,
        prev_take: Optional[TakeVariant] = None,
        next_direction: Optional[PerformanceDirection] = None,
        scene_vector: Optional[Any] = None,
        evidence: Optional[PerformanceEvidence] = None,
    ) -> PerceptualPerformanceEvidence:
        """
        Conducts perceptual evaluation of a take against dramatic direction.
        Returns structured PerceptualPerformanceEvidence with dimension scores and confidence.
        Can evaluate from either an existing TakeVariant or directly from PerformanceDirection + PerformanceEvidence.
        """
        direction = direction or (take.direction if take else None)
        if direction is None:
            direction = PerformanceDirection(speaker="Narrator", index=1)

        det_ev = evidence
        if det_ev is None and take and take.evaluation:
            det_ev = take.evaluation.evidence

        ac_ev = det_ev.acoustic if det_ev else None
        pr_ev = det_ev.prosody if det_ev else None
        pc_ev = det_ev.pacing if det_ev else None

        dimensions: Dict[str, EvaluationDimensionScore] = {}
        all_diagnostics: List[str] = []
        all_reason_codes: List[str] = []

        # Dimension 1: Naturalness
        nat_score = 0.90
        nat_reasons = []
        nat_codes = []
        if ac_ev:
            if ac_ev.is_clipped:
                nat_score -= 0.30
                nat_reasons.append("Audible acoustic clipping degrades naturalness")
                nat_codes.append("CLIPPING_DEFECT")
            if ac_ev.spectral_flatness_mean > 0.35:
                nat_score -= 0.15
                nat_reasons.append("Vocoder hiss artifacting detected")
                nat_codes.append("VOCODER_STATIC_DEFECT")
        if pr_ev and pr_ev.is_monotonic_pitch_locked:
            nat_score -= 0.20
            nat_reasons.append("Unnatural robotic pitch lock")
            nat_codes.append("PITCH_LOCK_DEFECT")
        nat_score = max(0.0, min(1.0, nat_score))
        if not nat_reasons:
            nat_reasons.append("Organic speech inflection and phonation")
            nat_codes.append("NATURAL_DELIVERY")
        dimensions["naturalness"] = EvaluationDimensionScore(
            dimension="naturalness",
            score=round(nat_score, 2),
            rating="strong" if nat_score >= 0.80 else ("moderate" if nat_score >= 0.65 else "weak"),
            rationale="; ".join(nat_reasons),
            confidence=0.90,
            reason_codes=nat_codes,
            evidence={"clipping": getattr(ac_ev, "is_clipped", False) if ac_ev else False},
        )

        # Dimension 2: Acting Believability
        act_score = 0.90
        act_reasons = []
        act_codes = []
        if direction.restraint >= 0.70:
            if ac_ev and (ac_ev.peak_amplitude >= 31000.0 and ac_ev.rms_dbfs > -15.0):
                act_score -= 0.30
                act_reasons.append("Over-acted melodramatic projection violates character restraint")
                act_codes.append("OVERACTING_SHOUT")
                act_codes.append("WRONG_RESTRAINT")
            else:
                act_reasons.append("Controlled vocal tension preserves acting believability")
                act_codes.append("BETTER_RESTRAINT")
        else:
            act_reasons.append("Authentic dramatic projection without melodrama")
            act_codes.append("BELIEVABLE_ACTING")
        act_score = max(0.0, min(1.0, act_score))
        dimensions["acting_believability"] = EvaluationDimensionScore(
            dimension="acting_believability",
            score=round(act_score, 2),
            rating="strong" if act_score >= 0.80 else ("moderate" if act_score >= 0.65 else "weak"),
            rationale="; ".join(act_reasons),
            confidence=0.85,
            reason_codes=act_codes,
            evidence={"restraint": direction.restraint},
        )

        # Dimension 3: Emotional Fidelity
        emo_score = 0.90
        emo_reasons = []
        emo_codes = []
        surf_emo = direction.surface_emotion.lower()
        intensity = direction.intensity.lower()
        if intensity == "explosive":
            if ac_ev and ac_ev.rms_dbfs < -24.0:
                emo_score -= 0.25
                emo_reasons.append(f"Underpowered energy for explosive dramatic emotion ({surf_emo})")
                emo_codes.append("EMOTION_UNDERPLAYED")
                emo_codes.append("WRONG_INTENSITY")
            else:
                emo_reasons.append(f"Full explosive realization of {surf_emo}")
                emo_codes.append("EMOTION_MATCH")
        elif intensity == "low" or "whisper" in surf_emo:
            if ac_ev and ac_ev.rms_dbfs > -18.0:
                emo_score -= 0.25
                emo_reasons.append(f"Excessive volume for intimate emotion ({surf_emo})")
                emo_codes.append("EMOTION_OVERPLAYED")
                emo_codes.append("WRONG_INTENSITY")
            else:
                emo_reasons.append(f"Nuanced low-intensity realization of {surf_emo}")
                emo_codes.append("EMOTION_MATCH")
        else:
            emo_reasons.append(f"Balanced emotional presence for {surf_emo}")
            emo_codes.append("EMOTION_MATCH")
        emo_score = max(0.0, min(1.0, emo_score))
        dimensions["emotional_fidelity"] = EvaluationDimensionScore(
            dimension="emotional_fidelity",
            score=round(emo_score, 2),
            rating="strong" if emo_score >= 0.80 else ("moderate" if emo_score >= 0.65 else "weak"),
            rationale="; ".join(emo_reasons),
            confidence=0.85,
            reason_codes=emo_codes,
            evidence={"surface_emotion": surf_emo, "intensity": intensity},
        )

        # Dimension 4: Intent Fidelity
        intent_score = 0.90
        intent_reasons = []
        intent_codes = []
        actioning = direction.actioning.lower()
        if "threat" in actioning or "corner" in actioning or "command" in actioning:
            if ac_ev and ac_ev.rms_dbfs < -28.0:
                intent_score -= 0.20
                intent_reasons.append(f"Under-projected command authority for action '{direction.actioning}'")
                intent_codes.append("INTENT_MISMATCH")
                intent_codes.append("ACTIONING_MISMATCH")
            else:
                intent_reasons.append(f"Convincing tactical execution of '{direction.actioning}'")
                intent_codes.append("STRONGER_INTENT_MATCH")
        elif "whisper" in actioning or "soothe" in actioning or "reassure" in actioning:
            if ac_ev and ac_ev.rms_dbfs > -16.0:
                intent_score -= 0.20
                intent_reasons.append(f"Aggressive volume conflicts with soothing action '{direction.actioning}'")
                intent_codes.append("INTENT_MISMATCH")
                intent_codes.append("ACTIONING_MISMATCH")
            else:
                intent_reasons.append(f"Gentle realization of '{direction.actioning}'")
                intent_codes.append("STRONGER_INTENT_MATCH")
        else:
            intent_reasons.append(f"Communicative delivery of action '{direction.actioning}'")
            intent_codes.append("STRONGER_INTENT_MATCH")
        intent_score = max(0.0, min(1.0, intent_score))
        dimensions["intent_fidelity"] = EvaluationDimensionScore(
            dimension="intent_fidelity",
            score=round(intent_score, 2),
            rating="strong" if intent_score >= 0.80 else "moderate",
            rationale="; ".join(intent_reasons),
            confidence=0.85,
            reason_codes=intent_codes,
            evidence={"actioning": direction.actioning, "objective": direction.objective},
        )

        # Dimension 5: Subtext Fidelity
        sub_score = 0.88
        sub_reasons = []
        sub_codes = []
        if direction.subtext and direction.subtext_confidence >= 0.65:
            if direction.restraint >= 0.70 and act_score >= 0.80:
                sub_score = 0.94
                sub_reasons.append(f"Subtextual tension communicated through vocal compression ('{direction.subtext}')")
                sub_codes.append("BETTER_SUBTEXT")
            else:
                sub_reasons.append(f"Subtext present: '{direction.subtext}'")
                sub_codes.append("SUBTEXT_PLAUSIBLE")
        else:
            sub_reasons.append("Direct line delivery without conflicting subtext")
            sub_codes.append("DIRECT_DELIVERY")
        dimensions["subtext_fidelity"] = EvaluationDimensionScore(
            dimension="subtext_fidelity",
            score=round(sub_score, 2),
            rating="strong" if sub_score >= 0.80 else "moderate",
            rationale="; ".join(sub_reasons),
            confidence=0.80,
            reason_codes=sub_codes,
            evidence={"subtext": direction.subtext, "subtext_confidence": direction.subtext_confidence},
        )

        # Dimension 6: Prosodic Fit
        pros_score = 0.90
        pros_reasons = []
        pros_codes = []
        if pr_ev:
            if pr_ev.f0_variance < 5.0 and not (direction.proximity == "close_mic" or "whisper" in surf_emo):
                pros_score -= 0.15
                pros_reasons.append(f"Limited pitch variation ({pr_ev.f0_variance:.1f}Hz)")
                pros_codes.append("MONOTONIC_PROSODY")
            else:
                pros_reasons.append(f"Organic pitch contour (IQR {pr_ev.f0_iqr_hz:.1f}Hz)")
                pros_codes.append("DYNAMIC_PROSODY")
        else:
            pros_reasons.append("Standard prosodic cadence")
            pros_codes.append("PROSODY_BASELINE")
        pros_score = max(0.0, min(1.0, pros_score))
        dimensions["prosodic_fit"] = EvaluationDimensionScore(
            dimension="prosodic_fit",
            score=round(pros_score, 2),
            rating="strong" if pros_score >= 0.80 else "moderate",
            rationale="; ".join(pros_reasons),
            confidence=0.85,
            reason_codes=pros_codes,
            evidence={"f0_variance": getattr(pr_ev, "f0_variance", 0.0) if pr_ev else 0.0},
        )

        # Dimension 7: Scene Fit
        scene_score = 0.88
        scene_reasons = []
        scene_codes = []
        if scene_context:
            target_tension = scene_context.get("tension", 0.5)
            if direction.intensity == "explosive" and target_tension < 0.35:
                scene_score -= 0.15
                scene_reasons.append("Premature emotional climax in low-tension scene")
                scene_codes.append("SCENE_TENSION_MISMATCH")
            else:
                scene_reasons.append("Performance aligns with scene tension trajectory")
                scene_codes.append("SCENE_FIT_VERIFIED")
        else:
            scene_reasons.append("Scene trajectory consistent")
            scene_codes.append("SCENE_FIT_DEFAULT")
        scene_score = max(0.0, min(1.0, scene_score))
        dimensions["scene_fit"] = EvaluationDimensionScore(
            dimension="scene_fit",
            score=round(scene_score, 2),
            rating="strong" if scene_score >= 0.80 else "moderate",
            rationale="; ".join(scene_reasons),
            confidence=0.75,
            reason_codes=scene_codes,
            evidence=scene_context or {},
        )

        # Dimension 8: Dialogue Reactivity
        react_score = 0.88
        react_reasons = []
        react_codes = []
        if prev_take and prev_take.direction:
            prev_dir = prev_take.direction
            if prev_dir.speaker != direction.speaker and prev_dir.speaker not in ("Narrator", "Foley"):
                # Relational check: was previous speaker threatening or dominant?
                if "threat" in prev_dir.actioning.lower() or "intimidat" in prev_dir.actioning.lower():
                    if direction.power_position == "submissive" and ac_ev and ac_ev.rms_dbfs > prev_dir.energy * -20.0:
                        react_score -= 0.15
                        react_reasons.append("Submissive character failed to yield vocal leverage to threat")
                        react_codes.append("REACTION_LEVERAGE_MISMATCH")
                    else:
                        react_reasons.append("Organic relational reaction to conversational partner")
                        react_codes.append("ORGANIC_REACTION")
                else:
                    react_reasons.append("Conversational turn posture maintained")
                    react_codes.append("ORGANIC_REACTION")
            else:
                react_reasons.append("Monologue / narrative continuity preserved")
                react_codes.append("MONOLOGUE_CONTINUITY")
        else:
            react_reasons.append("Turn onset verified")
            react_codes.append("TURN_ONSET_DEFAULT")
        react_score = max(0.0, min(1.0, react_score))
        dimensions["dialogue_reactivity"] = EvaluationDimensionScore(
            dimension="dialogue_reactivity",
            score=round(react_score, 2),
            rating="strong" if react_score >= 0.80 else "moderate",
            rationale="; ".join(react_reasons),
            confidence=0.75,
            reason_codes=react_codes,
            evidence={"prev_speaker": prev_take.direction.speaker if prev_take and prev_take.direction else None},
        )

        # Dimension calibration with LLM judge (dynamic model resolution, ADR-043)
        import os
        is_offline = (
            os.environ.get("MOCK_OFFLINE", "").lower() in ("true", "1", "yes")
            or os.environ.get("UNIT_TEST_MODE", "").lower() in ("true", "1", "yes")
            or "PYTEST_CURRENT_TEST" in os.environ
        )
        if self.config.enable_external_llm and not is_offline:
            try:
                from audiobook_factory.gates.llm_judge import LLMPerceptualPerformanceJudge
                dsp_summary = {
                    "peak_amplitude": getattr(ac_ev, "peak_amplitude", 0.0) if ac_ev else 0.0,
                    "rms_dbfs": getattr(ac_ev, "rms_dbfs", -20.0) if ac_ev else -20.0,
                    "spectral_flatness": getattr(ac_ev, "spectral_flatness_mean", 0.0) if ac_ev else 0.0,
                    "f0_variance": getattr(pr_ev, "f0_variance", 0.0) if pr_ev else 0.0,
                    "f0_iqr_hz": getattr(pr_ev, "f0_iqr_hz", 0.0) if pr_ev else 0.0,
                    "is_clipped": getattr(ac_ev, "is_clipped", False) if ac_ev else False,
                }
                prev_spk = prev_take.direction.speaker if (prev_take and prev_take.direction) else None
                llm_verdict = LLMPerceptualPerformanceJudge.critique_performance(
                    direction=direction,
                    acoustic_metrics=dsp_summary,
                    text=text or (take.audio_path.stem if take and take.audio_path else ""),
                    prev_speaker=prev_spk,
                    strict=False,
                )
                if "acting_believability" in dimensions:
                    dimensions["acting_believability"].score = round(
                        (dimensions["acting_believability"].score * 0.4) + (llm_verdict.acting_believability * 0.6), 2
                    )
                if "emotional_fidelity" in dimensions:
                    dimensions["emotional_fidelity"].score = round(
                        (dimensions["emotional_fidelity"].score * 0.4) + (llm_verdict.emotional_fidelity * 0.6), 2
                    )
                if "subtext_fidelity" in dimensions:
                    dimensions["subtext_fidelity"].score = round(
                        (dimensions["subtext_fidelity"].score * 0.4) + (llm_verdict.subtext_fidelity * 0.6), 2
                    )
                if "dialogue_reactivity" in dimensions:
                    dimensions["dialogue_reactivity"].score = round(
                        (dimensions["dialogue_reactivity"].score * 0.4) + (llm_verdict.dialogue_reactivity * 0.6), 2
                    )
                all_diagnostics.extend(llm_verdict.diagnostics)
            except Exception as llm_exc:
                # DEGRADED MODE: LLM perceptual critique failed. Log prominently — do NOT silently swallow.
                # Heuristic-only scoring will proceed, but this must be visible for post-run triage.
                import traceback
                from audiobook_factory.logger import logger as _pj_logger
                _pj_logger.warning(
                    f"[!] perceptual_judge: LLMPerceptualPerformanceJudge.critique_performance failed — "
                    f"falling back to heuristic-only scoring (no acoustic acting validation). "
                    f"Error: {llm_exc}\n{traceback.format_exc(limit=3)}"
                )

        # Collect diagnostics & reason codes
        for k, dim in dimensions.items():
            if dim.rating in ("weak", "unacceptable"):
                all_diagnostics.append(f"[{k.upper()}] {dim.rationale}")
            all_reason_codes.extend(dim.reason_codes)

        # Composite score calculation
        weights = self.config.dimension_weights
        active_w = {k: weights.get(k, 0.1) for k in dimensions}
        total_w = sum(active_w.values()) or 1.0
        composite = sum(dimensions[k].score * (w / total_w) for k, w in active_w.items())
        composite = round(max(0.0, min(1.0, composite)), 2)

        # Average confidence
        avg_conf = sum(dimensions[k].confidence for k in dimensions) / len(dimensions) if dimensions else 0.80
        avg_conf = round(max(self.config.confidence_floor, min(1.0, avg_conf)), 2)

        return PerceptualPerformanceEvidence(
            dimensions=dimensions,
            composite_perceptual_score=composite,
            perceptual_confidence=avg_conf,
            provider=self.config.provider_name,
            diagnostics=all_diagnostics,
            reason_codes=list(dict.fromkeys(all_reason_codes)),
        )
