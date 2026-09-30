#!/usr/bin/env python3
"""
Unit and Integration Tests for Stage 12: GoldenMasteringSuite.
==============================================================
Validates:
1. Registration of all 10 canonical golden mastering scenarios.
2. Full suite execution against synthesized fixtures.
3. Hard regression detection (clipping, corrupt file, QC failure).
4. Metric regression detection (unexpected loudness or peak drift).
5. Baseline governance enforcement (reason and author required).
"""

import json
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringAnalysisFacts,
    MasteringQCResult,
    MasteringResult,
)
from audiobook_factory.golden_mastering_suite import (
    GoldenMasteringSuite,
    CANONICAL_10_FIXTURES,
)


class TestGoldenMasteringRegression(unittest.TestCase):
    """Test suite for GoldenMasteringSuite."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        self.custom_baseline = self.tmp_dir / "test_baseline.json"
        self.suite = GoldenMasteringSuite(baseline_path=self.custom_baseline)

    def tearDown(self):
        self.td.cleanup()

    def test_canonical_10_fixtures_registered(self):
        """Verify all 10 canonical scenarios are registered with full specifications."""
        self.assertEqual(len(CANONICAL_10_FIXTURES), 10)
        fixture_ids = [f.fixture_id for f in CANONICAL_10_FIXTURES]
        self.assertIn("01_clean_narration", fixture_ids)
        self.assertIn("03_intimate_whisper", fixture_ids)
        self.assertIn("05_shouting_combat", fixture_ids)
        self.assertIn("07_music_heavy", fixture_ids)
        self.assertIn("09_dramatic_silence", fixture_ids)
        self.assertIn("10_cinematic_full_mix", fixture_ids)

    def test_golden_suite_execution_and_pass(self):
        """Verify full suite execution on synthesized fixtures completes with zero hard regressions."""
        report = self.suite.run_suite(self.tmp_dir / "golden_work")

        self.assertEqual(report["total_fixtures"], 10)
        self.assertEqual(report["hard_regressions"], 0)
        self.assertEqual(report["passed_count"], 10)
        self.assertEqual(report["overall_status"], "PASS")

        # Verify P4 certification and perceptual metrics in fixture results
        for f_id, f_data in report["fixtures"].items():
            metrics = f_data.get("metrics", {})
            self.assertIn("certification", metrics)
            self.assertIn(metrics["certification"], ("CERTIFIED", "WARNINGS"))
            self.assertIn("perceptual_overall", metrics)
            self.assertIn(metrics["perceptual_overall"], ("PASS", "WARN"))


    def test_hard_regression_detection_on_clipping(self):
        """Verify digital clipping (> 0.0 dBTP) is detected as a HARD_REGRESSION."""
        clipping_facts = MasteringAnalysisFacts(
            filepath="clip.wav",
            duration_sec=3.0,
            integrated_lufs=-14.0,
            true_peak_dbtp=0.8,  # Severe clipping!
            clipping_detected=True,
            is_valid_audio=True,
        )
        fake_result = MasteringResult(
            status="SUCCESS",
            chapter_id="01_clean_narration",
            premaster_path="clip.wav",
            master_path=str(self.tmp_dir / "clip.wav"),
            profile=MasteringProfile(),
            analysis_before=clipping_facts,
            analysis_after=clipping_facts,
            qc_result=MasteringQCResult(status="PASS", passed=True),
        )
        # Create dummy file so exists check passes
        Path(fake_result.master_path).touch()

        audit = self.suite._audit_fixture(fake_result, baseline={"integrated_lufs": -19.0, "true_peak_dbtp": -1.5})
        self.assertEqual(audit["status"], "HARD_REGRESSION")
        self.assertIn("clipping", audit["reason"].lower())

    def test_metric_regression_detection_on_loudness_drift(self):
        """Verify unexpected loudness drift (> 0.5 LU) is detected as METRIC_REGRESSION."""
        drift_facts = MasteringAnalysisFacts(
            filepath="drift.wav",
            duration_sec=3.0,
            integrated_lufs=-17.2,  # Drifted from -19.0 baseline
            true_peak_dbtp=-1.5,
            clipping_detected=False,
            is_valid_audio=True,
        )
        fake_result = MasteringResult(
            status="SUCCESS",
            chapter_id="01_clean_narration",
            premaster_path="drift.wav",
            master_path=str(self.tmp_dir / "drift.wav"),
            profile=MasteringProfile(),
            analysis_before=drift_facts,
            analysis_after=drift_facts,
            qc_result=MasteringQCResult(status="PASS", passed=True),
        )
        Path(fake_result.master_path).touch()

        baseline = {"integrated_lufs": -19.0, "true_peak_dbtp": -1.5}
        audit = self.suite._audit_fixture(fake_result, baseline=baseline)

        self.assertEqual(audit["status"], "METRIC_REGRESSION")
        self.assertIn("drifted", audit["reason"].lower())

    def test_baseline_governance_enforcement(self):
        """Verify baseline cannot be updated without meaningful reason and author."""
        with self.assertRaises(ValueError) as ctx:
            self.suite.update_baseline({"01_clean_narration": {}}, reason="too short", author="tester")
        self.assertIn("min 10 chars", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx2:
            self.suite.update_baseline({"01_clean_narration": {}}, reason="Meaningful reason for upgrade", author="")
        self.assertIn("author identifier", str(ctx2.exception))

        # Valid update
        p = self.suite.update_baseline(
            {"01_clean_narration": {"integrated_lufs": -19.0}},
            reason="Official EBU R128 baseline calibration for v2.1",
            author="MasteringLead",
        )
        self.assertTrue(p.exists())
        data = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(len(data["governance_log"]), 1)
        self.assertEqual(data["governance_log"][0]["author"], "MasteringLead")


if __name__ == "__main__":
    unittest.main()
