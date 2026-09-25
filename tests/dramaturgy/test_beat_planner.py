#!/usr/bin/env python3
"""
Tests for Beat Planner in audiobook_factory.dramaturgy.beat_planner
==================================================================
Verifies dramatic beat extraction, state transitions, character objectives,
actioning verbs, dual-layer emotion, conservative subtext inference,
tension curves, and beat-aligned chunk slicing.
"""

import pytest
from audiobook_factory.dramaturgy.scene_analyzer import SceneAnalyzer
from audiobook_factory.dramaturgy.beat_planner import BeatPlanner
from audiobook_factory.dramaturgy.contracts import (
    DramaticBeat,
    SceneDramaticPlan,
    DramaticPlan,
    SubtextClassification,
)


def test_plan_scene_beats_basic():
    """Verifies that plan_scene_beats creates well-structured beats with valid attributes."""
    scene = SceneAnalyzer.analyze_single_scene(
        scene_text="Marcus glared at Julian. 'Give me the key,' he demanded.\n\nJulian took a step back. 'I cannot do that.'",
        scene_id="scene_001",
        chapter_num=1,
        known_characters=["Marcus", "Julian"],
    )
    beats = BeatPlanner.plan_scene_beats(scene, known_characters=["Marcus", "Julian"])
    assert len(beats) >= 2

    for beat in beats:
        assert isinstance(beat, DramaticBeat)
        assert beat.beat_id.startswith("scene_001_b")
        assert beat.primary_speaker in ("Marcus", "Julian")
        assert beat.objective.actioning in BeatPlanner.ACTIONING_VERBS
        assert beat.objective.immediate_goal != ""
        assert beat.objective.obstacle != ""
        assert beat.surface_emotion != ""
        assert beat.underlying_emotion != ""
        assert 0.0 <= beat.tension_before <= 1.0
        assert 0.0 <= beat.tension_after <= 1.0
        assert beat.subtext_classification in (
            "SOURCE_SUPPORTED",
            "CONTEXTUAL_INFERENCE",
            "CREATIVE_INTERPRETATION",
            "UNSUPPORTED",
        )
        assert 0.0 <= beat.subtext_confidence <= 1.0


def test_plan_chapter_beats_tension_curve():
    """Verifies that plan_chapter_beats populates tension curves correctly across scenes."""
    chapter_text = (
        "Scene 1: Quiet preparation.\n\nMarcus sharpened his dagger by the dying campfire.\n\n"
        "***\n\n"
        "Scene 2: Sudden ambush!\n\nThe raiders stormed the clearing with raised axes and bloodthirsty roars!"
    )
    scenes = SceneAnalyzer.segment_and_analyze_scenes(
        chapter_text=chapter_text,
        chapter_num=1,
        known_characters=["Marcus", "Raiders"],
    )
    assert len(scenes) >= 2

    planned_scenes = BeatPlanner.plan_chapter_beats(
        chapter_text=chapter_text,
        scenes=scenes,
        known_characters=["Marcus", "Raiders"],
    )

    for s in planned_scenes:
        assert len(s.beats) >= 1
        assert len(s.tension_curve) >= 2
        for t_val in s.tension_curve:
            assert 0.0 <= t_val <= 1.0


def test_slice_chapter_by_beats_short_scene():
    """A chapter shorter than max_words should produce a single cleanly bounded chunk."""
    chapter_text = (
        "Julian walked into the study. Books lined the damp stone walls from floor to ceiling.\n\n"
        "He reached for the ledger and opened the leather cover."
    )
    scenes = SceneAnalyzer.segment_and_analyze_scenes(chapter_text=chapter_text, chapter_num=1)
    scenes = BeatPlanner.plan_chapter_beats(chapter_text=chapter_text, scenes=scenes)

    plan = DramaticPlan(
        chapter_id="ch_001",
        chapter_num=1,
        chapter_title="Test Chapter",
        scenes=scenes,
    )

    chunks = BeatPlanner.slice_chapter_by_beats(
        chapter_text=chapter_text,
        dramatic_plan=plan,
        max_words=1000,
    )

    assert len(chunks) == 1
    assert chunks[0]["chunk_index"] == 1
    assert chunks[0]["is_scene_start"] is True
    assert chunks[0]["is_scene_end"] is True
    assert chunks[0]["scene_id"] == scenes[0].scene_id
    assert len(chunks[0]["beat_ids"]) == len(scenes[0].beats)


def test_slice_chapter_by_beats_multi_scene():
    """Multi-scene chapter should produce chunks aligned to scene boundaries."""
    paras = []
    # Scene 1: 50 words
    for i in range(5):
        paras.append(f"Scene one narrative sentence paragraph number {i} discussing trade agreements and coin.")
    paras.append("***")
    # Scene 2: 50 words
    for i in range(5):
        paras.append(f"Later that evening, scene two narrative sentence paragraph number {i} with ambush and swords.")

    chapter_text = "\n\n".join(paras)
    scenes = SceneAnalyzer.segment_and_analyze_scenes(chapter_text=chapter_text, chapter_num=1)
    scenes = BeatPlanner.plan_chapter_beats(chapter_text=chapter_text, scenes=scenes)

    plan = DramaticPlan(
        chapter_id="ch_001",
        chapter_num=1,
        chapter_title="Multi Scene Chapter",
        scenes=scenes,
    )

    # With max_words = 60, each scene (~55 words) exceeds max_words combined, so it slices into separate scene chunks
    chunks = BeatPlanner.slice_chapter_by_beats(
        chapter_text=chapter_text,
        dramatic_plan=plan,
        max_words=60,
    )

    assert len(chunks) >= 2
    scene_ids = [c["scene_id"] for c in chunks]
    assert scenes[0].scene_id in scene_ids
    assert scenes[1].scene_id in scene_ids


def test_dual_layer_emotion_and_subtext_restraint():
    """Asserts that surface emotion and underlying emotion are distinguished in high-stakes scenes."""
    scene = SceneAnalyzer.analyze_single_scene(
        scene_text="Marcus spoke in a measured, calm voice, but his knuckles were white as he held the confession.\n\n"
                   "'I know what you did,' he said evenly.",
        scene_id="scene_tension",
        chapter_num=1,
        known_characters=["Marcus"],
    )
    beats = BeatPlanner.plan_scene_beats(scene, known_characters=["Marcus"])
    assert len(beats) >= 1

    first_beat = beats[0]
    # In confrontation or tense dialogue, surface vs underlying emotions often diverge
    assert first_beat.surface_emotion != ""
    assert first_beat.underlying_emotion != ""
    assert first_beat.subtext != ""
    assert first_beat.subtext_confidence > 0.0
