#!/usr/bin/env python3
"""
Unit and Integration Tests for Production Certification (Prompt 7).
Verifies the production harness, failure injections, reproducibility,
chapter consistency, and 10 production gates.
"""

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from audiobook_factory.production_certification_harness import ProductionCertificationHarness


class TestProductionCertification(unittest.TestCase):
    """Verifies the complete production certification execution."""

    @classmethod
    def setUpClass(cls):
        cls.harness = ProductionCertificationHarness()
        cls.clean_run = cls.harness.execute_clean_room_production()
        cls.consistency = cls.harness.run_book_consistency_audit()
        cls.failures = cls.harness.run_failure_injections()
        cls.repro = cls.harness.run_reproducibility_test()
        cls.fatigue = cls.harness.run_fatigue_and_long_form_audit()
        cls.gates = cls.harness.evaluate_production_gates(
            cls.clean_run, cls.consistency, cls.repro, cls.failures, cls.fatigue
        )
        cls.cert_json, cls.cert_md = cls.harness.generate_certification_artifacts(
            cls.clean_run, cls.consistency, cls.repro, cls.failures, cls.fatigue, cls.gates
        )

    def test_01_clean_room_deliverable_created(self):
        """Verify final M4B container is generated and exists on disk."""
        final_m4b = Path(self.clean_run["final_m4b"])
        self.assertTrue(final_m4b.exists())
        self.assertGreater(final_m4b.stat().st_size, 50000)
        self.assertTrue(len(self.clean_run["m4b_hash"]) == 64)

    def test_02_all_chapters_broadcast_compliant(self):
        """Verify all 3 chapters meet EBU R128 (-19.0 LUFS, TP <= -1.4 dBTP)."""
        self.assertEqual(len(self.harness.chapter_results), 3)
        for ch in self.harness.chapter_results:
            self.assertEqual(ch["gate5_status"], "PASS")
            self.assertAlmostEqual(ch["integrated_lufs"], -19.0, delta=1.5)
            self.assertLessEqual(ch["true_peak_dbtp"], -1.4)
            self.assertGreaterEqual(ch["phase_correlation"], 0.20)

    def test_03_book_master_profile_and_consistency(self):
        """Verify BookMasterProfile and ChapterConsistency evaluations."""
        self.assertIn(self.consistency["consistency_verdict"], ("CONSISTENT", "PASS"))
        self.assertLessEqual(self.consistency["max_deviation_lu"], 1.0)
        self.assertGreaterEqual(self.consistency["book_profile"]["confidence_score"], 0.5)

    def test_04_controlled_failure_injections(self):
        """Verify all 8 failure injection scenarios fail closed."""
        self.assertEqual(len(self.failures), 8)
        for name, res in self.failures.items():
            self.assertTrue(res["caught"], f"Failure scenario '{name}' was not caught safely!")
            self.assertEqual(res["status"], "PASS")

    def test_05_reproducibility(self):
        """Verify controlled re-run on Chapter 1 is acoustically equivalent or identical."""
        self.assertIn(self.repro["classification"], ("EXPECTED", "BENIGN"))
        self.assertTrue(self.repro["is_acoustically_equivalent"])
        self.assertLess(self.repro["lufs_delta"], 0.1)

    def test_06_fatigue_and_long_form_risk(self):
        """Verify long-form continuity passes with low fatigue risk."""
        self.assertEqual(self.fatigue["fatigue_risk"], "LOW")
        self.assertTrue(self.fatigue["long_form_stress_passed"])
        self.assertLessEqual(self.fatigue["book_lufs_spread_lu"], 1.5)

    def test_07_all_production_gates_pass(self):
        """Verify all 10 production certification gates pass."""
        self.assertTrue(self.gates["all_gates_passed"])
        self.assertEqual(self.gates["final_status"], "PRODUCTION_CERTIFIED")
        for g_id, g_info in self.gates["gates"].items():
            self.assertTrue(g_info["passed"], f"Gate {g_id} failed!")

    def test_08_certification_artifacts_exist(self):
        """Verify machine-readable JSON and human-readable MD reports exist."""
        self.assertTrue(self.cert_json.exists())
        self.assertTrue(self.cert_md.exists())
        self.assertGreater(self.cert_json.stat().st_size, 500)
        self.assertGreater(self.cert_md.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
