#!/usr/bin/env python3
"""
Audiobook Factory - Capabilities 17 & 18: Acoustic Environment & Spatial Geography.
====================================================================================
Acoustic Environment:
- Models abstract room propagation physics (RT60, absorption, reflections, occlusion).
- Decoupled from final DSP: Track 11 applies the actual convolution reverb and filters.

Spatial Geography & Soundstage:
- Coordinates character and prop positions on the virtual soundstage (azimuth pan [-0.8, +0.8]).
- Enforces strict spatial continuity across dialogue turns: prevents disorienting stereo jumping.
- Locks narrator strictly to center (0.0) with intimate/normal room proximity.
- Models physical trajectories (approaching, retreating, passing, encircling).
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple, Literal
from pathlib import Path

from audiobook_factory.logger import logger
from audiobook_factory.sound_design.contracts import (
    AcousticProfileSpec,
    SpatialSourceSpec,
    SpatialMetadata,
    SpatialTrajectory,
    ProximityZone,
    OcclusionState,
)
from audiobook_factory.sound_design.environment_profiles import get_environment_registry


class SpatialAcousticsEngine:
    """
    Abstract room acoustic profile resolver.
    """

    def __init__(self):
        self.env_registry = get_environment_registry()

    def build_acoustic_profile_spec(
        self,
        environment_id: str,
        occlusion_state: OcclusionState = "direct_line_of_sight",
    ) -> AcousticProfileSpec:
        """
        Derives an abstract room acoustic specification from an environment slug.
        """
        env = self.env_registry.get_profile(environment_id) or self.env_registry.get_profile("castle_stone_corridor")
        rt60 = env.estimated_rt60_ms

        # Derive early reflection and late reverb intent
        if rt60 >= 2200:
            early: Literal["dry", "subtle", "prominent"] = "prominent"
            late: Literal["none", "short_decay", "medium_tail", "cavernous"] = "cavernous"
        elif rt60 >= 1200:
            early = "subtle"
            late = "medium_tail"
        elif rt60 >= 500:
            early = "subtle"
            late = "short_decay"
        else:
            early = "dry"
            late = "none"

        return AcousticProfileSpec(
            profile_id=f"acoustics_{env.env_id}",
            room_type=env.category,
            estimated_rt60_ms=rt60,
            early_reflections_intent=early,
            late_reverb_intent=late,
            high_frequency_absorption=env.default_absorption,
            occlusion_state=occlusion_state,
        )


class SpatialGeographyEngine:
    """
    Virtual soundstage coordinate manager enforcing spatial continuity.
    """

    def __init__(self):
        # scene_id -> {entity_name: SpatialMetadata}
        self._scene_staging: Dict[str, Dict[str, SpatialMetadata]] = {}

    def stage_scene_characters(
        self,
        scene_id: str,
        characters: List[str],
    ) -> Dict[str, SpatialMetadata]:
        """
        Stages characters on the stereo azimuth soundstage, enforcing spatial continuity.
        Narrator is strictly locked to center (0.0).
        """
        staged: Dict[str, SpatialMetadata] = {}

        # 1. Narrator is strictly locked to 0.0
        staged["narrator"] = SpatialMetadata(
            azimuth_pan=0.0,
            proximity="normal_room",
            trajectory="static",
        )

        non_narrators = [c for c in characters if c.lower() != "narrator"]

        # Standard dialogic staging geometry:
        # 1 character: center or slight conversational offset
        # 2 characters: left (-0.45) vs right (+0.45)
        # 3 characters: left (-0.55), mid-right (+0.20), far-right (+0.60)
        # 4+ characters: distributed across [-0.70, +0.70]
        count = len(non_narrators)
        if count == 1:
            staged[non_narrators[0]] = SpatialMetadata(
                azimuth_pan=-0.15,
                proximity="close",
                trajectory="static",
            )
        elif count == 2:
            staged[non_narrators[0]] = SpatialMetadata(
                azimuth_pan=-0.45,
                proximity="close",
                trajectory="static",
            )
            staged[non_narrators[1]] = SpatialMetadata(
                azimuth_pan=0.45,
                proximity="close",
                trajectory="static",
            )
        elif count == 3:
            staged[non_narrators[0]] = SpatialMetadata(
                azimuth_pan=-0.55,
                proximity="close",
                trajectory="static",
            )
            staged[non_narrators[1]] = SpatialMetadata(
                azimuth_pan=0.15,
                proximity="normal_room",
                trajectory="static",
            )
            staged[non_narrators[2]] = SpatialMetadata(
                azimuth_pan=0.55,
                proximity="close",
                trajectory="static",
            )
        elif count >= 4:
            step = 1.30 / (count - 1)
            for idx, c in enumerate(non_narrators):
                pan = round(-0.65 + idx * step, 2)
                pan = max(-0.80, min(0.80, pan))
                staged[c] = SpatialMetadata(
                    azimuth_pan=pan,
                    proximity="normal_room" if idx % 2 == 0 else "close",
                    trajectory="static",
                )

        self._scene_staging[scene_id] = staged
        return staged

    def get_entity_position(
        self,
        scene_id: str,
        entity_name: str,
    ) -> SpatialMetadata:
        """
        Retrieves current persistent soundstage position for an entity.
        Preserves continuity across multiple dialogue turns.
        """
        if entity_name.lower() == "narrator":
            return SpatialMetadata(azimuth_pan=0.0, proximity="normal_room", trajectory="static")

        scene_map = self._scene_staging.get(scene_id, {})
        for name, meta in scene_map.items():
            if name.lower() == entity_name.lower():
                return meta

        # Fallback staging if entity wasn't in initial roster
        meta = SpatialMetadata(azimuth_pan=0.25, proximity="normal_room", trajectory="static")
        if scene_id in self._scene_staging:
            self._scene_staging[scene_id][entity_name] = meta
        return meta

    def apply_trajectory(
        self,
        scene_id: str,
        entity_name: str,
        trajectory: SpatialTrajectory,
        target_proximity: Optional[ProximityZone] = None,
    ) -> SpatialMetadata:
        """
        Applies a dynamic movement trajectory to a character, updating spatial state.
        """
        current = self.get_entity_position(scene_id, entity_name)

        new_pan = current.azimuth_pan
        if trajectory == "passing_left_to_right":
            new_pan = 0.50
        elif trajectory == "passing_right_to_left":
            new_pan = -0.50

        prox = target_proximity or current.proximity
        if trajectory == "approaching":
            prox = "close"
        elif trajectory == "retreating":
            prox = "distant"

        updated = SpatialMetadata(
            azimuth_pan=new_pan,
            proximity=prox,
            trajectory=trajectory,
        )

        if scene_id in self._scene_staging:
            self._scene_staging[scene_id][entity_name] = updated

        return updated

    def build_spatial_sources(
        self,
        scene_id: str,
        characters: List[str],
        props: Optional[List[str]] = None,
    ) -> List[SpatialSourceSpec]:
        """
        Produces complete catalog of staged spatial sources for the scene.
        """
        staged_map = self.stage_scene_characters(scene_id, characters)
        sources: List[SpatialSourceSpec] = []

        # Add characters and narrator
        for name, meta in staged_map.items():
            role: Literal["narrator", "character", "prop_object", "creature", "environment_element"] = (
                "narrator" if name.lower() == "narrator" else "character"
            )
            sources.append(
                SpatialSourceSpec(
                    source_id=f"src_{scene_id}_{name.lower()}",
                    entity_name=name,
                    role=role,
                    spatial=meta,
                    is_active=True,
                )
            )

        # Add optional prop objects (e.g. door, hearth, chest)
        if props:
            for p_idx, prop in enumerate(props):
                pan = 0.60 if p_idx % 2 == 0 else -0.60
                sources.append(
                    SpatialSourceSpec(
                        source_id=f"src_{scene_id}_prop_{p_idx+1}",
                        entity_name=prop,
                        role="prop_object",
                        spatial=SpatialMetadata(
                            azimuth_pan=pan,
                            proximity="mid_distance",
                            trajectory="static",
                        ),
                        is_active=True,
                    )
                )

        return sources


_GLOBAL_SPATIAL_ACOUSTICS: Optional[SpatialAcousticsEngine] = None
_GLOBAL_SPATIAL_GEOGRAPHY: Optional[SpatialGeographyEngine] = None

def get_spatial_acoustics_engine() -> SpatialAcousticsEngine:
    """Returns singleton instance of SpatialAcousticsEngine."""
    global _GLOBAL_SPATIAL_ACOUSTICS
    if _GLOBAL_SPATIAL_ACOUSTICS is None:
        _GLOBAL_SPATIAL_ACOUSTICS = SpatialAcousticsEngine()
    return _GLOBAL_SPATIAL_ACOUSTICS

def get_spatial_geography_engine() -> SpatialGeographyEngine:
    """Returns singleton instance of SpatialGeographyEngine."""
    global _GLOBAL_SPATIAL_GEOGRAPHY
    if _GLOBAL_SPATIAL_GEOGRAPHY is None:
        _GLOBAL_SPATIAL_GEOGRAPHY = SpatialGeographyEngine()
    return _GLOBAL_SPATIAL_GEOGRAPHY
