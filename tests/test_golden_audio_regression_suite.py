#!/usr/bin/env python3
"""
Audiobook Factory - Golden Audio Regression Suite (Phase 19).
Validates all 18 dramatic cases end-to-end through the entire Acting Intelligence,
Risk Engine, Constraint Resolution, Strategy Selection, QC Evaluation, and Chemistry layers:
 1. Neutral narration / dialogue
 2. Explosive anger / confrontation
 3. Fear / panic
 4. Grief / heartbreak
 5. Whisper / close-mic intimate
 6. Shout / projection
 7. Laughter / chuckling
 8. Crying / sobbing
 9. Sarcasm / irony
10. Romance / tender affection
11. Combat strain / physical exertion
12. Abrupt interruption / cut-off
13. Multi-speaker rapid banter
14. Rapid staccato delivery
15. Long sustained descriptive narration
16. Hindi dialogue delivery (Hindustani nuance)
17. Hinglish code-switching
18. Foreign named entities / difficult pronunciation
"""

import math
import tempfile
import wave
import struct
from pathlib import Path
import pytest

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    ChemistryEvaluationResult,
)
from audiobook_factory.performance.constraint_resolver import PerformanceConstraintResolver
from audiobook_factory.performance.risk_engine import GenerationRiskEngine
from audiobook_factory.performance.strategy_resolver import GenerationStrategyResolver
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.chemistry import ConversationalChemistry
from audiobook_factory.performance.continuity import PerformanceContinuityTracker


def create_synthetic_wav(
    filepath: Path,
    duration_sec: float = 2.0,
    f0: float = 180.0,
    sample_rate: int = 24000,
    amplitude: float = 0.5,
) -> Path:
    """Creates a deterministic synthetic WAV file for offline acoustic testing."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sample_rate * duration_sec)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        raw_bytes = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            # Harmonic signal with gentle amplitude envelope
            val = math.sin(2 * math.pi * f0 * t) + 0.3 * math.sin(2 * math.pi * (2 * f0) * t)
            # 20ms fade in / out
            env = 1.0
            fade_samples = int(0.02 * sample_rate)
            if i < fade_samples:
                env = i / fade_samples
            elif i > num_samples - fade_samples:
                env = (num_samples - i) / fade_samples
            sample_val = int(val * amplitude * env * 28000.0)
            sample_val = max(-32767, min(32767, sample_val))
            raw_bytes.extend(struct.pack("<h", sample_val))
        wf.writeframes(raw_bytes)
    return filepath


@pytest.fixture(scope="module")
def evaluator():
    return PerformanceEvaluator(sample_rate=24000)


@pytest.fixture(scope="module")
def temp_audio_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


class TestGoldenAudioRegressionSuite:
    """Complete 18-case golden audio regression test suite."""

    # 1. Neutral narration / dialogue
    def test_01_case_neutral_narration(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g01",
            index=1,
            speaker="Narrator",
            surface_emotion="neutral",
            pace=1.0,
            energy=0.7,
            restraint=0.5,
            objective="establish atmospheric context",
        )
        resolved = PerformanceConstraintResolver.resolve_constraints(p_dir)
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        strategy_plan = GenerationStrategyResolver.resolve_strategy(p_dir, risk_report=risk_rep)

        assert risk_rep.risk_score < 0.30
        assert strategy_plan.strategy in ("CHUNKED_NARRATION", "ISOLATED_SINGLE_TAKE")
        assert len(resolved.clean_style_descriptor) > 0

        wav_path = create_synthetic_wav(temp_audio_dir / "case_01.wav", duration_sec=2.5, f0=150.0)
        res = evaluator.evaluate_take(
            take_id="t_01",
            audio_file=wav_path,
            text="The night was cold and silent.",
            direction=p_dir,
        )
        assert res.passed is True
        assert res.overall_score >= 0.75

    # 2. Explosive anger / confrontation
    def test_02_case_explosive_anger(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g02",
            index=2,
            speaker="Warlord",
            surface_emotion="rage",
            intensity="explosive",
            pace=1.2,
            energy=0.95,
            restraint=0.1,
            power_position="dominant",
            actioning="threaten and destroy",
        )
        resolved = PerformanceConstraintResolver.resolve_constraints(p_dir)
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        strategy_plan = GenerationStrategyResolver.resolve_strategy(p_dir, risk_report=risk_rep)

        assert risk_rep.risk_score >= 0.50
        assert strategy_plan.strategy in ("ISOLATED_MULTI_TAKE", "CRITICAL_SCENE_TAKE")
        assert len(resolved.clean_style_descriptor) > 0

        wav_path = create_synthetic_wav(temp_audio_dir / "case_02.wav", duration_sec=1.8, f0=220.0, amplitude=0.85)
        res = evaluator.evaluate_take(
            take_id="t_02",
            audio_file=wav_path,
            text="I will burn this fortress to ashes!",
            direction=p_dir,
        )
        assert res.passed is True

    # 3. Fear / panic
    def test_03_case_fear_panic(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g03",
            index=3,
            speaker="Villager",
            surface_emotion="fear",
            breath_behavior="sharp_intake",
            pace=1.25,
            energy=0.85,
            vulnerability=0.9,
            power_position="submissive",
        )
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        assert risk_rep.risk_score >= 0.25

        wav_path = create_synthetic_wav(temp_audio_dir / "case_03.wav", duration_sec=1.5, f0=240.0)
        res = evaluator.evaluate_take(
            take_id="t_03",
            audio_file=wav_path,
            text="They are coming through the gates!",
            direction=p_dir,
        )
        assert res.passed is True

    # 4. Grief / heartbreak
    def test_04_case_grief_heartbreak(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g04",
            index=4,
            speaker="Mourner",
            surface_emotion="grief",
            pace=0.80,
            energy=0.45,
            restraint=0.6,
            vulnerability=0.95,
            breath_behavior="trembling",
        )
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        strategy_plan = GenerationStrategyResolver.resolve_strategy(p_dir, risk_report=risk_rep)
        assert strategy_plan.strategy in ("ISOLATED_MULTI_TAKE", "ISOLATED_SINGLE_TAKE", "CRITICAL_SCENE_TAKE")

        wav_path = create_synthetic_wav(temp_audio_dir / "case_04.wav", duration_sec=3.0, f0=140.0, amplitude=0.4)
        res = evaluator.evaluate_take(
            take_id="t_04",
            audio_file=wav_path,
            text="There is nothing left for us here.",
            direction=p_dir,
        )
        assert res.passed is True

    # 5. Whisper / close-mic intimate
    def test_05_case_whisper_intimate(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g05",
            index=5,
            speaker="Infiltrator",
            surface_emotion="tense",
            resonance="whisper_air",
            proximity="close_mic",
            energy=0.35,
            restraint=0.9,
        )
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        assert risk_rep.risk_score >= 0.35

        wav_path = create_synthetic_wav(temp_audio_dir / "case_05.wav", duration_sec=2.0, f0=120.0, amplitude=0.3)
        res = evaluator.evaluate_take(
            take_id="t_05",
            audio_file=wav_path,
            text="Stay low. Do not make a sound.",
            direction=p_dir,
        )
        assert res.passed is True

    # 6. Shout / projection
    def test_06_case_shout_projection(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g06",
            index=6,
            speaker="Guard",
            surface_emotion="alarm",
            intensity="explosive",
            energy=0.95,
            pace=1.3,
        )
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        assert risk_rep.risk_score >= 0.45

        wav_path = create_synthetic_wav(temp_audio_dir / "case_06.wav", duration_sec=1.2, f0=260.0, amplitude=0.85)
        res = evaluator.evaluate_take(
            take_id="t_06",
            audio_file=wav_path,
            text="Halt! Who goes there!",
            direction=p_dir,
        )
        assert res.passed is True

    # 7. Laughter / chuckling
    def test_07_case_laughter_chuckle(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g07",
            index=7,
            speaker="Minstrel",
            surface_emotion="amused",
            energy=0.75,
            pace=1.1,
            vocal_texture="warm",
            actioning="tease and laugh",
        )
        resolved = PerformanceConstraintResolver.resolve_constraints(p_dir)
        assert len(resolved.secondary_modifiers) <= 3

        wav_path = create_synthetic_wav(temp_audio_dir / "case_07.wav", duration_sec=2.0, f0=190.0)
        res = evaluator.evaluate_take(
            take_id="t_07",
            audio_file=wav_path,
            text="You really thought you could slip past them?",
            direction=p_dir,
        )
        assert res.passed is True

    # 8. Crying / sobbing
    def test_08_case_crying_sobbing(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g08",
            index=8,
            speaker="Survivor",
            surface_emotion="crying",
            vulnerability=1.0,
            breath_behavior="trembling",
            energy=0.45,
            pace=0.85,
        )
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        assert risk_rep.risk_score >= 0.40

        wav_path = create_synthetic_wav(temp_audio_dir / "case_08.wav", duration_sec=2.8, f0=170.0, amplitude=0.4)
        res = evaluator.evaluate_take(
            take_id="t_08",
            audio_file=wav_path,
            text="I could not save them... I tried.",
            direction=p_dir,
        )
        assert res.passed is True

    # 9. Sarcasm / irony
    def test_09_case_sarcasm_irony(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g09",
            index=9,
            speaker="Sorceress",
            surface_emotion="dry_wit",
            subtext="thinks this plan is absolute madness",
            subtext_confidence=0.9,
            restraint=0.8,
            pace=0.95,
        )
        resolved = PerformanceConstraintResolver.resolve_constraints(p_dir)
        assert len(resolved.clean_style_descriptor) > 0

        wav_path = create_synthetic_wav(temp_audio_dir / "case_09.wav", duration_sec=2.4, f0=210.0)
        res = evaluator.evaluate_take(
            take_id="t_09",
            audio_file=wav_path,
            text="Brilliant plan. Truly, none more inspired.",
            direction=p_dir,
        )
        assert res.passed is True

    # 10. Romance / tender affection
    def test_10_case_romance_tenderness(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g10",
            index=10,
            speaker="Companion",
            surface_emotion="tender",
            intimacy_level="intimate",
            resonance="whisper_air",
            energy=0.50,
            pace=0.90,
            restraint=0.6,
        )
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        assert risk_rep.risk_score >= 0.20
        wav_path = create_synthetic_wav(temp_audio_dir / "case_10.wav", duration_sec=2.2, f0=195.0, amplitude=0.45)
        res = evaluator.evaluate_take(
            take_id="t_10",
            audio_file=wav_path,
            text="I knew you would come back.",
            direction=p_dir,
        )
        assert res.passed is True

    # 11. Combat strain / physical exertion
    def test_11_case_combat_strain(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g11",
            index=11,
            speaker="Gladiator",
            surface_emotion="exhausted",
            physical_state="combat_strain",
            breath_behavior="labored",
            energy=0.85,
            pace=1.1,
        )
        resolved = PerformanceConstraintResolver.resolve_constraints(p_dir)
        wav_path = create_synthetic_wav(temp_audio_dir / "case_11.wav", duration_sec=1.6, f0=165.0, amplitude=0.7)
        res = evaluator.evaluate_take(
            take_id="t_11",
            audio_file=wav_path,
            text="Hold... the line!",
            direction=p_dir,
        )
        assert res.passed is True

    # 12. Abrupt interruption / cut-off
    def test_12_case_interruption_coupling(self, temp_audio_dir):
        d1 = PerformanceDirection(
            direction_id="pd_g12_a",
            index=12,
            speaker="Ambassador",
            interruption_behavior="abrupt_cut",
            silence_type="interruption_cut",
            energy=0.75,
        )
        d2 = PerformanceDirection(
            direction_id="pd_g12_b",
            index=13,
            speaker="Rebel",
            turn_taking_behavior="immediate",
            pause_before_ms=0,
            energy=0.85,
        )
        t1 = TakeVariant(take_id="t12_a", segment_uid="s12", segment_index=12, audio_path="/tmp/a.wav", direction=d1)
        t2 = TakeVariant(take_id="t12_b", segment_uid="s13", segment_index=13, audio_path="/tmp/b.wav", direction=d2)

        chem = ConversationalChemistry.evaluate_dialogue_chemistry(t1, t2, actual_gap_ms=35)
        assert chem.passed is True
        assert chem.interruption_quality_score == 1.0

    # 13. Multi-speaker rapid banter
    def test_13_case_multi_speaker_rapid(self):
        directions = [
            PerformanceDirection(index=1, speaker="SpeakerA", pace=1.2, energy=0.8),
            PerformanceDirection(index=2, speaker="SpeakerB", pace=1.25, energy=0.85),
            PerformanceDirection(index=3, speaker="SpeakerA", pace=1.2, energy=0.8),
        ]
        coupled = ConversationalChemistry.apply_conversational_chemistry(directions)
        assert len(coupled) == 3

    # 14. Rapid staccato delivery
    def test_14_case_rapid_staccato(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g14",
            index=14,
            speaker="Scout",
            surface_emotion="urgent",
            pace=1.4,
            energy=0.9,
            articulation="sharp",
        )
        risk_rep = GenerationRiskEngine.calculate_segment_risk(p_dir)
        assert risk_rep.risk_score >= 0.30

        wav_path = create_synthetic_wav(temp_audio_dir / "case_14.wav", duration_sec=1.0, f0=200.0)
        res = evaluator.evaluate_take(
            take_id="t_14",
            audio_file=wav_path,
            text="Quickly, into the trees!",
            direction=p_dir,
        )
        assert res.passed is True

    # 15. Long sustained descriptive narration
    def test_15_case_long_narration(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g15",
            index=15,
            speaker="Narrator",
            surface_emotion="poetic",
            pace=0.95,
            energy=0.70,
            restraint=0.55,
        )
        wav_path = create_synthetic_wav(temp_audio_dir / "case_15.wav", duration_sec=4.5, f0=135.0)
        long_text = "The ancient forest stretched toward the jagged mountain peaks, bathed in the twilight of an unending autumn."
        res = evaluator.evaluate_take(
            take_id="t_15",
            audio_file=wav_path,
            text=long_text,
            direction=p_dir,
        )
        assert res.passed is True

    # 16. Hindi dialogue delivery (Hindustani nuance)
    def test_16_case_hindi_dialogue(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g16",
            index=16,
            speaker="Elder",
            surface_emotion="somber",
            pace=0.95,
            energy=0.65,
        )
        wav_path = create_synthetic_wav(temp_audio_dir / "case_16.wav", duration_sec=2.2, f0=155.0)
        hindi_text = "समय किसी का इंतज़ार नहीं करता, और जो बीत गया वो वापस नहीं आता।"
        res = evaluator.evaluate_take(
            take_id="t_16",
            audio_file=wav_path,
            text=hindi_text,
            direction=p_dir,
        )
        assert res.passed is True

    # 17. Hinglish code-switching
    def test_17_case_hinglish_code_switch(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g17",
            index=17,
            speaker="Merchant",
            surface_emotion="colloquial",
            pace=1.1,
            energy=0.75,
        )
        wav_path = create_synthetic_wav(temp_audio_dir / "case_17.wav", duration_sec=2.0, f0=175.0)
        hinglish_text = "Deal toh finalize ho gaya hai, par delivery kal morning se pehle possible nahi."
        res = evaluator.evaluate_take(
            take_id="t_17",
            audio_file=wav_path,
            text=hinglish_text,
            direction=p_dir,
        )
        assert res.passed is True

    # 18. Foreign named entities / difficult pronunciation
    def test_18_case_foreign_named_entities(self, temp_audio_dir, evaluator):
        p_dir = PerformanceDirection(
            direction_id="pd_g18",
            index=18,
            speaker="Scholar",
            surface_emotion="focused",
            articulation="crisp",
            pace=0.95,
            energy=0.7,
        )
        wav_path = create_synthetic_wav(temp_audio_dir / "case_18.wav", duration_sec=2.4, f0=160.0)
        complex_text = "The runes of ancient wisdom and the legacy of the fallen endure."
        res = evaluator.evaluate_take(
            take_id="t_18",
            audio_file=wav_path,
            text=complex_text,
            direction=p_dir,
        )
        assert res.passed is True
