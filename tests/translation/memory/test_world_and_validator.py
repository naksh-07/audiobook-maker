#!/usr/bin/env python3
"""
Unit tests for WorldState mutations and all 7 Contradiction Detection classes
in MemoryValidator (Memory 2.0).
"""

import unittest
from audiobook_factory.translation.book_bible import BookBible, BookEntity, WorldRule
from audiobook_factory.translation.memory import (
    StoryEventType,
    TemporalMode,
    StoryEvent,
    DeltaDomain,
    StateMutability,
    StateDelta,
    ValidationOutcome,
    MemoryValidator,
    MemoryStore,
)


class TestWorldAndValidator(unittest.TestCase):

    def _build_bible(self) -> BookBible:
        bible = BookBible(book_title="Chronicles of the Iron Citadel")
        bible.characters["Vikram"] = BookEntity(
            canonical_id="vikram",
            english_name="Vikram",
            hindi_name="विक्रम",
            gender="male",
            description="Commander",
            is_canonical=True,
        )
        bible.world_rules.append(
            WorldRule(
                rule_id="No Mortal Magic",
                category="magic_system",
                statement="Mortals cannot use magic inside the Iron Null-Zone.",
                immutable=True,
            )
        )
        return bible


    def test_01_all_seven_contradiction_classes_detected(self):
        """
        Verifies that MemoryValidator catches all 7 required contradiction classes:
        1. canon_contradiction
        2. timeline_contradiction
        3. knowledge_violation
        4. relationship_jump
        5. physical_impossibility
        6. dead_character_violation
        7. world_rule_violation
        """
        bible = self._build_bible()
        store = MemoryStore()
        store.seed_from_book_bible(bible)

        # Establish baseline: Chapter 3 PRESENT timeline point, Kavi Dev is deceased, Obsidian Seal owned by Vikram
        ev_init = StoryEvent(
            event_type=StoryEventType.CHARACTER_DIED,
            chapter=3,
            scene="scene_01",
            participants=["Kavi Dev", "Vikram"],
            location="Iron Citadel",
            description="Kavi Dev dies defending the gate while Vikram acquires the Obsidian Seal.",
            character_updates={"Kavi Dev": {"is_alive": False}},
            world_updates={"objects_acquired": [{"object_name": "Obsidian Seal", "owner": "Vikram"}]},
        )
        store.commit_scene_memory("scene_01", 3, [ev_init], book_bible=bible, location="Iron Citadel")
        self.assertFalse(store.get_character_state("Kavi Dev").is_alive)
        self.assertEqual(store.world_state.object_states["Obsidian Seal"].current_owner, "Vikram")

        # Now construct deltas triggering each of the 7 contradiction classes
        bad_deltas = [
            # 1. canon_contradiction (mutating locked gender / HARD_CANON)
            StateDelta(
                domain=DeltaDomain.CHARACTER,
                target_entity="Vikram",
                field_name="gender",
                old_value="male",
                new_value="female",
                mutability=StateMutability.HARD_CANON,
                source_event_id="evt_bad_1",
                chapter=4,
                scene="scene_01",
            ),
            # 2. timeline_contradiction (PRESENT mode moving backward to chapter 1)
            StateDelta(
                domain=DeltaDomain.CHARACTER,
                target_entity="Vikram",
                field_name="current_emotion",
                old_value="neutral",
                new_value="calm",
                temporal_mode=TemporalMode.PRESENT,
                source_event_id="evt_bad_2",
                chapter=1,
                scene="scene_01",
            ),
            # 3. knowledge_violation (Vikram acting on an UNKNOWN secret fact)
            StateDelta(
                domain=DeltaDomain.KNOWLEDGE,
                target_entity="fact_hidden_vault",
                field_name="fact_status",
                new_value={
                    "fact_id": "fact_hidden_vault",
                    "acted_upon_by": "Vikram",
                    "known_by": [],
                },
                source_event_id="evt_bad_3",
                chapter=4,
                scene="scene_01",
            ),
            # 4. relationship_jump (silent jump without source_event_id, or jump > 2 on low importance)
            StateDelta(
                domain=DeltaDomain.RELATIONSHIP,
                target_entity="Vikram->Meera",
                field_name="trust",
                operation="adjust",
                numeric_delta=4.0,
                source_event_id="evt_bad_4",
                chapter=4,
                scene="scene_01",
                metadata={"importance": 2},
            ),
            # 5. physical_impossibility (transferring Obsidian Seal claiming previous_owner="Rudra" when Vikram owns it)
            StateDelta(
                domain=DeltaDomain.WORLD,
                target_entity="Obsidian Seal",
                field_name="object_owner",
                old_value="Rudra",
                new_value="Meera",
                source_event_id="evt_bad_5",
                chapter=4,
                scene="scene_01",
                metadata={"previous_owner": "Rudra"},
            ),
            # 6. dead_character_violation (deceased Kavi Dev changing location in PRESENT mode)
            StateDelta(
                domain=DeltaDomain.CHARACTER,
                target_entity="Kavi Dev",
                field_name="current_location",
                old_value="Iron Citadel",
                new_value="Market Square",
                temporal_mode=TemporalMode.PRESENT,
                source_event_id="evt_bad_6",
                chapter=4,
                scene="scene_01",
            ),
            # 7. world_rule_violation (violating 'No Mortal Magic' rule)
            StateDelta(
                domain=DeltaDomain.WORLD,
                target_entity="Vikram",
                field_name="discovered_rule",
                new_value="Vikram uses magic inside the Iron Null-Zone",
                rationale="Mortal uses magic to break No Mortal Magic rule",
                source_event_id="evt_bad_7",
                chapter=4,
                scene="scene_01",
            ),
        ]

        report = MemoryValidator.validate_deltas(
            deltas=bad_deltas,
            book_bible=bible,
            character_states=store.character_states,
            relationships=store.relationships,
            facts_registry=store.facts_registry,
            world_state=store.world_state,
        )

        self.assertEqual(report.outcome, ValidationOutcome.CONFLICT)
        self.assertEqual(len(report.accepted_deltas), 0)
        self.assertEqual(len(report.rejected_deltas), 7)

        conflict_types = {fc.conflict_type for fc in report.flagged_conflicts}
        self.assertEqual(
            conflict_types,
            {
                "canon_contradiction",
                "timeline_contradiction",
                "knowledge_violation",
                "relationship_jump",
                "physical_impossibility",
                "dead_character_violation",
                "world_rule_violation",
            },
        )

    def test_02_flashback_and_dream_modes_do_not_trigger_false_contradictions(self):
        """
        Refinement 4: Deceased characters appearing in FLASHBACK or MEMORY_DREAM scenes
        are allowed and do NOT overwrite PRESENT physical survival or location state.
        """
        bible = self._build_bible()
        store = MemoryStore()
        store.seed_from_book_bible(bible)

        # Kavi Dev dies in Chapter 3 at Iron Citadel
        ev_death = StoryEvent(
            event_type=StoryEventType.CHARACTER_DIED,
            chapter=3,
            scene="scene_01",
            participants=["Kavi Dev"],
            location="Iron Citadel",
            description="Kavi Dev falls in battle at Iron Citadel.",
            character_updates={"Kavi Dev": {"is_alive": False, "location": "Iron Citadel"}},
        )
        store.commit_scene_memory("scene_01", 3, [ev_death], book_bible=bible, location="Iron Citadel")
        self.assertFalse(store.get_character_state("Kavi Dev").is_alive)

        # Chapter 4 is a FLASHBACK to ten years earlier where Kavi Dev is at River Gurukul
        ev_flashback = StoryEvent(
            event_type=StoryEventType.LOCATION_CHANGED,
            chapter=4,
            scene="scene_01",
            temporal_mode=TemporalMode.FLASHBACK,
            chronological_epoch=-1,
            story_time_reference="ten years earlier",
            participants=["Kavi Dev", "Vikram"],
            location="River Gurukul",
            description="Ten years earlier, Kavi Dev taught young Vikram by the River Gurukul.",
            character_updates={
                "Kavi Dev": {"location": "River Gurukul", "emotion": "serene"},
                "Vikram": {"turning_point": "Recalled Kavi Dev's lesson on patience"},
            },
        )
        report = store.commit_scene_memory("scene_01", 4, [ev_flashback], book_bible=bible, location="River Gurukul")

        # Must NOT flag a dead_character_violation or timeline_contradiction
        self.assertEqual(len(report.flagged_conflicts), 0)
        # Present survival and present location of Kavi Dev must remain unchanged
        kavi_state = store.get_character_state("Kavi Dev")
        self.assertFalse(kavi_state.is_alive)
        self.assertEqual(kavi_state.current_location, "Iron Citadel")
        # Vikram's psychological turning point from the flashback IS preserved
        vikram_state = store.get_character_state("Vikram")
        self.assertTrue(any("patience" in tp for tp in vikram_state.arc_state.turning_points))


if __name__ == "__main__":
    unittest.main()
