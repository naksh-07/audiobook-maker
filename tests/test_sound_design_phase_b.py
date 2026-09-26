#!/usr/bin/env python3
"""
Unit and Integration Tests for Sound Design Phase B:
Atmosphere, Evolution, Walla & Negative Sound Design (Capabilities 04, 05, 06, 16).
"""

import pytest
from audiobook_factory.sound_design.ambience_engine import AmbienceEngine, get_ambience_engine
from audiobook_factory.sound_design.walla_engine import WallaEngine, get_walla_engine
from audiobook_factory.sound_design.silence_engine import SilenceEngine, get_silence_engine
from audiobook_factory.sound_design.contracts import (
    SceneAudioUnderstandingResult,
    AmbienceLayerSpec,
    WallaLayerSpec,
    SilenceEventSpec,
)
from audiobook_factory.dramaturgy.contracts import DramaticSilenceIntent


def test_ambience_engine_layering_and_evolution():
    engine = AmbienceEngine()

    # Scene 1: Castle stone corridor, calm
    layers_s1 = engine.build_scene_ambience(
        scene_id="scene_001",
        chapter_id="chap_01",
        environment_id="castle_stone_corridor",
        start_ms=0,
        end_ms=15000,
        tension_level=0.3,
        mood="calm",
    )

    assert len(layers_s1) >= 2
    base_tier = [l for l in layers_s1 if l.layer_tier == "BASE"]
    assert len(base_tier) == 1
    assert base_tier[0].loop is True
    assert base_tier[0].mix_intent.duck_under_dialogue is False  # Bed tone stays stable

    # Scene 2: Continuing in Castle stone corridor, rising tension
    layers_s2 = engine.build_scene_ambience(
        scene_id="scene_002",
        chapter_id="chap_01",
        environment_id="castle_stone_corridor",
        start_ms=15000,
        end_ms=30000,
        tension_level=0.75,
        mood="tense",
        previous_scene_id="scene_001",
    )

    base_tier_2 = [l for l in layers_s2 if l.layer_tier == "BASE"]
    assert len(base_tier_2) == 1
    # Preserves seamless bedrock continuity
    assert base_tier_2[0].asset_path == base_tier[0].asset_path


def test_ambience_to_scene_acoustic_profile():
    engine = get_ambience_engine()
    layers = engine.build_scene_ambience(
        scene_id="scene_profile_test",
        chapter_id="chap_01",
        environment_id="castle_great_hall",
        start_ms=0,
        end_ms=20000,
        tension_level=0.5,
    )

    profile = engine.to_scene_acoustic_profile(
        scene_id="scene_profile_test",
        start_ms=0,
        end_ms=20000,
        environment_id="castle_great_hall",
        layers=layers,
        act_index=1,
    )

    assert profile.scene_id == "scene_profile_test"
    assert profile.environment_id == "castle_great_hall"
    assert len(profile.layers) <= 4  # Stems capped for cinema stem engine compatibility
    assert profile.ir_preset in ("room", "hall")


def test_walla_engine_generation_and_restraint():
    walla_engine = get_walla_engine()

    # 1. Tavern scene with crowd -> should generate walla
    walla_tavern = walla_engine.build_scene_walla(
        scene_id="scene_tavern_01",
        environment_id="tavern_common_room",
        characters_present=["Barkeep", "Traveler", "Guard", "Patron1", "Patron2"],
        scene_text="The patrons cheered and raised their tankards as murmurs spread across the crowded tavern.",
        tension_level=0.4,
        dominant_emotion="joyful",
        requires_walla=True,
    )

    assert walla_tavern is not None
    assert walla_tavern.activity_type in ("tavern_murmur", "festival_cheering")
    assert walla_tavern.mix_intent.duck_under_dialogue is True
    assert walla_tavern.relative_intensity in ("subtle_bed", "whisper_quiet")

    # Legacy conversion check
    legacy_layer = walla_engine.to_legacy_ambience_layer(walla_tavern)
    assert legacy_layer.layer_type == "crowd_wallah"
    assert legacy_layer.loop is True

    # 2. Solitary dark forest scene with 1 character -> strictly suppressed
    walla_forest = walla_engine.build_scene_walla(
        scene_id="scene_forest_01",
        environment_id="dark_forest",
        characters_present=["LoneWanderer"],
        scene_text="He walked alone through the deserted trees in hushed solitude.",
        tension_level=0.5,
    )

    assert walla_forest is None  # Restraint enforced!

    # 3. Solitary crypt scene -> strictly suppressed
    walla_crypt = walla_engine.build_scene_walla(
        scene_id="scene_crypt_01",
        environment_id="crypt_subterranean",
        characters_present=["Hero", "Rival"],
        scene_text="They faced each other in the ancient silent tomb, not a soul in sight.",
        tension_level=0.7,
    )

    assert walla_crypt is None  # Restraint enforced!


def test_silence_engine_adaptive_budget_and_events():
    silence_engine = get_silence_engine()

    # 1. High restraint budget for stealth / crypt
    budget_stealth = silence_engine.calculate_adaptive_silence_budget(
        tension_level=0.25,
        environment_type="crypt_subterranean",
        dominant_emotion="secretive",
    )
    assert budget_stealth["restraint_tier"] == "high"
    assert budget_stealth["target_silence"] >= 0.50

    # 2. Dense action budget for battle
    budget_action = silence_engine.calculate_adaptive_silence_budget(
        tension_level=0.90,
        environment_type="battlefield_siege",
        dominant_emotion="terror",
    )
    assert budget_action["restraint_tier"] == "dense"
    assert budget_action["min_density"] >= 0.50

    # 3. Plan silence events from scene understanding & dramaturgy
    understanding = SceneAudioUnderstandingResult(
        scene_id="sc_silence_test",
        chapter_id="chap_01",
        environment_type="castle_corridor",
        tension_level=0.75,
        dominant_emotion="suspense",
        silence_opportunities=[
            "Sudden ambient drop before the shadow turns the corner",
            "Music drop on the final revelation",
        ],
    )

    beats = [
        {
            "start_ms": 12000,
            "duration_ms": 2000,
            "silence_intent": DramaticSilenceIntent(
                purpose="shock",
                dramatic_rationale="Protagonist discovers the forged seal.",
                listening_focus="character_reaction",
            ),
        }
    ]

    events = silence_engine.plan_silence_events(
        scene_id="sc_silence_test",
        scene_understanding=understanding,
        start_ms=0,
        end_ms=25000,
        dramatic_beats=beats,
    )

    assert len(events) >= 2
    purposes = [ev.purpose for ev in events]
    assert "music_drop_impact" in purposes
    assert "ambient_drop_suspense" in purposes


def test_silence_engine_evaluate_scene_density_no_rigid_failure():
    silence_engine = get_silence_engine()

    # Test moderate restraint scene with 40% active sound (60% silence)
    res_mod = silence_engine.evaluate_scene_density(
        total_duration_ms=100000,
        active_sound_spans=[(10000, 30000), (50000, 70000)],
        restraint_target="moderate",
    )
    assert res_mod["compliant"] is True
    assert res_mod["density"] == 0.4
    assert res_mod["silence_ratio"] == 0.6

    # Test dense action scene with 75% active sound (25% silence)
    res_dense = silence_engine.evaluate_scene_density(
        total_duration_ms=100000,
        active_sound_spans=[(0, 40000), (45000, 80000)],
        restraint_target="dense",
    )
    # Under an arbitrary universal >=60% silence rule, 75% sound would be falsely failed!
    # Under adaptive scene-dependent density, this is compliant for dense action.
    assert res_dense["compliant"] is True
    assert res_dense["target_restraint"] == "dense"
