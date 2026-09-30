#!/usr/bin/env python3
"""
Test Suite: test_mastering_analyzer.py
Verifies forensic acoustic analysis, cache determinism, and metric calculations in MasteringAnalyzer.
"""

import math
import tempfile
import unittest
import wave
from pathlib import Path

from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.mastering_contracts import MasteringAnalysisFacts


def create_test_wav(
    filepath: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 48000,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    channels: int = 2,
) -> Path:
    """Creates a deterministic PCM WAV file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        raw_bytes = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            val = math.sin(2 * math.pi * frequency * t)
            int_val = int(val * amplitude * 32767.0)
            int_val = max(-32767, min(32767, int_val))
            packed = int_val.to_bytes(2, byteorder="little", signed=True)
            for _ in range(channels):
                raw_bytes.extend(packed)
        wf.writeframes(raw_bytes)
    return filepath


class TestMasteringAnalyzer(unittest.TestCase):
    """Unit tests for MasteringAnalyzer."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        self.analyzer = MasteringAnalyzer()
        self.audio_wav = self.tmp_dir / "test_audio.wav"
        create_test_wav(self.audio_wav, duration_sec=3.0, frequency=440.0, amplitude=0.4)

    def tearDown(self):
        self.td.cleanup()

    def test_analyze_valid_audio(self):
        """Verify comprehensive facts extracted from physical audio file."""
        facts = self.analyzer.analyze(self.audio_wav)
        self.assertIsInstance(facts, MasteringAnalysisFacts)
        self.assertTrue(facts.is_valid_audio)
        self.assertAlmostEqual(facts.duration_sec, 3.0, delta=0.1)
        self.assertEqual(facts.sample_rate, 48000)
        self.assertEqual(facts.channels, 2)
        self.assertIsNotNone(facts.integrated_lufs)
        self.assertGreater(facts.integrated_lufs, -60.0)
        self.assertIsNotNone(facts.true_peak_dbtp)
        self.assertIsNotNone(facts.rms_level_dbfs)
        self.assertIsNotNone(facts.dynamic_range_db)
        self.assertTrue(facts.mono_compatible)
        self.assertFalse(facts.clipping_detected)

    def test_deterministic_cache_acceleration(self):
        """Verify repeated calls hit in-memory cache with identical results."""
        f1 = self.analyzer.analyze(self.audio_wav)
        st = self.audio_wav.stat()
        cache_key = (str(self.audio_wav.resolve()), st.st_size, st.st_mtime_ns)
        self.assertIn(cache_key, self.analyzer._analysis_cache)

        # Second call returns identical copy
        f2 = self.analyzer.analyze(self.audio_wav)
        self.assertEqual(f1.integrated_lufs, f2.integrated_lufs)
        self.assertEqual(f1.true_peak_dbtp, f2.true_peak_dbtp)
        self.assertEqual(f1.duration_sec, f2.duration_sec)

        # Cache clear
        self.analyzer.clear_cache()
        self.assertEqual(len(self.analyzer._analysis_cache), 0)

    def test_analyze_invalid_or_missing_audio(self):
        """Verify graceful fail-safe handling of missing audio."""
        missing = self.tmp_dir / "does_not_exist.wav"
        facts = self.analyzer.analyze(missing)
        self.assertFalse(facts.is_valid_audio)
        self.assertEqual(facts.duration_sec, 0.0)
        self.assertEqual(facts.integrated_lufs, -70.0)

    def test_vocal_anchor_ratio_calculation(self):
        """Verify vocal anchor ratio calculation between DX and master."""
        dx_wav = self.tmp_dir / "dx.wav"
        create_test_wav(dx_wav, duration_sec=3.0, frequency=440.0, amplitude=0.45)
        master_wav = self.tmp_dir / "master.wav"
        create_test_wav(master_wav, duration_sec=3.0, frequency=440.0, amplitude=0.35)

        ratio = self.analyzer.calculate_vocal_anchor_ratio(dx_wav, master_wav)
        self.assertIsInstance(ratio, float)
        # DX is louder than master here, ratio should be positive
        self.assertGreater(ratio, 0.0)


if __name__ == "__main__":
    unittest.main()
