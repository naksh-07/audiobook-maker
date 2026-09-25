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
    MemoryValidator,
    StateDelta,
    DeltaDomain,
    MemoryRetriever,
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

    def test_03_epistemic_validation_distinguishes_transmitting_vs_receiving(self):
        """
        Amendment 2: Knowledge validation must distinguish between:
        - A character USING or TRANSMITTING knowledge they do not possess -> REJECTED.
        - A character RECEIVING knowledge through a valid revelation event -> ALLOWED (UNKNOWN -> KNOWN).
        """
        store = MemoryStore()

        # Step 1: Meera learns a secret fact. Vikram does NOT know it.
        ev_learn = StoryEvent(
            event_type=StoryEventType.FACT_LEARNED,
            chapter=1,
            scene="scene_01",
            participants=["Meera"],
            description="Meera discovers the poisoned vial in the royal chamber.",
            metadata={
                "fact_id": "fact_queen_poison",
                "subject": "Queen",
                "predicate": "poison_plot",
                "value": "The Queen is using nightshade poison",
                "knower": "Meera",
                "witnesses": ["Meera"],
            },
        )
        report1 = store.commit_scene_memory("scene_01", 1, [ev_learn])
        self.assertEqual(len(report1.rejected_deltas), 0)
        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status("Meera", "fact_queen_poison", store.facts_registry),
            KnowledgeStatus.KNOWN,
        )
        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status("Vikram", "fact_queen_poison", store.facts_registry),
            KnowledgeStatus.UNKNOWN,
        )

        # Step 2: VIOLATION A - Vikram (UNKNOWN) attempts to ACT upon fact_queen_poison
        ev_bad_act = StoryEvent(
            event_type=StoryEventType.OTHER,
            chapter=1,
            scene="scene_02",
            participants=["Vikram"],
            description="Vikram uses the poison antidote.",
        )
        delta_bad_act = StateDelta(
            domain=DeltaDomain.KNOWLEDGE,
            target_entity="fact_queen_poison",
            field_name="acted_upon",
            new_value={"fact_id": "fact_queen_poison", "acted_upon_by": "Vikram"},
            source_event_id=ev_bad_act.event_id,
            chapter=1,
            scene="scene_02",
        )
        report_bad_act = store.commit_scene_memory("scene_02", 1, [ev_bad_act], deltas=[delta_bad_act])
        self.assertEqual(len(report_bad_act.flagged_conflicts), 1)
        self.assertEqual(report_bad_act.flagged_conflicts[0].conflict_type, "knowledge_violation")
        self.assertIn("UNKNOWN", report_bad_act.flagged_conflicts[0].description)

        # Step 3: VIOLATION B - Vikram (UNKNOWN) attempts to TRANSMIT/REVEAL fact_queen_poison
        ev_bad_reveal = StoryEvent(
            event_type=StoryEventType.SECRET_REVEALED,
            chapter=1,
            scene="scene_02",
            participants=["Vikram", "Rudra"],
            description="Vikram claims to know the Queen's poison.",
            metadata={
                "fact_id": "fact_queen_poison",
                "knower": "Vikram",
                "witnesses": ["Rudra"],
            },
        )
        report_bad_reveal = store.commit_scene_memory("scene_02", 1, [ev_bad_reveal])
        self.assertEqual(len(report_bad_reveal.flagged_conflicts), 1)
        self.assertEqual(report_bad_reveal.flagged_conflicts[0].conflict_type, "knowledge_violation")
        self.assertIn("revealer 'Vikram'", report_bad_reveal.flagged_conflicts[0].description)

        # Step 4: VALID TRANSMISSION - Meera (KNOWN) reveals fact_queen_poison to Vikram (UNKNOWN)
        ev_valid_reveal = StoryEvent(
            event_type=StoryEventType.SECRET_REVEALED,
            chapter=2,
            scene="scene_01",
            participants=["Meera", "Vikram"],
            description="Meera whispers the Queen's secret poison plot to Vikram.",
            metadata={
                "fact_id": "fact_queen_poison",
                "knower": "Meera",
                "witnesses": ["Meera", "Vikram"],
            },
        )
        report_valid = store.commit_scene_memory("scene_01", 2, [ev_valid_reveal])
        self.assertEqual(len(report_valid.rejected_deltas), 0)
        self.assertEqual(len(report_valid.flagged_conflicts), 0)

        # Verify Vikram transitioned UNKNOWN -> KNOWN
        self.assertEqual(
            CharacterKnowledgeEngine.get_character_knowledge_status("Vikram", "fact_queen_poison", store.facts_registry),
            KnowledgeStatus.KNOWN,
        )

        # Step 5: Vikram (now KNOWN) CAN now validly act upon or reference the fact!
        ev_good_act = StoryEvent(
            event_type=StoryEventType.OTHER,
            chapter=2,
            scene="scene_02",
            participants=["Vikram"],
            description="Vikram searches the royal pantry for the antidote.",
        )
        delta_good_act = StateDelta(
            domain=DeltaDomain.KNOWLEDGE,
            target_entity="fact_queen_poison",
            field_name="acted_upon",
            new_value={"fact_id": "fact_queen_poison", "acted_upon_by": "Vikram"},
            source_event_id=ev_good_act.event_id,
            chapter=2,
            scene="scene_02",
        )
        report_good = store.commit_scene_memory("scene_02", 2, [ev_good_act], deltas=[delta_good_act])
        self.assertEqual(len(report_good.rejected_deltas), 0)
        self.assertEqual(len(report_good.flagged_conflicts), 0)

    def test_04_cross_scene_knowledge_isolation_and_adversarial_leakage(self):
        """
        Adversarial Test:
        Verifies that facts learned in earlier scenes do NOT leak to unrelated characters across scenes,
        and that MemoryContext strictly places unlearned facts in MUST_NOT_KNOW.
        """
        store = MemoryStore()

        # Meera learns classified conspiracy in Chapter 1 Scene 1
        ev_secret = StoryEvent(
            event_type=StoryEventType.FACT_LEARNED,
            chapter=1,
            scene="scene_01",
            participants=["Meera"],
            description="Meera discovers the hidden royal ledger.",
            metadata={
                "fact_id": "fact_hidden_ledger",
                "subject": "Citadel",
                "predicate": "conspiracy",
                "value": "Gold reserves have been stolen",
                "knower": "Meera",
                "witnesses": ["Meera"],
            },
        )
        store.commit_scene_memory("scene_01", 1, [ev_secret])

        # Chapter 3 Scene 1: Senapati Rudra and Kavi Dev meet. Meera is absent.
        ctx = MemoryRetriever.retrieve_for_scene(
            store=store,
            chapter=3,
            scene_id="scene_01",
            active_characters=["Rudra", "Kavi Dev"],
            location="Barracks",
        )

        # Neither Rudra nor Kavi Dev know the secret
        r_status = CharacterKnowledgeEngine.get_character_knowledge_status("Rudra", "fact_hidden_ledger", store.facts_registry)
        k_status = CharacterKnowledgeEngine.get_character_knowledge_status("Kavi Dev", "fact_hidden_ledger", store.facts_registry)
        self.assertEqual(r_status, KnowledgeStatus.UNKNOWN)
        self.assertEqual(k_status, KnowledgeStatus.UNKNOWN)

        # Epistemic isolation matrix in MemoryContext MUST tag it as MUST_NOT_KNOW
        rudra_unknown = ctx.epistemic_constraints.get("Rudra", {}).get("UNKNOWN", [])
        self.assertTrue(any("stolen" in u or "Citadel" in u for u in rudra_unknown))

        # Prompt block must include explicit critical epistemic guard
        prompt_block = ctx.get_prompt_context()
        self.assertIn("CRITICAL EPISTEMIC GUARD", prompt_block)
        self.assertIn("MUST_NOT_KNOW", prompt_block)


if __name__ == "__main__":
    unittest.main()
