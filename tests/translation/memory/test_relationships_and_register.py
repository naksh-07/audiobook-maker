#!/usr/bin/env python3
"""
Unit tests for evidence-backed relationship evolution, bounded contextual priors,
and Hindi pronoun/register resolution (Memory 2.0).
"""

import unittest
from audiobook_factory.translation.relationship_state import (
    DynamicRelationshipState,
    RelationshipStateEngine,
)
from audiobook_factory.translation.memory import (
    StoryEventType,
    StoryEvent,
    MemoryStore,
)


class TestRelationshipsAndRegister(unittest.TestCase):

    def test_01_bounded_contextual_priors_and_pronoun_evolution(self):
        """
        Refinement 3: Archetype priors modulate relationship state based on existing state,
        event importance, and semantic evidence, driving aap -> tum -> tu shifts.
        """
        rel = DynamicRelationshipState(
            speaker="Vikram",
            target="Meera",
            familiarity=1,
            power_balance=0,
            respect=3,
            trust=1,
            affection=0,
            tension=1,
            active_pronoun="aap",
        )
        self.assertEqual(RelationshipStateEngine.resolve_hindi_pronoun(rel), "aap")
        self.assertEqual(RelationshipStateEngine.resolve_vocabulary_register(rel), "formal_respectful")

        # Shared danger event shifts familiarity and trust -> aap to tum
        prior_deltas = RelationshipStateEngine.compute_contextual_prior_deltas(
            interaction_type="shared_danger",
            existing_rel=rel,
            event_importance=4,
        )
        rel = RelationshipStateEngine.apply_relationship_mutation(
            rel=rel,
            deltas=prior_deltas,
            event_id="evt_shared_danger_01",
            chapter=2,
            scene="scene_02",
            notes="Survived canyon ambush together",
        )
        self.assertEqual(rel.active_pronoun, "tum")
        self.assertIn("evt_shared_danger_01", rel.evidence_event_ids)
        self.assertEqual(len(rel.mutation_history), 1)

        # Romantic confession / deep reconciliation increases affection and familiarity -> tu/intimate
        confess_deltas = RelationshipStateEngine.compute_contextual_prior_deltas(
            interaction_type="romantic_confession",
            existing_rel=rel,
            event_importance=5,
            explicit_deltas={"familiarity": 2, "affection": 2, "respect": -2},
        )
        rel = RelationshipStateEngine.apply_relationship_mutation(
            rel=rel,
            deltas=confess_deltas,
            event_id="evt_confess_02",
            chapter=6,
            scene="scene_03",
            notes="Intimate confession by the campfire",
        )
        self.assertEqual(rel.active_pronoun, "tu")
        self.assertEqual(RelationshipStateEngine.resolve_vocabulary_register(rel), "intimate_warm")
        self.assertEqual(len(rel.evidence_event_ids), 2)

    def test_02_betrayal_collapses_trust_to_hostile_street_register(self):
        """Betrayal by a deeply trusted ally causes a sharp drop in trust and shifts register to hostile_street."""
        store = MemoryStore()
        store.relationships["Vikram->Rudra"] = DynamicRelationshipState(
            speaker="Vikram",
            target="Rudra",
            familiarity=3,
            respect=2,
            trust=4,
            affection=2,
            tension=0,
            active_pronoun="tum",
        )

        ev_betray = StoryEvent(
            event_type=StoryEventType.BETRAYAL,
            chapter=5,
            scene="scene_01",
            participants=["Vikram", "Rudra"],
            location="Iron Gate",
            description="Rudra betrays Vikram to the assassins.",
            importance=5,
            relationship_impacts=[
                {"speaker": "Vikram", "target": "Rudra", "interaction_type": "betrayal"}
            ],
        )
        report = store.commit_scene_memory("scene_01", 5, [ev_betray], location="Iron Gate")
        self.assertEqual(len(report.rejected_deltas), 0)

        updated_rel = store.get_relationship("Vikram", "Rudra")
        self.assertIsNotNone(updated_rel)
        self.assertLess(updated_rel.trust, 2)
        self.assertGreaterEqual(updated_rel.tension, 2)
        self.assertIn(ev_betray.event_id, updated_rel.evidence_event_ids)


if __name__ == "__main__":
    unittest.main()
