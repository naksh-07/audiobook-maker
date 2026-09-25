#!/usr/bin/env python3
"""
Audiobook Factory - Conversational Chemistry & Turn-Taking Staging (Pillar 3.5).
Couples adjacent dialogue turns so characters react to each other acoustically
rather than existing as isolated TTS generations.
"""

from __future__ import annotations
from typing import List, Optional
from .contracts import PerformanceDirection, TakeVariant, ChemistryEvaluationResult


class ConversationalChemistry:
    """
    Applies interpersonal conversational chemistry across sequential dialogue segments.
    Provides pre-synthesis turn coupling and post-synthesis chemistry evaluation.
    """

    @classmethod
    def apply_conversational_chemistry(
        cls,
        directions: List[PerformanceDirection],
    ) -> List[PerformanceDirection]:
        """
        Adjusts timing, energy, and turn-taking behavior across consecutive dialogue lines.
        """
        if len(directions) < 2:
            return directions

        for i in range(1, len(directions)):
            prev = directions[i - 1]
            curr = directions[i]

            # Only couple dialogue turns between different speakers
            if prev.speaker in ("Narrator", "Foley") or curr.speaker in ("Narrator", "Foley"):
                continue
            if prev.speaker == curr.speaker:
                continue

            # 1. Interruption Coupling: If prev was cut off abruptly, curr starts immediately
            if prev.interruption_behavior == "abrupt_cut" or prev.silence_type == "interruption_cut":
                curr.pause_before_ms = 0
                curr.turn_taking_behavior = "immediate"
                prev.pause_after_ms = 60

            # 2. Threat / Intimidation Reaction: If prev was dominant or threatening
            if "threat" in prev.actioning.lower() or "intimidat" in prev.actioning.lower():
                if curr.power_position == "submissive":
                    # Hesitant or delayed response to threat
                    curr.pause_before_ms = max(curr.pause_before_ms, 700)
                    curr.turn_taking_behavior = "delayed_reaction"
                    curr.vulnerability = min(1.0, curr.vulnerability + 0.20)
                elif curr.power_position in ("contested", "dominant"):
                    # Defiant fast retort
                    curr.pause_before_ms = min(curr.pause_before_ms, 200)
                    curr.turn_taking_behavior = "eager_counter"

            # 3. Question & Answer Chemistry
            if prev.actioning in ("question", "probe", "interrogate"):
                if curr.subtext and curr.subtext_confidence >= 0.6:
                    # Guilt / concealed truth causes hesitation before replying
                    curr.hesitation_ms = max(curr.hesitation_ms, 400)
                    curr.pause_before_ms = max(curr.pause_before_ms, 650)
                    curr.turn_taking_behavior = "delayed_reaction"

            # 4. Intimate / Binaural Proximity Resonance
            if prev.intimacy_level == "intimate" and curr.intimacy_level == "intimate":
                curr.proximity = "close_mic"
                curr.resonance = "whisper_air"
                curr.energy = min(curr.energy, 0.55)
                # Intimate exchanges have gentle breath intake
                if curr.pre_roll_breath_ms == 0:
                    curr.pre_roll_breath_ms = 140

        return directions

    @classmethod
    def evaluate_dialogue_chemistry(
        cls,
        prev_take: TakeVariant,
        curr_take: TakeVariant,
        actual_gap_ms: Optional[int] = None,
    ) -> ChemistryEvaluationResult:
        """
        Post-synthesis acoustic and dramatic chemistry evaluation across adjacent dialogue turns.
        Evaluates response latency, interruption sharpness, and dynamic energy contrast.
        """
        prev_dir = prev_take.direction
        curr_dir = curr_take.direction
        diagnostics: List[str] = []

        # 1. Expected Turn-Taking Gap
        if prev_dir.interruption_behavior in ("abrupt_cut", "overlap_start") or curr_dir.turn_taking_behavior == "immediate":
            expected_gap = 40
        elif curr_dir.turn_taking_behavior == "delayed_reaction":
            expected_gap = max(curr_dir.pause_before_ms, 700)
        elif curr_dir.turn_taking_behavior == "reluctant":
            expected_gap = max(curr_dir.pause_before_ms, 550)
        elif curr_dir.turn_taking_behavior == "eager_counter":
            expected_gap = min(curr_dir.pause_before_ms, 200) if curr_dir.pause_before_ms > 0 else 150
        else:
            expected_gap = curr_dir.pause_before_ms if curr_dir.pause_before_ms > 0 else (
                prev_dir.pause_after_ms if prev_dir.pause_after_ms > 0 else 400
            )

        effective_gap = actual_gap_ms if actual_gap_ms is not None else (
            curr_dir.pause_before_ms if curr_dir.pause_before_ms > 0 else expected_gap
        )

        # 2. Pause Fidelity Score
        diff = abs(effective_gap - expected_gap)
        if diff <= 100:
            pause_fidelity = 1.0
        else:
            pause_fidelity = max(0.0, 1.0 - (diff - 100) / 500.0)

        if pause_fidelity < 0.80:
            diagnostics.append(f"Turn pause latency mismatch: expected ~{expected_gap}ms, measured {effective_gap}ms")

        # 3. Interruption Sharpness
        interruption_score = 1.0
        if prev_dir.interruption_behavior in ("abrupt_cut", "overlap_start") or prev_dir.silence_type == "interruption_cut":
            if effective_gap > 150:
                interruption_score = max(0.20, 1.0 - (effective_gap - 150) / 250.0)
                diagnostics.append(f"Dead air on interrupted turn: {effective_gap}ms gap breaks dramatic tension")
            else:
                interruption_score = 1.0
                diagnostics.append("Crisp interruption turn coupling")

        # 4. Energy Contrast & Relational Dynamics
        energy_score = 1.0
        prev_energy = prev_dir.energy
        curr_energy = curr_dir.energy

        # Intimidation / Submissive check
        is_threat = "threat" in prev_dir.actioning.lower() or "intimidat" in prev_dir.actioning.lower()
        if is_threat:
            if curr_dir.power_position == "submissive":
                if curr_energy > prev_energy:
                    energy_score -= 0.35
                    diagnostics.append("Submissive respondent inappropriately projected higher energy than intimidator")
                else:
                    diagnostics.append("Submissive respondent properly yielded vocal projection")
            elif curr_dir.power_position in ("contested", "dominant"):
                if curr_energy < 0.55:
                    energy_score -= 0.25
                    diagnostics.append("Counter-assertion delivered with insufficient vocal energy")

        # Intimate proximity check
        if prev_dir.intimacy_level == "intimate" and curr_dir.intimacy_level == "intimate":
            if curr_energy > 0.65 or prev_energy > 0.65:
                energy_score -= 0.25
                diagnostics.append("Excessive vocal projection during intimate proximity scene")

        # Unmotivated energy jump
        if abs(curr_energy - prev_energy) > 0.60 and curr_dir.power_position == "neutral" and not is_threat:
            energy_score -= 0.20
            diagnostics.append("Unmotivated energy leap between conversational partners")

        energy_score = max(0.0, min(1.0, energy_score))

        # Composite Score
        composite = round(0.40 * pause_fidelity + 0.30 * interruption_score + 0.30 * energy_score, 2)
        passed = bool(composite >= 0.70)

        return ChemistryEvaluationResult(
            prev_take_id=prev_take.take_id,
            curr_take_id=curr_take.take_id,
            prev_speaker=prev_dir.speaker,
            curr_speaker=curr_dir.speaker,
            expected_gap_ms=expected_gap,
            actual_gap_ms=actual_gap_ms,
            pause_fidelity_score=round(pause_fidelity, 2),
            interruption_quality_score=round(interruption_score, 2),
            energy_contrast_score=round(energy_score, 2),
            composite_chemistry_score=composite,
            passed=passed,
            diagnostics=diagnostics,
        )

