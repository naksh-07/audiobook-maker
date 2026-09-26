#!/usr/bin/env python3
"""
Unit and Integration Tests for Sound Design Phase F:
Acoustic Environment & Spatial Geography (Capabilities 17, 18).
"""

import pytest
from audiobook_factory.sound_design.spatial_acoustics import (
    SpatialAcousticsEngine,
    SpatialGeographyEngine,
    get_spatial_acoustics_engine,
    get_spatial_geography_engine,
)


def test_spatial_acoustics_profile_resolution():
    engine = get_spatial_acoustics_engine()

    # Castle corridor (reverberant hall)
    corridor_spec = engine.build_acoustic_profile_spec("castle_stone_corridor")
    assert corridor_spec.estimated_rt60_ms >= 2000
    assert corridor_spec.late_reverb_intent == "cavernous"
    assert corridor_spec.early_reflections_intent == "prominent"

    # Bedchamber / small room (dry / short)
    bedchamber_spec = engine.build_acoustic_profile_spec("castle_bedchamber")
    assert bedchamber_spec.estimated_rt60_ms < 1500
    assert bedchamber_spec.late_reverb_intent in ("short_decay", "medium_tail")


def test_spatial_geography_soundstage_and_continuity():
    geo = SpatialGeographyEngine()
    scene_id = "sc_staging_test"

    # Stage two characters + narrator
    staged = geo.stage_scene_characters(scene_id, ["Harry", "Hermione", "Narrator"])

    # 1. Narrator must be locked to 0.0
    assert staged["narrator"].azimuth_pan == 0.0
    assert staged["narrator"].proximity == "normal_room"

    # 2. Characters positioned left and right within [-0.8, +0.8]
    assert staged["Harry"].azimuth_pan == -0.45
    assert staged["Hermione"].azimuth_pan == 0.45

    # 3. Spatial Continuity across turns: position remains stable
    pos_harry = geo.get_entity_position(scene_id, "Harry")
    assert pos_harry.azimuth_pan == -0.45

    # 4. Trajectory application: Harry approaches
    updated = geo.apply_trajectory(scene_id, "Harry", "approaching")
    assert updated.trajectory == "approaching"
    assert updated.proximity == "close"

    # 5. Build full spatial source catalog with props
    sources = geo.build_spatial_sources(scene_id, ["Harry", "Hermione"], props=["heavy_oak_door"])
    assert len(sources) >= 4  # Narrator + Harry + Hermione + Door
    roles = [s.role for s in sources]
    assert "narrator" in roles
    assert "character" in roles
    assert "prop_object" in roles
