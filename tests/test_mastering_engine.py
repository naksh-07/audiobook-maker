#!/usr/bin/env python3
"""
Unit and Integration Tests for Stage 12: MasteringEngineV2.
===========================================================
Validates:
1. Deterministic dual-pass linear loudnorm mastering.
2. Inter-sample true-peak brickwall limiting.
3. Closed-loop QC validation (PASS / WARN / FAIL).
4. Idempotency & double-master protection.
5. Fail-closed handling on corrupt / empty premaster.
6. Provenance SHA-256 recording and disk ledger serialization.
"""

import math
import shutil
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringRequest,
    MasteringResult,
    MasteringLedger,
)
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.mastering_qc import MasteringQCAgent
from audiobook_factory.mastering_engine import MasteringEngineV2


def generate_synthetic_audio(
    target_path: Path,
    duration_sec: float = 3.0,
    sample_rate: int = 44100,
    channels: int = 1,
    frequency: float = 440.0,
    amplitude: float = 0.5,
) -> Path:
    """Generates synthetic sine wave audio for deterministic mastering tests."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)
    # Sine wave with gentle fade-in / fade-out
    audio = amplitude * np.sin(2 * np.pi * frequency * t)
    fade_len = min(int(0.05 * sample_rate), num_samples // 4)
    if fade_len > 0:
        audio[:fade_len] *= np.linspace(0, 1, fade_len)
        audio[-fade_len:] *= np.linspace(1, 0, fade_len)

    int_data = (audio * 32767.0).astype(np.int16)
    if channels == 2:
        int_data = np.column_stack((int_data, int_data)).flatten()

    with wave.open(str(target_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_data.tobytes())

    return target_path


class TestMasteringEngineV2(unittest.TestCase):
    """Test suite for MasteringEngineV2."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="mastering_engine_test_"))
        self.engine = MasteringEngineV2()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_engine_initialization(self):
        """Verify engine properties and default initialization."""
        self.assertIsNotNone(self.engine.analyzer)
        self.assertIsNotNone(self.engine.qc_agent)
        self.assertEqual(self.engine.version, "2.2.0")
        self.assertIsNotNone(self.engine.perceptual_critic)
        self.assertIsNotNone(self.engine.scene_engine)
        self.assertIsNotNone(self.engine.certifier)
        self.assertIn("ffmpeg", self.engine._ffmpeg_version.lower())

    def test_double_master_protection(self):
        """Verify request rejects non-premaster input to prevent double-mastering."""
        premaster_wav = self.tmp_dir / "test_premaster.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=1.5)

        with self.assertRaises(ValueError) as ctx:
            MasteringRequest(
                chapter_id="ch_double_master",
                premaster_path=str(premaster_wav),
                is_premaster=False,
            )
        self.assertIn("Double-master protection", str(ctx.exception))

    def test_corrupt_premaster_fail_closed(self):
        """Verify engine returns FAILED and halts when premaster is empty or corrupt."""
        corrupt_wav = self.tmp_dir / "corrupt_premaster.wav"
        corrupt_wav.write_bytes(b"NOT_A_VALID_WAV_HEADER_DATA")

        req = MasteringRequest(
            chapter_id="ch_corrupt",
            premaster_path=str(corrupt_wav),
            is_premaster=True,
        )
        result = self.engine.master(req)

        self.assertEqual(result.status, "FAILED")
        self.assertFalse(result.qc_result.passed)
        self.assertEqual(result.qc_result.checks.get("audio_integrity"), "FAIL")
        self.assertIn("premaster_audio_integrity_failed_empty_or_corrupt", result.qc_result.failures)
        self.assertIn("empty or corrupt", result.error_message.lower())

    def test_deterministic_mastering_success(self):
        """Verify end-to-end mastering execution produces compliant 48kHz stereo master and ledger."""
        premaster_wav = self.tmp_dir / "ch01_premaster.wav"
        out_master_wav = self.tmp_dir / "ch01_cinema_master.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=3.0, sample_rate=44100, channels=1, amplitude=0.4)

        profile = MasteringProfile(
            target_lufs=-19.0,
            tolerance_lu=1.0,
            true_peak_ceiling_dbtp=-1.5,
            limiter_ceiling_db=-1.6,
            output_sample_rate=48000,
            output_channels=2,
        )
        req = MasteringRequest(
            chapter_id="ch01",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
            profile=profile,
        )

        result = self.engine.master(req)

        # 1. Verification of Status and Certification
        self.assertEqual(result.status, "SUCCESS")
        self.assertTrue(result.qc_result.passed)
        self.assertIn(result.qc_result.status, ("PASS", "WARN"))

        # 2. Output File Verification
        self.assertTrue(out_master_wav.exists())
        self.assertGreater(out_master_wav.stat().st_size, 1000)

        # 3. Measurable Acoustic Facts Verification
        after = result.analysis_after
        self.assertIsNotNone(after)
        self.assertEqual(after.sample_rate, 48000)
        self.assertEqual(after.channels, 2)
        # Integrated LUFS close to -19.0 within tolerance
        self.assertAlmostEqual(after.integrated_lufs, -19.0, delta=1.5)
        # True peak must not exceed ceiling
        if after.true_peak_dbtp is not None:
            self.assertLessEqual(after.true_peak_dbtp, -1.2)  # within ceiling margin

        # 4. Provenance Verification
        self.assertIn("premaster_sha256", result.provenance)
        self.assertIn("master_sha256", result.provenance)
        self.assertEqual(result.provenance["premaster_sha256"], self.engine._compute_sha256(premaster_wav))
        self.assertEqual(result.provenance["master_sha256"], self.engine._compute_sha256(out_master_wav))

        # 5. Disk Ledger Persistence Verification
        ledger_path = self.tmp_dir / "ch01_mastering_ledger.json"
        self.assertTrue(ledger_path.exists())
        ledger = MasteringLedger.load_from_disk(ledger_path)
        self.assertEqual(ledger.chapter_id, "ch01")
        self.assertEqual(ledger.result.status, "SUCCESS")
        self.assertEqual(ledger.result.master_path, str(out_master_wav))

    def test_dialogue_protection_integration(self):
        """Verify vocal anchor ratio is analyzed and recorded when dialogue stem is provided."""
        premaster_wav = self.tmp_dir / "ch02_premaster.wav"
        dialogue_wav = self.tmp_dir / "ch02_dialogue.wav"
        out_master_wav = self.tmp_dir / "ch02_cinema_master.wav"

        generate_synthetic_audio(premaster_wav, duration_sec=3.0, amplitude=0.5)
        generate_synthetic_audio(dialogue_wav, duration_sec=3.0, amplitude=0.45)

        req = MasteringRequest(
            chapter_id="ch02",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
            dialogue_stem_path=str(dialogue_wav),
            profile=MasteringProfile(target_lufs=-19.0),
        )

        result = self.engine.master(req)
        self.assertEqual(result.status, "SUCCESS")
        self.assertTrue(result.qc_result.passed)
        self.assertIn("dialogue_protection", result.qc_result.checks)


if __name__ == "__main__":
    unittest.main()
