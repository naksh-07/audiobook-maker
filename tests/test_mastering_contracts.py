#!/usr/bin/env python3
"""
Test Suite: test_mastering_contracts.py
Verifies Pydantic contracts and serialization for Stage 12 Mastering V2.
"""

import tempfile
import unittest
from pathlib import Path
import pydantic

from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringAnalysisFacts,
    MasteringQCResult,
    MasteringRequest,
    MasteringResult,
    MasteringLedger,
)


class TestMasteringContracts(unittest.TestCase):
    """Unit tests for Mastering V2 data models and contracts."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        # Create a dummy premaster file for validation tests
        self.dummy_premaster = self.tmp_dir / "c001_premaster.wav"
        self.dummy_premaster.write_bytes(b"RIFF" + b"\x00" * 100)

    def tearDown(self):
        self.td.cleanup()

    def test_mastering_profile_defaults_and_bounds(self):
        """Verify default broadcast mastering values and safety bound enforcement."""
        profile = MasteringProfile()
        self.assertEqual(profile.target_lufs, -19.0)
        self.assertEqual(profile.true_peak_ceiling_dbtp, -1.6)
        self.assertEqual(profile.tolerance_lu, 0.5)
        self.assertEqual(profile.subsonic_highpass_hz, 28)
        self.assertTrue(profile.enable_dual_pass_linear)
        self.assertEqual(profile.max_retries, 2)

        # Test bounds validation
        with self.assertRaises(pydantic.ValidationError):
            MasteringProfile(target_lufs=-5.0)  # Too loud (> -14.0)

        with self.assertRaises(pydantic.ValidationError):
            MasteringProfile(true_peak_ceiling_dbtp=1.0)  # Must be <= -0.5

        with self.assertRaises(pydantic.ValidationError):
            MasteringProfile(subsonic_highpass_hz=10)  # Must be >= 18Hz

    def test_mastering_analysis_facts_instantiation(self):
        """Verify MasteringAnalysisFacts holds ground-truth physical metrics."""
        facts = MasteringAnalysisFacts(
            filepath=str(self.dummy_premaster),
            duration_sec=30.5,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-18.9,
            true_peak_dbtp=-1.52,
            sample_peak_dbfs=-1.8,
            rms_level_dbfs=-22.0,
            dynamic_range_db=20.2,
            crest_factor_db=20.2,
            spectral_centroid_hz=1250.0,
            phase_correlation=0.98,
            mono_compatible=True,
            clipping_detected=False,
            is_valid_audio=True,
        )
        self.assertEqual(facts.integrated_lufs, -18.9)
        self.assertTrue(facts.mono_compatible)
        self.assertFalse(facts.clipping_detected)

    def test_mastering_request_validation_and_double_master_protection(self):
        """Verify MasteringRequest rejects missing files and double-mastering."""
        # Valid request
        req = MasteringRequest(
            chapter_id="ch_001",
            premaster_path=str(self.dummy_premaster),
        )
        self.assertEqual(req.chapter_id, "ch_001")
        self.assertTrue(req.is_premaster)

        # Missing file rejected
        with self.assertRaises(FileNotFoundError):
            MasteringRequest(
                chapter_id="ch_001",
                premaster_path=str(self.tmp_dir / "non_existent.wav"),
            )

        # Double-master protection: is_premaster=False rejected
        with self.assertRaises(ValueError):
            MasteringRequest(
                chapter_id="ch_001",
                premaster_path=str(self.dummy_premaster),
                is_premaster=False,
            )

    def test_mastering_qc_result_status(self):
        """Verify MasteringQCResult machine-readable verdicts."""
        qc_pass = MasteringQCResult(
            status="PASS",
            passed=True,
            checks={"audio_integrity": "PASS", "loudness": "PASS"},
        )
        self.assertTrue(qc_pass.passed)
        self.assertEqual(qc_pass.status, "PASS")

        qc_fail = MasteringQCResult(
            status="FAIL",
            passed=False,
            checks={"audio_integrity": "FAIL"},
            failures=["corrupt_file_truncated"],
        )
        self.assertFalse(qc_fail.passed)
        self.assertEqual(len(qc_fail.failures), 1)

    def test_mastering_ledger_disk_serialization(self):
        """Verify MasteringLedger round-trip persistence to disk."""
        req = MasteringRequest(
            chapter_id="ch_ledger_test",
            premaster_path=str(self.dummy_premaster),
        )
        facts = MasteringAnalysisFacts(
            filepath=str(self.dummy_premaster),
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
        )
        qc = MasteringQCResult(status="PASS", passed=True)
        res = MasteringResult(
            status="SUCCESS",
            chapter_id="ch_ledger_test",
            premaster_path=str(self.dummy_premaster),
            master_path=str(self.tmp_dir / "master.wav"),
            profile=req.profile,
            analysis_before=facts,
            analysis_after=facts,
            qc_result=qc,
            provenance={"hash": "abc1234"},
        )
        ledger = MasteringLedger(
            chapter_id="ch_ledger_test",
            request=req,
            result=res,
        )

        ledger_path = self.tmp_dir / "ledger.json"
        saved = ledger.save_to_disk(ledger_path)
        self.assertTrue(saved.exists())

        loaded = MasteringLedger.load_from_disk(ledger_path)
        self.assertEqual(loaded.chapter_id, "ch_ledger_test")
        self.assertEqual(loaded.result.status, "SUCCESS")
        self.assertEqual(loaded.result.analysis_after.integrated_lufs, -19.0)

    def test_p4_perceptual_and_certification_contracts(self):
        """Verify P4 Perceptual, Reference, Scene, and Certification contracts."""
        from audiobook_factory.mastering_contracts import (
            PerceptualIssue,
            PerceptualEvaluation,
            ReferenceProfile,
            ReferenceComparisonResult,
            SceneMasteringDecision,
            FinalCertificationReport,
        )

        # 1. Perceptual Evaluation
        issue = PerceptualIssue(
            dimension="fatigue_risk",
            severity="MINOR",
            description="Elevated high frequency energy in 3-5kHz band.",
            evidence=["spectral_centroid=3400Hz"],
            confidence=0.85,
        )
        peval = PerceptualEvaluation(
            overall="WARN",
            scores={"intelligibility": 0.95, "naturalness": 0.90, "fatigue_risk": 0.60},
            issues=[issue],
            confidence=0.90,
            evidence=["spectral_centroid_hz=3400.0"],
        )
        self.assertEqual(peval.overall, "WARN")
        self.assertEqual(len(peval.issues), 1)

        # 2. Reference Profile
        ref = ReferenceProfile(
            reference_id="ref_narration_gold",
            reference_type="narration",
            target_lufs=-19.0,
            dynamic_range_db=8.5,
            crest_factor_db=10.0,
            spectral_centroid_hz=1150.0,
        )
        self.assertEqual(ref.reference_type, "narration")

        # 3. Scene Decision
        decision = SceneMasteringDecision(
            scene_type="INTIMATE",
            primary_element="dialogue",
            context_confidence=0.95,
            perceptual_findings=["Intimate close-mic whisper scene"],
            recommended_action="Preserve low-level dynamic contrast",
            risk="LOW",
            expected_effect="Warm intimate whisper without noise floor boost",
            requires_review=False,
            bounded_adjustments={"target_lufs_offset": 1.0},
        )
        self.assertEqual(decision.scene_type, "INTIMATE")
        self.assertEqual(decision.bounded_adjustments["target_lufs_offset"], 1.0)

        # 4. Final Certification Report
        cert = FinalCertificationReport(
            certification="CERTIFIED",
            chapter_id="ch_cert_test",
            technical_qc={"passed": True},
            mechanical_mastering={"passed": True},
            dialogue_protection={"passed": True},
            book_consistency={"passed": True},
            perceptual_evaluation={"overall": "PASS"},
            warnings=[],
            review_items=[],
            provenance={"engine_version": "2.2.0"},
        )
        self.assertEqual(cert.certification, "CERTIFIED")


if __name__ == "__main__":
    unittest.main()

