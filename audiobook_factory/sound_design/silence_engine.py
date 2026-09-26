#!/usr/bin/env python3
"""
Audiobook Factory - Capability 16: Silence & Negative Sound Design Engine.
==========================================================================
Implements intentional, scene-dependent negative sound design:
- Replaces naive universal >=60% silence rules with adaptive acoustic density targets.
- Generates first-class negative sound events (ambient drops, foley suppression,
  walla drops, music drops, aftermath contemplation, reveal breaths).
- Directly reuses DramaticSilenceIntent from dramaturgy.
- Prunes acoustic clutter and directs listener attention into the stillness.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple, Literal
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    SilenceEventSpec,
    SilencePurpose,
    SceneAudioUnderstandingResult,
)
from audiobook_factory.dramaturgy.contracts import DramaticSilenceIntent


# Adaptive target density profiles per restraint tier:
# (min_active_density, max_active_density, target_silence_ratio)
RESTRAINT_DENSITY_PROFILES = {
    "high": {
        "min_density": 0.15,
        "max_density": 0.45,
        "target_silence": 0.65,
        "description": "Intimate, stealth, horror, or profound mystery. High silence budget.",
    },
    "moderate": {
        "min_density": 0.35,
        "max_density": 0.70,
        "target_silence": 0.45,
        "description": "Standard dramatic dialogue, classroom, travel, or investigation.",
    },
    "dense": {
        "min_density": 0.60,
        "max_density": 0.88,
        "target_silence": 0.20,
        "description": "Action climax, major battle, panic, or heightened festive celebration.",
    },
}


class SilenceEngine:
    """
    Orchestrates Negative Sound Design & Adaptive Scene Density.
    """

    def calculate_adaptive_silence_budget(
        self,
        tension_level: float,
        environment_type: str,
        dominant_emotion: str = "neutral",
    ) -> Dict[str, Any]:
        """
        Calculates scene-dependent acoustic density target and silence budget.
        Replaces arbitrary fixed quotas with dramatic contextual policies.
        """
        env_lower = environment_type.lower()
        emo_lower = dominant_emotion.lower()

        # Determine restraint tier
        if tension_level > 0.82 or "battle" in env_lower or emo_lower in ("terror", "furious", "panic"):
            restraint_tier = "dense"
        elif tension_level < 0.35 or any(w in env_lower for w in ["crypt", "forest", "cell", "study"]) or emo_lower in ("grief", "secretive", "stealth", "intimate"):
            restraint_tier = "high"
        else:
            restraint_tier = "moderate"

        profile = RESTRAINT_DENSITY_PROFILES[restraint_tier]
        return {
            "restraint_tier": restraint_tier,
            "min_density": profile["min_density"],
            "max_density": profile["max_density"],
            "target_silence": profile["target_silence"],
            "description": profile["description"],
        }

    def plan_silence_events(
        self,
        scene_id: str,
        scene_understanding: SceneAudioUnderstandingResult,
        start_ms: int,
        end_ms: int,
        dramatic_beats: Optional[List[Dict[str, Any]]] = None,
        screenplay_segments: Optional[List[Dict[str, Any]]] = None,
    ) -> List[SilenceEventSpec]:
        """
        Synthesizes intentional negative sound events for a scene.
        """
        duration_ms = max(0, end_ms - start_ms)
        if duration_ms < 3000:
            return []

        silence_events: List[SilenceEventSpec] = []
        budget = self.calculate_adaptive_silence_budget(
            tension_level=scene_understanding.tension_level,
            environment_type=scene_understanding.environment_type,
            dominant_emotion=scene_understanding.dominant_emotion,
        )

        # 1. Evaluate explicit silence opportunities identified in scene understanding
        for idx, opp in enumerate(scene_understanding.silence_opportunities):
            opp_lower = opp.lower()
            purpose: SilencePurpose = "ambient_drop_suspense"
            affected_buses: List[Literal["AMBIENCE", "WALLA", "FOLEY", "MUSIC", "ALL"]] = ["MUSIC"]
            focus: Literal["dialogue_whisper", "room_acoustics", "subtext_digestion", "breath"] = "subtext_digestion"

            if "ambient" in opp_lower:
                purpose = "ambient_drop_suspense"
                affected_buses = ["AMBIENCE"]
                focus = "room_acoustics"
            elif "music" in opp_lower:
                purpose = "music_drop_impact"
                affected_buses = ["MUSIC"]
                focus = "room_acoustics"
            elif "walla" in opp_lower or "crowd" in opp_lower or "arrival" in opp_lower:
                purpose = "walla_drop_arrival"
                affected_buses = ["WALLA"]
                focus = "subtext_digestion"
            elif "foley" in opp_lower or "stealth" in opp_lower:
                purpose = "foley_suppression_stealth"
                affected_buses = ["FOLEY"]
                focus = "breath"
            elif "breath" in opp_lower or "reveal" in opp_lower:
                purpose = "reveal_breath"
                affected_buses = ["FOLEY", "AMBIENCE"]
                focus = "breath"
            elif "aftermath" in opp_lower or "contemplat" in opp_lower:
                purpose = "aftermath_contemplation"
                affected_buses = ["MUSIC", "FOLEY"]
                focus = "subtext_digestion"
            elif "stillness" in opp_lower:
                purpose = "profound_stillness"
                affected_buses = ["ALL"]
                focus = "dialogue_whisper"
            elif "drop" in opp_lower:
                purpose = "ambient_drop_suspense"
                affected_buses = ["AMBIENCE"]
                focus = "room_acoustics"


            # Allocate timing near mid-to-late section of scene
            offset = int(start_ms + (duration_ms * (0.35 + idx * 0.25)))
            silence_dur = 1500 if budget["restraint_tier"] == "dense" else 2500

            silence_events.append(
                SilenceEventSpec(
                    silence_id=f"silence_{scene_id}_{idx+1}",
                    start_ms=offset,
                    duration_ms=silence_dur,
                    purpose=purpose,
                    affected_buses=affected_buses,
                    dramatic_rationale=opp,
                    listening_focus=focus,
                )
            )

        # 2. Integrate DramaticSilenceIntent from dramatic beats if provided
        if dramatic_beats:
            for b_idx, beat in enumerate(dramatic_beats):
                silence_intent_data = beat.get("silence_intent")
                if not silence_intent_data:
                    continue

                if isinstance(silence_intent_data, dict):
                    intent = DramaticSilenceIntent.model_validate(silence_intent_data)
                elif isinstance(silence_intent_data, DramaticSilenceIntent):
                    intent = silence_intent_data
                else:
                    continue

                b_start = beat.get("start_ms", start_ms + int(duration_ms * 0.5))
                b_dur = beat.get("duration_ms", 1800)

                purpose_map: Dict[str, SilencePurpose] = {
                    "anticipation": "ambient_drop_suspense",
                    "shock": "music_drop_impact",
                    "realization": "reveal_breath",
                    "grief": "aftermath_contemplation",
                    "emotional_absorption": "aftermath_contemplation",
                    "intimidation": "walla_drop_arrival",
                    "hesitation": "foley_suppression_stealth",
                    "suspense": "ambient_drop_suspense",
                }
                purpose = purpose_map.get(intent.purpose, "ambient_drop_suspense")

                silence_events.append(
                    SilenceEventSpec(
                        silence_id=f"silence_beat_{scene_id}_{b_idx+1}",
                        start_ms=b_start,
                        duration_ms=b_dur,
                        purpose=purpose,
                        affected_buses=["MUSIC", "WALLA"] if purpose in ("walla_drop_arrival", "music_drop_impact") else ["AMBIENCE", "FOLEY"],
                        dramatic_rationale=intent.dramatic_rationale,
                        listening_focus="dialogue_whisper" if intent.listening_focus == "character_reaction" else "subtext_digestion",
                    )
                )

        # 3. High-restraint scene default silence event if none planned
        if not silence_events and budget["restraint_tier"] == "high" and duration_ms > 5000:
            silence_events.append(
                SilenceEventSpec(
                    silence_id=f"silence_auto_{scene_id}_1",
                    start_ms=start_ms + int(duration_ms * 0.4),
                    duration_ms=2000,
                    purpose="ambient_drop_suspense",
                    affected_buses=["AMBIENCE"],
                    dramatic_rationale="Acoustic restraint in high-suspense / intimate environment.",
                    listening_focus="room_acoustics",
                )
            )

        logger.debug(
            f"[SilenceEngine] Planned {len(silence_events)} silence events for scene '{scene_id}' (tier={budget['restraint_tier']})."
        )
        return silence_events

    def evaluate_scene_density(
        self,
        total_duration_ms: int,
        active_sound_spans: List[Tuple[int, int]],
        restraint_target: str = "moderate",
        scene_start_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates whether total active sound event coverage aligns with restraint policy.
        Returns detailed compliance metrics without rigid arbitrary failures.
        """
        if total_duration_ms <= 0:
            return {"compliant": True, "density": 0.0, "reason": "Zero duration"}

        # Compute merged union of active sound intervals
        spans = sorted(active_sound_spans, key=lambda x: x[0])
        
        # Determine base offset to correctly handle absolute timestamps across multi-scene chapters
        if scene_start_ms is not None:
            base_offset = scene_start_ms
        elif spans and any(s >= total_duration_ms for s, _ in spans):
            base_offset = min(s for s, _ in spans)
        else:
            base_offset = 0

        merged: List[Tuple[int, int]] = []
        for s, e in spans:
            s_rel = s - base_offset
            e_rel = e - base_offset
            s_clamped = max(0, min(total_duration_ms, s_rel))
            e_clamped = max(0, min(total_duration_ms, e_rel))
            if s_clamped >= e_clamped:
                continue
            if not merged or s_clamped > merged[-1][1]:
                merged.append((s_clamped, e_clamped))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e_clamped))

        total_active_ms = sum(e - s for s, e in merged)
        density = round(total_active_ms / float(total_duration_ms), 3)
        silence_ratio = round(1.0 - density, 3)

        profile = RESTRAINT_DENSITY_PROFILES.get(restraint_target, RESTRAINT_DENSITY_PROFILES["moderate"])
        is_compliant = profile["min_density"] <= density <= profile["max_density"]

        return {
            "compliant": is_compliant,
            "density": density,
            "silence_ratio": silence_ratio,
            "target_restraint": restraint_target,
            "expected_range": (profile["min_density"], profile["max_density"]),
            "feedback": (
                f"Density {density:.1%} within [{profile['min_density']:.1%}, {profile['max_density']:.1%}]"
                if is_compliant
                else (
                    f"Scene is acoustically over-cluttered ({density:.1%} > {profile['max_density']:.1%})"
                    if density > profile["max_density"]
                    else f"Scene is acoustically sparse ({density:.1%} < {profile['min_density']:.1%})"
                )
            ),
        }


_GLOBAL_SILENCE_ENGINE: Optional[SilenceEngine] = None

def get_silence_engine() -> SilenceEngine:
    """Returns singleton instance of SilenceEngine."""
    global _GLOBAL_SILENCE_ENGINE
    if _GLOBAL_SILENCE_ENGINE is None:
        _GLOBAL_SILENCE_ENGINE = SilenceEngine()
    return _GLOBAL_SILENCE_ENGINE
