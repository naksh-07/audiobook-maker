#!/usr/bin/env python3
"""
Audiobook Factory - Intelligent Take Selector.
Performs explainable multi-dimensional comparison of candidate takes
to select the best dramatic performance rather than blindly choosing the loudest.
"""

from __future__ import annotations
from typing import List, Optional
from pathlib import Path

from audiobook_factory.logger import logger
from .contracts import TakeVariant, PerformanceDirection, PerformanceEvaluationResult
from .evaluator import PerformanceEvaluator


class IntelligentTakeSelector:
    """
    World-Class Performance Take Selector.
    Selects the optimal performance take based on multi-dimensional balance
    (intent, restraint, subtext, naturalness, and relationship consistency).
    """

    def __init__(self, evaluator: Optional[PerformanceEvaluator] = None):
        self.evaluator = evaluator or PerformanceEvaluator()

    def select_best_take(
        self,
        takes: List[TakeVariant],
        text: str,
        direction: PerformanceDirection,
    ) -> TakeVariant:
        """
        Evaluates and selects the winning take from a list of candidate TakeVariants.
        Sets is_selected=True and selection_reason on the chosen take.
        """
        if not takes:
            raise ValueError(f"No candidate takes provided for segment {direction.segment_uid}")

        # Ensure all takes are evaluated
        for t in takes:
            if t.evaluation is None:
                t.evaluation = self.evaluator.evaluate_take(
                    take_id=t.take_id,
                    audio_file=t.audio_path,
                    text=text,
                    direction=direction,
                )

        # Single candidate take
        if len(takes) == 1:
            sole = takes[0]
            sole.is_selected = True
            ev = sole.evaluation
            if ev and ev.passed:
                sole.selection_reason = (
                    f"Selected sole candidate ({sole.variant_type}): overall score {ev.overall_score:.2f} "
                    f"satisfies performance standards."
                )
            else:
                score_str = f"{ev.overall_score:.2f}" if ev else "N/A"
                sole.selection_reason = (
                    f"Selected sole candidate ({sole.variant_type}) as baseline (score: {score_str})."
                )
            return sole

        # Multi-take selection: Rank candidates by context-aware weighted priority (Wave 4 Upgrade)
        # Context-aware scoring:
        # - Exposition: naturalness dominates
        # - Climax: emotional truth & subtext dominate
        # - Whisper: intimacy & intelligibility dominate
        # - Voice drift: penalized heavily (-0.40) to enforce voice identity stability
        is_whisper = direction.proximity == "close_mic" or direction.intimacy_level == "intimate" or "whisper" in direction.surface_emotion.lower()
        is_climax = direction.intensity in ("high", "explosive") or direction.performance_priority in ("high", "climactic")
        is_exposition = direction.narrative_mode == "narrator_exposition" or direction.speaker in ("Narrator", "Foley")

        scored_candidates = []
        for t in takes:
            ev = t.evaluation
            if not ev:
                continue

            base_score = ev.overall_score
            sub_score = ev.dimensions.get("subtext", None)
            rel_score = ev.dimensions.get("relationship_consistency", None)
            nat_score = ev.dimensions.get("naturalness", None)
            emo_score = ev.dimensions.get("emotional_match", None)

            bonus = 0.0

            # 1. Voice Identity & Drift Enforcement
            if ev.voice_drift_detected:
                bonus -= 0.40  # Heavy penalty for voice drift
            elif ev.voice_identity_score and ev.voice_identity_score >= 0.85:
                bonus += 0.05  # Bonus for rock-solid acoustic signature match

            # 2. Context-Aware Weighting
            if is_exposition:
                if nat_score and nat_score.score >= 0.85:
                    bonus += 0.08
            elif is_climax:
                if emo_score and emo_score.score >= 0.85:
                    bonus += 0.08
                if direction.restraint >= 0.70 and sub_score and sub_score.score >= 0.85:
                    bonus += 0.06
            elif is_whisper:
                if t.variant_type in ("more_intimate", "vulnerable", "restraint"):
                    bonus += 0.08
                if nat_score and nat_score.score >= 0.80:
                    bonus += 0.04
            else:
                # Standard Dialogue
                if direction.restraint >= 0.70 and sub_score and sub_score.score >= 0.85:
                    bonus += 0.05
                if rel_score and rel_score.score >= 0.85:
                    bonus += 0.04

            # Naturalness prerequisite
            if nat_score and nat_score.score < 0.70:
                bonus -= 0.15

            effective_score = base_score + bonus
            scored_candidates.append((effective_score, t))

        if not scored_candidates:
            winner = takes[0]
            winner.is_selected = True
            winner.selection_reason = "Selected fallback candidate (no scored takes)."
            return winner

        # Sort descending by effective score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        winner = scored_candidates[0][1]
        runner_up = scored_candidates[1][1] if len(scored_candidates) > 1 else None

        # Build explainable selection rationale
        w_ev = winner.evaluation
        ru_ev = runner_up.evaluation if runner_up else None

        reason_parts = [
            f"Selected Take '{winner.variant_type}' (overall: {w_ev.overall_score:.2f})"
        ]
        if ru_ev:
            w_sub = w_ev.dimensions.get("subtext", None)
            ru_sub = ru_ev.dimensions.get("subtext", None)
            if w_sub and ru_sub and w_sub.score > ru_sub.score:
                reason_parts.append(
                    f"superior subtext control ({w_sub.score:.2f} vs {ru_sub.score:.2f})"
                )
            if direction.target_character:
                reason_parts.append(
                    f"better relationship dynamic toward {direction.target_character}"
                )
            reason_parts.append(
                f"preferred over '{runner_up.variant_type}' ({ru_ev.overall_score:.2f})"
            )

        winner.is_selected = True
        winner.selection_reason = "; ".join(reason_parts)

        # Mark other takes as unselected
        for t in takes:
            if t.take_id != winner.take_id:
                t.is_selected = False
                t.selection_reason = f"Outperformed by winning take '{winner.variant_type}'."

        logger.info(
            f"  [TAKE SELECTION] Segment {direction.index} ({direction.speaker}): {winner.selection_reason}"
        )
        return winner
