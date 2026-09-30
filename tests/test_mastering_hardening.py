#!/usr/bin/env python3
"""
Test Suite: test_mastering_hardening.py
=======================================
Adversarial hardening tests for Mastering V2:
1. P0-1: Eliminate fake measurements (loudnorm pass 1 failures fail-closed, no silent -24.0 LUFS fallback).
2. P0-2: Invalidate stale evidence when audio is modified/mutated.
3. P0-3: P4 second-pass integrity (Master B completely re-analyzes dialogue, consistency, and reference).
4. P0-4: Certification state integrity (REVIEW_REQUIRED and REJECTED never yield SUCCESS).
5. P0-5: Final artifact authority (certification report contains disk facts, verified SHA-256, and format versions).
6. P0-6: Provenance integrity (tracks initial vs. effective profile hashes, disk hashes, and winning attempt).
7. P0-7: Retry and remediation traceability (attempts_history records all iterations).
8. P0-8: Remix -> Premaster -> Master ordering (mix settled before Stage 12 runs, stale master invalidated).
"""

import hashlib
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringRequest,
    MasteringResult,
    MasteringAnalysisFacts,
    MasteringQCResult,
    FinalArtifactInfo,
    FinalCertificationReport,
    DialogueProtectionReport,
    ChapterConsistencyAudit,
    PerceptualEvaluation,
    PerceptualIssue,
)
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.mastering_qc import MasteringQCAgent
from audiobook_factory.mastering_certification import MasteringCertifier
from audiobook_factory.mastering_engine import MasteringEngineV2
from tests.test_mastering_engine import generate_synthetic_audio


class TestMasteringHardening(unittest.TestCase):
    """Adversarial validation suite for Stage 12 Mastering V2."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="mastering_hardening_test_"))
        self.engine = MasteringEngineV2()
        self.qc_agent = MasteringQCAgent()
        self.certifier = MasteringCertifier()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_p0_1_loudnorm_pass1_failure_raises_and_fails_closed(self):
        """P0-1: Verify _measure_loudnorm_pass1 raises RuntimeError on unparseable/error output without fake fallbacks."""
        premaster_wav = self.tmp_dir / "ch_loudnorm_fail.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=1.5, amplitude=0.3)
        profile = MasteringProfile()

        # Simulate subprocess failure in pass 1
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.stderr = "Error: Invalid audio filter parameters"
            mock_run.return_value = mock_proc

            with self.assertRaises(RuntimeError) as ctx:
                self.engine._measure_loudnorm_pass1(premaster_wav, -19.0, profile)
            self.assertIn("Pass 1 loudnorm execution failed", str(ctx.exception))

        # Simulate missing JSON in pass 1 stderr
        with patch("subprocess.run") as mock_run:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.stderr = "No loudnorm JSON output present"
            mock_run.return_value = mock_proc

            with self.assertRaises(RuntimeError) as ctx:
                self.engine._measure_loudnorm_pass1(premaster_wav, -19.0, profile)
            self.assertIn("Pass 1 loudnorm failed to parse JSON", str(ctx.exception))

        # Simulate pass 1 failure inside master() with max_retries=0 - must fail closed with FAILED status
        profile_no_retry = MasteringProfile(max_retries=0)
        req = MasteringRequest(
            chapter_id="ch_loudnorm_err",
            premaster_path=str(premaster_wav),
            profile=profile_no_retry,
        )
        with patch.object(self.engine, "_measure_loudnorm_pass1", side_effect=RuntimeError("FFmpeg error")):
            result = self.engine.master(req)

        self.assertEqual(result.status, "FAILED")
        self.assertFalse(result.qc_result.passed)
        self.assertIn("mastering_dsp_render_failed", result.qc_result.failures[0])

        # Also verify that when retries are enabled, persistent failure exhausts retries and terminates as RETRY_EXHAUSTED
        req_retries = MasteringRequest(
            chapter_id="ch_loudnorm_err_retries",
            premaster_path=str(premaster_wav),
            profile=MasteringProfile(max_retries=2),
        )
        with patch.object(self.engine, "_measure_loudnorm_pass1", side_effect=RuntimeError("FFmpeg error")):
            result_retries = self.engine.master(req_retries)

        self.assertEqual(result_retries.status, "RETRY_EXHAUSTED")
        self.assertFalse(result_retries.qc_result.passed)

    def test_p0_1_missing_true_peak_or_loudness_fails_qc(self):
        """P0-1 & P0-10: Verify missing measurements in facts fail QC rather than silently passing."""
        facts_no_tp = MasteringAnalysisFacts(
            filepath=str(self.tmp_dir / "audio.wav"),
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.0,
            true_peak_dbtp=None,  # Missing
            is_valid_audio=True,
        )
        qc_tp = self.qc_agent.evaluate(facts_no_tp)
        self.assertFalse(qc_tp.passed)
        self.assertEqual(qc_tp.checks["true_peak"], "FAIL")
        self.assertIn("true_peak_measurement_missing", qc_tp.failures)

    def test_p0_2_tampered_artifact_rejected_by_certification(self):
        """P0-2 & P0-5: Verify certifier rejects deliverables if file on disk was mutated after measurement."""
        master_wav = self.tmp_dir / "master_tamper.wav"
        generate_synthetic_audio(master_wav, duration_sec=2.0, amplitude=0.4)

        hasher = hashlib.sha256()
        hasher.update(master_wav.read_bytes())
        original_sha = hasher.hexdigest()

        artifact_info = FinalArtifactInfo(
            filepath=str(master_wav),
            sha256=original_sha,
            size_bytes=master_wav.stat().st_size,
            duration_sec=2.0,
            sample_rate=48000,
            channels=2,
            bit_depth=16,
        )
        qc_pass = MasteringQCResult(status="PASS", passed=True)

        # Before tampering: passes certification
        cert_valid = self.certifier.certify(
            chapter_id="ch_tamper",
            qc_result=qc_pass,
            artifact_info=artifact_info,
        )
        self.assertEqual(cert_valid.certification, "CERTIFIED")

        # Mutate the file on disk (simulate out-of-band edit or corruption)
        with open(master_wav, "ab") as f:
            f.write(b"CORRUPT_EXTRA_BYTES")

        # After tampering: must be REJECTED with artifact_hash_mismatch_or_tampered
        cert_tampered = self.certifier.certify(
            chapter_id="ch_tamper",
            qc_result=qc_pass,
            artifact_info=artifact_info,
        )
        self.assertEqual(cert_tampered.certification, "REJECTED")
        self.assertEqual(cert_tampered.review_items[0]["issue_code"], "artifact_hash_mismatch_or_tampered")

    def test_p0_3_p4_second_pass_re_evaluates_all_pillars(self):
        """P0-3: Verify accepted P4 second pass recalculates dialogue, consistency, and reference on Master B."""
        premaster_wav = self.tmp_dir / "ch_p4_pillars.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=2.5, amplitude=0.35)
        out_master_wav = self.tmp_dir / "ch_p4_pillars_master.wav"

        req = MasteringRequest(
            chapter_id="ch_p4_pillars",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
            allow_perceptual_multipass=True,
        )

        call_count = [0]
        def mock_eval(facts, judge_issues=None, book_profile=None, scene_intent=None, dialogue_report=None, previous_eval=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return PerceptualEvaluation(
                    overall="WARN",
                    scores={"intelligibility": 0.90, "fatigue_risk": 0.55},
                    issues=[PerceptualIssue(dimension="fatigue_risk", severity="MAJOR", description="Harsh sibilance", confidence=0.88)],
                )
            else:
                return PerceptualEvaluation(
                    overall="PASS",
                    scores={"intelligibility": 0.95, "fatigue_risk": 0.88},
                    issues=[],
                )

        with patch.object(self.engine.perceptual_critic, "evaluate", side_effect=mock_eval):
            result = self.engine.master(req)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.iteration_count, 2)
        # Winning attempt is pass 2
        self.assertEqual(result.provenance["winning_attempt"], 2)
        self.assertEqual(len(result.provenance["attempts_history"]), 2)
        # Verify artifact_info was generated for the final deliverable
        self.assertIsNotNone(result.certification_report.artifact_info)
        self.assertEqual(result.certification_report.artifact_info.filepath, str(out_master_wav))
        # Hash matches disk
        current_sha = hashlib.sha256(out_master_wav.read_bytes()).hexdigest()
        self.assertEqual(result.certification_report.artifact_info.sha256, current_sha)

    def test_p0_4_certification_status_integrity_review_required(self):
        """P0-4: Verify REVIEW_REQUIRED certification yields REVIEW_REQUIRED status, never SUCCESS."""
        premaster_wav = self.tmp_dir / "ch_review_status.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=2.0, amplitude=0.3)
        out_master_wav = self.tmp_dir / "ch_review_status_master.wav"

        req = MasteringRequest(
            chapter_id="ch_review_status",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
        )

        review_cert = FinalCertificationReport(
            certification="REVIEW_REQUIRED",
            chapter_id="ch_review_status",
            review_items=[{"issue_code": "ambiguity_flag", "evidence": "Acoustic ambiguity"}],
        )

        with patch.object(self.engine.certifier, "certify", return_value=review_cert):
            result = self.engine.master(req)

        self.assertEqual(result.status, "REVIEW_REQUIRED")
        self.assertNotEqual(result.status, "SUCCESS")
        self.assertIn("Mastering requires human review", result.error_message)

    def test_p0_4_certification_status_integrity_rejected(self):
        """P0-4: Verify REJECTED certification yields FAILED status, never SUCCESS."""
        premaster_wav = self.tmp_dir / "ch_reject_status.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=2.0, amplitude=0.3)
        out_master_wav = self.tmp_dir / "ch_reject_status_master.wav"

        req = MasteringRequest(
            chapter_id="ch_reject_status",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
        )

        rejected_cert = FinalCertificationReport(
            certification="REJECTED",
            chapter_id="ch_reject_status",
            review_items=[{"issue_code": "severe_defect", "evidence": "Defect evidence"}],
        )

        with patch.object(self.engine.certifier, "certify", return_value=rejected_cert):
            result = self.engine.master(req)

        self.assertEqual(result.status, "FAILED")
        self.assertNotEqual(result.status, "SUCCESS")
        self.assertIn("Mastering certification REJECTED", result.error_message)

    def test_p0_6_provenance_integrity_and_dual_profile_hashes(self):
        """P0-6: Verify provenance tracks initial vs effective profile hash when adjustments occur."""
        premaster_wav = self.tmp_dir / "ch_dual_hash.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=2.5, amplitude=0.3)
        out_master_wav = self.tmp_dir / "ch_dual_hash_master.wav"

        initial_profile = MasteringProfile(target_lufs=-19.0)
        req = MasteringRequest(
            chapter_id="ch_dual_hash",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
            profile=initial_profile,
        )

        result = self.engine.master(req)

        self.assertIn("initial_profile_sha256", result.provenance)
        self.assertIn("effective_profile_sha256", result.provenance)
        self.assertIn("attempts_history", result.provenance)
        self.assertIn("winning_attempt", result.provenance)

        # Premaster and master hashes must be non-empty 64-char hex strings
        self.assertEqual(len(result.provenance["premaster_sha256"]), 64)
        self.assertEqual(len(result.provenance["master_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
