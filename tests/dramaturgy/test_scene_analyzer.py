#!/usr/bin/env python3
"""
Tests for Scene Analyzer in audiobook_factory.dramaturgy.scene_analyzer
====================================================================
Verifies scene boundary discovery, dramatic question/stakes derivation,
conflict extraction, character detection, and complexity scoring.
"""

import pytest
from audiobook_factory.dramaturgy.scene_analyzer import SceneAnalyzer
from audiobook_factory.dramaturgy.contracts import SceneDramaticPlan, SceneType, DramaticComplexity


def test_segment_empty_chapter():
    """Empty chapter should return empty scene list."""
    scenes = SceneAnalyzer.segment_and_analyze_scenes("")
    assert scenes == []
    scenes_ws = SceneAnalyzer.segment_and_analyze_scenes("   \n\n   ")
    assert scenes_ws == []


def test_discover_scene_boundaries_explicit_divider():
    """Explicit dividers like *** or --- should trigger new scene boundaries."""
    paras = [
        "The sun rose over the silent village. Smoke curled from stone chimneys.",
        "A merchant hitched his horses, whispering curses at the heavy cart.",
        "He counted the copper coins in his leather pouch, wondering if it would suffice.",
        "***",
        "Later that evening, inside the crowded tavern, shadows danced against the wooden walls.",
        "A cloaked traveler sat near the fire, nursing a flagon of spiced cider.",
        "The tavern keeper slammed a heavy pewter mug onto the oak table.",
    ]
    ranges = SceneAnalyzer._discover_scene_boundaries(paras)
    assert len(ranges) >= 2
    # First range ends before divider or at divider boundary
    assert ranges[0][0] == 0
    assert ranges[-1][1] == len(paras) - 1


def test_discover_scene_boundaries_narrative_transitions():
    """Narrative time/location shifts combined with paragraph depth trigger boundaries."""
    paras = [
        "Para 1 with enough words to establish scene setting and background lore for the characters involved in the story.",
        "Para 2 continues the quiet discussion between the characters about the impending storm and harvest preparations.",
        "Para 3 expands on the worries and supplies stored within the cellar to keep everyone safe through the coming winter.",
        "Para 4 wraps up the discussion as everyone prepares to retire for the night after a long demanding day.",
        "The next morning, at dawn, the traveler entered the temple gates seeking sanctuary.",
        "The stone arches echoed with solemn chants as priests in white robes gathered for prayers.",
        "Incense drifted through the cold vaulted hall as prayers began in quiet devotion.",
    ]
    ranges = SceneAnalyzer._discover_scene_boundaries(paras)
    assert len(ranges) >= 2
    assert ranges[0][0] == 0
    assert ranges[-1][1] == len(paras) - 1


def test_analyze_single_scene_combat():
    """Verifies combat scene identification, high stakes, and physical conflict."""
    scene_text = (
        "The assassin lunged forward with a serrated blade, aiming for the throat.\n\n"
        "Marcus drew his iron sword just in time to parry the deadly blow.\n\n"
        "Sparks flew in the damp courtyard. Blood dripped onto the cobblestones as the strike landed."
    )
    plan = SceneAnalyzer.analyze_single_scene(
        scene_text=scene_text,
        scene_id="scene_001",
        chapter_num=1,
        known_characters=["Marcus", "Assassin"],
    )
    assert isinstance(plan, SceneDramaticPlan)
    assert plan.scene_type == "combat"
    assert "Marcus" in plan.participants
    assert "Assassin" in plan.participants
    assert "Life" in plan.stakes or "trauma" in plan.stakes.lower() or "physical" in plan.stakes.lower()
    assert plan.location == "Courtyard"
    assert plan.source_hash != ""


def test_analyze_single_scene_confrontation_and_stakes():
    """Verifies confrontation identification, dramatic question, and psychological stakes."""
    scene_text = (
        "Elena slammed her hands onto the oak desk, her eyes blazing with fury.\n\n"
        "'You are a liar!' she hissed. 'You sold the ledger to the council!'\n\n"
        "Julian stepped back towards the doorway, his voice trembling under her furious glare."
    )
    plan = SceneAnalyzer.analyze_single_scene(
        scene_text=scene_text,
        scene_id="scene_002",
        chapter_num=2,
        known_characters=["Elena", "Julian"],
    )
    assert plan.scene_type == "confrontation"
    assert "Elena" in plan.participants
    assert "Julian" in plan.participants
    assert "?" in plan.scene_question
    assert "Status" in plan.stakes or "autonomy" in plan.stakes.lower() or "destruction" in plan.stakes.lower()


def test_analyze_single_scene_revelation_and_reversals():
    """Verifies detection of revelations, secrets, and dramatic reversals."""
    scene_text = (
        "In the quiet library, the truth is finally laid bare before them.\n\n"
        "'The seal is forged,' Julian whispered, horrified. 'Lord Raymond betrayed us from the start.'\n\n"
        "Suddenly, the realization hit her like ice water. Everything they believed was an illusion."
    )
    plan = SceneAnalyzer.analyze_single_scene(
        scene_text=scene_text,
        scene_id="scene_003",
        chapter_num=3,
        known_characters=["Julian", "Raymond"],
    )
    assert plan.scene_type == "revelation"
    assert plan.location == "Library"
    assert len(plan.major_reveals) >= 1
    assert any("betray" in r.lower() or "truth" in r.lower() or "secret" in r.lower() for r in plan.major_reveals)


def test_dramatic_complexity_calculation():
    """Verifies that combat/confrontation with multiple characters yields higher complexity."""
    simple_text = (
        "Julian sat alone in his room at night, reflecting on the long journey ahead.\n\n"
        "He wondered if his choices had led him astray."
    )
    plan_simple = SceneAnalyzer.analyze_single_scene(
        scene_text=simple_text,
        scene_id="scene_simple",
        chapter_num=1,
    )
    assert plan_simple.dramatic_complexity in ("LOW", "MEDIUM")

    complex_text = (
        "The assassins ambushed the carriage at dusk. Marcus shouted commands as steel clashed on steel.\n\n"
        "Blood splattered across the carriage door. Elena drew her dagger, stabbing at the flanking guard.\n\n"
        "Suddenly the bridge collapsed beneath them with a deafening roar, plunging them into the raging river."
    )
    plan_complex = SceneAnalyzer.analyze_single_scene(
        scene_text=complex_text,
        scene_id="scene_complex",
        chapter_num=1,
        known_characters=["Marcus", "Elena"],
    )
    assert plan_complex.dramatic_complexity in ("HIGH", "CRITICAL")
