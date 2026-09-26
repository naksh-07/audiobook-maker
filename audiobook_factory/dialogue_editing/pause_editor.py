#!/usr/bin/env python3
"""
Audiobook Factory - Contextual Pause & Turn-Taking Editor (DE-04).
Realizes human-like conversational turn latencies, eliminates robotic metronome pacing,
and protects narrative cadence through deterministic, reproducible anti-mechanical modulation.
Derives timing from TimingRealizer and performance intent (never hardcoded 400ms defaults).
"""

from __future__ import annotations
import hashlib
from typing import Dict, Any, List, Tuple, Optional

from audiobook_factory.performance.contracts import PerformanceDirection
from audiobook_factory.performance.timing_realizer import TimingRealizer
from .contracts import PauseEditClassification, DialogueEditorialConfig


class PauseEditor:
    """
    Contextual Turn-Taking and Dramatic Silence Editor.
    Answers: 'Given what the scene intends, how long should the listener actually wait before the next line?'
    """

    def __init__(self, config: Optional[DialogueEditorialConfig] = None):
        self.config = config or DialogueEditorialConfig()

    def realize_pause(
        self,
        text: str = "",
        speaker: str = "Narrator",
        direction: Optional[PerformanceDirection] = None,
        next_speaker: Optional[str] = None,
        next_direction: Optional[PerformanceDirection] = None,
        segment_uid: str = "",
        segment_index: int = 1,
    ) -> Dict[str, Any]:
        """
        Calculates realized contextual silence and interruption dynamics following a dialogue segment.

        Returns:
            Dict containing:
                - pause_after_ms: int
                - pause_classification: PauseEditClassification
                - decision_reason: str
                - overlap_ms: int
                - interruption_mode: str
        """
        # ---------------------------------------------------------------------
        # 1. Derive Base Timing from Performance Intent or TimingRealizer
        # ---------------------------------------------------------------------
        if direction is not None:
            base_pause_ms = direction.pause_after_ms
            silence_type = direction.silence_type
            interruption_behavior = direction.interruption_behavior
            turn_taking = direction.turn_taking_behavior
            power_pos = direction.power_position
            hesitation_ms = direction.hesitation_ms
            tension_after = direction.tension_after
            char_state = direction.character_state
            surface_emotion = direction.surface_emotion
            actioning = direction.actioning
        else:
            # Fall back to TimingRealizer directly
            timing_dict = TimingRealizer.calculate_performance_timing(
                text=text,
                speaker=speaker,
            )
            base_pause_ms = timing_dict["pause_after_ms"]
            silence_type = timing_dict["silence_type"]
            interruption_behavior = timing_dict["interruption_behavior"]
            turn_taking = timing_dict["turn_taking_behavior"]
            power_pos = "neutral"
            hesitation_ms = timing_dict["hesitation_ms"]
            tension_after = 0.5
            char_state = "neutral"
            surface_emotion = "neutral"
            actioning = "speak"

        # ---------------------------------------------------------------------
        # 2. Contextual Classification & Latency Calibration
        # ---------------------------------------------------------------------
        cleaned_text = (text or "").strip()
        ends_with_dash = cleaned_text.endswith(("--", "—", "-"))

        overlap_ms = 0
        interruption_mode = "none"

        # Check explicit dramatic silence / emotional freeze FIRST (preserves aposiopesis)
        is_aposiopesis_or_freeze = bool(
            silence_type == "emotional_freeze"
            or surface_emotion in ("grief", "despair")
            or getattr(direction, "silence_intent", None) in ("grief", "shock", "realization", "emotional_absorption")
            or getattr(direction, "character_state", None) in ("grief", "trauma", "shock")
        )
        is_dramatic_silence = bool(silence_type in ("dramatic_silence", "reaction_silence"))

        if is_aposiopesis_or_freeze:
            pause_cls = "EMOTIONAL_PAUSE"
            target_pause_ms = max(base_pause_ms, 1250)
            reason = "Emotional freeze / grief processing pause"

        elif is_dramatic_silence:
            if tension_after >= 0.75:
                pause_cls = "SUSPENSE_PAUSE"
                target_pause_ms = max(base_pause_ms, 1100)
                reason = "High tension suspense silence"
            elif actioning in ("realize", "absorb", "assess"):
                pause_cls = "THINKING_PAUSE"
                target_pause_ms = max(base_pause_ms, 900)
                reason = "Thinking / realization absorption gap"
            else:
                pause_cls = "REACTION_PAUSE"
                target_pause_ms = max(base_pause_ms, 650)
                reason = "Reaction space before respondent turn"

        elif interruption_behavior == "overlap_start":
            pause_cls = "INTERRUPTED_TURN"
            interruption_mode = "overlap_start"
            overlap_ms = min(self.config.max_interruption_overlap_ms, self.config.default_interruption_overlap_ms)
            target_pause_ms = 0
            reason = f"Interrupted turn with conversational overlap ({overlap_ms}ms cross-talk)"

        elif interruption_behavior == "fade_under":
            pause_cls = "INTERRUPTED_TURN"
            interruption_mode = "fade_under"
            overlap_ms = min(self.config.max_interruption_overlap_ms, 120)
            target_pause_ms = 0
            reason = f"Interrupted turn with fade-under ducking ({overlap_ms}ms overlap)"

        elif interruption_behavior == "abrupt_cut" or silence_type == "interruption_cut":
            pause_cls = "INTERRUPTED_TURN"
            interruption_mode = "abrupt_cut"
            target_pause_ms = 35
            reason = "Abrupt cutoff / interruption turn"

        elif ends_with_dash:
            # Check if next turn is an eager counter or interruptor
            next_is_eager = bool(
                next_direction and (
                    next_direction.turn_taking_behavior == "eager_counter"
                    or next_direction.actioning in ("interrupt", "cut_off", "counter", "shout_down")
                )
            )
            if next_is_eager:
                pause_cls = "INTERRUPTED_TURN"
                interruption_mode = "overlap_start"
                overlap_ms = min(self.config.max_interruption_overlap_ms, self.config.default_interruption_overlap_ms)
                target_pause_ms = 0
                reason = f"Cutoff dash with eager counter overlap ({overlap_ms}ms cross-talk)"
            else:
                pause_cls = "INTERRUPTED_TURN"
                interruption_mode = "abrupt_cut"
                target_pause_ms = 35
                reason = "Abrupt cutoff / interruption turn"

        elif turn_taking == "eager_counter" or char_state == "escalation":
            pause_cls = "RAPID_TURN"
            target_pause_ms = 120
            reason = "Rapid dialogue escalation / eager counter"

        elif hesitation_ms > 0 or silence_type == "hesitation" or "..." in cleaned_text or "…" in cleaned_text:
            pause_cls = "HESITATION"
            target_pause_ms = max(base_pause_ms, 520)
            reason = f"Hesitation absorption gap ({target_pause_ms}ms)"

        else:
            pause_cls = "NORMAL_TURN"
            target_pause_ms = max(base_pause_ms, 260)
            reason = "Normal conversational turn latency"

        # ---------------------------------------------------------------------
        # 3. Interpersonal & Conversational Modulation
        # ---------------------------------------------------------------------
        is_same_speaker = bool(next_speaker and next_speaker.strip().lower() == speaker.strip().lower())
        if is_same_speaker:
            if pause_cls == "NORMAL_TURN":
                target_pause_ms = 380 if power_pos == "dominant" else 320
                reason = "Intra-speaker sentential cadence"
        else:
            # Multi-speaker turn taking status:
            # Subordinates responding to dominant authority answer promptly
            if power_pos == "dominant" and speaker.lower() not in ("narrator", "foley"):
                target_pause_ms = int(target_pause_ms * 0.90)
                reason += " (prompt response to dominant authority)"
            # Authority figures take time before responding to subordinate
            elif power_pos == "submissive" and speaker.lower() not in ("narrator", "foley"):
                target_pause_ms = int(target_pause_ms * 1.20)
                reason += " (unhurried authority response cadence)"

        # ---------------------------------------------------------------------
        # 4. Anti-Mechanical Rhythm Protection (Deterministic Pseudo-Jitter)
        # ---------------------------------------------------------------------
        # Prevents robotic sequences without non-deterministic randomness (never jitter overlaps or hard cuts)
        if pause_cls not in ("INTERRUPTED_TURN", "RAPID_TURN") and overlap_ms == 0:
            h_str = f"{segment_uid}:{segment_index}:{speaker}:{cleaned_text[:16]}"
            h_int = int(hashlib.sha256(h_str.encode("utf-8")).hexdigest()[:6], 16)
            jitter_span = 2 * self.config.anti_mechanical_jitter_ms + 1
            jitter_ms = (h_int % jitter_span) - self.config.anti_mechanical_jitter_ms
            target_pause_ms += jitter_ms

        # ---------------------------------------------------------------------
        # 5. Bounds Enforcement
        # ---------------------------------------------------------------------
        if overlap_ms > 0:
            clamped_pause_ms = 0
        else:
            min_floor = 25 if pause_cls == "INTERRUPTED_TURN" else self.config.min_pause_ms
            clamped_pause_ms = max(min_floor, min(self.config.max_contextual_pause_ms, target_pause_ms))

        return {
            "pause_after_ms": clamped_pause_ms,
            "pause_classification": pause_cls,
            "decision_reason": reason,
            "overlap_ms": overlap_ms,
            "interruption_mode": interruption_mode,
        }
