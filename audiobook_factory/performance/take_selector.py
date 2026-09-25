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

        # Multi-take selection: Rank candidates by weighted composite priority
        # Scoring logic:
        # If character has high restraint (>= 0.70), heavily favor subtext and restraint over raw energy
        scored_candidates = []
        for t in takes:
            ev = t.evaluation
            if not ev:
                continue

            base_score = ev.overall_score
            sub_score = ev.dimensions.get("subtext", None)
            rel_score = ev.dimensions.get("relationship_consistency", None)
            nat_score = ev.dimensions.get("naturalness", None)

            bonus = 0.0
            # Restraint bonus
            if direction.restraint >= 0.70 and sub_score and sub_score.score >= 0.85:
                bonus += 0.06
            # Relationship bonus
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
