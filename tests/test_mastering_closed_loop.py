#!/usr/bin/env python3
"""
Integration Tests for Stage 12: Closed-Loop Mastering & Remediation.
=====================================================================
Validates:
1. Closed-loop feedback cycle: Analyze -> Render -> Re-analyze -> QC.
2. Bounded remediation parameter adjustments (loudness offset and peak limiter).
3. Retry exhaustion and fail-closed safety (max_retries respected).
4. Ledger disk serialization roundtrip and provenance integrity.
"""

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
    MasteringLedger,
    MasteringAnalysisFacts,
    MasteringQCResult,
)
from audiobook_factory.mastering_engine import MasteringEngineV2
from tests.test_mastering_engine import generate_synthetic_audio


class TestMasteringClosedLoop(unittest.TestCase):
    """Test suite for closed-loop validation and remediation."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="mastering_closed_loop_test_"))
        self.engine = MasteringEngineV2()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_remediation_retry_on_loudness_tolerance_exceeded(self):
        """Verify that when first pass fails loudness QC, engine performs bounded parameter compensation and retries."""
        premaster_wav = self.tmp_dir / "ch_retry_loudness.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=3.0, amplitude=0.3)

        out_master_wav = self.tmp_dir / "ch_retry_loudness_master.wav"

        profile = MasteringProfile(
            target_lufs=-19.0,
            tolerance_lu=0.5,
            max_retries=2,
        )
        req = MasteringRequest(
            chapter_id="ch_retry_lufs",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
            profile=profile,
        )

        # Mock the QC agent: fail on attempt 1 due to loudness deviation, pass on attempt 2
        real_evaluate = self.engine.qc_agent.evaluate
        call_count = [0]

        def simulated_qc(master_facts, premaster_facts=None, dialogue_facts=None, profile=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return MasteringQCResult(
                    status="FAIL",
                    passed=False,
                    checks={"loudness": "FAIL"},
                    failures=["integrated_loudness_severe_violation: -17.20 LUFS outside target -19.0 +/- 0.5 LU"],
                    warnings=[],
                    details={"measured_integrated_lufs": -17.20, "target_lufs": -19.0},
                )
            else:
                return real_evaluate(master_facts, premaster_facts, dialogue_facts, profile)

        with patch.object(self.engine.qc_agent, "evaluate", side_effect=simulated_qc):
            result = self.engine.master(req)

        self.assertEqual(result.status, "SUCCESS")
        self.assertIn(result.iteration_count, (2, 3))
        self.assertGreaterEqual(len(result.provenance["remediation_actions"]), 1)
        remediation = result.provenance["remediation_actions"][0]
        self.assertEqual(remediation["type"], "loudness_offset_compensation")
        self.assertEqual(remediation["attempt"], 1)

    def test_remediation_retry_on_true_peak_overshoot(self):
        """Verify that when first pass exceeds true-peak ceiling, engine lowers limiter ceiling and retries."""
        premaster_wav = self.tmp_dir / "ch_retry_tp.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=3.0, amplitude=0.6)
        out_master_wav = self.tmp_dir / "ch_retry_tp_master.wav"

        profile = MasteringProfile(
            target_lufs=-19.0,
            true_peak_ceiling_dbtp=-1.5,
            limiter_ceiling_db=-1.6,
            max_retries=2,
        )
        req = MasteringRequest(
            chapter_id="ch_retry_tp",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
            profile=profile,
        )

        real_evaluate = self.engine.qc_agent.evaluate
        call_count = [0]

        def simulated_qc(master_facts, premaster_facts=None, dialogue_facts=None, profile=None):
            call_count[0] += 1
            if call_count[0] == 1:
                return MasteringQCResult(
                    status="FAIL",
                    passed=False,
                    checks={"true_peak": "FAIL"},
                    failures=["true_peak_ceiling_violation: -1.10 dBTP exceeds ceiling -1.5 dBTP"],
                    warnings=[],
                    details={"measured_true_peak_dbtp": -1.10, "true_peak_ceiling_dbtp": -1.5},
                )
            else:
                return real_evaluate(master_facts, premaster_facts, dialogue_facts, profile)

        with patch.object(self.engine.qc_agent, "evaluate", side_effect=simulated_qc):
            result = self.engine.master(req)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.iteration_count, 2)
        self.assertEqual(len(result.provenance["remediation_actions"]), 1)
        remediation = result.provenance["remediation_actions"][0]
        self.assertEqual(remediation["type"], "limiter_ceiling_backoff")
        self.assertLess(remediation["limiter_adjusted"], remediation["limiter_before"])

    def test_retry_exhaustion_on_persistent_defect(self):
        """Verify engine halts after max_retries and marks RETRY_EXHAUSTED when defects persist."""
        premaster_wav = self.tmp_dir / "ch_retry_exhaust.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=2.5, amplitude=0.4)
        out_master_wav = self.tmp_dir / "ch_retry_exhaust_master.wav"

        profile = MasteringProfile(
            target_lufs=-19.0,
            max_retries=2,
        )
        req = MasteringRequest(
            chapter_id="ch_exhaust",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
            profile=profile,
        )

        # Persistent failure
        persistent_fail = MasteringQCResult(
            status="FAIL",
            passed=False,
            checks={"loudness": "FAIL"},
            failures=["integrated_loudness_severe_violation"],
            warnings=[],
            details={},
        )

        with patch.object(self.engine.qc_agent, "evaluate", return_value=persistent_fail):
            result = self.engine.master(req)

        self.assertEqual(result.status, "RETRY_EXHAUSTED")
        self.assertFalse(result.qc_result.passed)
        # Attempted initial + 2 retries = 3 iterations
        self.assertEqual(result.iteration_count, 3)
        self.assertIn("Mastering QC failed after 3 passes", result.error_message)

    def test_ledger_disk_roundtrip(self):
        """Verify MasteringLedger serializes and deserializes from disk with full fidelity."""
        premaster_wav = self.tmp_dir / "ch_ledger_trip.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=2.0, amplitude=0.3)
        out_master_wav = self.tmp_dir / "ch_ledger_trip_master.wav"

        req = MasteringRequest(
            chapter_id="ch_ledger",
            premaster_path=str(premaster_wav),
            output_master_path=str(out_master_wav),
        )
        result = self.engine.master(req)

        ledger_file = self.tmp_dir / "ch_ledger_mastering_ledger.json"
        self.assertTrue(ledger_file.exists())

        loaded = MasteringLedger.load_from_disk(ledger_file)
        self.assertEqual(loaded.chapter_id, "ch_ledger")
        self.assertEqual(loaded.result.status, result.status)
        self.assertEqual(loaded.result.provenance["master_sha256"], result.provenance["master_sha256"])
        self.assertEqual(loaded.result.analysis_after.sample_rate, 48000)

    def test_perceptual_multipass_improvement_accepted(self):
        """Verify that when perceptual critic flags fatigue risk, engine performs corrective pass and accepts improvement."""
        from audiobook_factory.mastering_contracts import PerceptualEvaluation, PerceptualIssue

        premaster_wav = self.tmp_dir / "ch_p4_accept.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=2.0, amplitude=0.35)
        out_master_wav = self.tmp_dir / "ch_p4_accept_master.wav"

        req = MasteringRequest(
            chapter_id="ch_p4_accept",
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
                    scores={"intelligibility": 0.90, "fatigue_risk": 0.60},
                    issues=[
                        PerceptualIssue(
                            dimension="fatigue_risk",
                            severity="MAJOR",
                            description="Harsh high frequencies detected.",
                            confidence=0.85,
                        )
                    ],
                )
            else:
                return PerceptualEvaluation(
                    overall="PASS",
                    scores={"intelligibility": 0.95, "fatigue_risk": 0.85},
                    issues=[],
                )

        with patch.object(self.engine.perceptual_critic, "evaluate", side_effect=mock_eval):
            result = self.engine.master(req)

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.iteration_count, 2)
        self.assertEqual(result.perceptual_evaluation.overall, "PASS")

    def test_perceptual_multipass_degradation_reverted(self):
        """Verify that if a perceptual corrective pass degrades scores, the engine safely reverts."""
        from audiobook_factory.mastering_contracts import PerceptualEvaluation, PerceptualIssue

        premaster_wav = self.tmp_dir / "ch_p4_revert.wav"
        generate_synthetic_audio(premaster_wav, duration_sec=2.0, amplitude=0.35)
        out_master_wav = self.tmp_dir / "ch_p4_revert_master.wav"

        req = MasteringRequest(
            chapter_id="ch_p4_revert",
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
                    scores={"intelligibility": 0.90, "fatigue_risk": 0.60},
                    issues=[
                        PerceptualIssue(
                            dimension="fatigue_risk",
                            severity="MAJOR",
                            description="Harsh high frequencies detected.",
                            confidence=0.85,
                        )
                    ],
                )
            else:
                # Degraded score
                return PerceptualEvaluation(
                    overall="REVIEW",
                    scores={"intelligibility": 0.80, "fatigue_risk": 0.40},  # worse!
                    issues=[],
                )

        with patch.object(self.engine.perceptual_critic, "evaluate", side_effect=mock_eval):
            result = self.engine.master(req)

        self.assertEqual(result.status, "SUCCESS")
        # Retained previous evaluation because degraded pass was reverted
        self.assertEqual(result.perceptual_evaluation.overall, "WARN")
        self.assertEqual(result.perceptual_evaluation.scores["fatigue_risk"], 0.60)


if __name__ == "__main__":
    unittest.main()

