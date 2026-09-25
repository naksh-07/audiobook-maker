#!/usr/bin/env python3
"""
Audiobook Factory - Wave D Scene Selection, Chemistry & Continuity Test Suite.
Validates:
1. Scene-level simultaneous take selection (`select_scene_takes`).
2. Interpersonal conversational chemistry integration into multi-take selection.
3. Dramatic performance arc tracking (fatigue defense, premature climax defense, climactic release).
4. Performance continuity tracker synchronization across scene dialogue turns.
"""

from pathlib import Path
import pytest
import numpy as np
import wave

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceEvaluationResult,
    EvaluationDimensionScore,
    PerformanceEvidence,
    AcousticEvidence,
    ProsodyEvidence,
    PacingEvidence,
)
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.take_selector import IntelligentTakeSelector
from audiobook_factory.performance.chemistry import ConversationalChemistry
from audiobook_factory.performance.continuity import PerformanceContinuityTracker


def create_waveform_file(
    filepath: Path,
    duration_sec: float = 1.5,
    sample_rate: int = 24000,
    amplitude: float = 0.5,
) -> Path:
    """Helper to create dummy wave file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sample_rate * duration_sec)
    t = np.arange(num_samples) / float(sample_rate)
    samples = (np.sin(2 * np.pi * 150.0 * t) * amplitude * 28000.0).clip(-32767, 32767).astype(np.int16)

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())

    return filepath


class TestSceneSelectionAndContinuitySuite:
    """Wave D scene-level selection, chemistry, and continuity test matrix."""

    @pytest.fixture(autouse=True)
    def setup_suite(self, tmp_path):
        self.tmp_dir = tmp_path
        self.takes_dir = self.tmp_dir / "scene_takes"
        self.takes_dir.mkdir(parents=True, exist_ok=True)
        self.evaluator = PerformanceEvaluator()
        self.selector = IntelligentTakeSelector(evaluator=self.evaluator)

    def test_01_scene_empty_and_single_turn_boundary(self):
        """Verifies boundary handling for empty scenes and single-turn scenes."""
        # Empty scene
        empty_res = self.selector.select_scene_takes(scene_takes=[], directions=[], texts=[])
        assert empty_res == []

        # Single-turn scene
        pd = PerformanceDirection(index=1, speaker="Narrator")
        w = create_waveform_file(self.takes_dir / "s01.wav")
        t = TakeVariant(take_id="t_single", segment_uid="u1", segment_index=1, variant_type="standard", audio_path=str(w), direction=pd)

        res = self.selector.select_scene_takes(
            scene_takes=[[t]],
            directions=[pd],
            texts=["The night was dark."],
        )
        assert len(res) == 1
        assert res[0].take_id == "t_single"
        assert res[0].is_selected is True

    def test_02_conversational_chemistry_in_dialogue_scene(self):
        """Verifies conversational chemistry biases selection toward responsive turn-taking."""
        d1 = PerformanceDirection(
            index=1,
            speaker="SpeakerA",
            interruption_behavior="abrupt_cut",
            silence_type="interruption_cut",
            energy=0.85,
            actioning="challenge",
        )
        d2_immediate = PerformanceDirection(
            index=2,
            speaker="SpeakerB",
            turn_taking_behavior="immediate",
            pause_before_ms=0,
            energy=0.80,
            power_position="contested",
            actioning="counter",
        )
        d2_delayed = PerformanceDirection(
            index=2,
            speaker="SpeakerB",
            turn_taking_behavior="delayed_reaction",
            pause_before_ms=800,
            energy=0.80,
            power_position="contested",
            actioning="counter",
        )

        w1 = create_waveform_file(self.takes_dir / "turn1.wav")
        w2_a = create_waveform_file(self.takes_dir / "turn2_fast.wav")
        w2_b = create_waveform_file(self.takes_dir / "turn2_slow.wav")

        t1 = TakeVariant(take_id="t1", segment_uid="s1", segment_index=1, variant_type="standard", audio_path=str(w1), direction=d1)

        # Candidate A has immediate chemistry coupling (40ms turn-taking)
        t2_fast = TakeVariant(
            take_id="t2_fast",
            segment_uid="s2",
            segment_index=2,
            variant_type="standard",
            audio_path=str(w2_a),
            direction=d2_immediate,
            evaluation=PerformanceEvaluationResult(
                take_id="t2_fast",
                overall_score=0.82,
                passed=True,
                dimensions={"subtext": EvaluationDimensionScore(dimension="subtext", score=0.82)},
            ),
        )
        # Candidate B has slightly higher isolated score but awkward delayed latency after an abrupt cut
        t2_slow = TakeVariant(
            take_id="t2_slow",
            segment_uid="s2",
            segment_index=2,
            variant_type="more_restrained",
            audio_path=str(w2_b),
            direction=d2_delayed,
            evaluation=PerformanceEvaluationResult(
                take_id="t2_slow",
                overall_score=0.83,
                passed=True,
                dimensions={"subtext": EvaluationDimensionScore(dimension="subtext", score=0.83)},
            ),
        )

        results = self.selector.select_scene_takes(
            scene_takes=[[t1], [t2_slow, t2_fast]],
            directions=[d1, d2_immediate],
            texts=["Listen to me—", "I am listening!"],
        )

        assert len(results) == 2
        assert results[0].take_id == "t1"
        assert results[1].take_id == "t2_fast"
        assert results[1].is_selected is True

    def test_03_performance_arc_fatigue_defense(self):
        """Verifies scene arc tracker penalizes endless maximum-energy shouting in favor of dynamic breathing room."""
        # 3 preceding turns with maximum energy
        d1 = PerformanceDirection(index=1, speaker="Warrior", energy=0.90, intensity="high")
        d2 = PerformanceDirection(index=2, speaker="Warrior", energy=0.90, intensity="high")
        d3 = PerformanceDirection(index=3, speaker="Warrior", energy=0.88, intensity="high")

        # Turn 4: Warrior is speaking aftermath line
        d4 = PerformanceDirection(index=4, speaker="Warrior", energy=0.60, intensity="medium", restraint=0.75)

        w = create_waveform_file(self.takes_dir / "arc_wav.wav")
        t1 = TakeVariant(take_id="t_arc_1", segment_uid="a1", segment_index=1, variant_type="standard", audio_path=str(w), direction=d1)
        t2 = TakeVariant(take_id="t_arc_2", segment_uid="a2", segment_index=2, variant_type="standard", audio_path=str(w), direction=d2)
        t3 = TakeVariant(take_id="t_arc_3", segment_uid="a3", segment_index=3, variant_type="standard", audio_path=str(w), direction=d3)

        # Cand 4A: Controlled restraint / dynamic decompression
        t4_decomp = TakeVariant(
            take_id="t4_decomp",
            segment_uid="a4",
            segment_index=4,
            variant_type="more_restrained",
            audio_path=str(w),
            direction=PerformanceDirection(index=4, speaker="Warrior", energy=0.55, restraint=0.80),
            evaluation=PerformanceEvaluationResult(
                take_id="t4_decomp",
                overall_score=0.82,
                passed=True,
                dimensions={"subtext": EvaluationDimensionScore(dimension="subtext", score=0.85)},
            ),
        )

        # Cand 4B: Continued fatigued shouting
        t4_shout = TakeVariant(
            take_id="t4_shout",
            segment_uid="a4",
            segment_index=4,
            variant_type="exposed",
            audio_path=str(w),
            direction=PerformanceDirection(index=4, speaker="Warrior", energy=0.92, restraint=0.20),
            evaluation=PerformanceEvaluationResult(
                take_id="t4_shout",
                overall_score=0.83,
                passed=True,
                dimensions={"subtext": EvaluationDimensionScore(dimension="subtext", score=0.70)},
            ),
        )

        results = self.selector.select_scene_takes(
            scene_takes=[[t1], [t2], [t3], [t4_shout, t4_decomp]],
            directions=[d1, d2, d3, d4],
            texts=["Charge!", "Strike!", "Hold the line!", "It is over."],
        )

        assert len(results) == 4
        # Turn 4 winner should be decompression, avoiding listener fatigue
        assert results[3].take_id == "t4_decomp"
        assert results[3].is_selected is True

    def test_04_performance_arc_premature_climax_defense(self):
        """Verifies scene arc tracker penalizes unmotivated explosive delivery at scene onset."""
        d1 = PerformanceDirection(
            index=1,
            speaker="Hero",
            energy=0.60,
            intensity="low",
            performance_priority="standard",
        )
        d2 = PerformanceDirection(
            index=2,
            speaker="Hero",
            energy=0.70,
            intensity="medium",
            performance_priority="standard",
        )
        d3 = PerformanceDirection(
            index=3,
            speaker="Hero",
            energy=0.95,
            intensity="explosive",
            performance_priority="climactic",
        )

        w = create_waveform_file(self.takes_dir / "pre_climax.wav")

        # In turn 1 (onset, progress=0.0):
        # Cand A: Measured opening delivery
        t1_measured = TakeVariant(
            take_id="t1_measured",
            segment_uid="c1",
            segment_index=1,
            variant_type="standard",
            audio_path=str(w),
            direction=PerformanceDirection(index=1, speaker="Hero", energy=0.55),
            evaluation=PerformanceEvaluationResult(
                take_id="t1_measured",
                overall_score=0.81,
                passed=True,
                dimensions={"naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.85)},
            ),
        )
        # Cand B: Premature explosive scream
        t1_premature = TakeVariant(
            take_id="t1_premature",
            segment_uid="c1",
            segment_index=1,
            variant_type="exposed",
            audio_path=str(w),
            direction=PerformanceDirection(index=1, speaker="Hero", energy=0.95),
            evaluation=PerformanceEvaluationResult(
                take_id="t1_premature",
                overall_score=0.83,
                passed=True,
                dimensions={"naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.75)},
            ),
        )

        t2 = TakeVariant(take_id="t2", segment_uid="c2", segment_index=2, variant_type="standard", audio_path=str(w), direction=d2)
        t3 = TakeVariant(take_id="t3", segment_uid="c3", segment_index=3, variant_type="more_restrained", audio_path=str(w), direction=d3)

        results = self.selector.select_scene_takes(
            scene_takes=[[t1_premature, t1_measured], [t2], [t3]],
            directions=[d1, d2, d3],
            texts=["The mist is gathering.", "I hear them coming.", "Stand and fight!"],
        )

        assert results[0].take_id == "t1_measured"
        assert results[0].is_selected is True

    def test_05_scene_continuity_tracker_integration(self):
        """Verifies PerformanceContinuityTracker is populated and rewarded during scene selection."""
        tracker = PerformanceContinuityTracker()

        d1 = PerformanceDirection(index=1, speaker="Scholar", pace=1.05, energy=0.65)
        d2 = PerformanceDirection(index=2, speaker="Scholar", pace=1.05, energy=0.68)
        d3 = PerformanceDirection(index=3, speaker="Scholar", pace=1.05, energy=0.66)

        w = create_waveform_file(self.takes_dir / "cont.wav")
        t1 = TakeVariant(take_id="t_c1", segment_uid="sc1", segment_index=1, variant_type="standard", audio_path=str(w), direction=d1, duration_sec=1.5)
        t2 = TakeVariant(take_id="t_c2", segment_uid="sc2", segment_index=2, variant_type="standard", audio_path=str(w), direction=d2, duration_sec=1.4)
        t3 = TakeVariant(take_id="t_c3", segment_uid="sc3", segment_index=3, variant_type="standard", audio_path=str(w), direction=d3, duration_sec=1.6)

        results = self.selector.select_scene_takes(
            scene_takes=[[t1], [t2], [t3]],
            directions=[d1, d2, d3],
            texts=["First entry.", "Second entry.", "Third entry."],
            continuity_tracker=tracker,
        )

        assert len(results) == 3
        assert "Scholar" in tracker.characters
        telem = tracker.characters["Scholar"]
        assert telem.total_segments == 3
        assert round(telem.average_pace, 2) == 1.05
        assert len(telem.recent_take_ids) == 3
