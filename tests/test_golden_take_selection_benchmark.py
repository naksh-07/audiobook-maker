#!/usr/bin/env python3
"""
Audiobook Factory - Wave E Golden Take Selection Behavioral Benchmark Suite.
Validates that IntelligentTakeSelector and PairwiseTakeJudge make genuine artistic,
commercial studio-quality decisions across 7 golden dramatic scenarios:

1. Restraint beats loudness: Controlled delivery beats shouting in an iron-restraint beat.
2. Dramatic pause beats dead air: Authentic dramatic timing beats unmotivated trailing dead air.
3. Voice stability beats exaggerated emotion: Timbre consistency beats pitch drift.
4. Chemistry beats isolated line score: Turn-taking rhythm beats disconnected isolated performance.
5. Scene arc beats individual segment score: Preserving scene escalation beats premature shouting.
6. Naturalness beats raw distorted intensity: Clean acoustic delivery beats clipped distortion.
7. Correct subtext intent beats generic aggressive yell: Subtextual menace beats unmotivated volume.
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
    TakeSelectionResult,
)
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.take_selector import IntelligentTakeSelector
from audiobook_factory.performance.chemistry import ConversationalChemistry
from audiobook_factory.performance.continuity import PerformanceContinuityTracker


def create_waveform_file(
    filepath: Path,
    duration_sec: float = 1.5,
    sample_rate: int = 24000,
    f0_hz: float = 150.0,
    amplitude: float = 0.5,
    pitch_mod_depth: float = 10.0,
    pitch_mod_freq: float = 4.0,
    is_clipped: bool = False,
    trailing_silence_sec: float = 0.0,
) -> Path:
    """Helper to create deterministic WAV files."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_speech = int(sample_rate * duration_sec)
    t = np.arange(num_speech) / float(sample_rate)

    instantaneous_f0 = f0_hz + pitch_mod_depth * np.sin(2 * np.pi * pitch_mod_freq * t)
    phase = 2 * np.pi * np.cumsum(instantaneous_f0) / sample_rate
    signal = np.sin(phase) + 0.3 * np.sin(2 * phase)
    raw = signal * amplitude * 28000.0

    if is_clipped:
        raw[:50] = 32767.0

    speech = raw.clip(-32767, 32767).astype(np.int16)

    if trailing_silence_sec > 0:
        silence = np.zeros(int(sample_rate * trailing_silence_sec), dtype=np.int16)
        samples = np.concatenate([speech, silence])
    else:
        samples = speech

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())

    return filepath


class TestGoldenTakeSelectionBenchmarkSuite:
    """Golden behavioral benchmark suite for take selection."""

    @pytest.fixture(autouse=True)
    def setup_suite(self, tmp_path):
        self.tmp_dir = tmp_path
        self.takes_dir = self.tmp_dir / "golden_takes"
        self.takes_dir.mkdir(parents=True, exist_ok=True)
        self.evaluator = PerformanceEvaluator()
        self.selector = IntelligentTakeSelector(evaluator=self.evaluator)

    def test_01_restraint_beats_loudness(self):
        """Scenario 1: Controlled subtext delivery defeats shouting in an iron-restraint beat."""
        pd = PerformanceDirection(
            index=1,
            speaker="Inquisitor",
            restraint=0.85,
            surface_emotion="cold_menace",
            actioning="intimidate_with_silence",
        )

        w_restrained = create_waveform_file(self.takes_dir / "t01_restrained.wav", amplitude=0.40)
        w_shouting = create_waveform_file(self.takes_dir / "t01_shouting.wav", amplitude=0.98)

        # Restrained take: deep subtext, controlled RMS, 0 clipping
        take_restrained = TakeVariant(
            take_id="t01_restrained",
            segment_uid="s01",
            segment_index=1,
            variant_type="more_restrained",
            audio_path=str(w_restrained),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t01_restrained",
                overall_score=0.83,
                passed=True,
                dimensions={
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.92),
                    "naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.88),
                    "intent_match": EvaluationDimensionScore(dimension="intent_match", score=0.90),
                },
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(rms_dbfs=-22.0, clipping_samples_pinned=0),
                    prosody=ProsodyEvidence(dynamic_range_db=16.0),
                    pacing=PacingEvidence(),
                ),
            ),
        )

        # Shouting take: high surface volume, low subtext, aggressive projection
        take_shouting = TakeVariant(
            take_id="t01_shouting",
            segment_uid="s01",
            segment_index=1,
            variant_type="exposed",
            audio_path=str(w_shouting),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t01_shouting",
                overall_score=0.84,
                passed=True,
                dimensions={
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.68),
                    "naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.76),
                    "intent_match": EvaluationDimensionScore(dimension="intent_match", score=0.82),
                },
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(rms_dbfs=-13.5, clipping_samples_pinned=6),
                    prosody=ProsodyEvidence(dynamic_range_db=9.0),
                    pacing=PacingEvidence(),
                ),
            ),
        )

        result = self.selector.select_take_with_result(
            takes=[take_shouting, take_restrained],
            text="If you lie to me again, there will be nothing left of you to bury.",
            direction=pd,
        )

        assert result.winner.take_id == "t01_restrained"
        assert result.winner.is_selected is True
        assert "BETTER_RESTRAINT" in result.reason_codes
        assert "more_restrained" in result.winner.selection_reason

    def test_02_dramatic_pause_beats_dead_air(self):
        """Scenario 2: Motivated pregnant pause defeats awkward unmotivated dead air."""
        pd = PerformanceDirection(
            index=2,
            speaker="Monarch",
            surface_emotion="solemn",
            restraint=0.75,
        )

        w1 = create_waveform_file(self.takes_dir / "t02_dramatic.wav", trailing_silence_sec=0.4)
        w2 = create_waveform_file(self.takes_dir / "t02_dead.wav", trailing_silence_sec=1.9)

        take_dramatic = TakeVariant(
            take_id="t02_dramatic",
            segment_uid="s02",
            segment_index=2,
            variant_type="slower_heavier",
            audio_path=str(w1),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t02_dramatic",
                overall_score=0.82,
                passed=True,
                dimensions={"subtext": EvaluationDimensionScore(dimension="subtext", score=0.88)},
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(dead_air_sec=0.35),
                    prosody=ProsodyEvidence(),
                    pacing=PacingEvidence(dramatic_timing_fit=0.94),
                ),
            ),
        )

        take_dead = TakeVariant(
            take_id="t02_dead",
            segment_uid="s02",
            segment_index=2,
            variant_type="standard",
            audio_path=str(w2),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t02_dead",
                overall_score=0.83,
                passed=True,
                dimensions={"subtext": EvaluationDimensionScore(dimension="subtext", score=0.80)},
                evidence=PerformanceEvidence(
                    acoustic=AcousticEvidence(dead_air_sec=1.85),
                    prosody=ProsodyEvidence(),
                    pacing=PacingEvidence(dramatic_timing_fit=0.45),
                ),
            ),
        )

        result = self.selector.select_take_with_result(
            takes=[take_dead, take_dramatic],
            text="The realm cannot survive another winter of war.",
            direction=pd,
        )

        assert result.winner.take_id == "t02_dramatic"
        assert "BETTER_DRAMATIC_PAUSE" in result.reason_codes

    def test_03_voice_stability_beats_exaggerated_emotion(self):
        """Scenario 3: Character timbre consistency defeats an exaggerated take with severe pitch drift."""
        pd = PerformanceDirection(
            index=3,
            speaker="Protagonist",
            intensity="high",
            surface_emotion="grief",
        )

        w1 = create_waveform_file(self.takes_dir / "t03_stable.wav", f0_hz=140.0)
        w2 = create_waveform_file(self.takes_dir / "t03_drift.wav", f0_hz=260.0)

        # Stable take: fits character acoustic signature
        take_stable = TakeVariant(
            take_id="t03_stable",
            segment_uid="s03",
            segment_index=3,
            variant_type="vulnerable",
            audio_path=str(w1),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t03_stable",
                overall_score=0.81,
                passed=True,
                voice_identity_score=0.91,
                voice_drift_detected=False,
                dimensions={"emotional_match": EvaluationDimensionScore(dimension="emotional_match", score=0.85)},
            ),
        )

        # Drifted take: exaggerated vocal strain causing character voice break
        take_drifted = TakeVariant(
            take_id="t03_drifted",
            segment_uid="s03",
            segment_index=3,
            variant_type="exposed",
            audio_path=str(w2),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t03_drifted",
                overall_score=0.85,
                passed=False,
                voice_identity_score=0.40,  # Below threshold
                voice_drift_detected=True,
                dimensions={"emotional_match": EvaluationDimensionScore(dimension="emotional_match", score=0.90)},
            ),
        )

        result = self.selector.select_take_with_result(
            takes=[take_drifted, take_stable],
            text="I thought I could save them both.",
            direction=pd,
        )

        assert result.winner.take_id == "t03_stable"
        assert take_drifted.is_selected is False
        assert result.winner.is_selected is True

    def test_04_chemistry_beats_isolated_line_score(self):
        """Scenario 4: Turn-taking conversational responsiveness defeats a higher-scoring isolated line."""
        d_prev = PerformanceDirection(
            index=4,
            speaker="Detective",
            interruption_behavior="abrupt_cut",
            silence_type="interruption_cut",
            energy=0.80,
        )
        d_curr_immediate = PerformanceDirection(
            index=5,
            speaker="Suspect",
            turn_taking_behavior="immediate",
            pause_before_ms=0,
            energy=0.75,
        )
        d_curr_delayed = PerformanceDirection(
            index=5,
            speaker="Suspect",
            turn_taking_behavior="delayed_reaction",
            pause_before_ms=750,
            energy=0.75,
        )

        w_prev = create_waveform_file(self.takes_dir / "t04_prev.wav")
        w_curr_a = create_waveform_file(self.takes_dir / "t04_resp_fast.wav")
        w_curr_b = create_waveform_file(self.takes_dir / "t04_resp_slow.wav")

        t_prev = TakeVariant(take_id="t04_prev", segment_uid="s04", segment_index=4, variant_type="standard", audio_path=str(w_prev), direction=d_prev)

        # Fast response candidate: snaps directly on interruption
        t_fast = TakeVariant(
            take_id="t04_fast",
            segment_uid="s05",
            segment_index=5,
            variant_type="standard",
            audio_path=str(w_curr_a),
            direction=d_curr_immediate,
            evaluation=PerformanceEvaluationResult(
                take_id="t04_fast",
                overall_score=0.81,
                passed=True,
                dimensions={"intent_match": EvaluationDimensionScore(dimension="intent_match", score=0.82)},
            ),
        )

        # Slow response candidate: awkward pregnant gap after abrupt cut
        t_slow = TakeVariant(
            take_id="t04_slow",
            segment_uid="s05",
            segment_index=5,
            variant_type="slower_heavier",
            audio_path=str(w_curr_b),
            direction=d_curr_delayed,
            evaluation=PerformanceEvaluationResult(
                take_id="t04_slow",
                overall_score=0.82,
                passed=True,
                dimensions={"intent_match": EvaluationDimensionScore(dimension="intent_match", score=0.83)},
            ),
        )

        results = self.selector.select_scene_takes(
            scene_takes=[[t_prev], [t_slow, t_fast]],
            directions=[d_prev, d_curr_immediate],
            texts=["Where was the key—", "I never touched it!"],
        )

        assert results[1].take_id == "t04_fast"
        assert results[1].is_selected is True

    def test_05_scene_arc_beats_individual_segment_score(self):
        """Scenario 5: Scene selector preserves dramatic escalation arc over individually noisy takes."""
        # 3 beats leading into a climactic finish
        d1 = PerformanceDirection(index=1, speaker="Leader", energy=0.55, intensity="low", performance_priority="standard")
        d2 = PerformanceDirection(index=2, speaker="Leader", energy=0.70, intensity="medium", performance_priority="standard")
        d3 = PerformanceDirection(index=3, speaker="Leader", energy=0.92, intensity="explosive", performance_priority="climactic")

        w = create_waveform_file(self.takes_dir / "arc_dummy.wav")

        # Turn 1: candidate A is measured, candidate B is premature screaming
        t1_measured = TakeVariant(
            take_id="t1_measured", segment_uid="u1", segment_index=1, variant_type="standard", audio_path=str(w),
            direction=PerformanceDirection(index=1, speaker="Leader", energy=0.55),
            evaluation=PerformanceEvaluationResult(take_id="t1_measured", overall_score=0.81, passed=True, dimensions={"naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.86)}),
        )
        t1_screaming = TakeVariant(
            take_id="t1_screaming", segment_uid="u1", segment_index=1, variant_type="exposed", audio_path=str(w),
            direction=PerformanceDirection(index=1, speaker="Leader", energy=0.95),
            evaluation=PerformanceEvaluationResult(take_id="t1_screaming", overall_score=0.83, passed=True, dimensions={"naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.74)}),
        )

        t2 = TakeVariant(take_id="t2", segment_uid="u2", segment_index=2, variant_type="standard", audio_path=str(w), direction=d2)
        t3 = TakeVariant(take_id="t3", segment_uid="u3", segment_index=3, variant_type="more_restrained", audio_path=str(w), direction=d3)

        results = self.selector.select_scene_takes(
            scene_takes=[[t1_screaming, t1_measured], [t2], [t3]],
            directions=[d1, d2, d3],
            texts=["The perimeter is breached.", "Form the shield wall.", "Hold for the dawn!"],
        )

        # Measured beat wins scene opening despite slightly lower isolated score
        assert results[0].take_id == "t1_measured"
        assert results[0].is_selected is True

    def test_06_naturalness_beats_raw_distorted_intensity(self):
        """Scenario 6: Clean acoustic delivery beats distorted/clipped audio during an intense line."""
        pd = PerformanceDirection(
            index=6,
            speaker="Sorcerer",
            intensity="explosive",
            surface_emotion="rage",
        )

        w_clean = create_waveform_file(self.takes_dir / "t06_clean.wav", is_clipped=False)
        w_clipped = create_waveform_file(self.takes_dir / "t06_clipped.wav", is_clipped=True)

        take_clean = TakeVariant(
            take_id="t06_clean",
            segment_uid="s06",
            segment_index=6,
            variant_type="standard",
            audio_path=str(w_clean),
            direction=pd,
        )
        take_clipped = TakeVariant(
            take_id="t06_clipped",
            segment_uid="s06",
            segment_index=6,
            variant_type="standard",
            audio_path=str(w_clipped),
            direction=pd,
        )

        result = self.selector.select_take_with_result(
            takes=[take_clipped, take_clean],
            text="Burn to ash!",
            direction=pd,
        )

        assert result.winner.take_id == "t06_clean"
        assert take_clipped.is_selected is False
        assert "Audible clipping" in take_clipped.selection_reason

    def test_07_correct_subtext_intent_beats_generic_aggressive_yell(self):
        """Scenario 7: Subtle subtextual menace defeats a generic aggressive shout."""
        pd = PerformanceDirection(
            index=7,
            speaker="Noble",
            restraint=0.80,
            surface_emotion="polite_menace",
            target_character="Rival",
        )

        w1 = create_waveform_file(self.takes_dir / "t07_subtle.wav", amplitude=0.45)
        w2 = create_waveform_file(self.takes_dir / "t07_yell.wav", amplitude=0.90)

        take_subtle = TakeVariant(
            take_id="t07_subtle",
            segment_uid="s07",
            segment_index=7,
            variant_type="more_restrained",
            audio_path=str(w1),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t07_subtle",
                overall_score=0.83,
                passed=True,
                dimensions={
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.91),
                    "intent_match": EvaluationDimensionScore(dimension="intent_match", score=0.89),
                    "relationship_consistency": EvaluationDimensionScore(dimension="relationship_consistency", score=0.88),
                },
            ),
        )

        take_yell = TakeVariant(
            take_id="t07_yell",
            segment_uid="s07",
            segment_index=7,
            variant_type="standard",
            audio_path=str(w2),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="t07_yell",
                overall_score=0.84,
                passed=True,
                dimensions={
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.69),
                    "intent_match": EvaluationDimensionScore(dimension="intent_match", score=0.75),
                    "relationship_consistency": EvaluationDimensionScore(dimension="relationship_consistency", score=0.72),
                },
            ),
        )

        result = self.selector.select_take_with_result(
            takes=[take_yell, take_subtle],
            text="Do give my warmest regards to your family before tomorrow night.",
            direction=pd,
        )

        assert result.winner.take_id == "t07_subtle"
        assert result.winner.is_selected is True
        assert "BETTER_SUBTEXT" in result.reason_codes
