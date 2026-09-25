#!/usr/bin/env python3
"""
Audiobook Factory - Performance Realization: Timing, Pauses, Breaths, and Dramatic Silence.
Realizes Stage 3 dramatic silence intent, conversational turn-taking, breathing,
and interruption dynamics into millisecond-accurate actor delivery and staging timing.
"""

from __future__ import annotations
import re
from typing import Dict, Any, Optional, Tuple
from .contracts import SilenceType, InterruptionBehavior, TurnTakingBehavior


class TimingRealizer:
    """
    Translates dramatic intent and conversational dynamics into calibrated timing:
    - Pre-roll breath intake (ms)
    - Post-roll breath release (ms)
    - Pre-speech reaction pause (ms)
    - Post-speech dramatic silence (ms)
    - Mid-speech hesitation (ms)
    - Interruption cutoff dynamics
    """

    SILENCE_INTENT_DURATIONS: Dict[str, Tuple[int, SilenceType]] = {
        "shock": (1600, "dramatic_silence"),
        "realization": (1400, "dramatic_silence"),
        "grief": (1800, "emotional_freeze"),
        "emotional_absorption": (1500, "emotional_freeze"),
        "intimidation": (1300, "reaction_silence"),
        "hesitation": (550, "hesitation"),
        "suspense": (1200, "dramatic_silence"),
        "anticipation": (1100, "dramatic_silence"),
    }

    CONVERSATIONAL_DYNAMIC_TIMINGS: Dict[str, Dict[str, Any]] = {
        "interruption": {
            "pause_after_ms": 80,
            "silence_type": "interruption_cut",
            "interruption_behavior": "abrupt_cut",
            "turn_taking_behavior": "immediate",
        },
        "hesitation": {
            "hesitation_ms": 400,
            "pause_after_ms": 600,
            "silence_type": "hesitation",
            "turn_taking_behavior": "delayed_reaction",
        },
        "escalation": {
            "pause_after_ms": 250,
            "silence_type": "conversational_gap",
            "turn_taking_behavior": "eager_counter",
        },
        "deflection_avoidance": {
            "pause_before_ms": 500,
            "pause_after_ms": 550,
            "silence_type": "reaction_silence",
            "turn_taking_behavior": "defensive_parry",
        },
        "tactical_silence": {
            "pause_after_ms": 1400,
            "silence_type": "reaction_silence",
            "turn_taking_behavior": "delayed_reaction",
        },
        "cross_talk": {
            "pause_after_ms": 100,
            "silence_type": "interruption_cut",
            "interruption_behavior": "overlap_start",
            "turn_taking_behavior": "immediate",
        },
    }

    @classmethod
    def calculate_performance_timing(
        cls,
        text: str,
        speaker: str,
        is_interruption: bool = False,
        silence_intent: Optional[str] = None,
        conversational_dynamic: Optional[str] = None,
        hesitation_pause_ms: Optional[int] = None,
        tension: float = 0.5,
        restraint: float = 0.5,
        physical_state: str = "normal",
        existing_pause_after_ms: Optional[int] = None,
        target_character: Optional[str] = None,
        power_position: str = "neutral",
    ) -> Dict[str, Any]:
        """
        Calculates holistic, explainable timing parameters for line performance.
        """
        cleaned_text = (text or "").strip()
        word_count = max(len(cleaned_text.split()), 1)

        # Baseline defaults
        pause_before_ms = 0
        pause_after_ms = 400 if existing_pause_after_ms is None else existing_pause_after_ms
        pre_roll_breath_ms = 0
        post_roll_breath_ms = 0
        hesitation_ms = hesitation_pause_ms or 0
        silence_type: SilenceType = "punctuation"
        interruption_behavior: InterruptionBehavior = "none"
        turn_taking_behavior: TurnTakingBehavior = "immediate"

        # 1. Interruption Check (Abrupt cutoff)
        text_ends_with_dash = cleaned_text.endswith(("--", "—", "-"))
        if is_interruption or text_ends_with_dash or conversational_dynamic == "interruption":
            pause_after_ms = 80
            silence_type = "interruption_cut"
            interruption_behavior = "abrupt_cut"
            turn_taking_behavior = "immediate"
            return {
                "pause_before_ms": pause_before_ms,
                "pause_after_ms": pause_after_ms,
                "pre_roll_breath_ms": pre_roll_breath_ms,
                "post_roll_breath_ms": post_roll_breath_ms,
                "hesitation_ms": hesitation_ms,
                "silence_type": silence_type,
                "interruption_behavior": interruption_behavior,
                "turn_taking_behavior": turn_taking_behavior,
            }

        # 2. Conversational Dynamics
        if conversational_dynamic and conversational_dynamic in cls.CONVERSATIONAL_DYNAMIC_TIMINGS:
            dyn = cls.CONVERSATIONAL_DYNAMIC_TIMINGS[conversational_dynamic]
            if "pause_before_ms" in dyn:
                pause_before_ms = max(pause_before_ms, dyn["pause_before_ms"])
            if "pause_after_ms" in dyn:
                pause_after_ms = max(pause_after_ms, dyn["pause_after_ms"])
            if "hesitation_ms" in dyn:
                hesitation_ms = max(hesitation_ms, dyn["hesitation_ms"])
            if "silence_type" in dyn:
                silence_type = dyn["silence_type"]
            if "interruption_behavior" in dyn:
                interruption_behavior = dyn["interruption_behavior"]
            if "turn_taking_behavior" in dyn:
                turn_taking_behavior = dyn["turn_taking_behavior"]

        # 3. Dramatic Silence Intent (Authoritative Stage 3 intention)
        if silence_intent:
            intent_key = str(silence_intent).strip().lower()
            if intent_key in cls.SILENCE_INTENT_DURATIONS:
                s_dur, s_typ = cls.SILENCE_INTENT_DURATIONS[intent_key]
                # High tension or high restraint can extend dramatic silence
                adjusted_dur = int(s_dur * (0.9 + 0.3 * tension + 0.2 * restraint))
                pause_after_ms = max(pause_after_ms, adjusted_dur)
                silence_type = s_typ

        # 4. Text-driven Hesitation & Ellipses
        if "..." in cleaned_text or "…" in cleaned_text:
            hesitation_ms = max(hesitation_ms, 350)
            if silence_type == "punctuation":
                silence_type = "hesitation"
            if turn_taking_behavior == "immediate":
                turn_taking_behavior = "delayed_reaction"

        # 5. Organic Respiratory Breath Intake
        needs_breath = (
            word_count >= 16
            or tension >= 0.72
            or physical_state in ("combat_strain", "exhausted", "wounded")
            or "[gasp]" in cleaned_text.lower()
            or "[sigh]" in cleaned_text.lower()
        )
        if needs_breath and speaker not in ("Narrator", "Foley"):
            if physical_state in ("combat_strain", "exhausted"):
                pre_roll_breath_ms = 280
                post_roll_breath_ms = 220
                if silence_type == "punctuation":
                    silence_type = "breathing"
            elif tension >= 0.8:
                pre_roll_breath_ms = 180
            elif word_count >= 20:
                pre_roll_breath_ms = 150

        # Post-roll release on heavy realizations or grief
        if silence_intent in ("grief", "emotional_absorption") or "[sigh]" in cleaned_text.lower():
            post_roll_breath_ms = max(post_roll_breath_ms, 250)

        # 6. Power position adjustments
        # Dominant speakers take longer, unhurried pauses before and after speaking
        if power_position == "dominant" and speaker != "Narrator":
            pause_after_ms = int(pause_after_ms * 1.15)
        elif power_position == "submissive" and speaker != "Narrator":
            # Submissive speakers hurry their responses or hesitate
            pause_after_ms = int(pause_after_ms * 0.90)

        return {
            "pause_before_ms": pause_before_ms,
            "pause_after_ms": max(pause_after_ms, 100),
            "pre_roll_breath_ms": pre_roll_breath_ms,
            "post_roll_breath_ms": post_roll_breath_ms,
            "hesitation_ms": hesitation_ms,
            "silence_type": silence_type,
            "interruption_behavior": interruption_behavior,
            "turn_taking_behavior": turn_taking_behavior,
        }
