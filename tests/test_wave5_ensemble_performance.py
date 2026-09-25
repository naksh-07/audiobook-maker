#!/usr/bin/env python3
"""
Test Suite for Wave 5: Ensemble Performance (Phases 17 & 18).
Validates Dialogue Chemistry Turn Coupling, Interruption Sharpness,
Dynamic Energy Contrast, and Long-Form Continuity Persistence.
"""

import tempfile
from pathlib import Path
import pytest

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    ChemistryEvaluationResult,
)
from audiobook_factory.performance.chemistry import ConversationalChemistry
from audiobook_factory.performance.continuity import (
    PerformanceContinuityTracker,
    CharacterPerformanceTelemetry,
)


class TestWave5EnsemblePerformance:
    """Wave 5 Ensemble Performance test suite."""

    def test_01_dialogue_chemistry_turn_taking_latency_and_fidelity(self):
        """Tests turn-taking pause fidelity between conversational turns."""
        dir1 = PerformanceDirection(
            direction_id="pd_001",
            segment_uid="s1",
            index=1,
            speaker="SpeakerA",
            actioning="question",
            pause_after_ms=350,
            energy=0.7,
        )
        dir2 = PerformanceDirection(
            direction_id="pd_002",
            segment_uid="s2",
            index=2,
            speaker="SpeakerB",
            actioning="answer",
            pause_before_ms=350,
            turn_taking_behavior="immediate",
            energy=0.7,
        )

        take1 = TakeVariant(
            take_id="t1",
            segment_uid="s1",
            segment_index=1,
            audio_path="/tmp/fake_1.wav",
            direction=dir1,
        )
        take2 = TakeVariant(
            take_id="t2",
            segment_uid="s2",
            segment_index=2,
            audio_path="/tmp/fake_2.wav",
            direction=dir2,
        )

        # 1. Matching actual gap
        chem_res = ConversationalChemistry.evaluate_dialogue_chemistry(
            prev_take=take1,
            curr_take=take2,
            actual_gap_ms=50,
        )
        assert chem_res.passed is True
        assert chem_res.pause_fidelity_score >= 0.90
        assert chem_res.composite_chemistry_score >= 0.80

        # 2. Large unexpected gap when immediate turn was expected
        chem_bad_gap = ConversationalChemistry.evaluate_dialogue_chemistry(
            prev_take=take1,
            curr_take=take2,
            actual_gap_ms=600,
        )
        assert chem_bad_gap.pause_fidelity_score < 0.50
        assert any("Turn pause latency mismatch" in d for d in chem_bad_gap.diagnostics)

    def test_02_dialogue_chemistry_interruption_sharpness(self):
        """Tests that interruption turns require clean near-zero gaps."""
        dir_cut = PerformanceDirection(
            direction_id="pd_003",
            segment_uid="s3",
            index=3,
            speaker="SpeakerA",
            interruption_behavior="abrupt_cut",
            silence_type="interruption_cut",
            energy=0.8,
        )
        dir_int = PerformanceDirection(
            direction_id="pd_004",
            segment_uid="s4",
            index=4,
            speaker="SpeakerB",
            turn_taking_behavior="immediate",
            pause_before_ms=0,
            energy=0.85,
        )

        take_cut = TakeVariant(
            take_id="t3",
            segment_uid="s3",
            segment_index=3,
            audio_path="/tmp/fake_3.wav",
            direction=dir_cut,
        )
        take_int = TakeVariant(
            take_id="t4",
            segment_uid="s4",
            segment_index=4,
            audio_path="/tmp/fake_4.wav",
            direction=dir_int,
        )

        # Crisp interruption (40ms)
        chem_good = ConversationalChemistry.evaluate_dialogue_chemistry(
            prev_take=take_cut,
            curr_take=take_int,
            actual_gap_ms=40,
        )
        assert chem_good.interruption_quality_score == 1.0
        assert chem_good.passed is True

        # Flawed interruption with dead air (350ms)
        chem_flawed = ConversationalChemistry.evaluate_dialogue_chemistry(
            prev_take=take_cut,
            curr_take=take_int,
            actual_gap_ms=350,
        )
        assert chem_flawed.interruption_quality_score < 0.50
        assert any("Dead air on interrupted turn" in d for d in chem_flawed.diagnostics)

    def test_03_dialogue_chemistry_energy_dynamics_and_threat(self):
        """Tests relational dynamic energy contrast in intimidation and intimacy."""
        # Intimidation scenario
        dir_threat = PerformanceDirection(
            direction_id="pd_005",
            segment_uid="s5",
            index=5,
            speaker="Inquisitor",
            actioning="threaten and corner",
            power_position="dominant",
            energy=0.85,
        )
        dir_submissive_proper = PerformanceDirection(
            direction_id="pd_006",
            segment_uid="s6",
            index=6,
            speaker="Captive",
            actioning="plead",
            power_position="submissive",
            energy=0.50,
        )
        dir_submissive_overpowering = PerformanceDirection(
            direction_id="pd_007",
            segment_uid="s7",
            index=7,
            speaker="Captive",
            actioning="plead",
            power_position="submissive",
            energy=0.95,
        )

        take_threat = TakeVariant(take_id="t5", segment_uid="s5", segment_index=5, audio_path="/tmp/t5.wav", direction=dir_threat)
        take_sub_good = TakeVariant(take_id="t6", segment_uid="s6", segment_index=6, audio_path="/tmp/t6.wav", direction=dir_submissive_proper)
        take_sub_bad = TakeVariant(take_id="t7", segment_uid="s7", segment_index=7, audio_path="/tmp/t7.wav", direction=dir_submissive_overpowering)

        eval_good = ConversationalChemistry.evaluate_dialogue_chemistry(take_threat, take_sub_good)
        assert eval_good.energy_contrast_score == 1.0

        eval_bad = ConversationalChemistry.evaluate_dialogue_chemistry(take_threat, take_sub_bad)
        assert eval_bad.energy_contrast_score < 0.70
        assert any("Submissive respondent inappropriately projected higher energy" in d for d in eval_bad.diagnostics)

    def test_04_character_performance_telemetry_and_take_tracking(self):
        """Tests CharacterPerformanceTelemetry tracking and take EMA confidence."""
        tracker = PerformanceContinuityTracker()
        dir_char = PerformanceDirection(
            direction_id="pd_010",
            segment_uid="s10",
            index=10,
            speaker="Commander",
            pace=1.1,
            energy=0.8,
            restraint=0.7,
            surface_emotion="grim",
            physical_state="normal",
        )

        tracker.record_direction(dir_char, duration_sec=4.2)
        assert "Commander" in tracker.characters
        telem = tracker.characters["Commander"]
        assert telem.total_segments == 1
        assert telem.total_duration_sec == 4.2
        assert telem.last_emotional_state == "grim"
        assert telem.last_energy == 0.8
        assert telem.last_pace == 1.1
        assert telem.last_physical_state == "normal"

        # Record takes with voice identity similarity
        tracker.record_take("Commander", take_id="c001_s010_take_a", duration_sec=4.2, voice_identity_score=0.92)
        assert "c001_s010_take_a" in telem.recent_take_ids
        assert telem.voice_identity_confidence < 1.0
        assert telem.voice_identity_confidence > 0.90

    def test_05_long_form_continuity_inter_chapter_transition_audit(self):
        """Tests inter-chapter continuity audits for unbuffered jumps."""
        tracker = PerformanceContinuityTracker()

        # Seed character in wounded state
        dir_old = PerformanceDirection(
            direction_id="pd_020",
            segment_uid="s20",
            index=20,
            speaker="Scout",
            pace=0.8,
            energy=0.3,
            physical_state="wounded",
            surface_emotion="exhausted",
        )
        tracker.record_direction(dir_old, duration_sec=3.0)

        # New chapter direction: sudden recovery to combat strain without transition beat
        dir_new_rupture = PerformanceDirection(
            direction_id="pd_021",
            segment_uid="s21",
            index=1,
            speaker="Scout",
            pace=1.3,
            energy=0.95,
            physical_state="combat_strain",
            surface_emotion="enraged",
        )

        warnings = tracker.audit_inter_chapter_transition("Scout", dir_new_rupture)
        assert len(warnings) >= 2
        assert any("Physical Continuity Alert" in w for w in warnings)
        assert any("Energy Continuity Alert" in w for w in warnings)

    def test_06_continuity_persistence_json_roundtrip(self):
        """Tests serializing and loading continuity bank across chapter boundaries."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "character_continuity.json"

            tracker1 = PerformanceContinuityTracker()
            for i in range(3):
                tracker1.record_direction(
                    PerformanceDirection(
                        index=i + 1,
                        speaker="Officer",
                        pace=1.05,
                        energy=0.75,
                        surface_emotion="focused",
                    ),
                    duration_sec=2.5,
                )
            tracker1.record_take("Officer", "take_101", 2.5, voice_identity_score=0.95)
            tracker1.advance_chapter("chapter_001")
            tracker1.save_to_file(file_path)

            assert file_path.exists()

            tracker2 = PerformanceContinuityTracker()
            tracker2.load_from_file(file_path)

            assert "Officer" in tracker2.characters
            t2 = tracker2.characters["Officer"]
            assert t2.total_segments == 3
            assert t2.chapter_count == 1
            assert t2.average_pace == 1.05
            assert "take_101" in t2.recent_take_ids
