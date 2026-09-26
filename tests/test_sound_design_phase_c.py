#!/usr/bin/env python3
"""
Unit and Integration Tests for Sound Design Phase C:
Physical World, Character Physics, Material Matrix, Hard SFX & Creatures (Capabilities 07, 08, 09, 10, 12).
"""

import pytest
from audiobook_factory.sound_design.contracts import (
    ActionCandidate,
    CharacterPhysicalProfile,
)
from audiobook_factory.sound_design.foley_engine import FoleyEngine, get_foley_engine
from audiobook_factory.sound_design.foley_character_material import (
    MaterialMatrixEngine,
    CharacterFoleyRegistry,
    get_character_foley_registry,
)
from audiobook_factory.sound_design.narrative_sfx import (
    HardSFXEngine,
    CreatureSoundEngine,
    get_hard_sfx_engine,
    get_creature_engine,
)


def test_foley_relevance_scoring_and_low_value_rejection():
    engine = FoleyEngine()

    # 1. High value narrative action: drawing sword
    sword_draw = ActionCandidate(
        segment_index=1,
        subject="Geralt",
        action_verb="drew",
        object_material="steel_sword",
        anchor_word="drew",
    )
    res_sword = engine.evaluate_candidate(sword_draw, tension_level=0.8, restraint_target="moderate")
    assert res_sword.status == "ACCEPTED"
    assert res_sword.foley_score >= 0.65
    assert res_sword.rejection_reason is None

    # 2. Low-value trivial verb: blinking
    blink_cand = ActionCandidate(
        segment_index=2,
        subject="Character",
        action_verb="blinked",
        object_material="",
        anchor_word="blinked",
    )
    res_blink = engine.evaluate_candidate(blink_cand, tension_level=0.2, restraint_target="high")
    assert res_blink.status in ("REJECTED_TRIVIAL", "REJECTED_RESTRAINT")
    assert res_blink.rejection_reason is not None

    # 3. Low-value trivial verb: sighing
    sigh_cand = ActionCandidate(
        segment_index=3,
        subject="Character",
        action_verb="sighed",
        object_material="",
        anchor_word="sighed",
    )
    res_sigh = engine.evaluate_candidate(sigh_cand, tension_level=0.3, restraint_target="moderate")
    assert res_sigh.status in ("REJECTED_TRIVIAL", "REJECTED_RESTRAINT")

    # 4. Conversion to legacy FoleyCue
    cues = engine.to_legacy_foley_cues([res_sword, res_blink])
    assert len(cues) == 1  # Only accepted cue is converted
    assert cues[0].segment_index == 1
    assert cues[0].ucs_category == "WEAPSwd"
    assert cues[0].anchor_word == "drew"


def test_material_matrix_tableware_isolation():
    matrix = MaterialMatrixEngine()

    # Standard interaction: steel on stone
    steel_res = matrix.resolve_surface_interaction("steel_sword", "stone_flagstone", energy=0.7)
    assert steel_res["ucs_category"] == "WEAPSwd"

    # Crucial Invariant: Tableware isolation prevents banquet dining from sounding like weapon clashes!
    tableware_res = matrix.resolve_surface_interaction("ceramic_plate", "wood_table", energy=0.5)
    assert tableware_res["ucs_category"] == "DOMETabl"

    # Conflicting ambiguous prompt (e.g. blade on plate or fork clash)
    collision_check = matrix.is_weapon_vs_tableware_collision("knife_blade", "ceramic_plate")
    assert collision_check is True

    forced_tableware = matrix.resolve_surface_interaction("knife_blade", "ceramic_plate", energy=0.5)
    # Must force DOMETabl to protect the listener from armory sword sounds during breakfast!
    assert forced_tableware["ucs_category"] == "DOMETabl"


def test_character_physics_foley_registry():
    registry = get_character_foley_registry()

    # Heavy knight profile
    heavy_knight = CharacterPhysicalProfile(
        character_name="SerGregor",
        body_mass="imposing_heavy",
        footwear="heavy_boots",
        equipment_weight="full_plate",
        physical_condition="normal",
    )
    registry.register_character(heavy_knight)

    # Stealth rogue profile
    stealth_rogue = CharacterPhysicalProfile(
        character_name="Arya",
        body_mass="lean_agile",
        footwear="light_leather",
        equipment_weight="unencumbered",
        physical_condition="stealthy_stalking",
    )
    registry.register_character(stealth_rogue)

    foley_knight = registry.resolve_movement_foley("SerGregor", surface="stone_flagstone", movement_pace="walk")
    foley_rogue = registry.resolve_movement_foley("Arya", surface="carpet_rug", movement_pace="walk")

    assert foley_knight["relative_intensity"] == "prominent"
    assert foley_knight["armor_layer"] == "plate_metal_clank"

    assert foley_rogue["relative_intensity"] == "whisper_quiet"
    assert foley_rogue["armor_layer"] is None


def test_hard_sfx_and_creature_engines():
    hard_sfx = get_hard_sfx_engine()
    creature_engine = get_creature_engine()

    segments = [
        {
            "segment_index": 1,
            "text": "The heavy iron gate slammed shut with a deafening reverberation.",
            "sfx_cues": ["gate slammed shut"],
            "start_ms": 1000,
        },
        {
            "segment_index": 2,
            "text": "From the shadowy recesses, the striga roared in fury, its talons raking the wet flagstones.",
            "sfx_cues": [],
            "start_ms": 5000,
        },
        {
            "segment_index": 3,
            "text": "A sudden explosion detonated near the perimeter, bursting the carriage apart.",
            "sfx_cues": ["explosion"],
            "start_ms": 12000,
        },
    ]

    # 1. Hard SFX
    sfx_events = hard_sfx.detect_events_from_segments(segments, tension_level=0.8)
    assert len(sfx_events) >= 2
    types = [e.sfx_type for e in sfx_events]
    assert "door_gate_slam" in types
    assert "explosion_concussive" in types
    assert any(e.has_lfe_sub_bass for e in sfx_events)

    # 2. Creature audio
    creature_events = creature_engine.detect_creature_events(segments, creature_presence="striga", tension_level=0.85)
    assert len(creature_events) >= 1
    assert creature_events[0].creature_type == "striga"
    assert creature_events[0].element in ("vocalization", "locomotion_step")
    assert creature_events[0].priority in ("HIGH", "CRITICAL")
