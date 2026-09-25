#!/usr/bin/env python3
"""
Unit tests for Selective 7-Tier MemoryRetriever, Narrative Salience ranking,
Conservative Performance Guidance (Refinement 2), and Versioned MemoryStore.
"""

import tempfile
import unittest
from pathlib import Path

from audiobook_factory.translation.book_bible import BookBible, BookEntity
from audiobook_factory.translation.relationship_state import DynamicRelationshipState
from audiobook_factory.translation.memory import (
    StoryEventType,
    StoryEvent,
    MemoryStore,
    MemoryRetriever,
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


if __name__ == "__main__":
    unittest.main()
