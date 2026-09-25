#!/usr/bin/env python3
"""
Unit tests for StoryEvent, TemporalMode, SceneChangeDetector, EventExtractor,
and StateDeltaEngine (Memory 2.0).
"""

import unittest
from audiobook_factory.translation.memory import (
    StoryEventType,
    TemporalMode,
    StoryEvent,
    SceneChangeDetector,
    EventExtractor,
    DeltaDomain,
    StateMutability,
    StateDeltaEngine,
    CharacterState,
    WorldState,
)
from audiobook_factory.translation.relationship_state import DynamicRelationshipState


class TestEventsAndDeltas(unittest.TestCase):

    def test_01_story_event_deterministic_id_and_salience(self):
        """Identical event inputs must produce identical SHA-256 event_ids and high salience for turning points."""
        ev1 = StoryEvent(
            event_type=StoryEventType.BETRAYAL,
            chapter=3,
            scene="scene_02",
            participants=["Vikram", "Rudra"],
            location="Iron Citadel",
            description="Rudra betrays Vikram at the northern gate.",
            evidence_text="Rudra locked the iron gate and drew his dagger.",
            importance=5,
        )
        ev2 = StoryEvent(
            event_type=StoryEventType.BETRAYAL,
            chapter=3,
            scene="scene_02",
            participants=["Rudra", "Vikram"],  # different order should still normalize
            location="Iron Citadel",
            description="Rudra betrays Vikram at the northern gate.",
            evidence_text="Different quote does not alter canonical identity hash.",
            importance=5,
        )
        self.assertEqual(ev1.event_id, ev2.event_id)
        self.assertGreaterEqual(ev1.salience_score, 0.85)
        self.assertLess(ev1.emotional_valence, 0.0)
        self.assertIn("betrayal", ev1.dramatic_tags)

    def test_02_scene_change_detector_skips_llm_on_routine_scenes(self):
        """Refinement 1: Routine scenes must not trigger semantic LLM extraction."""
        routine_text = (
            "The morning breeze blew gently across the courtyard. "
            "Vikram walked beside the fountain and looked at the clouds."
        )
        assessment = SceneChangeDetector.assess_scene(routine_text, known_characters=["Vikram"])
        self.assertFalse(assessment.requires_llm_extraction)
        self.assertEqual(assessment.temporal_mode, TemporalMode.PRESENT)

        llm_called = False

        def mock_llm(*args, **kwargs):
            nonlocal llm_called
            llm_called = True
            return "[]"

        events, _ = EventExtractor.extract_scene_events(
            scene_text=routine_text,
            chapter=1,
            scene_id="scene_01",
            known_characters=["Vikram"],
            location="Courtyard",
            call_llm_fn=mock_llm,
        )
        self.assertFalse(llm_called, "LLM should NOT be called when requires_llm_extraction is False")

    def test_03_scene_change_detector_triggers_llm_with_deterministic_fallback(self):
        """Refinement 1: State-changing scenes trigger LLM extraction and gracefully fallback on failure."""
        dramatic_text = (
            "Rudra betrayed Vikram and stabbed his shoulder with a poisoned dagger. "
            "Meera discovered the truth about the secret treaty and swore an oath to avenge him."
        )
        assessment = SceneChangeDetector.assess_scene(
            dramatic_text, known_characters=["Vikram", "Rudra", "Meera"]
        )
        self.assertTrue(assessment.requires_llm_extraction)
        self.assertGreaterEqual(len(assessment.detected_triggers), 2)

        def failing_llm(*args, **kwargs):
            raise RuntimeError("Simulated 429 rate limit")

        events, _ = EventExtractor.extract_scene_events(
            scene_text=dramatic_text,
            chapter=2,
            scene_id="scene_01",
            known_characters=["Vikram", "Rudra", "Meera"],
            location="Fortress Hall",
            call_llm_fn=failing_llm,
        )
        event_types = {e.event_type for e in events}
        self.assertIn(StoryEventType.BETRAYAL, event_types)
        self.assertIn(StoryEventType.CHARACTER_INJURED, event_types)

    def test_04_temporal_mode_detection_for_flashback_and_dream(self):
        """Refinement 4: SceneChangeDetector accurately identifies FLASHBACK and MEMORY_DREAM modes."""
        flashback_text = "Ten years earlier, in his childhood memory, Vikram trained in the mountain monastery."
        mode, epoch, ref = SceneChangeDetector.detect_temporal_mode(flashback_text)
        self.assertEqual(mode, TemporalMode.FLASHBACK)
        self.assertEqual(epoch, -1)
        self.assertTrue(len(ref) > 0)

        dream_text = "In a nightmare, Meera saw the burning tower collapse into ash."
        mode_dream, _, _ = SceneChangeDetector.detect_temporal_mode(dream_text)
        self.assertEqual(mode_dream, TemporalMode.MEMORY_DREAM)

    def test_05_state_delta_engine_generates_multi_domain_deltas(self):
        """StateDeltaEngine converts StoryEvents into structured StateDeltas with provenance."""
        char_states = {"Vikram": CharacterState(character_name="Vikram")}
        rels = {"Vikram->Rudra": DynamicRelationshipState(speaker="Vikram", target="Rudra", trust=2)}
        facts = {}
        world = WorldState()

        ev = StoryEvent(
            event_type=StoryEventType.BETRAYAL,
            chapter=4,
            scene="scene_03",
            participants=["Vikram", "Rudra"],
            location="Citadel",
            description="Rudra betrayed Vikram to the enemy garrison.",
            importance=5,
            character_updates={"Vikram": {"emotion": "enraged", "emotion_intensity": 0.9}},
            relationship_impacts=[
                {"speaker": "Vikram", "target": "Rudra", "interaction_type": "betrayal"}
            ],
        )
        deltas = StateDeltaEngine.compute_deltas_for_events(
            events=[ev],
            character_states=char_states,
            relationships=rels,
            facts_registry=facts,
            world_state=world,
        )
        domains = {d.domain for d in deltas}
        self.assertIn(DeltaDomain.CHARACTER, domains)
        self.assertIn(DeltaDomain.RELATIONSHIP, domains)
        for d in deltas:
            self.assertEqual(d.source_event_id, ev.event_id)
            self.assertEqual(d.mutability, StateMutability.DYNAMIC_SCENE)


if __name__ == "__main__":
    unittest.main()
