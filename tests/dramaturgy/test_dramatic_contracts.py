#!/usr/bin/env python3
"""
Unit Tests for Dramaturgy Data Contracts & Schemas.
Verifies strictly typed Pydantic v2 schemas, backward compatibility with legacy
ScreenplaySegment models, serialization, and round-trip consistency.
"""

import json
import unittest
from audiobook_factory.contracts import ScreenplaySegment, ScreenplayScript
from audiobook_factory.dramaturgy.contracts import (
    DramaticBeat,
    CharacterDramaticObjective,
    SceneDramaticPlan,
    DramaticPlan,
    CharacterPerformanceProfile,
    PerformanceBible,
    DramaticValidationResult,
    DramaticValidationIssue,
    RelationshipShift,
    PhysicalBlocking,
    StoryConnectionRecord,
    ConversationalDynamic,
    DramaticSilenceIntent,
    DramaticStateDelta,
    AdaptationFidelityPolicy,
)


class TestDramaticContracts(unittest.TestCase):

    def test_legacy_screenplay_segment_backward_compatibility(self):
        """Verify legacy segments without dramatic fields parse cleanly with safe defaults."""
        legacy_data = {
            "index": 1,
            "type": "dialogue",
            "speaker": "SpeakerA",
            "text": "Hello there.",
            "emotion": "neutral",
            "pause_after_ms": 500,
        }
        seg = ScreenplaySegment.model_validate(legacy_data)
        self.assertEqual(seg.speaker, "SpeakerA")
        self.assertEqual(seg.text, "Hello there.")
        self.assertIsNone(seg.scene_id)
        self.assertIsNone(seg.beat_id)
        self.assertIsNone(seg.actioning)
        self.assertIsNone(seg.subtext)
        self.assertEqual(seg.performance_priority, "standard")

    def test_enriched_screenplay_segment_parsing(self):
        """Verify new dramatic fields parse and serialize correctly."""
        enriched_data = {
            "index": 2,
            "type": "dialogue",
            "speaker": "SpeakerB",
            "text": "Step back immediately.",
            "emotion": "angry",
            "scene_id": "scene_001",
            "beat_id": "beat_002",
            "dramatic_function": "threat",
            "character_objective": "Halt approach",
            "actioning": "threaten",
            "subtext": "I will strike if you advance.",
            "subtext_confidence": 0.85,
            "surface_emotion": "cold_menace",
            "underlying_emotion": "fear",
            "tension_before": 0.6,
            "tension_after": 0.75,
            "listener_knowledge_state": "Audience knows weapon is poisoned.",
            "performance_priority": "climactic",
        }
        seg = ScreenplaySegment.model_validate(enriched_data)
        self.assertEqual(seg.scene_id, "scene_001")
        self.assertEqual(seg.beat_id, "beat_002")
        self.assertEqual(seg.dramatic_function, "threat")
        self.assertEqual(seg.actioning, "threaten")
        self.assertEqual(seg.subtext, "I will strike if you advance.")
        self.assertEqual(seg.subtext_confidence, 0.85)
        self.assertEqual(seg.tension_after, 0.75)
        self.assertEqual(seg.performance_priority, "climactic")

        # Round trip
        dumped = seg.model_dump()
        self.assertEqual(dumped["actioning"], "threaten")
        self.assertEqual(dumped["tension_before"], 0.6)

    def test_dramatic_beat_creation_and_validation(self):
        """Verify DramaticBeat schema and objective nesting."""
        obj = CharacterDramaticObjective(
            immediate_goal="Extract the secret cipher",
            obstacle="Guards approaching",
            underlying_desire="Protect rebellion",
            core_fear="Execution",
            strategy="Direct intimidation",
            actioning="intimidate",
        )
        beat = DramaticBeat(
            beat_id="scene_001_b001",
            scene_id="scene_001",
            index=1,
            dramatic_function="approach",
            summary="Hero interrogates courier",
            active_characters=["Hero", "Courier"],
            primary_speaker="Hero",
            target_character="Courier",
            objective=obj,
            surface_emotion="cold_menace",
            underlying_emotion="urgency",
            subtext="Speak before the patrol arrives.",
            subtext_confidence=0.9,
            tension_before=0.4,
            tension_after=0.55,
            intensity="medium",
            performance_priority="high_focus",
        )
        self.assertEqual(beat.objective.actioning, "intimidate")
        self.assertEqual(beat.tension_after, 0.55)
        self.assertEqual(beat.performance_priority, "high_focus")

    def test_scene_dramatic_plan_and_chapter_plan(self):
        """Verify SceneDramaticPlan and DramaticPlan serialization."""
        scene = SceneDramaticPlan(
            scene_id="scene_001",
            chapter_num=1,
            scene_title="The Midnight Interrogation",
            scene_type="confrontation",
            location="Stone Crypt",
            time_context="Midnight",
            dramatic_purpose="Force courier to surrender coordinates",
            scene_question="Will courier yield before patrol arrives?",
            stakes="Survival of the vanguard",
            opening_state="Cold tension",
            closing_state="Coordinates secured, courier captive",
            primary_conflict="Interrogator vs defiant captive",
            participants=["Hero", "Courier"],
            dramatic_complexity="HIGH",
            listener_knowledge_state="Audience knows patrol is 5 minutes away",
            major_reveals=["Courier is double agent"],
            reversals=["Courier attempts suicide pill"],
            tension_curve=[0.4, 0.6, 0.85, 0.7],
        )
        plan = DramaticPlan(
            chapter_id="chapter_001",
            chapter_num=1,
            scenes=[scene],
            total_beats=3,
        )
        self.assertEqual(plan.chapter_id, "chapter_001")
        self.assertEqual(len(plan.scenes), 1)
        self.assertEqual(plan.get_scene("scene_001").scene_type, "confrontation")

    def test_performance_bible_contracts(self):
        """Verify PerformanceBible and character profiles."""
        profile = CharacterPerformanceProfile(
            character_name="Protagonist",
            baseline_pace=0.92,
            baseline_energy=0.75,
            articulation="deliberate_crisp",
            emotional_behaviors={"anger": "cold_menace", "fear": "silent_vigilance"},
            restraint_level=0.85,
            speech_quirks=["cynical grunt"],
            performance_rules=["Never shout unless physically mortally wounded"],
        )
        bible = PerformanceBible(
            characters={"Protagonist": profile},
            narrator_style={"baseline_pace": 1.0, "tone": "objective"},
        )
        self.assertIsNotNone(bible.get_profile("protagonist"))
        self.assertEqual(bible.get_profile("protagonist").baseline_pace, 0.92)

    def test_dramatic_validation_contracts(self):
        """Verify DramaticValidationResult serialization."""
        issue = DramaticValidationIssue(
            code="EMOTIONAL_TELEPORTATION",
            severity="WARNING",
            message="Abrupt transition without bridge",
            scene_id="scene_001",
            beat_id="beat_001",
        )
        result = DramaticValidationResult(
            status="WARNING",
            passed=True,
            total_issues=1,
            issues=[issue],
            summary="Validation completed with 1 warning.",
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.total_issues, 1)

    def test_refined_dramatic_contracts_roundtrip(self):
        """Verify serialization and round-trip fidelity of all 10 refined dramatic models."""
        delta = DramaticStateDelta(
            knowledge_delta=["Disclosed: ancient map"],
            relationship_shifts=["Hostility heightened between Harry and Draco"],
            power_shift="Harry established leverage",
            danger_level_delta="escalated",
            decisions_made=["Committed to duel at midnight"],
            emotional_trajectory="Calm defiance -> High alertness",
        )
        rel_shift = RelationshipShift(
            source_character="Harry",
            target_character="Draco",
            dimension="hostility",
            direction="increased",
            description="Duel challenged openly",
        )
        blocking = PhysicalBlocking(
            character="Harry",
            action_description="Harry raises wand in defensive dueling stance",
            dramatic_significance="threat_display",
            spatial_intent="mid_stage",
        )
        s_conn = StoryConnectionRecord(
            connection_type="setup",
            reference_target="ch_midnight_duel",
            description="Sets up midnight trophy room encounter",
            motif_name="wand",
            confidence=0.9,
        )
        dynamic = ConversationalDynamic(
            dynamic_type="escalation",
            initiator="Draco",
            target="Harry",
            description="Draco goads Harry into accepting duel",
        )
        silence = DramaticSilenceIntent(
            purpose="anticipation",
            affected_character="Harry",
            dramatic_rationale="Stillness before wand draw",
            listening_focus="character_reaction",
        )
        policy = AdaptationFidelityPolicy(
            preserve_plot_events=True,
            disallow_fabricated_reveals=True,
        )

        beat = DramaticBeat(
            beat_id="beat_ref_001",
            scene_id="scene_ref_001",
            index=1,
            causal_trigger="Draco insults Harry in common room",
            character_response="Harry steps forward",
            consequence="Duel challenge issued",
            causal_link_type="therefore",
            relationship_shift=rel_shift,
            leverage_holder="Harry",
            vulnerable_character="Draco",
            dramatic_irony="Audience knows Filch is on night patrol",
            blocking=blocking,
            provenance_mode="SOURCE_DIRECT",
            story_connection=s_conn,
            conversational_dynamic=dynamic,
            silence_intent=silence,
        )

        scene = SceneDramaticPlan(
            scene_id="scene_ref_001",
            state_delta=delta,
            epistemic_asymmetry=["Audience aware of Filch prowling halls"],
            narrative_pov="third_person_limited",
            narrative_distance="close_third_person",
            pov_character="Harry",
            story_connections=[s_conn],
            beats=[beat],
        )

        plan = DramaticPlan(
            chapter_id="chap_ref_001",
            scenes=[scene],
            adaptation_policy=policy,
        )

        # JSON Round trip
        raw_json = plan.model_dump_json()
        loaded = DramaticPlan.model_validate_json(raw_json)

        self.assertEqual(loaded.chapter_id, "chap_ref_001")
        self.assertEqual(loaded.version, "1.1")
        self.assertTrue(loaded.adaptation_policy.disallow_fabricated_reveals)
        sc = loaded.scenes[0]
        self.assertEqual(sc.state_delta.danger_level_delta, "escalated")
        self.assertEqual(sc.narrative_pov, "third_person_limited")
        b = sc.beats[0]
        self.assertEqual(b.causal_link_type, "therefore")
        self.assertEqual(b.relationship_shift.dimension, "hostility")
        self.assertEqual(b.blocking.dramatic_significance, "threat_display")
        self.assertEqual(b.silence_intent.purpose, "anticipation")
        self.assertEqual(b.conversational_dynamic.dynamic_type, "escalation")


if __name__ == "__main__":
    unittest.main()
