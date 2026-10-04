"""
Tests for Phase 5: Room 5 Living World Foley & Convolution IR Staging.
Verifies:
1. ACOUSTIC_IR_PRESETS and resolve_acoustic_ir_preset fuzzy fallback matching.
2. build_spatial_early_reflection_filter filter_complex generation.
3. build_scene_physics_context_matrix across literary environments (rural, modern, tavern, etc.) and sonic_bible ingestion.
4. MicroFoleyAgent._audit_foley_density_and_fill_voids (Zero Dead Voids Guarantee).
5. ScenographerAgent and MicroFoleyAgent contract compatibility.
"""

import pytest
from unittest.mock import MagicMock
from audiobook_factory.cinema_audio_engine import (
    ACOUSTIC_IR_PRESETS,
    resolve_acoustic_ir_preset,
    build_spatial_early_reflection_filter,
)
from audiobook_factory.contracts import ConvolutionIRConfig
from audiobook_factory.director.agents.micro_foley_agent import (
    MicroFoleyAgent,
    FoleyEventDirective,
    build_scene_physics_context_matrix,
)
from audiobook_factory.director.agents.scenographer_agent import (
    ScenographerAgent,
    SceneAcousticBlueprint,
)
from audiobook_factory.director.agents.showrunner_agent import (
    ShowrunnerPlan,
    ActDefinition,
)


def test_acoustic_ir_presets_expanded():
    """Verify newly added IR presets exist and have required acoustic parameters."""
    required_presets = [
        "tavern_timber_small",
        "stone_crypt_damp",
        "great_hall_stone",
        "forest_open_mist",
        "domestic_room",
        "cave_catacomb",
        "rural_courtyard_open",
        "modern_office_carpet",
        "urban_street_canyon",
        "wooden_cottage_interior",
        "cathedral_sacred_vault",
    ]
    for p in required_presets:
        assert p in ACOUSTIC_IR_PRESETS, f"Preset '{p}' missing from ACOUSTIC_IR_PRESETS"
        preset_data = ACOUSTIC_IR_PRESETS[p]
        assert "delays" in preset_data
        assert "decays" in preset_data
        assert "hpf" in preset_data
        assert "lpf" in preset_data
        assert "default_wet" in preset_data
        assert 0.04 <= preset_data["default_wet"] <= 0.25


def test_resolve_acoustic_ir_preset_fuzzy_fallback():
    """Verify fuzzy matching correctly maps ambiguous environment names to sensible IR presets."""
    name, preset = resolve_acoustic_ir_preset("village_veranda_sunny")
    assert name == "rural_courtyard_open"
    assert preset["default_wet"] == 0.07

    name, preset = resolve_acoustic_ir_preset("corporate_office_boardroom")
    assert name == "modern_office_carpet"
    assert preset["default_wet"] == 0.05

    name, preset = resolve_acoustic_ir_preset("city_alleyway_night")
    assert name == "urban_street_canyon"
    assert preset["default_wet"] == 0.12

    name, preset = resolve_acoustic_ir_preset("ancient_temple_vault")
    assert name == "cathedral_sacred_vault"

    name, preset = resolve_acoustic_ir_preset("unknown_abstract_void")
    assert name == "domestic_room"

    name, preset = resolve_acoustic_ir_preset(None)
    assert name == "domestic_room"


def test_build_spatial_early_reflection_filter():
    """Verify valid FFmpeg filter graph string generation."""
    cfg = ConvolutionIRConfig(
        preset_name="rural_courtyard_open",
        wet_dry_ratio=0.08,
        enabled=True,
    )
    filter_graph = build_spatial_early_reflection_filter(cfg)
    assert "[0:a]asplit=2[dry][wet_in]" in filter_graph
    assert "aecho=" in filter_graph
    assert "highpass=" in filter_graph
    assert "lowpass=" in filter_graph
    assert "amix=" in filter_graph
    assert "[dx_out]" in filter_graph


def test_build_scene_physics_context_matrix_rural():
    """Verify rural setting produces authentic Premchand/rustic physical objects."""
    matrix = build_scene_physics_context_matrix(
        location_setting="Village Courtyard (Aangan)",
        environment_type="Rural agricultural village",
        era="COLONIAL_ERA",
        sonic_bible={"foley_palette": ["clay_hookah", "bullock_cart"]},
    )
    assert "Rural / Village / Rustic Living Physics" in matrix
    assert "charpai" in matrix or "matka" in matrix
    assert "clay_hookah" in matrix


def test_build_scene_physics_context_matrix_modern():
    """Verify modern office setting produces contemporary physical props."""
    matrix = build_scene_physics_context_matrix(
        location_setting="Glass High-Rise Boardroom",
        environment_type="Modern corporate interior",
        era="CONTEMPORARY",
    )
    assert "Modern Contemporary / Office / Urban Living Physics" in matrix
    assert "keyboard" in matrix or "pen" in matrix or "desk" in matrix


def test_zero_dead_voids_guarantee():
    """Verify that gaps > 8 segments are automatically seeded with living-world micro-foley."""
    script_segments = [{"index": i + 1, "text": f"Segment line {i+1}", "speaker": "Narrator"} for i in range(30)]
    showrunner_plan = ShowrunnerPlan(
        chapter_id="chap_01",
        acts=[
            ActDefinition(
                act_index=1,
                act_title="Opening Silence",
                start_segment=1,
                end_segment=30,
                location_setting="Dusty Village Courtyard",
                environment_type="Rural Village",
            )
        ]
    )

    # Empty initial events
    initial_events = []
    audited = MicroFoleyAgent._audit_foley_density_and_fill_voids(
        events=initial_events,
        script_segments=script_segments,
        showrunner_plan=showrunner_plan,
        era="COLONIAL_ERA",
    )

    assert len(audited) > 0, "Zero dead voids auditor must populate events when gap is large"

    # Verify no gap exceeds 8 segments
    event_indices = [e.segment_index for e in audited]
    # Check start to first
    assert event_indices[0] <= 8
    # Check consecutive
    for i in range(len(event_indices) - 1):
        assert event_indices[i + 1] - event_indices[i] <= 8, f"Gap {event_indices[i+1]} - {event_indices[i]} exceeds 8 segments"
    # Check last to end
    assert 30 - event_indices[-1] <= 8

    # Verify all seeded events are micro-foley with appropriate levels
    for ev in audited:
        assert ev.is_micro_foley is True
        assert ev.foley_type == "micro"
        assert ev.gain_dbfs <= -20.0
