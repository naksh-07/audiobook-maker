#!/usr/bin/env python3
"""
Audiobook Factory - Wave B Performance Evidence & Grounded Evaluation Test Suite.
Validates multi-dimensional evidence extraction, removal of false precision,
monotonic pitch lock detection, restraint vs over-acting, emotional headroom,
and voice identity hard-gating.
"""

import math
import wave
import struct
import tempfile
from pathlib import Path
import pytest
import numpy as np

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceEvidence,
    PacingEvidence,
    AcousticEvidence,
    EvaluatorCalibrationConfig,
)
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.identity.reference_bank import AcousticSignature
from audiobook_factory.alignment_contracts import AlignmentResult, WordAlignment, PauseInterval


def create_waveform_file(
    filepath: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 24000,
    f0_hz: float = 150.0,
    amplitude: float = 0.5,
    pitch_mod_depth: float = 0.0,
    pitch_mod_freq: float = 5.0,
    is_clipped: bool = False,
) -> Path:
    """
    Creates deterministic test audio with customizable pitch modulation and dynamics.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sample_rate * duration_sec)
    t = np.arange(num_samples) / float(sample_rate)

    if pitch_mod_depth > 0:
        # Dynamic frequency modulation for natural prosody
        instantaneous_f0 = f0_hz + pitch_mod_depth * np.sin(2 * np.pi * pitch_mod_freq * t)
        phase = 2 * np.pi * np.cumsum(instantaneous_f0) / sample_rate
        signal = np.sin(phase) + 0.3 * np.sin(2 * phase)
    else:
        # Constant pitch (monotonic)
        signal = np.sin(2 * np.pi * f0_hz * t) + 0.3 * np.sin(2 * np.pi * 2 * f0_hz * t)

    raw_samples = (signal * amplitude * 28000.0)
    if is_clipped:
        # Pin samples to rail to simulate hard digital clipping
        raw_samples[:int(0.1 * sample_rate)] = 32767.0

    samples = raw_samples.clip(-32767, 32767).astype(np.int16)

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())

    return filepath


@pytest.fixture(scope="module")
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture(scope="module")
def evaluator():
    return PerformanceEvaluator(sample_rate=24000)


class TestPerformanceEvidenceAndEvaluator2:

    # 1. Complete Evidence Extraction
    def test_01_evidence_extraction_complete(self, temp_dir, evaluator):
        wav = create_waveform_file(temp_dir / "ev_01.wav", duration_sec=1.5, f0_hz=140.0)
        pd = PerformanceDirection(index=1, speaker="Geralt", surface_emotion="neutral")
        res = evaluator.evaluate_take(
            take_id="t_01",
            audio_file=wav,
            text="The road goes ever on.",
            direction=pd,
        )
        assert res.evidence is not None
        assert res.evidence.acoustic.rms_dbfs < 0.0
        assert res.evidence.prosody.f0_median_hz > 50.0
        assert res.evidence.pacing.words_per_sec > 0.0
        assert "naturalness" in res.dimensions
        assert "prosody" in res.dimensions
        assert "pacing" in res.dimensions
        assert res.passed is True

    # 2. Monotonic Pitch Lock Detection (Robotic Delivery Penalized)
    def test_02_monotonic_pitch_lock_penalized(self, temp_dir, evaluator):
        # Monotonic audio: pitch_mod_depth = 0.0 (F0 variance near 0)
        wav = create_waveform_file(temp_dir / "ev_mono.wav", duration_sec=2.0, f0_hz=150.0, pitch_mod_depth=0.0)
        pd = PerformanceDirection(index=2, speaker="Narrator", surface_emotion="neutral")
        res = evaluator.evaluate_take(
            take_id="t_mono",
            audio_file=wav,
            text="The fortress walls were cold and silent.",
            direction=pd,
        )
        prosody_ev = res.evidence.prosody
        assert prosody_ev.f0_variance < 5.0
        assert prosody_ev.is_monotonic_pitch_locked is True
        # Prosody score penalized for robotic pitch lock
        assert res.dimensions["prosody"].score <= 0.70
        assert "Monotonic pitch lock" in res.dimensions["prosody"].rationale

    # 3. Rich Expressive Prosodic Inflection Rewarded
    def test_03_expressive_prosodic_inflection_rewarded(self, temp_dir, evaluator):
        # Expressive audio with natural pitch contour: pitch_mod_depth = 25.0 Hz
        wav = create_waveform_file(temp_dir / "ev_prosody.wav", duration_sec=2.0, f0_hz=160.0, pitch_mod_depth=25.0)
        pd = PerformanceDirection(index=3, speaker="Jaskier", surface_emotion="excitement")
        res = evaluator.evaluate_take(
            take_id="t_prosody",
            audio_file=wav,
            text="What a marvelous adventure this will be!",
            direction=pd,
        )
        assert res.evidence.prosody.is_monotonic_pitch_locked is False
        assert res.dimensions["prosody"].score >= 0.85
        assert "Natural prosodic inflection" in res.dimensions["prosody"].rationale

    # 4. Restraint Preservation vs Over-Acting Shouting
    def test_04_restraint_preservation_vs_overacting(self, temp_dir, evaluator):
        pd_restrained = PerformanceDirection(
            index=4,
            speaker="Yennefer",
            surface_emotion="cold_fury",
            restraint=0.90,  # High iron restraint
        )
        # Take A: Controlled dynamic compression (RMS ~ -20 dBFS, peak amp controlled)
        wav_restrained = create_waveform_file(temp_dir / "yen_controlled.wav", amplitude=0.4)
        res_a = evaluator.evaluate_take(
            take_id="t_yen_a",
            audio_file=wav_restrained,
            text="You have no idea what you have done.",
            direction=pd_restrained,
        )
        assert res_a.dimensions["subtext"].score >= 0.85
        assert "Restraint preserved" in res_a.dimensions["subtext"].rationale

        # Take B: Shouting that breaks character restraint (loud peak amplitude, high RMS)
        wav_shouting = create_waveform_file(temp_dir / "yen_shouting.wav", amplitude=1.15)
        res_b = evaluator.evaluate_take(
            take_id="t_yen_b",
            audio_file=wav_shouting,
            text="You have no idea what you have done.",
            direction=pd_restrained,
        )
        assert res_b.dimensions["subtext"].score <= 0.60
        assert "Over-acted delivery" in res_b.dimensions["subtext"].rationale

    # 5. Explosive Intensity Underpowered Detection
    def test_05_explosive_intensity_underpowered_detection(self, temp_dir, evaluator):
        pd_explosive = PerformanceDirection(
            index=5,
            speaker="Warlord",
            intensity="explosive",
            surface_emotion="rage",
        )
        # Soft underpowered audio for explosive scene (amplitude 0.05 -> RMS ~ -30 dBFS)
        wav_quiet = create_waveform_file(temp_dir / "quiet_war.wav", amplitude=0.05)
        res = evaluator.evaluate_take(
            take_id="t_quiet_war",
            audio_file=wav_quiet,
            text="I will destroy you all!",
            direction=pd_explosive,
        )
        assert res.dimensions["emotional_match"].score <= 0.70
        assert "Underpowered energy" in res.dimensions["emotional_match"].rationale

    # 6. Intimate Whisper Excessive Volume Detection
    def test_06_intimate_whisper_excessive_volume_detection(self, temp_dir, evaluator):
        pd_whisper = PerformanceDirection(
            index=6,
            speaker="Renfri",
            proximity="close_mic",
            surface_emotion="whispering",
            intensity="low",
        )
        # Loud audio for intimate whisper scene (amplitude 0.90 -> RMS > -16 dBFS)
        wav_loud = create_waveform_file(temp_dir / "loud_whisper.wav", amplitude=0.90)
        res = evaluator.evaluate_take(
            take_id="t_loud_whisper",
            audio_file=wav_loud,
            text="Keep your head down.",
            direction=pd_whisper,
        )
        assert res.dimensions["emotional_match"].score <= 0.70
        assert "Excessive volume" in res.dimensions["emotional_match"].rationale

    # 7. Voice Identity Hard Gate vs Soft Preference
    def test_07_voice_identity_hard_gate(self, temp_dir, evaluator):
        sig = AcousticSignature(
            character_id="geralt",
            voice_id="fenrir",
            f0_median_hz=115.0,
            spectral_centroid_hz=1350.0,
        )
        pd = PerformanceDirection(index=7, speaker="Geralt", surface_emotion="neutral")

        # Catastrophic drift: 280Hz vs 115Hz (> 100% shift)
        wav_catastrophic = create_waveform_file(temp_dir / "catastrophic.wav", f0_hz=280.0)
        res = evaluator.evaluate_take(
            take_id="t_catastrophic",
            audio_file=wav_catastrophic,
            text="Hmm.",
            direction=pd,
            signature=sig,
        )
        assert res.passed is False
        assert res.voice_drift_detected is True
        assert res.evidence.voice_identity.is_hard_gate_violation is True
        assert res.recommendation == "regenerate"

    # 8. Soft Voice Preference within Emotional Tolerance
    def test_08_soft_voice_preference_within_tolerance(self, temp_dir, evaluator):
        sig = AcousticSignature(
            character_id="geralt",
            voice_id="fenrir",
            f0_median_hz=115.0,
            spectral_centroid_hz=1350.0,
        )
        pd = PerformanceDirection(index=8, speaker="Geralt", surface_emotion="neutral")

        # Close pitch: 118Hz vs 115Hz (2.6% shift, within tolerance)
        wav_close = create_waveform_file(temp_dir / "close_pitch.wav", f0_hz=118.0)
        res = evaluator.evaluate_take(
            take_id="t_close",
            audio_file=wav_close,
            text="Hmm.",
            direction=pd,
            signature=sig,
        )
        assert res.passed is True
        assert res.voice_drift_detected is False
        assert res.evidence.voice_identity.is_hard_gate_violation is False
        assert res.evidence.voice_identity.similarity_score >= 0.85

    # 9. Evaluator Calibration Configurability
    def test_09_calibration_configurability(self, temp_dir):
        custom_cfg = EvaluatorCalibrationConfig(
            explosive_min_rms_dbfs=-20.0,  # Stricter threshold
            monotonic_f0_var_threshold=10.0,
        )
        custom_evaluator = PerformanceEvaluator(config=custom_cfg)
        assert custom_evaluator.config.explosive_min_rms_dbfs == -20.0
        assert custom_evaluator.config.monotonic_f0_var_threshold == 10.0

    # 10. Defensive Audio File Handling: Missing, Empty, Corrupt, and Oversized (>600s)
    def test_10_defensive_file_handling_corrupt_empty_and_oversized(self, temp_dir, evaluator):
        pd = PerformanceDirection(index=10, speaker="Geralt", surface_emotion="neutral")

        # A. Missing file
        res_missing = evaluator.evaluate_take(
            take_id="t_missing",
            audio_file=temp_dir / "does_not_exist.wav",
            text="Hello.",
            direction=pd,
        )
        assert res_missing.passed is False
        assert res_missing.recommendation == "regenerate"

        # B. Truncated header (<= 44 bytes)
        trunc_path = temp_dir / "truncated.wav"
        trunc_path.write_bytes(b"RIFF1234WAVEfmt ")
        res_trunc = evaluator.evaluate_take(
            take_id="t_trunc",
            audio_file=trunc_path,
            text="Hello.",
            direction=pd,
        )
        assert res_trunc.passed is False
        assert res_trunc.recommendation == "regenerate"

        # C. Oversized file (>600s bound)
        oversized_path = temp_dir / "oversized.wav"
        with wave.open(str(oversized_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(100)
            wf.writeframes(b"\x00" * (100 * 2 * 605))  # 605s duration

        res_over = evaluator.evaluate_take(
            take_id="t_over",
            audio_file=oversized_path,
            text="Long speech.",
            direction=pd,
        )
        assert res_over.passed is False
        assert any("exceeds bounded limit of 600.0s" in d for d in res_over.diagnostics)

    # 11. Multi-channel Downmixing & Contract Property Aliases
    def test_11_stereo_downmix_and_evidence_property_aliases(self, temp_dir, evaluator):
        # A. Property aliases on contracts
        pe = PacingEvidence(words_per_sec=3.4)
        assert pe.words_per_second == 3.4
        ae = AcousticEvidence(spectral_flatness_mean=0.08)
        assert ae.spectral_flatness == 0.08

        # B. Stereo downmixing in evaluator
        stereo_path = temp_dir / "stereo.wav"
        with wave.open(str(stereo_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            # Create stereo sine wave (Left and Right)
            t = np.arange(24000) / 24000.0
            left = (np.sin(2 * np.pi * 150.0 * t) * 15000.0).astype(np.int16)
            right = (np.sin(2 * np.pi * 150.0 * t) * 15000.0).astype(np.int16)
            interleaved = np.empty((24000 * 2,), dtype=np.int16)
            interleaved[0::2] = left
            interleaved[1::2] = right
            wf.writeframes(interleaved.tobytes())

        pd = PerformanceDirection(index=11, speaker="Geralt", surface_emotion="neutral")
        res_stereo = evaluator.evaluate_take(
            take_id="t_stereo",
            audio_file=stereo_path,
            text="Stereo sample.",
            direction=pd,
        )
        assert res_stereo.passed is True
        assert res_stereo.overall_score >= 0.70
