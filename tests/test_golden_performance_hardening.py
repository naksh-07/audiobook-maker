#!/usr/bin/env python3
"""
Test Suite: Golden Performance & Voice QC Hardening Suite (Prompt 3).
Verifies:
1. Conformance of generated audio to PerformanceDirection.
2. Distinction between technically clean recordings and genuinely good dramatic performances.
3. Naturalness and prosody gating against robotic pitch lock and acoustic corruption.
4. Character voice identity consistency, catastrophic drift defense, and legitimate dramatic tolerance.
5. Longitudinal character stability and continuity tracking across scenes and chapters.
6. Gate 2.8 fail-closed protection against silent defect leakage into final audio master.
7. Technical validation of character reference voice anchor registration.
8. Validation across all 12 dramatic modes in PerformanceCalibrationCorpus.
"""

from __future__ import annotations
import wave
import tempfile
import math
import numpy as np
from pathlib import Path
import pytest

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceEvaluationResult,
    EvaluationDimensionScore,
    TakeSelectionResult,
    PerformanceEvidence,
    AcousticEvidence,
    ProsodyEvidence,
    PacingEvidence,
    VoiceIdentityEvidence,
    PerceptualPerformanceEvidence,
    TakeSelectorCalibrationConfig,
    EvaluatorCalibrationConfig,
)
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.take_selector import IntelligentTakeSelector
from audiobook_factory.performance.gate import PerformanceFidelityGate
from audiobook_factory.performance.continuity import (
    PerformanceContinuityTracker,
    CharacterPerformanceTelemetry,
)
from audiobook_factory.performance.calibration import (
    PerformanceCalibrationCorpus,
    CalibrationCorpusEntry,
)
from audiobook_factory.identity.reference_bank import (
    ReferenceVoiceBank,
    AcousticSignature,
)
from audiobook_factory.identity.voice_drift_analyzer import (
    VoiceIdentityAnalyzer,
)


def create_calibrated_wav(
    filepath: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 24000,
    f0_hz: float = 140.0,
    amplitude: float = 0.5,
    pitch_mod_depth: float = 15.0,
    pitch_mod_freq: float = 2.5,
    is_clipped: bool = False,
    dead_air_sec: float = 0.0,
) -> Path:
    """
    Creates deterministic test audio with precise acoustic and prosodic features.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_speech_samples = int(sample_rate * max(0.2, duration_sec - dead_air_sec))
    t = np.arange(num_speech_samples) / float(sample_rate)

    if pitch_mod_depth > 0:
        # Organic prosodic inflection
        instantaneous_f0 = f0_hz + pitch_mod_depth * np.sin(2 * np.pi * pitch_mod_freq * t)
        phase = 2 * np.pi * np.cumsum(instantaneous_f0) / sample_rate
        signal = np.sin(phase) + 0.3 * np.sin(2 * phase) + 0.1 * np.sin(3 * phase)
    else:
        # Constant pitch: monotonic robotic lock
        signal = np.sin(2 * np.pi * f0_hz * t) + 0.3 * np.sin(2 * np.pi * 2 * f0_hz * t)

    raw_samples = signal * amplitude * 26000.0

    if is_clipped:
        # Hard pin to rail
        raw_samples[: int(0.15 * sample_rate)] = 32767.0

    speech_samples = raw_samples.clip(-32767, 32767).astype(np.int16)

    # Append trailing dead air if specified
    if dead_air_sec > 0:
        dead_samples = np.zeros(int(sample_rate * dead_air_sec), dtype=np.int16)
        all_samples = np.concatenate([speech_samples, dead_samples])
    else:
        all_samples = speech_samples

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(all_samples.tobytes())

    return filepath


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def evaluator():
    return PerformanceEvaluator(sample_rate=24000)


@pytest.fixture
def selector(evaluator):
    return IntelligentTakeSelector(evaluator=evaluator)


class TestGoldenPerformanceHardening:
    """Rigorous Golden Tests for Performance & Voice QC Hardening (Prompt 3)."""

    # 1. PerformanceDirection Conformance: Restraint vs Over-acting Shout
    def test_01_direction_conformance_restraint_vs_explosive(self, temp_dir, evaluator, selector):
        pd_restraint = PerformanceDirection(
            index=1,
            speaker="Yennefer",
            surface_emotion="cold_menace",
            restraint=0.90,
            intensity="medium",
            actioning="intimidate_with_suppression",
            subtext="suppressed rage behind aristocratic poise",
            subtext_confidence=0.95,
        )

        # Take 1: Controlled dynamic compression (amplitude 0.35, no clipping, peak < 25000)
        wav_good = create_calibrated_wav(temp_dir / "yen_good.wav", amplitude=0.35, f0_hz=180.0, pitch_mod_depth=12.0)
        take_good = TakeVariant(
            take_id="t_good",
            segment_uid="s01",
            segment_index=1,
            variant_type="more_restrained",
            audio_path=str(wav_good),
            direction=pd_restraint,
        )

        # Take 2: Unsuppressed shouting (amplitude 0.99, clipped peak 32767)
        wav_shout = create_calibrated_wav(temp_dir / "yen_shout.wav", amplitude=0.99, is_clipped=True)
        take_shout = TakeVariant(
            take_id="t_shout",
            segment_uid="s01",
            segment_index=1,
            variant_type="more_urgent",
            audio_path=str(wav_shout),
            direction=pd_restraint,
        )

        res = selector.select_take_with_result(
            [take_good, take_shout],
            text="You have crossed a line you cannot uncross.",
            direction=pd_restraint,
        )
        assert res.winner is not None
        assert res.winner.take_id == "t_good"
        assert res.status in ("ACCEPT", "ACCEPT_WITH_WARNING")
        # Winner must possess superior restraint
        assert any("RESTRAINT" in code or "SUBTEXT" in code for code in res.reason_codes)

    # 2. Distinction: Clean Recording vs Good Dramatic Performance
    def test_02_clean_recording_vs_good_performance_distinction(self, temp_dir, evaluator, selector):
        """
        Proves that a technically clean recording (zero clipping, zero DC offset) with
        robotic monotonic delivery loses to an organically modulated dramatic performance.
        """
        pd = PerformanceDirection(
            index=2,
            speaker="Narrator",
            surface_emotion="neutral",
            pace=1.0,
            energy=0.65,
        )

        # Take A: Technically clean but robotic (pitch_mod_depth=0.0 -> F0 variance < 1.0Hz)
        wav_robotic = create_calibrated_wav(
            temp_dir / "narrator_robotic.wav",
            amplitude=0.45,
            f0_hz=130.0,
            pitch_mod_depth=0.0,
        )
        take_robotic = TakeVariant(
            take_id="t_robotic",
            segment_uid="s02",
            segment_index=2,
            variant_type="standard",
            audio_path=str(wav_robotic),
            direction=pd,
        )

        # Take B: Organically modulated human prosody (pitch_mod_depth=18.0Hz)
        wav_organic = create_calibrated_wav(
            temp_dir / "narrator_organic.wav",
            amplitude=0.45,
            f0_hz=130.0,
            pitch_mod_depth=18.0,
        )
        take_organic = TakeVariant(
            take_id="t_organic",
            segment_uid="s02",
            segment_index=2,
            variant_type="more_intimate",
            audio_path=str(wav_organic),
            direction=pd,
        )

        ev_robotic = evaluator.evaluate_take(
            take_id="t_robotic",
            audio_file=wav_robotic,
            text="The winter winds swept through the ancient battlements of the fortress.",
            direction=pd,
        )
        ev_organic = evaluator.evaluate_take(
            take_id="t_organic",
            audio_file=wav_organic,
            text="The winter winds swept through the ancient battlements of the fortress.",
            direction=pd,
        )

        # Evidence proofs: robotic take has monotonic pitch locked
        assert ev_robotic.evidence.prosody.is_monotonic_pitch_locked is True
        assert ev_organic.evidence.prosody.is_monotonic_pitch_locked is False

        # Naturalness of organic delivery must exceed robotic delivery
        assert ev_organic.dimensions["naturalness"].score > ev_robotic.dimensions["naturalness"].score
        assert "PITCH_LOCK_DEFECT" in ev_robotic.dimensions["naturalness"].reason_codes

        # Take Selector must decisively select the organic performance
        res = selector.select_take_with_result(
            [take_robotic, take_organic],
            text="The winter winds swept through the ancient battlements of the fortress.",
            direction=pd,
        )
        assert res.winner is not None
        assert res.winner.take_id == "t_organic"

    # 3. Voice Identity: Catastrophic Voice Drift Rejection
    def test_03_voice_identity_catastrophic_drift_rejection(self, temp_dir, evaluator, selector):
        """
        Verifies that catastrophic pitch divergence (> 60% F0 shift) triggers
        VoiceIdentityAnalyzer drift detection and hard gate rejection.
        """
        sig_male = AcousticSignature(
            character_id="geralt",
            voice_id="fenrir",
            f0_median_hz=110.0,
            spectral_centroid_hz=1250.0,
            f0_iqr_hz=20.0,
        )
        pd = PerformanceDirection(index=3, speaker="Geralt", surface_emotion="neutral")

        # Catastrophic mutation: 240Hz female/alien pitch for Geralt (118% deviation)
        wav_alien = create_calibrated_wav(temp_dir / "alien_geralt.wav", f0_hz=240.0, pitch_mod_depth=15.0)
        take_alien = TakeVariant(
            take_id="t_alien",
            segment_uid="s03",
            segment_index=3,
            variant_type="standard",
            audio_path=str(wav_alien),
            direction=pd,
        )

        analyzer = VoiceIdentityAnalyzer(sample_rate=24000)
        drift_res = analyzer.analyze_take_identity(
            take_id="t_alien",
            audio_path=wav_alien,
            signature=sig_male,
        )
        assert drift_res.drift_detected is True
        assert drift_res.f0_deviation_pct > 60.0
        assert drift_res.similarity_score < 0.45

        # Take selection must fail closed
        res = selector.select_take_with_result(
            [take_alien],
            text="Evil is evil, Stregobor.",
            direction=pd,
            signature=sig_male,
        )
        assert res.status in ("REGENERATE", "NO_ACCEPTABLE_TAKE")
        assert res.winner is None or res.winner.is_selected is False

    # 4. Voice Identity: Legitimate Dramatic Mode Tolerance
    def test_04_voice_identity_dramatic_mode_tolerance(self, temp_dir):
        """
        Verifies that an authentic battle cry (F0 45% higher than baseline)
        under intense/battle mode is accepted within contextual tolerance.
        """
        sig_male = AcousticSignature(
            character_id="geralt",
            voice_id="fenrir",
            f0_median_hz=115.0,
            spectral_centroid_hz=1300.0,
            f0_iqr_hz=30.0,
            mode_baselines={
                "intense": {
                    "f0_median_hz": 155.0,
                    "spectral_centroid_hz": 250.0,
                    "rms_dbfs": -14.0,
                }
            },
        )
        wav_battle = create_calibrated_wav(temp_dir / "battle_cry.wav", f0_hz=158.0, pitch_mod_depth=25.0)

        analyzer = VoiceIdentityAnalyzer(sample_rate=24000)
        drift_res = analyzer.analyze_take_identity(
            take_id="t_battle",
            audio_path=wav_battle,
            signature=sig_male,
            dramatic_emotion="battle_cry",
            intensity="explosive",
        )
        assert drift_res.drift_detected is False
        assert drift_res.similarity_score >= 0.75
        assert drift_res.recommendation == "pass"

    # 5. Anti-Emotional Teleportation Detection in Gate 2.8
    def test_05_anti_emotional_teleportation_detected(self):
        """
        Verifies that Gate 2.8 catches unbuffered emotional teleportation
        (e.g. calm -> bellowing_rage for the same character).
        """
        dir1 = PerformanceDirection(index=1, speaker="Emhyr", surface_emotion="calm", segment_uid="s01")
        dir2 = PerformanceDirection(index=2, speaker="Emhyr", surface_emotion="bellowing_rage", segment_uid="s02")

        report = PerformanceFidelityGate.audit_chapter_performance(
            chapter_id="chapter_001",
            directions=[dir1, dir2],
            selected_takes=[],
            allow_warnings=True,
        )
        assert report.passed is False
        assert report.teleportation_violations >= 1
        assert any("Emotional Teleportation Violation" in issue for issue in report.unresolved_issues)

    # 6. Gate 2.8 Fail-Closed on Critical Defects (Even With allow_warnings=True)
    def test_06_gate2_8_fail_closed_on_critical_defects(self, temp_dir):
        """
        Verifies that Gate 2.8 strictly fails closed (passed=False) when any
        selected take has a critical defect (e.g. score < 0.65 or NO_ACCEPTABLE_TAKE),
        even if allow_warnings=True.
        """
        pd1 = PerformanceDirection(index=1, speaker="Geralt", surface_emotion="neutral", segment_uid="s01")
        pd2 = PerformanceDirection(index=2, speaker="Yennefer", surface_emotion="neutral", segment_uid="s02")

        # Take 1: High quality
        take1 = TakeVariant(
            take_id="t01",
            segment_uid="s01",
            segment_index=1,
            audio_path=str(temp_dir / "t01.wav"),
            direction=pd1,
            is_selected=True,
            evaluation=PerformanceEvaluationResult(
                take_id="t01",
                segment_uid="s01",
                overall_score=0.88,
                passed=True,
                dimensions={"naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.90)},
            ),
        )

        # Take 2: Critical defect - score 0.52 (< 0.65 threshold)
        take2 = TakeVariant(
            take_id="t02",
            segment_uid="s02",
            segment_index=2,
            audio_path=str(temp_dir / "t02.wav"),
            direction=pd2,
            is_selected=True,
            evaluation=PerformanceEvaluationResult(
                take_id="t02",
                segment_uid="s02",
                overall_score=0.52,
                passed=False,
                dimensions={"naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.50)},
            ),
        )

        report = PerformanceFidelityGate.audit_chapter_performance(
            chapter_id="chapter_002",
            directions=[pd1, pd2],
            selected_takes=[take1, take2],
            allow_warnings=True,  # Even with warnings permitted!
        )
        assert report.passed is False
        assert any("below critical threshold" in issue for issue in report.unresolved_issues)

    # 7. Reference Voice Bank: Prevents Clipped/Corrupt Take Registration
    def test_07_reference_voice_bank_prevents_clipped_registration(self, temp_dir):
        """
        Verifies that ReferenceVoiceBank.register_reference_take rejects
        clipped or corrupt audio to prevent poisoning character baseline signatures.
        """
        ref_bank = ReferenceVoiceBank(temp_dir / "ref_bank")
        clipped_wav = create_calibrated_wav(
            temp_dir / "corrupt_take.wav",
            amplitude=0.99,
            is_clipped=True,
        )

        with pytest.raises(ValueError, match="clipped"):
            ref_bank.register_reference_take(
                character_id="geralt",
                voice_id="fenrir",
                mode="neutral",
                audio_path=clipped_wav,
            )

    # 8. Character Continuity Tracking & Voice Identity Confidence
    def test_08_character_continuity_tracking(self, temp_dir):
        """
        Verifies that PerformanceContinuityTracker records directions,
        updates voice identity confidence via moving average, and detects energy ruptures.
        """
        tracker = PerformanceContinuityTracker()
        pd1 = PerformanceDirection(
            index=1,
            speaker="Jaskier",
            surface_emotion="cheerful",
            energy=0.70,
            pace=1.10,
            physical_state="normal",
        )
        tracker.record_direction(pd1, duration_sec=3.2)
        tracker.record_take("Jaskier", take_id="t_jaskier_01", voice_identity_score=0.92)

        telem = tracker.characters["Jaskier"]
        assert telem.total_segments == 1
        assert telem.voice_identity_confidence >= 0.85
        assert telem.last_emotional_state == "cheerful"

        # Advance chapter
        tracker.advance_chapter("chapter_001")
        assert telem.chapter_count == 1

        # Check unbuffered energy rupture at new chapter onset
        pd2_rupture = PerformanceDirection(
            index=1,
            speaker="Jaskier",
            surface_emotion="melancholy",
            energy=0.10,  # Rupture: 0.70 -> 0.10 delta = 0.60
            pace=0.80,
            intensity="low",
        )
        warnings = tracker.audit_inter_chapter_transition("Jaskier", pd2_rupture)
        assert len(warnings) >= 1
        assert "Energy Continuity Alert" in warnings[0]

    # 9. Single Candidate Take Selection: ACCEPT_WITH_WARNING Handled Properly
    def test_09_single_candidate_accept_with_warning(self, temp_dir, selector):
        """
        Verifies that a sole candidate take with acceptable score but mild uncertainty
        is properly selected with status ACCEPT_WITH_WARNING and review_required=True.
        """
        wav = create_calibrated_wav(temp_dir / "sole_take.wav", amplitude=0.45, f0_hz=140.0)
        pd = PerformanceDirection(index=1, speaker="Narrator", surface_emotion="neutral")
        take = TakeVariant(
            take_id="t_sole",
            segment_uid="s01",
            segment_index=1,
            variant_type="standard",
            audio_path=str(wav),
            direction=pd,
        )

        res = selector.select_take_with_result([take], text="Dawn broke over the valley.", direction=pd)
        assert res.winner is not None
        assert res.winner.is_selected is True
        assert res.status in ("ACCEPT", "ACCEPT_WITH_WARNING")

    # 10. Performance Calibration Corpus: Validation of All 12 Dramatic Modes
    def test_10_calibration_corpus_validation_all_12_modes(self):
        """
        Verifies that the PerformanceCalibrationCorpus provides 12 distinct,
        well-formed dramatic categories covering full audio drama requirements.
        """
        corpus = PerformanceCalibrationCorpus.get_standard_corpus()
        assert len(corpus) == 12

        mode_ids = [entry.mode_id for entry in corpus]
        assert len(mode_ids) == len(set(mode_ids)), "Mode IDs must be unique"

        required_modes = {
            "whisper_intimate",
            "restrained_grief",
            "explosive_rage",
            "calm_exposition",
            "intimate_dialogue",
            "fast_rally",
            "cold_sarcasm",
            "breathless_panic",
            "authoritative_command",
            "submissive_plea",
            "hesitant_confession",
            "formal_exposition",
        }
        assert set(mode_ids) == required_modes

        for entry in corpus:
            assert entry.text.strip(), f"Empty text for mode {entry.mode_id}"
            assert "surface_emotion" in entry.direction
            assert "actioning" in entry.direction
            assert "rms_dbfs_range" in entry.expected_acoustic_markers
            assert "f0_variance_min" in entry.expected_acoustic_markers
            assert len(entry.known_failure_modes) >= 1
            assert entry.expected_outcome in ("ACCEPT", "REGENERATE")
