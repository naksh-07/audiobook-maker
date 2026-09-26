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


class CrossSystemPolicy:
    """A declarative rule for cross-system acoustic reactions."""
    def __init__(
        self,
        policy_id: str,
        source_category: str,
        target_system: str,
        reaction_type: str,
        description: str,
        phase_override: Optional[DramaticNarrativePhase] = None,
        suppress_walla: bool = False,
        walla_attenuation: Optional[float] = None,
        silence_active: bool = False,
        music_variation: Optional[MotifVariationMode] = None,
        foley_prominence: Optional[RelativeIntensity] = None,
        creature_proximity: Optional[ProximityZone] = None,
        mix_intent_override: Optional[MixIntent] = None,
    ):
        self.policy_id = policy_id
        self.source_category = source_category
        self.target_system = target_system
        self.reaction_type = reaction_type
        self.description = description
        self.phase_override = phase_override
        self.suppress_walla = suppress_walla
        self.walla_attenuation = walla_attenuation
        self.silence_active = silence_active
        self.music_variation = music_variation
        self.foley_prominence = foley_prominence
        self.creature_proximity = creature_proximity
        self.mix_intent_override = mix_intent_override


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
            # 1 char roughly equals 55ms of speech + pause
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
        t = understanding.tension_level
        initial_phase: DramaticNarrativePhase = "CALM"
        if t > 0.8:
            initial_phase = "THREAT"
        elif t > 0.6:
            initial_phase = "TENSION"
        elif t > 0.35:
            initial_phase = "UNEASE"

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
        has_reveal: bool = False,
        authority_enters: bool = False,
        is_combat: bool = False,
        is_intimate: bool = False,
        has_interruption: bool = False,
        is_aftermath: bool = False,
        has_supernatural_presence: bool = False,
        is_chase: bool = False,
    ) -> List[CrossSystemInteraction]:
        """
        Evaluates dynamic cross-system influences and updates the shared state
        using a set of 12 reusable cross-system choreography patterns.
        """
        interactions: List[CrossSystemInteraction] = []

        # 1. Pattern 1: Creature Approach
        # Creature in vicinity suppresses crowd walla, thins ambience, and elevates music tension
        if has_creature or state.active_creature:
            if state.tension_level > 0.70:
                state.creature_proximity = "close"
                state.active_phase = "THREAT"
                state.music_variation = "TENSE"
                state.walla_permitted = False
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

        # 2. Pattern 2: Magical Attack & Incantation
        # Spell charge subordinates music score priority and thins high-frequency room tone
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

        # 3. Pattern 3: Major Reveal / Shocking Discovery
        # Sudden revelation drops ambience, cuts active music variation, opens stunned silence pocket
        if has_reveal or state.dominant_emotion.lower() in ("shock", "revelation"):
            state.silence_window_active = True
            interactions.append(
                CrossSystemInteraction(
                    source_category="REVEAL",
                    target_system="AMBIENCE",
                    reaction_type="attenuation",
                    description="Ambience instantly ducks -6dB to create vacuum for emotional reveal",
                )
            )
            interactions.append(
                CrossSystemInteraction(
                    source_category="REVEAL",
                    target_system="MUSIC",
                    reaction_type="sharp_cutoff",
                    description="Music cuts sharply on shocking turn, transitioning to stunned silence",
                )
            )

        # 4. Pattern 4: Authority Enters Crowd
        # King, lord, or military commander enters: crowd walla drops to hush, center footsteps emphasized
        if authority_enters or (state.environment_id == "castle_great_hall" and state.tension_level > 0.65 and state.walla_permitted):
            state.walla_attenuation_factor = 0.25  # Hush to 25%
            interactions.append(
                CrossSystemInteraction(
                    source_category="AUTHORITY",
                    target_system="WALLA",
                    reaction_type="hush_suppression",
                    description="Walla hushed by authoritative presence; footsteps focused on center stage",
                )
            )

        # 5. Pattern 5: Major Impact / Concussive Transient
        # Structural crash or explosion triggers dynamic sidechain ducking across all background beds
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

        # 6. Pattern 6: Stealth Infiltration
        # Absolute silence of crowds, intimate foley focus, muffled room reflections
        if is_stealth or "stealth" in state.dominant_emotion.lower():
            state.foley_prominence = "prominent"
            state.walla_permitted = False
            interactions.append(
                CrossSystemInteraction(
                    source_category="FOLEY",
                    target_system="WALLA",
                    reaction_type="suppression",
                    description="Walla suppressed during high-stakes stealth approach",
                )
            )
            interactions.append(
                CrossSystemInteraction(
                    source_category="FOLEY",
                    target_system="AMBIENCE",
                    reaction_type="muffling",
                    description="Room ambience low-passed to bring close footsteps and breathing to focus",
                )
            )

        # 7. Pattern 7: Combat Escalation
        # Violent clashes shift music to CLIMAX driving pulse and promote weapon Foley prominence
        if is_combat or (state.tension_level > 0.85 and not is_stealth):
            state.music_variation = "CLIMAX"
            state.active_phase = "EVENT"
            interactions.append(
                CrossSystemInteraction(
                    source_category="COMBAT",
                    target_system="MUSIC",
                    reaction_type="climax_escalation",
                    description="Full driving rhythm score engaged as armed combat escalates",
                )
            )

        # 8. Pattern 8: Intimate Confession / Vulnerability
        # Distant sounds drop away; solo intimate instrument bed with dry vocal intelligibility
        if is_intimate or state.dominant_emotion.lower() in ("intimate", "grief", "secretive"):
            state.music_variation = "INTIMATE"
            state.walla_permitted = False
            interactions.append(
                CrossSystemInteraction(
                    source_category="DIALOGUE",
                    target_system="AMBIENCE",
                    reaction_type="whisper_bed",
                    description="Ambience drops to subtle bedrock tone for intimate emotional disclosure",
                )
            )

        # 9. Pattern 9: Sudden Interruption
        # Violent intrusion immediately silences ongoing dialogue/beds
        if has_interruption:
            interactions.append(
                CrossSystemInteraction(
                    source_category="INTERRUPTION",
                    target_system="ALL",
                    reaction_type="abrupt_cutoff",
                    description="Ongoing sound design abruptly truncated by violent intrusion",
                )
            )

        # 10. Pattern 10: Aftermath Stillness
        # Post-conflict recovery: diffuse reverb tail, warm slow musical resolution, room breath
        if is_aftermath or state.dominant_emotion.lower() in ("aftermath", "peace", "somber_calm"):
            state.active_phase = "AFTERMATH"
            state.music_variation = "AFTERMATH"
            interactions.append(
                CrossSystemInteraction(
                    source_category="NARRATIVE",
                    target_system="MUSIC",
                    reaction_type="aftermath_tail",
                    description="Music transitions to sparse aftermath resolution and ambient decay",
                )
            )

        # 11. Pattern 11: Supernatural Presence
        # Spectral chilling: walla froze, pitch drop drone in ambience
        if has_supernatural_presence or state.active_magic_family == "shadow_necrotic":
            state.walla_permitted = False
            interactions.append(
                CrossSystemInteraction(
                    source_category="SUPERNATURAL",
                    target_system="AMBIENCE",
                    reaction_type="pitch_drop_drone",
                    description="Room tone shifts to unnatural low drone upon supernatural manifest",
                )
            )

        # 12. Pattern 12: Chase & Pursuit
        # Rapid footstep foley prominence and accelerating musical tempo
        if is_chase or "chase" in state.dominant_emotion.lower():
            state.music_variation = "TENSE"
            state.active_phase = "EVENT"
            interactions.append(
                CrossSystemInteraction(
                    source_category="CHASE",
                    target_system="FOLEY",
                    reaction_type="prominence_boost",
                    description="Locomotion and obstacle impacts elevated to forefront of mix",
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
