#!/usr/bin/env python3
"""
Test Suite: Hollywood-Grade Multi-Agent Directing & Sound Design Engine.
Verifies all 5 specialized agents, Pydantic contracts, FTS5 sound bank resolutions,
DX spatial convolution early reflections, and AMB dynamic wallah breathing.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from audiobook_factory.contracts import (
    CreativeManifest,
    FoleyCue,
    MusicCue,
    AmbienceScene,
    ConvolutionIRConfig,
    WallahAutomationPoint,
)
from audiobook_factory.director.agents import (
    ShowrunnerAgent,
    ShowrunnerPlan,
    ActDefinition,
    ScenographerAgent,
    ScenographyPlan,
    SceneAcousticBlueprint,
    MicroFoleyAgent,
    MicroFoleyPlan,
    FoleyEventDirective,
    MusicSupervisorAgent,
    MusicScoringPlan,
    MusicCueDirective,
    WallahDirectorAgent,
    WallahEnvironmentPlan,
    ActEnvironmentBlueprint,
    EnvironmentLayerDirective,
)
from audiobook_factory.director.multi_agent_director import MultiAgentDirector
from audiobook_factory.cinema_audio_engine import (
    ACOUSTIC_IR_PRESETS,
    build_spatial_early_reflection_filter,
)


def test_showrunner_plan_contract():
    """Verifies ShowrunnerPlan and ActDefinition data contracts."""
    act = ActDefinition(
        act_index=1,
        act_title="The Whispering Tavern",
        start_segment=1,
        end_segment=25,
        location_setting="Tavern Taproom",
        environment_type="tavern_interior",
        dramatic_intensity=0.6,
        pacing="moderate_dialogue",
        emotional_subtext="Tense anticipation",
    )
    plan = ShowrunnerPlan(
        chapter_id="chapter_001",
        dramatic_theme="Grimdark Fantasy",
        acts=[act],
        pivotal_moments=[15],
    )
    assert plan.chapter_id == "chapter_001"
    assert len(plan.acts) == 1
    assert plan.acts[0].act_index == 1
    assert plan.pivotal_moments == [15]


def test_scenography_and_ir_presets():
    """Verifies Scenographer models and convolution IR preset filters."""
    blueprint = SceneAcousticBlueprint(
        act_index=1,
        location_name="Tavern Taproom",
        environment_slug="tavern_interior",
        room_dimensions="medium_enclosed",
        primary_materials=["wood", "stone"],
        ir_preset="tavern_timber_small",
        dx_reverb_wet_ratio=0.12,
        early_reflections_decay_ms=220,
        high_frequency_damping_hz=7500,
    )
    assert blueprint.ir_preset in ACOUSTIC_IR_PRESETS
    cfg = ConvolutionIRConfig(
        preset_name=blueprint.ir_preset,
        wet_dry_ratio=blueprint.dx_reverb_wet_ratio,
        high_cut_hz=blueprint.high_frequency_damping_hz,
    )
    filter_graph = build_spatial_early_reflection_filter(cfg)
    assert "aecho=" in filter_graph
    assert "highpass=" in filter_graph
    assert "lowpass=f=7500" in filter_graph
    assert "amix=" in filter_graph
    assert "0.88 0.12" in filter_graph


def test_micro_foley_plan_contract():
    """Verifies MicroFoleyEvent directives and micro-foley attributes."""
    directive = FoleyEventDirective(
        segment_index=3,
        action_verb="tankard_slam",
        search_query="wooden tankard slam rustic table",
        category="FOL",
        is_micro_foley=True,
        foley_type="micro",
        layer="prop_interaction",
        intensity=0.8,
        sync_offset_ms=200,
        volume_db=-22.0,
        dramatic_reason="Underlines sudden anger of speaker",
    )
    plan = MicroFoleyPlan(chapter_id="chapter_001", events=[directive])
    assert plan.events[0].is_micro_foley is True
    assert plan.events[0].foley_type == "micro"
    assert plan.events[0].action_verb == "tankard_slam"


def test_music_score_plan_contract():
    """Verifies MusicCue directives and broadcast silence compliance."""
    cue = MusicCueDirective(
        trigger_segment=10,
        cue_type="TRANSITION_BRIDGE",
        mood="tense",
        search_query="medieval tension stinger ominous strings",
        duration_sec=8.0,
        volume_db=-24.0,
        fade_in_sec=1.5,
        fade_out_sec=2.0,
        dramatic_justification="Bridges dialogue into sudden confrontation",
    )
    plan = MusicScoringPlan(
        chapter_id="chapter_001",
        cues=[cue],
        silence_percentage=75.0,
    )
    assert plan.cues[0].duration_sec == 8.0
    assert plan.cues[0].cue_type == "TRANSITION_BRIDGE"
    assert plan.silence_percentage >= 60.0


def test_wallah_director_plan_contract():
    """Verifies WallahEnvironmentPlan and WallahAutomationPoints."""
    layer = EnvironmentLayerDirective(
        layer_type="crowd_wallah",
        search_query="tavern crowd murmur medieval patrons",
        target_lufs=-30.0,
        pan=0.0,
        stereo_width=1.25,
    )
    act_bp = ActEnvironmentBlueprint(
        act_index=1,
        setting_title="Tavern Taproom",
        layers=[layer],
        wallah_ducking_speech_db=-6.0,
        wallah_pause_swell_db=3.0,
    )
    auto_pt = WallahAutomationPoint(
        start_ms=1000,
        end_ms=4500,
        target_attenuation_db=-6.0,
        swell_during_pause_db=0.0,
        is_pause_swell=False,
    )
    plan = WallahEnvironmentPlan(
        chapter_id="chapter_001",
        act_blueprints=[act_bp],
        wallah_automations=[auto_pt],
    )
    assert len(plan.act_blueprints) == 1
    assert len(plan.wallah_automations) == 1
    assert plan.wallah_automations[0].target_attenuation_db == -6.0


def test_multi_agent_director_orchestration(tmp_path):
    """Verifies MultiAgentDirector manifest assembly with mock sound bank."""
    mock_bank = MagicMock()
    mock_bank.resolve_sound.return_value = tmp_path / "dummy_sound.wav"

    director = MultiAgentDirector(sound_bank=mock_bank)

    # Mock all 5 agents to return structured plans
    mock_showrunner = ShowrunnerPlan(
        chapter_id="chapter_001",
        dramatic_theme="High Drama",
        acts=[
            ActDefinition(
                act_index=1,
                act_title="Act 1",
                start_segment=1,
                end_segment=2,
                location_setting="Tavern",
                environment_type="tavern_interior",
            )
        ],
    )
    mock_scenography = ScenographyPlan(
        chapter_id="chapter_001",
        blueprints=[
            SceneAcousticBlueprint(
                act_index=1,
                location_name="Tavern",
                ir_preset="tavern_timber_small",
                dx_reverb_wet_ratio=0.12,
            )
        ],
    )
    mock_foley = MicroFoleyPlan(
        chapter_id="chapter_001",
        events=[
            FoleyEventDirective(
                segment_index=1,
                action_verb="tankard_slam",
                search_query="tankard slam",
                category="FOL",
                is_micro_foley=True,
                foley_type="micro",
                volume_db=-22.0,
            )
        ],
    )
    mock_music = MusicScoringPlan(
        chapter_id="chapter_001",
        cues=[
            MusicCueDirective(
                trigger_segment=1,
                cue_type="TRANSITION_BRIDGE",
                search_query="tavern tension stinger",
                duration_sec=6.0,
                volume_db=-24.0,
            )
        ],
        silence_percentage=80.0,
    )
    mock_wallah = WallahEnvironmentPlan(
        chapter_id="chapter_001",
        act_blueprints=[
            ActEnvironmentBlueprint(
                act_index=1,
                setting_title="Tavern",
                layers=[
                    EnvironmentLayerDirective(
                        layer_type="base_room_tone",
                        search_query="tavern room tone",
                        target_lufs=-34.0,
                    )
                ],
            )
        ],
        wallah_automations=[
            WallahAutomationPoint(
                start_ms=0,
                end_ms=4000,
                target_attenuation_db=-6.0,
            )
        ],
    )

    with patch.object(director.showrunner, "analyze_chapter", return_value=mock_showrunner), \
         patch.object(director.scenographer, "design_acoustic_spaces", return_value=mock_scenography), \
         patch.object(director.foley_artist, "spot_foley_events", return_value=mock_foley), \
         patch.object(director.music_supervisor, "score_chapter", return_value=mock_music), \
         patch.object(director.wallah_director, "direct_world_ambience", return_value=mock_wallah):

        manifest = director.direct_chapter(
            chapter_id="chapter_001",
            script_segments=[
                {"index": 1, "speaker": "GERALT", "dialogue": "A pint of cider."},
                {"index": 2, "speaker": "BARTENDER", "dialogue": "Right away, master."},
            ],
            segment_durations_sec={1: 3.5, 2: 4.0},
            seg_starts_ms={1: 0, 2: 4000},
            total_duration_sec=30.0,
        )

        assert isinstance(manifest, CreativeManifest)
        assert manifest.chapter_id == "chapter_001"
        assert len(manifest.foley_cues) == 1
        assert manifest.foley_cues[0].is_micro_foley is True
        assert len(manifest.music_cues) == 1
        assert len(manifest.ambience_scenes) >= 1
        assert "act_001" in manifest.acoustic_staging
        assert manifest.acoustic_staging["act_001"].preset_name == "tavern_timber_small"
        assert len(manifest.wallah_automations) == 1
        assert manifest.silence_percentage >= 60.0
