#!/usr/bin/env python3
"""
Targeted Test Suite for Stage 3 Refined Dramatic Capabilities.
==============================================================
Validates all 10 dramatic capabilities:
1. Beat Causality (Continuous causal chains, South Park therefore/but)
2. Dramatic State Delta (Scene entry vs exit transformation)
3. Relationship Evolution (Interpersonal shifts in hostility, trust, dominance)
4. Power + Information Dynamics (Leverage, vulnerability, dramatic irony)
5. Meaningful Physical Blocking (Material physical staging)
6. Narrative Mode & Perspective (Direct, internal monologue, reported speech, POV)
7. Explicit Adaptation & Fidelity Policy (Gate 2.5 fail-closed on fabricated lore)
8. Long-Range Story Connections (Motif echo, setup, callbacks)
9. Conversational Dynamics (Interruptions, hesitation, strategy shifts)
10. Dramatic Silence Intent (Narrative purpose of pause without DSP execution)
11. Backward Compatibility (Legacy ScreenplaySegments parse with safe defaults)
"""

import json
import pytest
from audiobook_factory.contracts import ScreenplaySegment, ScreenplayScript
from audiobook_factory.dramaturgy.contracts import (
    DramaticPlan,
    SceneDramaticPlan,
    DramaticBeat,
    CharacterDramaticObjective,
    RelationshipShift,
    PhysicalBlocking,
    StoryConnectionRecord,
    ConversationalDynamic,
    DramaticSilenceIntent,
    DramaticStateDelta,
    AdaptationFidelityPolicy,
)
from audiobook_factory.dramaturgy.scene_analyzer import SceneAnalyzer
from audiobook_factory.dramaturgy.beat_planner import BeatPlanner
from audiobook_factory.dramaturgy.dramatic_validator import DramaticValidator
from audiobook_factory.script_builder import clean_screenplay_pass2


# =============================================================================
# 1. Beat Causality Tests
# =============================================================================

def test_beat_causality_continuous_chain():
    """Verify beats form an unbroken causal chain where beat N feeds beat N+1."""
    text = (
        "Captain Harris slammed his fist onto the council table. 'Surrender the map now!'\n\n"
        "Lyra took a step back, hand resting on her concealed dagger. 'Never.'\n\n"
        "Harris lunged, blade catching the candlelight as he struck."
    )
    scene = SceneAnalyzer.analyze_single_scene(
        scene_text=text,
        scene_id="sc_causality",
        known_characters=["Harris", "Lyra"],
    )
    beats = BeatPlanner.plan_scene_beats(scene, known_characters=["Harris", "Lyra"])
    scene.beats = beats

    assert len(beats) >= 3
    # Beat 1 should be catalyst
    assert beats[0].causal_link_type == "catalyst"
    assert beats[0].consequence is not None
    assert len(beats[0].consequence) > 5

    # Beat 2 must inherit beat 1's consequence as its causal trigger
    assert beats[1].causal_trigger == beats[0].consequence
    assert beats[1].consequence is not None

    # Beat 3 must inherit beat 2's consequence
    assert beats[2].causal_trigger == beats[1].consequence
    assert beats[2].causal_link_type in ("therefore", "but")


# =============================================================================
# 2. Dramatic State Delta Tests
# =============================================================================

def test_dramatic_state_delta_computation():
    """Verify that a high-complexity confrontation derives a rich state delta."""
    text = (
        "The inquisitor unmasked his face, revealing the scarred countenance of Prince Vane.\n\n"
        "Marcus stared in horror as the truth was revealed. 'You were dead at Oakhaven!'\n\n"
        "Vane laughed darkly. 'I was reborn. And now, you will join me or perish.'\n\n"
        "Marcus drew his broadsword and decided to fight to the last breath."
    )
    scene = SceneAnalyzer.analyze_single_scene(
        scene_text=text,
        scene_id="sc_delta",
        known_characters=["Marcus", "Vane"],
    )

    delta = scene.state_delta
    assert delta is not None
    assert isinstance(delta, DramaticStateDelta)
    assert len(delta.knowledge_delta) >= 1
    assert any("truth" in k.lower() or "disclosed" in k.lower() for k in delta.knowledge_delta)
    assert len(delta.relationship_shifts) >= 1
    assert delta.danger_level_delta in ("escalated", "latent")
    assert any("fight" in d.lower() or "committed" in d.lower() for d in delta.decisions_made)
    assert "->" in delta.emotional_trajectory


# =============================================================================
# 3. Relationship Evolution Tests
# =============================================================================

def test_relationship_evolution_tracking():
    """Verify beats produce granular relationship shifts across hostility, dominance, and trust."""
    scene = SceneDramaticPlan(
        scene_id="sc_rel",
        scene_type="confrontation",
        location="Grand Hall",
        participants=["Vane", "Marcus"],
    )
    beats = BeatPlanner.plan_scene_beats(scene, known_characters=["Vane", "Marcus"])

    shifts = [b.relationship_shift for b in beats if b.relationship_shift is not None]
    assert len(shifts) >= 1

    # Check that at least one hostility, dominance, or cooperation shift was logged
    dimensions = [s.dimension for s in shifts]
    assert any(d in ("hostility", "dominance", "cooperation") for d in dimensions)
    assert all(s.source_character in ("Vane", "Marcus") for s in shifts)


# =============================================================================
# 4. Power & Information Dynamics Tests
# =============================================================================

def test_power_and_information_dynamics_and_irony():
    """Verify leverage holder, vulnerable character, and dramatic irony tracking."""
    text = (
        "Unbeknownst to Lord Baelish, Arya was standing invisibly behind the tapestries.\n\n"
        "'The castle is entirely mine,' Baelish muttered with supreme confidence."
    )
    scene = SceneAnalyzer.analyze_single_scene(
        scene_text=text,
        scene_id="sc_irony",
        known_characters=["Baelish", "Arya"],
    )
    assert "irony" in scene.listener_knowledge_state.lower() or len(scene.epistemic_asymmetry) >= 1

    beats = BeatPlanner.plan_scene_beats(scene, known_characters=["Baelish", "Arya"])
    assert any(b.dramatic_irony is not None for b in beats)


# =============================================================================
# 5. Meaningful Physical Blocking Tests
# =============================================================================

def test_meaningful_physical_blocking_preservation():
    """Verify dramatic beats attach physical blocking with spatial and dramatic significance."""
    scene = SceneDramaticPlan(
        scene_id="sc_combat",
        scene_type="combat",
        location="Courtyard",
        participants=["Kaelen", "Riven"],
    )
    beats = BeatPlanner.plan_scene_beats(scene, known_characters=["Kaelen", "Riven"])

    blockings = [b.blocking for b in beats if b.blocking is not None]
    assert len(blockings) >= 1
    sample = blockings[0]
    assert isinstance(sample, PhysicalBlocking)
    assert sample.character in ("Kaelen", "Riven")
    assert sample.dramatic_significance in (
        "power_assertion", "threat_display", "barrier_creation", "territorial_control"
    )
    assert sample.spatial_intent is not None


# =============================================================================
# 6. Narrative Mode & Perspective Tests
# =============================================================================

def test_narrative_mode_and_perspective():
    """Verify narrative mode distinguishes direct dialogue, internal thought, and reported speech."""
    first_person_text = (
        "I looked across the darkened canyon and saw my brother's fire burning.\n\n"
        "'We move at dawn,' he shouted across the gorge."
    )
    fp_scene = SceneAnalyzer.analyze_single_scene(scene_text=first_person_text, scene_id="sc_fp")
    assert fp_scene.narrative_pov == "first_person"
    assert fp_scene.narrative_distance == "first_person_intimate"

    third_person_text = (
        "Jon Snow climbed the stone wall. He felt the cold biting through his leather gloves.\n\n"
        "'Winter is here,' he whispered."
    )
    tp_scene = SceneAnalyzer.analyze_single_scene(scene_text=third_person_text, scene_id="sc_tp")
    assert tp_scene.narrative_pov == "third_person_limited"

    # Test script segment mode detection in clean_screenplay_pass2
    raw_segments = [
        {"type": "narration", "speaker": "Narrator", "text": "The wind howled outside the gates."},
        {"type": "dialogue", "speaker": "Jon", "text": "We cannot wait any longer."},
        {"type": "dialogue", "speaker": "Jon", "text": "[whispers] (मन में: अगर मैंने सच बताया तो सब खत्म हो जाएगा)"},
        {"type": "dialogue", "speaker": "Sansa", "text": "Bran said that the army crossed the river yesterday."},
    ]
    cleaned = clean_screenplay_pass2(raw_segments, is_hindi=False)

    assert cleaned[0]["narrative_mode"] == "narrator_exposition"
    assert cleaned[1]["narrative_mode"] == "direct_dialogue"
    assert cleaned[2]["narrative_mode"] == "internal_monologue"
    assert cleaned[3]["narrative_mode"] == "reported_speech"


# =============================================================================
# 7. Adaptation & Fidelity Policy Tests (Gate 2.5 Enforcement)
# =============================================================================

def test_adaptation_fidelity_policy_fail_closed():
    """Verify that ungrounded fabricated reveals trigger hard FAIL under AdaptationFidelityPolicy."""
    source_text = "The old hermit lived alone in the cave, gathering herbs and moss."
    fabricated_plan = DramaticPlan(
        chapter_id="ch_fab",
        chapter_num=1,
        adaptation_policy=AdaptationFidelityPolicy(disallow_fabricated_reveals=True),
        scenes=[
            SceneDramaticPlan(
                scene_id="sc_fab",
                major_reveals=["Disclosed: 'nuclear spacecraft launch codes hidden in ancient chamber'"],
                beats=[],
            )
        ],
    )
    segments = [
        {"uid": "s001", "index": 1, "type": "dialogue", "speaker": "Hermit", "text": "I gather moss."}
    ]

    res = DramaticValidator.validate_screenplay_and_plan(
        segments=segments,
        dramatic_plan=fabricated_plan,
        source_text=source_text,
    )
    assert res.status == "FAIL"
    assert res.passed is False
    assert any(i.code == "FABRICATED_REVEAL_BREACH" for i in res.issues)


# =============================================================================
# 8. Long-Range Story Connections Tests
# =============================================================================

def test_long_range_story_connections_detection():
    """Verify motif presence in scene triggers StoryConnectionRecord creation."""
    text = (
        "She ran her fingers across the rusted iron key. It had been her mother's only legacy.\n\n"
        "'This opens the door beneath the city,' she whispered."
    )
    scene = SceneAnalyzer.analyze_single_scene(scene_text=text, scene_id="sc_motif")
    assert len(scene.story_connections) >= 1
    sample = scene.story_connections[0]
    assert isinstance(sample, StoryConnectionRecord)
    assert sample.motif_name == "key"
    assert sample.connection_type == "setup"


# =============================================================================
# 9. Conversational Dynamics Tests
# =============================================================================

def test_conversational_dynamics_interruptions_and_hesitations():
    """Verify turn-taking interruptions and hesitation markers in dialogue."""
    raw = [
        {"type": "dialogue", "speaker": "Arthur", "text": "Listen to me, we have to--"},
        {"type": "dialogue", "speaker": "Morgana", "text": "I will not listen to your lies!"},
        {"type": "dialogue", "speaker": "Arthur", "text": "I... I only wanted to protect you..."},
    ]
    cleaned = clean_screenplay_pass2(raw)

    # First line has cutoff dash: must be interruption
    assert cleaned[0]["is_interruption"] is True
    assert cleaned[0]["conversational_dynamic"] == "interruption"

    # Third line has ellipses: must have hesitation metadata
    assert cleaned[2]["hesitation_pause_ms"] == 350
    assert cleaned[2]["conversational_dynamic"] == "hesitation"


# =============================================================================
# 10. Dramatic Silence Intent Tests
# =============================================================================

def test_dramatic_silence_intent_narrative_purpose():
    """Verify dramatic silence identifies narrative intent without audio DSP execution."""
    scene = SceneDramaticPlan(
        scene_id="sc_silence",
        scene_type="revelation",
        location="Throne Room",
        participants=["King", "Assassin"],
    )
    beats = BeatPlanner.plan_scene_beats(scene, known_characters=["King", "Assassin"])

    silence_beats = [b.silence_intent for b in beats if b.silence_intent is not None]
    assert len(silence_beats) >= 1

    purposes = [s.purpose for s in silence_beats]
    # Check that revelation scene has shock or realization silence intent
    assert any(p in ("shock", "realization", "anticipation") for p in purposes)
    for s in silence_beats:
        assert isinstance(s, DramaticSilenceIntent)
        assert len(s.dramatic_rationale) > 10
        assert s.listening_focus in ("character_reaction", "subtext_digestion", "acoustic_space")


# =============================================================================
# 11. Backward Compatibility Tests
# =============================================================================

def test_screenplay_segment_backward_compatibility():
    """Verify legacy segments without dramatic attributes validate 100% cleanly."""
    legacy_data = {
        "index": 1,
        "type": "dialogue",
        "speaker": "OldMan",
        "text": "The night is cold.",
        "emotion": "neutral",
        "pause_after_ms": 400,
    }
    seg = ScreenplaySegment.model_validate(legacy_data)
    assert seg.speaker == "OldMan"
    assert seg.causal_trigger is None
    assert seg.consequence is None
    assert seg.relationship_shift is None
    assert seg.leverage_holder is None
    assert seg.dramatic_irony is None
    assert seg.blocking_directive is None
    assert seg.narrative_mode == "direct_dialogue"
    assert seg.silence_intent is None

    # Serialization round trip
    dumped = seg.model_dump()
    seg2 = ScreenplaySegment.model_validate(dumped)
    assert seg2.speaker == "OldMan"
    assert seg2.text == "The night is cold."
