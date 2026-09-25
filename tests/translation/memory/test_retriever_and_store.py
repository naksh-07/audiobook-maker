#!/usr/bin/env python3
"""
Unit tests for Selective 7-Tier MemoryRetriever, Narrative Salience ranking,
Conservative Performance Guidance (Refinement 2), and Versioned MemoryStore.
"""

import tempfile
import unittest
from pathlib import Path

from audiobook_factory.translation.book_bible import BookBible, BookEntity, DynamicRelationship
from audiobook_factory.translation.relationship_state import DynamicRelationshipState
from audiobook_factory.translation.memory import (
    StoryEventType,
    StoryEvent,
    MemoryStore,
    MemoryRetriever,
    MemoryPersistenceError,
)


class TestRetrieverAndStore(unittest.TestCase):

    def test_01_selective_retrieval_excludes_unrelated_entities_and_retrieves_salient_events(self):
        """
        Rule 10 & Narrative Salience:
        MemoryRetriever must include ONLY active scene characters/objects/relationships
        and surface high-salience earlier events alongside recent events.
        """
        bible = BookBible(book_title="Sands of Marwar")
        bible.characters["Vikram"] = BookEntity(canonical_id="vikram", english_name="Vikram", gender="male")
        bible.characters["Meera"] = BookEntity(canonical_id="meera", english_name="Meera", gender="female")
        bible.characters["UnrelatedMerchant"] = BookEntity(canonical_id="merchant", english_name="UnrelatedMerchant", gender="male")
        bible.locations["Iron Citadel"] = "लौह दुर्ग"
        bible.locations["DistantPort"] = "दूरस्थ बंदरगाह"


        store = MemoryStore()
        store.seed_from_book_bible(bible)
        store.relationships["Vikram->Meera"] = DynamicRelationshipState(
            speaker="Vikram", target="Meera", trust=3, familiarity=3, active_pronoun="tum"
        )
        store.relationships["UnrelatedMerchant->Vikram"] = DynamicRelationshipState(
            speaker="UnrelatedMerchant", target="Vikram", trust=0, familiarity=0, active_pronoun="aap"
        )

        # Chapter 1: High-salience blood oath between Vikram and Meera + object acquired
        ev_oath = StoryEvent(
            event_type=StoryEventType.PROMISE_MADE,
            chapter=1,
            scene="scene_01",
            participants=["Vikram", "Meera"],
            location="Iron Citadel",
            description="Vikram swears a blood oath to protect Meera's lineage.",
            importance=5,
            salience_score=0.95,
            world_updates={
                "objects_acquired": [
                    {"object_name": "Sun Medallion", "owner": "Meera", "location": "Iron Citadel"},
                    {"object_name": "Merchant Ledger", "owner": "UnrelatedMerchant", "location": "DistantPort"},
                ]
            },
        )
        store.commit_scene_memory("scene_01", 1, [ev_oath], book_bible=bible, location="Iron Citadel")

        # Chapters 2 to 6: 5 routine movement events so ev_oath falls outside max_recent_events=3
        for ch_idx in range(2, 7):
            ev_routine = StoryEvent(
                event_type=StoryEventType.LOCATION_CHANGED,
                chapter=ch_idx,
                scene="scene_01",
                participants=["Vikram", "Meera"],
                location="Iron Citadel",
                description=f"Patrol shift {ch_idx} inside Iron Citadel.",
                importance=2,
                salience_score=0.25,
            )
            store.commit_scene_memory("scene_01", ch_idx, [ev_routine], book_bible=bible, location="Iron Citadel")

        # Retrieve for Chapter 7 scene with ONLY Vikram and Meera at Iron Citadel
        ctx = MemoryRetriever.retrieve_for_scene(
            store=store,
            book_bible=bible,
            chapter=7,
            scene_id="scene_01",
            active_characters=["Vikram", "Meera"],
            location="Iron Citadel",
            scene_text="Vikram and Meera stood inside the Iron Citadel hall.",
            max_recent_events=3,
            max_salient_events=3,
        )

        # Active characters included, UnrelatedMerchant excluded!
        self.assertIn("Vikram", ctx.active_character_states)
        self.assertIn("Meera", ctx.active_character_states)
        self.assertNotIn("UnrelatedMerchant", ctx.active_character_states)

        # Only Vikram->Meera relationship included, UnrelatedMerchant->Vikram excluded!
        rel_pairs = {(r.speaker, r.target) for r in ctx.active_relationships}
        self.assertIn(("Vikram", "Meera"), rel_pairs)
        self.assertNotIn(("UnrelatedMerchant", "Vikram"), rel_pairs)

        # Sun Medallion included, Merchant Ledger excluded!
        obj_names = {o.object_name for o in ctx.relevant_objects}
        self.assertIn("Sun Medallion", obj_names)
        self.assertNotIn("Merchant Ledger", obj_names)

        # High-salience Ch 1 blood oath retrieved in salient_events even though recent_events only holds Ch 4-6!
        recent_ids = {e.event_id for e in ctx.recent_events}
        salient_ids = {e.event_id for e in ctx.salient_events}
        self.assertNotIn(ev_oath.event_id, recent_ids)
        self.assertIn(ev_oath.event_id, salient_ids)

    def test_02_conservative_performance_guidance_respects_screenplay_intent(self):
        """
        Refinement 2: MemoryContext enriches neutral segments with injured/acoustic context
        but NEVER overwrites explicit screenplay emotion, delivery_style, or vocal tags.
        """
        store = MemoryStore()
        ev_inj = StoryEvent(
            event_type=StoryEventType.CHARACTER_INJURED,
            chapter=1,
            scene="scene_01",
            participants=["Vikram", "Meera"],
            location="Stone Dungeon",
            description="Vikram is wounded in the ribs inside the Stone Dungeon.",
            character_updates={
                "Vikram": {
                    "physical_condition": "injured",
                    "injury_added": "cracked ribs",
                    "energy_delta": -0.5,
                }
            },
            world_updates={
                "location_states": {
                    "Stone Dungeon": {"acoustic_env": "echoing_dungeon", "atmosphere": "grim"}
                }
            },
        )
        store.commit_scene_memory("scene_01", 1, [ev_inj], location="Stone Dungeon")

        ctx = MemoryRetriever.retrieve_for_scene(
            store=store,
            chapter=1,
            scene_id="scene_02",
            active_characters=["Vikram", "Meera"],
            location="Stone Dungeon",
        )

        # Case A: Neutral segment -> receives conservative "strained" emotion and acoustic_env
        seg_neutral = {
            "speaker": "Vikram",
            "type": "dialogue",
            "text": "हमें यहाँ से निकलना होगा।",
            "emotion": "neutral",
        }
        enriched_a = ctx.apply_performance_guidance_to_segment(seg_neutral, target_speaker="Meera")
        self.assertEqual(enriched_a["emotion"], "strained")
        self.assertEqual(enriched_a["acoustic_env"], "echoing_dungeon")
        self.assertEqual(enriched_a["memory_vocal_constraint"], "strained_breath")

        # Case B: Explicit screenplay emotion ("sarcastic_laugh") -> MUST NOT be overwritten!
        seg_explicit = {
            "speaker": "Vikram",
            "type": "dialogue",
            "text": "[laughing] यह घाव तो बस एक खरोंच है!",
            "emotion": "sarcastic_laugh",
        }
        enriched_b = ctx.apply_performance_guidance_to_segment(seg_explicit, target_speaker="Meera")
        self.assertEqual(enriched_b["emotion"], "sarcastic_laugh")
        self.assertNotIn("memory_vocal_constraint", enriched_b)

    def test_03_memory_store_versioning_and_save_load_roundtrip(self):
        """MemoryStore increments memory_version deterministically, persists to JSON, and traces mutations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = MemoryStore.default_store_path(Path(tmpdir))
            store = MemoryStore()

            ev = StoryEvent(
                event_type=StoryEventType.GOAL_UPDATED,
                chapter=1,
                scene="scene_01",
                participants=["Meera"],
                location="Watchtower",
                description="Meera resolves to decode the cipher.",
                character_updates={"Meera": {"immediate_goal": "Decode the northern cipher"}},
            )
            store.commit_scene_memory("scene_01", 1, [ev], source_text="Meera resolved to decode the cipher.")
            self.assertEqual(store.memory_version, 1)
            self.assertNotEqual(store.version_hash, "genesis")

            store.save(store_path)
            loaded = MemoryStore.load(store_path)
            self.assertEqual(loaded.memory_version, 1)
            self.assertEqual(loaded.version_hash, store.version_hash)
            self.assertEqual(
                loaded.get_character_state("Meera").immediate_goal,
                "Decode the northern cipher",
            )

            mutations = loaded.trace_mutations(entity_name="Meera", chapter=1)
            self.assertGreaterEqual(len(mutations), 1)
            self.assertEqual(mutations[0].source_event_id, ev.event_id)

    def test_04_persistence_safety_and_backup_recovery(self):
        """
        Persistence Safety:
        - Saving creates .bak copy of prior valid state.
        - Primary file corruption recovers from valid .bak.
        - Unrecoverable corruption (corrupt primary + missing/corrupt backup) raises MemoryPersistenceError.
        - Invalid schema in backup is rejected (fails closed).
        """
        import json
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = MemoryStore.default_store_path(Path(tmpdir))
            bak_path = store_path.with_name(store_path.name + ".bak")
            store = MemoryStore()

            ev1 = StoryEvent(
                event_type=StoryEventType.GOAL_UPDATED,
                chapter=1,
                scene="scene_01",
                participants=["Meera"],
                description="Initial valid state.",
                character_updates={"Meera": {"immediate_goal": "Initial Goal"}},
            )
            store.commit_scene_memory("scene_01", 1, [ev1])
            store.save(store_path)

            # First save: store_path exists, no .bak yet
            self.assertTrue(store_path.exists())
            self.assertFalse(bak_path.exists())

            # Second save: modifies state and saves again -> creates .bak
            ev2 = StoryEvent(
                event_type=StoryEventType.GOAL_UPDATED,
                chapter=1,
                scene="scene_02",
                participants=["Meera"],
                description="Updated valid state.",
                character_updates={"Meera": {"immediate_goal": "Updated Goal"}},
            )
            store.commit_scene_memory("scene_02", 1, [ev2])
            store.save(store_path)

            self.assertTrue(store_path.exists())
            self.assertTrue(bak_path.exists())

            # Verify backup contains the prior valid version 1 state
            bak_data = json.loads(bak_path.read_text(encoding="utf-8"))
            self.assertEqual(bak_data["memory_version"], 1)

            # Scenario A: Corrupt primary file, valid backup exists -> recovers safely
            store_path.write_text("{CORRUPT_JSON_SYNTAX_ERROR!", encoding="utf-8")
            recovered = MemoryStore.load(store_path)
            self.assertEqual(recovered.memory_version, 1)
            self.assertEqual(recovered.get_character_state("Meera").immediate_goal, "Initial Goal")

            # Scenario B: Corrupt primary file AND corrupt backup file -> raises MemoryPersistenceError
            bak_path.write_text("{ANOTHER_CORRUPT_JSON_ERROR!", encoding="utf-8")
            with self.assertRaises(MemoryPersistenceError):
                MemoryStore.load(store_path)

            # Scenario C: Corrupt primary file AND backup has invalid schema / missing fields -> raises MemoryPersistenceError
            bak_path.write_text(json.dumps({"schema_version": "2.0", "some_random_key": 123}), encoding="utf-8")
            with self.assertRaises(MemoryPersistenceError):
                MemoryStore.load(store_path)

            # Scenario D: Missing backup and corrupt primary -> raises MemoryPersistenceError (never silent reset)
            bak_path.unlink()
            with self.assertRaises(MemoryPersistenceError):
                MemoryStore.load(store_path)

    def test_05_transactional_rollback_after_nested_mutations(self):
        """
        Transactional Rollback:
        If an exception is raised after nested character, world, relationship, or timeline mutations,
        the true deep snapshot restores 100% of the pre-commit state exactly.
        """
        from unittest.mock import patch

        store = MemoryStore()
        # Seed initial state
        ev_init = StoryEvent(
            event_type=StoryEventType.CHARACTER_INJURED,
            chapter=1,
            scene="scene_01",
            participants=["Vikram"],
            description="Vikram starts with slight strain.",
            character_updates={"Vikram": {"energy_delta": -0.1}},
        )
        store.commit_scene_memory("scene_01", 1, [ev_init])
        self.assertEqual(store.memory_version, 1)
        init_version_hash = store.version_hash

        # Capture pre-failure snapshot representation
        initial_dump = store.model_dump()

        # Propose multi-domain scene event
        ev_multi = StoryEvent(
            event_type=StoryEventType.LOCATION_CHANGED,
            chapter=2,
            scene="scene_01",
            participants=["Vikram"],
            location="Secret Fortress",
            description="Vikram travels to Secret Fortress.",
            character_updates={
                "Vikram": {
                    "location": "Secret Fortress",
                    "energy_delta": -0.2,
                }
            },
            world_updates={
                "location_states": {
                    "Secret Fortress": {"atmosphere": "tense", "acoustic_env": "echoing_stone"}
                }
            },
        )

        # Inject failure in record_events_on_timeline, which occurs AFTER character and world deltas have been applied
        with patch(
            "audiobook_factory.translation.memory.memory_store.record_events_on_timeline",
            side_effect=RuntimeError("Simulated mid-commit failure after nested mutation"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                store.commit_scene_memory(
                    scene_id="scene_01",
                    chapter=2,
                    events=[ev_multi],
                    location="Secret Fortress",
                )
            self.assertIn("Simulated mid-commit failure", str(ctx.exception))

        # Verify that store state was 100% rolled back
        self.assertEqual(store.memory_version, 1)
        self.assertEqual(store.version_hash, init_version_hash)
        self.assertEqual(len(store.commit_history), 1)

        # Vikram's location should still be Unspecified, NOT Secret Fortress
        self.assertEqual(store.get_character_state("Vikram").current_location, "Unspecified")
        # World state should NOT have Secret Fortress
        self.assertNotIn("Secret Fortress", store.world_state.location_states)
        # Event should NOT be in store.events
        self.assertNotIn(ev_multi.event_id, store.events)

        # Complete deep equality check
        self.assertEqual(store.model_dump(), initial_dump)

    def test_06_book_bible_hard_canon_immutability(self):
        """
        Hard Canon Immutability:
        Dynamic relationship evolution and scene commits must NEVER mutate BookBible.
        BookBible version hash and relationship records remain 100% identical.
        """
        bible = BookBible(book_title="The Frozen Citadel")
        bible.characters["Vikram"] = BookEntity(canonical_id="vikram", english_name="Vikram", gender="male")
        bible.characters["Rudra"] = BookEntity(canonical_id="rudra", english_name="Rudra", gender="male")
        bible.relationships.append(
            DynamicRelationship(
                from_entity="Vikram",
                to_entity="Rudra",
                default_pronoun="aap",
                current_pronoun="aap",
                respect_level=4,
                hostility_level=0,
            )
        )
        h_initial = bible.get_version_hash()

        store = MemoryStore()
        store.seed_from_book_bible(bible)

        # Verify initial seeded state in MemoryStore
        rel = store.get_relationship("Vikram", "Rudra")
        self.assertIsNotNone(rel)
        self.assertEqual(rel.active_pronoun, "aap")

        # Create scene event where Vikram betrays Rudra and relationship collapses
        ev_betray = StoryEvent(
            event_type=StoryEventType.BETRAYAL,
            chapter=3,
            scene="scene_01",
            participants=["Vikram", "Rudra"],
            description="Vikram confronts Rudra with hostile disrespect.",
            importance=5,
            relationship_impacts=[
                {
                    "speaker": "Vikram",
                    "target": "Rudra",
                    "interaction_type": "betrayal",
                    "explicit_deltas": {"trust": -3, "tension": 3, "respect": -3},
                }
            ],
        )
        store.commit_scene_memory(
            scene_id="scene_01",
            chapter=3,
            events=[ev_betray],
            book_bible=bible,
        )

        # 1. Dynamic state in MemoryStore evolved
        dyn_rel = store.get_relationship("Vikram", "Rudra")
        self.assertIsNotNone(dyn_rel)
        self.assertLess(dyn_rel.trust, 2)
        self.assertGreaterEqual(dyn_rel.tension, 2)

        # 2. BookBible remains strictly immutable Hard Canon!
        self.assertEqual(len(bible.relationships), 1)
        self.assertEqual(bible.relationships[0].current_pronoun, "aap")
        self.assertEqual(bible.relationships[0].default_pronoun, "aap")
        self.assertEqual(bible.relationships[0].respect_level, 4)
        self.assertEqual(bible.relationships[0].hostility_level, 0)
        self.assertEqual(bible.get_version_hash(), h_initial)


if __name__ == "__main__":
    unittest.main()
