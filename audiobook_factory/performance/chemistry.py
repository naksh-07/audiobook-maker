#!/usr/bin/env python3
"""
Audiobook Factory - Conversational Chemistry & Turn-Taking Staging (Pillar 3.5).
Couples adjacent dialogue turns so characters react to each other acoustically
rather than existing as isolated TTS generations.
"""

from __future__ import annotations
from typing import List, Optional
from .contracts import PerformanceDirection


class ConversationalChemistry:
    """
    Applies interpersonal conversational chemistry across sequential dialogue segments.
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
