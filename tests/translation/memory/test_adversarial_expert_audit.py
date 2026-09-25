#!/usr/bin/env python3
"""
Adversarial Expert Audit Test Suite for World + Character Memory 2.0.
Conducts rigorous chaos injection, boundary stress, epistemic attack simulation,
Devanagari script contracts, and fail-closed persistence probing.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from audiobook_factory.translation.book_bible import BookBible
from audiobook_factory.translation.memory.events import StoryEvent, StoryEventType, TemporalMode
from audiobook_factory.translation.memory.memory_delta import StateDelta, DeltaDomain, StateMutability
from audiobook_factory.translation.relationship_state import DynamicRelationshipState
from audiobook_factory.translation.memory.character_memory import (
    CharacterState,
    CharacterKnowledgeEngine,
    KnowledgeStatus,
    KnowledgeFact,
)
from audiobook_factory.translation.memory.memory_store import MemoryStore, MemoryPersistenceError
from audiobook_factory.translation.memory.memory_validator import MemoryValidator, ValidationOutcome
from audiobook_factory.translation.memory.memory_context import MemoryContext
from audiobook_factory.translation.memory.memory_retriever import MemoryRetriever


class TestAdversarialExpertAudit:
    """Adversarial stress and boundary tests designed by the Dual Expert Audit team."""

    def test_audit_devanagari_parenthetical_director_supremacy(self):
        """
        Probe 1 (P1 finding): Screenplay contains Hindi/Devanagari parenthetical stage cue.
        Memory performance guidance must NOT override existing emotion or inject strain
        when explicit Devanagari directorial cues like (धीमी आवाज़ में) are present.
        """
        store = MemoryStore()
        c_state = store.get_character_state("Kabir")
        c_state.physical_condition = "critical"
        c_state.active_injuries = ["deep_wound"]
        c_state.current_emotion = "terrified"
        c_state.emotion_intensity = 0.95

        ctx = MemoryContext(
            chapter=1,
            scene_id="scene_01",
            active_character_states={"Kabir": c_state},
        )

        # Segment with Devanagari parenthetical stage direction
        seg = {
            "speaker": "Kabir",
            "text": "मैं तुम्हें कभी माफ नहीं करूंगा (धीमी आवाज़ में)!",
            "emotion": "neutral",  # Director used parenthetical for acting cue
        }

        enriched = ctx.apply_performance_guidance_to_segment(seg)

        # Director's intent must remain supreme: memory must NOT stomp emotion to 'strained'
        assert enriched["emotion"] == "neutral"
        assert not enriched.get("memory_vocal_constraint")

    def test_audit_secret_revealed_metadata_revealer_and_participants(self):
        """
        Probe 2 (P2 finding): SECRET_REVEALED event specifies revealer via metadata['revealer']
        or participants[0]. If the revealer does not know the secret (status != KNOWN),
        validator must strictly reject the event.
        """
        store = MemoryStore()
        # Vikram does NOT know secret_plan
        store.get_character_state("Vikram")

        ev = StoryEvent(
            event_id="evt_rev_001",
            chapter=2,
            scene="scene_01",
            event_type=StoryEventType.SECRET_REVEALED,
            description="Vikram reveals the hidden tunnel to Rohit",
            participants=["Vikram", "Rohit"],
            metadata={"revealer": "Vikram", "fact_id": "secret_tunnel"},
        )

        report = store.commit_scene_memory(
            scene_id="scene_01",
            chapter=2,
            events=[ev],
        )

        assert report.outcome == ValidationOutcome.CONFLICT
        assert "evt_rev_001" in report.rejected_event_ids
        assert any(c.conflict_type == "knowledge_violation" for c in report.flagged_conflicts)
        assert "secret_tunnel" not in store.facts_registry

    def test_audit_knowledge_fact_case_insensitive_status(self):
        """
        Probe 3: Case-insensitive character name query on KnowledgeFact.
        Must not return UNKNOWN due to case mismatch when character is in known_by.
        """
        fact = KnowledgeFact(
            fact_id="fact_truth_01",
            subject="Rajesh",
            predicate="location",
            value="Old Fort",
            source_event="evt_01",
            known_by=["Rajesh", "Maya"],
            status=KnowledgeStatus.KNOWN,
            character_statuses={"Rajesh": KnowledgeStatus.KNOWN, "Maya": KnowledgeStatus.KNOWN},
        )

        # Query with lowercase and titlecase
        assert fact.get_status_for_character("rajesh") == KnowledgeStatus.KNOWN
        assert fact.get_status_for_character("MAYA") == KnowledgeStatus.KNOWN
        assert fact.get_status_for_character("UnknownPerson") == KnowledgeStatus.UNKNOWN

    def test_audit_deep_snapshot_nested_collections_isolation(self):
        """
        Probe 4: Deep snapshot must fully isolate nested mutable collections
        (active_injuries, known_facts, arc_state) across rolled-back transactions.
        """
        store = MemoryStore()
        c = store.get_character_state("Karan")
        c.active_injuries = ["broken_rib"]
        c.known_facts = ["secret_map"]

        # Snapshot taken before failed commit
        with patch.object(
            MemoryValidator,
            "validate_deltas",
            side_effect=RuntimeError("Simulated catastrophic crash mid-commit"),
        ):
            with pytest.raises(RuntimeError):
                store.commit_scene_memory(
                    scene_id="scene_fail",
                    chapter=1,
                    events=[],
                )

        # Verify Karan's collections are exact and deepcopy-isolated
        restored = store.get_character_state("Karan")
        assert restored.active_injuries == ["broken_rib"]
        assert restored.known_facts == ["secret_map"]

        # Mutating restored must not be aliased
        restored.active_injuries.append("sprained_ankle")
        fresh_snap = store._create_snapshot()
        assert "sprained_ankle" in fresh_snap["character_states"]["Karan"].active_injuries

    def test_audit_corrupted_bak_schema_version_fail_closed(self, tmp_path):
        """
        Probe 5: Primary file is corrupt, but .bak file has incompatible schema version ("1.0").
        Must strictly fail-closed with MemoryPersistenceError without loading invalid backup.
        """
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir(parents=True)
        primary_file = mem_dir / "memory_store.json"
        bak_file = mem_dir / "memory_store.json.bak"

        # Corrupt primary
        primary_file.write_text("{CORRUPTED_JSON_NOT_VALID", encoding="utf-8")

        # Invalid legacy schema version in backup
        bak_data = {
            "schema_version": "1.0",  # Legacy/incompatible version
            "character_states": {},
            "relationships": {},
            "facts_registry": {},
            "world_state": {
                "location_states": {},
                "organization_states": {},
                "object_states": {},
                "timeline": [],
                "open_threads": [],
                "discovered_rules": [],
            },
            "events": {},
            "commit_history": [],
        }
        bak_file.write_text(json.dumps(bak_data), encoding="utf-8")

        with pytest.raises(MemoryPersistenceError) as exc_info:
            MemoryStore.load(primary_file)

        assert "Incompatible or missing schema_version" in str(exc_info.value)
        assert "Silent reset is prevented" in str(exc_info.value)

    def test_audit_long_novel_1000_event_token_budget_enforcement(self):
        """
        Probe 6: 1,000 events, 50 characters, and 100 relationships across a massive novel.
        MemoryRetriever.retrieve_for_scene must enforce the token budget (<= 800 tokens)
        without memory leaks or unbounded prompt bloating.
        """
        store = MemoryStore()

        # Seed 50 characters and 100 relationships
        for i in range(50):
            c_name = f"Char_{i:02d}"
            c_st = store.get_character_state(c_name)
            c_st.immediate_goal = f"Goal for character {i}"
            c_st.active_injuries = [f"injury_{i}"]

        for i in range(100):
            s = f"Char_{i % 50:02d}"
            t = f"Char_{(i + 1) % 50:02d}"
            store.relationships[f"{s}->{t}"] = DynamicRelationshipState(speaker=s, target=t)

        # Seed 1,000 events
        for e_idx in range(1, 1001):
            p1 = f"Char_{e_idx % 50:02d}"
            p2 = f"Char_{(e_idx + 1) % 50:02d}"
            ev = StoryEvent(
                event_id=f"evt_{e_idx:04d}",
                chapter=1 + (e_idx // 10),
                scene=f"scene_{e_idx % 5:02d}",
                event_type=StoryEventType.OTHER,
                description=f"Event number {e_idx} where {p1} interacts with {p2} intensely.",
                participants=[p1, p2],
                salience_score=0.75 if e_idx % 20 == 0 else 0.4,
            )
            store.events[ev.event_id] = ev

        ctx = MemoryRetriever.retrieve_for_scene(
            store=store,
            chapter=50,
            scene_id="scene_01",
            active_characters=["Char_00", "Char_01"],
            max_token_budget=800,
        )

        assert ctx.estimated_tokens() <= 800
        prompt_block = ctx.get_prompt_context()
        assert "Char_00" in prompt_block
        assert "Char_01" in prompt_block
        # Unrelated characters must NOT appear in the prompt block
        assert "Char_25" not in prompt_block

    def test_audit_flashback_mode_chronological_isolation(self):
        """
        Probe 7: Flashback scene referencing deceased character must be allowed without
        triggering dead_character_violation conflicts.
        """
        store = MemoryStore()
        karan = store.get_character_state("Karan")
        karan.is_alive = False
        karan.physical_condition = "deceased"

        # FLASHBACK event involving Karan
        ev_flashback = StoryEvent(
            event_id="evt_fb_001",
            chapter=10,
            scene="scene_03",
            event_type=StoryEventType.OTHER,
            description="Flashback: Karan laughing with Kabir before the tragedy",
            participants=["Karan", "Kabir"],
            temporal_mode=TemporalMode.FLASHBACK,
        )

        delta = StateDelta(
            source_event_id="evt_fb_001",
            chapter=10,
            scene="scene_03",
            domain=DeltaDomain.CHARACTER,
            mutability=StateMutability.SOFT_STATE,
            target_entity="Karan",
            field_name="current_emotion",
            operation="set",
            new_value="joyful",
            temporal_mode=TemporalMode.FLASHBACK,
        )

        report = store.commit_scene_memory(
            scene_id="scene_03",
            chapter=10,
            events=[ev_flashback],
            deltas=[delta],
        )

        # Must NOT conflict because mode is FLASHBACK
        assert report.outcome in (ValidationOutcome.PASS, ValidationOutcome.WARN)
        assert "evt_fb_001" not in report.rejected_event_ids
