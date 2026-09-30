#!/usr/bin/env python3
"""
Unit and Integration Tests for Stage 12: BookMasterProfileBuilder.
==================================================================
Validates:
1. Robust median/IQR statistical aggregation across multiple chapters.
2. Outlier rejection (loud explosions and silence do not skew baseline).
3. Sample-size confidence scoring (0.0 to 1.0).
4. Disk serialization and deserialization fidelity.
"""

import tempfile
import unittest
from pathlib import Path

from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    BookMasterProfile,
)
from audiobook_factory.book_master_profile import BookMasterProfileBuilder


class TestBookMasterProfile(unittest.TestCase):
    """Test suite for BookMasterProfileBuilder."""

    def setUp(self):
        self.builder = BookMasterProfileBuilder()

    def test_robust_median_rejects_extreme_outliers(self):
        """Verify median-based profile generation is not distorted by an anomalous loud chapter."""
        # 4 normal chapters around -19.0 LUFS, 1 explosion chapter at -12.0 LUFS
        chapters = {
            "ch01": MasteringAnalysisFacts(filepath="c1.wav", duration_sec=3.0, integrated_lufs=-19.0, true_peak_dbtp=-1.5, crest_factor_db=8.0, spectral_centroid_hz=1200.0, is_valid_audio=True),
            "ch02": MasteringAnalysisFacts(filepath="c2.wav", duration_sec=3.0, integrated_lufs=-19.1, true_peak_dbtp=-1.5, crest_factor_db=8.2, spectral_centroid_hz=1220.0, is_valid_audio=True),
            "ch03": MasteringAnalysisFacts(filepath="c3.wav", duration_sec=3.0, integrated_lufs=-18.9, true_peak_dbtp=-1.6, crest_factor_db=7.9, spectral_centroid_hz=1190.0, is_valid_audio=True),
            "ch04": MasteringAnalysisFacts(filepath="c4.wav", duration_sec=3.0, integrated_lufs=-19.0, true_peak_dbtp=-1.5, crest_factor_db=8.1, spectral_centroid_hz=1210.0, is_valid_audio=True),
            "ch_outlier": MasteringAnalysisFacts(filepath="c_out.wav", duration_sec=3.0, integrated_lufs=-12.0, true_peak_dbtp=-0.2, crest_factor_db=3.0, spectral_centroid_hz=3500.0, is_valid_audio=True),
        }

        profile = self.builder.build_profile("book_witcher", chapters)

        self.assertEqual(profile.book_id, "book_witcher")
        self.assertEqual(profile.sample_count, 5)
        self.assertEqual(profile.confidence, 1.0)
        # Median LUFS should be exactly -19.0, immune to the -12.0 outlier
        self.assertEqual(profile.target_lufs_median, -19.0)
        self.assertAlmostEqual(profile.crest_factor_median_db, 8.0, delta=0.2)

    def test_sample_confidence_scoring(self):
        """Verify confidence scales with available representative chapter count."""
        ch1 = MasteringAnalysisFacts(filepath="c1.wav", duration_sec=3.0, integrated_lufs=-19.0, is_valid_audio=True)
        ch2 = MasteringAnalysisFacts(filepath="c2.wav", duration_sec=3.0, integrated_lufs=-19.2, is_valid_audio=True)
        ch3 = MasteringAnalysisFacts(filepath="c3.wav", duration_sec=3.0, integrated_lufs=-18.8, is_valid_audio=True)

        prof0 = self.builder.build_profile("book_0", {})
        self.assertEqual(prof0.confidence, 0.0)

        prof1 = self.builder.build_profile("book_1", {"c1": ch1})
        self.assertEqual(prof1.confidence, 0.50)

        prof2 = self.builder.build_profile("book_2", {"c1": ch1, "c2": ch2})
        self.assertEqual(prof2.confidence, 0.75)

        prof3 = self.builder.build_profile("book_3", {"c1": ch1, "c2": ch2, "c3": ch3})
        self.assertEqual(prof3.confidence, 1.0)

    def test_corrupt_and_silent_chapter_filtering(self):
        """Verify invalid or silence-dropout chapters are filtered out before aggregation."""
        valid_ch = MasteringAnalysisFacts(filepath="valid.wav", duration_sec=3.0, integrated_lufs=-19.0, is_valid_audio=True)
        corrupt_ch = MasteringAnalysisFacts(filepath="corrupt.wav", duration_sec=0.0, integrated_lufs=-70.0, is_valid_audio=False)
        silent_ch = MasteringAnalysisFacts(filepath="silent.wav", duration_sec=3.0, integrated_lufs=-68.0, is_valid_audio=True)

        profile = self.builder.build_profile("book_filter", {
            "valid": valid_ch,
            "corrupt": corrupt_ch,
            "silent": silent_ch,
        })

        self.assertEqual(profile.sample_count, 1)
        self.assertEqual(profile.source_chapters, ["valid"])

    def test_disk_serialization_roundtrip(self):
        """Verify BookMasterProfile saves to disk and reloads identically."""
        ch1 = MasteringAnalysisFacts(filepath="c1.wav", duration_sec=3.0, integrated_lufs=-19.0, is_valid_audio=True)
        profile = self.builder.build_profile("book_persist", {"c1": ch1})

        with tempfile.TemporaryDirectory() as td:
            disk_path = Path(td) / "book_master_profile.json"
            profile.save_to_disk(disk_path)
            self.assertTrue(disk_path.exists())

            loaded = BookMasterProfile.load_from_disk(disk_path)
            self.assertEqual(loaded.book_id, "book_persist")
            self.assertEqual(loaded.target_lufs_median, profile.target_lufs_median)
            self.assertEqual(loaded.version, profile.version)


if __name__ == "__main__":
    unittest.main()
