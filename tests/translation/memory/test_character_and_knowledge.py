#!/usr/bin/env python3
"""
Unit tests for CharacterState, CharacterArcMemory, KnowledgeFact,
and CharacterKnowledgeEngine (Epistemic Isolation in Memory 2.0).
"""

import unittest
from audiobook_factory.translation.memory import (
    StoryEventType,
    StoryEvent,
    CharacterState,
    KnowledgeStatus,
    KnowledgeFact,
    CharacterKnowledgeEngine,
    MemoryStore,
)


class TestCharacterAndKnowledge(unittest.TestCase):

    def test_01_injury_and_recovery_lifecycle(self):
        """Character injury persists across scenes until an explicit recovery event occurs."""
        store = MemoryStore()

        ev_inj = StoryEvent(
            event_type=StoryEventType.CHARACTER_INJURED,
            chapter=2,
            scene="scene_01",
            participants=["Vikram"],
            location="Ravine",
            description="Vikram takes an arrow wound to his left shoulder.",
            character_updates={
                "Vikram": {
                    "physical_condition": "injured",
                    "injury_added": "arrow wound in left shoulder",
                    "energy_delta": -0.3,
                }
            },
        )
        store.commit_scene_memory("scene_01", 2, [ev_inj], location="Ravine")

        st_ch2 = store.get_character_state("Vikram")
        self.assertEqual(st_ch2.physical_condition, "injured")
        self.assertIn("arrow wound in left shoulder", st_ch2.active_injuries)
        self.assertAlmostEqual(st_ch2.energy, 0.5, places=1)

        # Scene in Chapter 3 without recovery: injury must persist!
        ev_move = StoryEvent(
            event_type=StoryEventType.LOCATION_CHANGED,
            chapter=3,
            scene="scene_01",
            participants=["Vikram"],
            location="Monastery Infirmary",
            description="Vikram limps into the Monastery Infirmary.",
            character_updates={"Vikram": {"location": "Monastery Infirmary"}},
        )
        store.commit_scene_memory("scene_01", 3, [ev_move], location="Monastery Infirmary")
        st_ch3 = store.get_character_state("Vikram")
        self.assertEqual(st_ch3.physical_condition, "injured")
        self.assertIn("arrow wound in left shoulder", st_ch3.active_injuries)
        self.assertEqual(st_ch3.current_location, "Monastery Infirmary")

        # Chapter 4: Explicit recovery event clears injury
        ev_rec = StoryEvent(
            event_type=StoryEventType.CHARACTER_RECOVERED,
            chapter=4,
            scene="scene_02",
            participants=["Vikram"],
            location="Monastery Infirmary",
            description="Vikram recovers from his shoulder wound after herbal treatment.",
            character_updates={
                "Vikram": {
                    "physical_condition": "healthy",
                    "injury_removed": "arrow wound in left shoulder",
                    "energy_delta": 0.3,
                }
            },
        )
        store.commit_scene_memory("scene_02", 4, [ev_rec], location="Monastery Infirmary")
        st_ch4 = store.get_character_state("Vikram")
        self.assertEqual(st_ch4.physical_condition, "healthy")
        self.assertEqual(len(st_ch4.active_injuries), 0)

    def test_02_epistemic_isolation_known_unknown_false_belief_disproven(self):
        """
        Rule 13: Characters must only know what they have experienced or been told.
        Tracks KNOWN, SUSPECTED, FALSE_BELIEF, UNKNOWN, and DISPROVEN states per character.
        """
        facts_registry: dict[str, KnowledgeFact] = {}
        char_states = {
            "Meera": CharacterState(character_name="Meera"),
            "Vikram": CharacterState(character_name="Vikram"),
        }

        # 1. Meera learns a secret fact in Ch 2; Vikram does not know it
        CharacterKnowledgeEngine.register_or_update_fact(
            facts_registry=facts_registry,
            character_states=char_states,
            fact_id="fact_rudra_traitor",
            subject="Rudra",
            predicate="secret_allegiance",
            value="Rudra secretly works for the Northern Syndicate",
            source_event="evt_ch2_secret",
            learned_at="ch002_scene_01",
            learners=["Meera"],
            status=KnowledgeStatus.KNOWN,
        )

        # 2. Vikram holds a FALSE_BELIEF that Rudra is loyal
        CharacterKnowledgeEngine.register_or_update_fact(
            facts_registry=facts_registry,
            character_states=char_states,
            fact_id="fact_rudra_loyal_myth",
            subject="Rudra",
            predicate="loyalty_belief",
            value="Rudra is the most loyal commander of the Citadel",
            source_event="evt_ch1_intro",
            learned_at="ch001_scene_01",
            learners=["Vikram"],
            status=KnowledgeStatus.FALSE_BELIEF,
        )

        # 3. Vikram suspects an ambush at the pass
        CharacterKnowledgeEngine.register_or_update_fact(
            facts_registry=facts_registry,
            character_states=char_states,
            fact_id="fact_pass_ambush",
            subject="Vindhya Pass",
            predicate="ambush_risk",
            value="Scouts may have trapped Vindhya Pass",
            source_event="evt_ch2_scouts",
            learned_at="ch002_scene_02",
            learners=["Vikram"],
            status=KnowledgeStatus.SUSPECTED,
            confidence=0.6,
        )

        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status(
                "Meera", "fact_rudra_traitor", facts_registry, char_states
            ),
            KnowledgeStatus.KNOWN,
        )
        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status(
                "Vikram", "fact_rudra_traitor", facts_registry, char_states
            ),
            KnowledgeStatus.UNKNOWN,
        )
        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status(
                "Vikram", "fact_rudra_loyal_myth", facts_registry, char_states
            ),
            KnowledgeStatus.FALSE_BELIEF,
        )

        matrix = CharacterKnowledgeEngine.build_epistemic_constraints_for_scene(
            active_characters=["Meera", "Vikram"],
            facts_registry=facts_registry,
            character_states=char_states,
        )
        self.assertTrue(any("Northern Syndicate" in s for s in matrix["Meera"]["KNOWN"]))
        self.assertTrue(any("Northern Syndicate" in s for s in matrix["Vikram"]["UNKNOWN"]))
        self.assertTrue(any("loyal commander" in s for s in matrix["Vikram"]["FALSE_BELIEF"]))

        # 4. In Ch 5, Meera reveals the truth to Vikram -> Vikram's false belief is DISPROVEN
        CharacterKnowledgeEngine.register_or_update_fact(
            facts_registry=facts_registry,
            character_states=char_states,
            fact_id="fact_rudra_loyal_myth",
            subject="Rudra",
            predicate="loyalty_belief",
            value="Rudra is the most loyal commander of the Citadel",
            source_event="evt_ch5_reveal",
            learned_at="ch005_scene_01",
            learners=["Vikram"],
            status=KnowledgeStatus.DISPROVEN,
        )
        CharacterKnowledgeEngine.register_or_update_fact(
            facts_registry=facts_registry,
            character_states=char_states,
            fact_id="fact_rudra_traitor",
            subject="Rudra",
            predicate="secret_allegiance",
            value="Rudra secretly works for the Northern Syndicate",
            source_event="evt_ch5_reveal",
            learned_at="ch005_scene_01",
            learners=["Vikram"],
            status=KnowledgeStatus.KNOWN,
        )

        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status(
                "Vikram", "fact_rudra_loyal_myth", facts_registry, char_states
            ),
            KnowledgeStatus.DISPROVEN,
        )
        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status(
                "Vikram", "fact_rudra_traitor", facts_registry, char_states
            ),
            KnowledgeStatus.KNOWN,
        )


if __name__ == "__main__":
    unittest.main()
