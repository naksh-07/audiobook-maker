#!/usr/bin/env python3
"""
Audiobook Factory - Capability 02: Scene Audio Blueprint.
========================================================
Constructs the persistent scene-level sound-design blueprint (Director Instruction Sheet).
Encodes acoustic context, character staging, layer intents, cues, and silence intent.
Outputs relative intensity, priority, attention, and mix intent—leaving final mixing to Track 11.
"""

from __future__ import annotations
import hashlib
from typing import Dict, Any, List, Optional
from pathlib import Path

from audiobook_factory.sound_design.contracts import (
    SceneAudioBlueprint,
    SceneAudioUnderstandingResult,
    SpatialMetadata,
    MixIntent,
)
from audiobook_factory.sound_design.environment_profiles import get_environment_registry


class SceneAudioBlueprintBuilder:
    """
    Constructs the authoritative SceneAudioBlueprint from scene understanding,
    environment profiles, and dramatic context.
    """

    def __init__(self):
        self.env_registry = get_environment_registry()

    def build_blueprint(
        self,
        understanding: SceneAudioUnderstandingResult,
        character_roster: Optional[Any] = None,
        sonic_bible: Optional[Any] = None,
        source_text_hash: str = "",
    ) -> SceneAudioBlueprint:
        """
        Builds the SceneAudioBlueprint for a dramatic scene.
        """
        env_profile = self.env_registry.get_profile(understanding.environment_type) or self.env_registry.get_profile("castle_stone_corridor")

        # 1. Character Staging & Azimuth Coordinates
        characters_staged: Dict[str, SpatialMetadata] = {}
        chars = understanding.characters_present

        # Spatial distribution across stereo stage [-0.8 to +0.8]
        if len(chars) == 1:
            characters_staged[chars[0]] = SpatialMetadata(azimuth_pan=0.0, proximity="close")
        elif len(chars) == 2:
            characters_staged[chars[0]] = SpatialMetadata(azimuth_pan=-0.35, proximity="normal_room")
            characters_staged[chars[1]] = SpatialMetadata(azimuth_pan=0.35, proximity="normal_room")
        elif len(chars) >= 3:
            step = 1.4 / max(1, len(chars) - 1)
            for idx, c in enumerate(chars):
                pan = -0.7 + idx * step
                characters_staged[c] = SpatialMetadata(azimuth_pan=round(pan, 2), proximity="normal_room")

        # 2. Planned Ambience Layers
        ambience_layers: List[Dict[str, Any]] = []
        for l_path in env_profile.typical_ambience_layers:
            ambience_layers.append({
                "layer_tier": "BASE" if len(ambience_layers) == 0 else "MIDGROUND",
                "asset_path": l_path,
                "relative_intensity": "subtle_bed",
                "loop": True,
                "mix_intent": {"duck_under_dialogue": False, "swell_in_dialogue_pauses": True},
            })

        # 3. Planned Walla
        walla_planned: Optional[Dict[str, Any]] = None
        if understanding.requires_walla and env_profile.typical_walla:
            walla_planned = {
                "activity_type": env_profile.typical_walla,
                "density": "moderate",
                "distance": "mid_distance",
                "relative_intensity": "subtle_bed",
                "mix_intent": {"duck_under_dialogue": True},
            }

        # 4. Planned Foley candidates
        foley_planned: List[Dict[str, Any]] = []
        for cand in understanding.action_candidates:
            foley_planned.append({
                "segment_index": cand.segment_index,
                "action_verb": cand.action_verb,
                "object_material": cand.object_material,
                "anchor_word": cand.anchor_word,
                "relative_intensity": "normal",
                "priority": "MEDIUM",
            })

        # 5. Planned Hard SFX
        hard_sfx_planned = list(understanding.hard_sfx_candidates)

        # 6. Planned Magic
        magic_planned = [{"spell": m, "stage": "release_burst"} for m in understanding.magical_phenomena]

        # 7. Planned Creature
        creatures_planned = []
        if understanding.creature_presence:
            creatures_planned.append({
                "creature_type": understanding.creature_presence,
                "element": "vocalization",
                "emotional_state": "stalking",
            })

        # 8. Planned Music & Motifs
        music_motifs_planned: List[Dict[str, Any]] = []
        music_cues_planned: List[Dict[str, Any]] = []

        if sonic_bible and hasattr(sonic_bible, "leitmotifs"):
            for c_name in chars:
                theme = sonic_bible.resolve_theme_for_character(c_name) if hasattr(sonic_bible, "resolve_theme_for_character") else None
                if theme:
                    music_motifs_planned.append({
                        "motif_id": getattr(theme, "motif_id", ""),
                        "associated_entity": c_name,
                        "primary_instrument": getattr(theme, "primary_instrument", "solo strings"),
                    })

        if understanding.music_required:
            cue_type = "CLIMACTIC_ACTION_CUE" if understanding.tension_level >= 0.75 else ("TRANSITION_BRIDGE" if understanding.tension_level <= 0.3 else "EMOTIONAL_UNDERSCORE")
            var_mode = "CLIMAX" if understanding.tension_level >= 0.75 else ("INTIMATE" if understanding.tension_level <= 0.3 else "MYSTERIOUS")
            music_cues_planned.append({
                "cue_id": f"mc_{understanding.scene_id}_01",
                "cue_type": cue_type,
                "variation_mode": var_mode,
                "relative_intensity": "subtle_bed" if cue_type != "CLIMACTIC_ACTION_CUE" else "prominent",
                "priority": "HIGH" if cue_type == "CLIMACTIC_ACTION_CUE" else "MEDIUM",
            })

        # 9. Planned Silence Events
        silence_planned = []
        for opp in understanding.silence_opportunities:
            silence_planned.append({
                "purpose": "reveal_breath" if "whispers" in opp else "ambient_drop_suspense",
                "rationale": opp,
                "affected_buses": ["MUSIC"],
            })

        # Construct Blueprint
        blueprint = SceneAudioBlueprint(
            scene_id=understanding.scene_id,
            chapter_id=understanding.chapter_id,
            blueprint_version="2.0",
            location_id=env_profile.env_id,
            weather_state=understanding.time_and_weather,
            time_context="scene_narrative",
            acoustic_profile_id=env_profile.env_id,
            characters_staged=characters_staged,
            ambience_layers_planned=ambience_layers,
            walla_planned=walla_planned,
            foley_planned=foley_planned,
            hard_sfx_planned=hard_sfx_planned,
            magic_planned=magic_planned,
            creatures_planned=creatures_planned,
            music_motifs_planned=music_motifs_planned,
            music_cues_planned=music_cues_planned,
            silence_events_planned=silence_planned,
            restraint_target="high" if understanding.tension_level <= 0.4 else "moderate",
            provenance_hash=source_text_hash,
        )

        return blueprint


# Ergonomic alias
BlueprintBuilder = SceneAudioBlueprintBuilder

_GLOBAL_BUILDER: Optional[SceneAudioBlueprintBuilder] = None

def get_blueprint_builder() -> SceneAudioBlueprintBuilder:
    """Returns singleton instance of SceneAudioBlueprintBuilder."""
    global _GLOBAL_BUILDER
    if _GLOBAL_BUILDER is None:
        _GLOBAL_BUILDER = SceneAudioBlueprintBuilder()
    return _GLOBAL_BUILDER
