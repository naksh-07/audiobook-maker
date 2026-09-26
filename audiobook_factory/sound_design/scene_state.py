#!/usr/bin/env python3
"""
Audiobook Factory - Scene-Level Acoustic & Dramatic State Manager.
==================================================================
Coordinative state machine bridging Foley, Ambience, Music, SFX, Silence,
Walla, Creature, Magic, and Spatial systems into a unified cinematic soundscape.

Transitions through 7 canonical narrative phases:
CALM -> UNEASE -> TENSION -> THREAT -> EVENT -> AFTERMATH -> RECOVERY

Coordinates reusable cross-system reactions without hardcoded scene scripts:
- Character entering a room modulates room acoustics, walla density, and footsteps.
- Creature approach increases spatial proximity, elevates tension, and triggers pre-reveal silence.
- Magical charge ducks ambient bed, synchronizes release to action beats, and opens aftermath stillness.
"""

from __future__ import annotations
import math
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    DramaticNarrativePhase,
    CrossSystemInteraction,
    SceneAcousticDramaticState,
    SpatialMetadata,
    MixIntent,
    ProximityZone,
    MotifVariationMode,
    RelativeIntensity,
    SceneAudioUnderstandingResult,
)


class SceneAcousticDramaticStateManager:
    """
    Manages the shared acoustic and dramatic state across all sound design subsystems
    for a single scene, orchestrating dynamic cross-system reactions.
    """

    def __init__(self):
        pass

    def compute_segment_timing_map(
        self,
        segments: List[Dict[str, Any]],
        start_ms: int,
        end_ms: int,
    ) -> Dict[int, Dict[str, Any]]:
        """
        Builds a precise chronological index of every screenplay segment.
        Reuses existing timestamps if present, or computes speech-cadence-accurate
        boundaries based on text lengths, acting pauses, and scene bounds.
        """
        duration_ms = max(1000, end_ms - start_ms)
        seg_map: Dict[int, Dict[str, Any]] = {}
        if not segments:
            seg_map[1] = {
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": duration_ms,
                "text": "",
                "tension": 0.5,
                "speaker": "Narrator",
            }
            return seg_map

        # Check if segments already carry valid absolute or relative timestamps
        has_explicit_timing = any(
            seg.get("start_ms") is not None and int(seg.get("start_ms", 0)) > 0
            for seg in segments
        )

        if has_explicit_timing:
            for idx, seg in enumerate(segments):
                s_idx = int(seg.get("segment_index") or seg.get("index") or (idx + 1))
                s_start = int(seg.get("start_ms", start_ms))
                s_end = int(seg.get("end_ms", s_start + int(seg.get("duration_ms", 1000))))
                # Clamp within scene boundaries
                s_start = max(start_ms, min(s_start, end_ms))
                s_end = max(s_start + 100, min(s_end, end_ms))
                seg_map[s_idx] = {
                    "start_ms": s_start,
                    "end_ms": s_end,
                    "duration_ms": max(100, s_end - s_start),
                    "text": str(seg.get("text", "")),
                    "tension": float(seg.get("tension_after") or seg.get("tension_level") or 0.5),
                    "speaker": str(seg.get("speaker", "Narrator")),
                    "uid": seg.get("uid"),
                    "beat_id": seg.get("beat_id"),
                }
            return seg_map

        # Derive speech-cadence-accurate cumulative boundaries
        total_weight = 0.0
        weights: List[float] = []
        for seg in segments:
            text = str(seg.get("text", ""))
            char_count = max(10, len(text))
            pause_ms = int(seg.get("pause_after_ms", 300) or 300)
            # 1 char roughly equals 60ms of speech + pause
            w = (char_count * 55.0) + pause_ms
            weights.append(w)
            total_weight += w

        curr_time = float(start_ms)
        for idx, seg in enumerate(segments):
            s_idx = int(seg.get("segment_index") or seg.get("index") or (idx + 1))
            fraction = weights[idx] / max(1.0, total_weight)
            seg_dur = max(200.0, fraction * duration_ms)
            s_start = int(curr_time)
            s_end = int(min(end_ms, curr_time + seg_dur))
            if idx == len(segments) - 1:
                s_end = end_ms

            seg_map[s_idx] = {
                "start_ms": s_start,
                "end_ms": s_end,
                "duration_ms": max(100, s_end - s_start),
                "text": str(seg.get("text", "")),
                "tension": float(seg.get("tension_after") or 0.5),
                "speaker": str(seg.get("speaker", "Narrator")),
                "uid": seg.get("uid"),
                "beat_id": seg.get("beat_id"),
            }
            curr_time += seg_dur

        return seg_map

    def initialize_state(
        self,
        scene_id: str,
        understanding: SceneAudioUnderstandingResult,
        staged_positions: Dict[str, SpatialMetadata],
    ) -> SceneAcousticDramaticState:
        """
        Initializes the shared acoustic and dramatic state for a scene.
        """
        # Determine initial narrative phase
        t = understanding.tension_level
        initial_phase: DramaticNarrativePhase = "CALM"
        if t > 0.8:
            initial_phase = "THREAT"
        elif t > 0.6:
            initial_phase = "TENSION"
        elif t > 0.35:
            initial_phase = "UNEASE"

        # Determine initial motif variation
        variation_mode: MotifVariationMode = "MYSTERIOUS"
        if initial_phase == "CALM":
            variation_mode = "INTIMATE"
        elif initial_phase in ("TENSION", "THREAT"):
            variation_mode = "TENSE"

        return SceneAcousticDramaticState(
            scene_id=scene_id,
            active_phase=initial_phase,
            environment_id=understanding.environment_type,
            tension_level=understanding.tension_level,
            dominant_emotion=understanding.dominant_emotion,
            character_spatial_map=dict(staged_positions),
            active_creature=understanding.creature_presence,
            creature_proximity="distant" if t < 0.5 else "mid_distance",
            walla_permitted=understanding.requires_walla,
            walla_attenuation_factor=1.0,
            music_variation=variation_mode,
            foley_prominence="normal",
            cross_interactions=[],
        )

    def evaluate_cross_system_reactions(
        self,
        state: SceneAcousticDramaticState,
        has_magic: bool = False,
        has_creature: bool = False,
        has_hard_sfx: bool = False,
        is_stealth: bool = False,
    ) -> List[CrossSystemInteraction]:
        """
        Evaluates dynamic cross-system influences and updates the shared state.
        """
        interactions: List[CrossSystemInteraction] = []

        # 1. Creature Stalking & Proximity Reactions
        if has_creature or state.active_creature:
            if state.tension_level > 0.75:
                state.creature_proximity = "close"
                state.active_phase = "THREAT"
                state.music_variation = "TENSE"
                state.walla_permitted = False  # Crowd scatters or is silenced
                interactions.append(
                    CrossSystemInteraction(
                        source_category="CREATURE",
                        target_system="WALLA",
                        reaction_type="suppression",
                        description=f"Crowd walla suppressed by close creature proximity ({state.creature_proximity})",
                    )
                )
                interactions.append(
                    CrossSystemInteraction(
                        source_category="CREATURE",
                        target_system="AMBIENCE",
                        reaction_type="thinning",
                        description="Bed ambience thinned to emphasize unnatural silence and stalking foley",
                        mix_intent_override=MixIntent(duck_under_dialogue=False),
                    )
                )

        # 2. Supernatural & Magic Invocations
        if has_magic:
            state.active_phase = "EVENT"
            interactions.append(
                CrossSystemInteraction(
                    source_category="MAGIC",
                    target_system="MUSIC",
                    reaction_type="subordination",
                    description="Music score priority lowered to allow magical arcane charge and burst clarity",
                    mix_intent_override=MixIntent(duck_under_dialogue=True, carve_vocal_presence=True),
                )
            )
            interactions.append(
                CrossSystemInteraction(
                    source_category="MAGIC",
                    target_system="AMBIENCE",
                    reaction_type="spectral_thinning",
                    description="High-frequency room ambience carved to highlight spell shimmer",
                )
            )

        # 3. Action Hard SFX Impacts
        if has_hard_sfx:
            state.active_phase = "EVENT"
            interactions.append(
                CrossSystemInteraction(
                    source_category="HARD_SFX",
                    target_system="ALL",
                    reaction_type="sidechain_trigger",
                    description="Concussive transient triggers dynamic sidechain ducking in background beds",
                )
            )

        # 4. Stealth & Solitary Restraint
        if is_stealth or "stealth" in state.dominant_emotion:
            state.foley_prominence = "prominent"  # Every breath and cloth rustle is critical
            state.walla_permitted = False
            interactions.append(
                CrossSystemInteraction(
                    source_category="FOLEY",
                    target_system="WALLA",
                    reaction_type="suppression",
                    description="Walla suppressed during high-stakes stealth approach",
                )
            )

        state.cross_interactions.extend(interactions)
        return interactions


_GLOBAL_STATE_MANAGER: Optional[SceneAcousticDramaticStateManager] = None

def get_scene_state_manager() -> SceneAcousticDramaticStateManager:
    """Returns singleton instance of SceneAcousticDramaticStateManager."""
    global _GLOBAL_STATE_MANAGER
    if _GLOBAL_STATE_MANAGER is None:
        _GLOBAL_STATE_MANAGER = SceneAcousticDramaticStateManager()
    return _GLOBAL_STATE_MANAGER
