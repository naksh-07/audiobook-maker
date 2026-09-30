#!/usr/bin/env python3
"""
Test Suite: test_mastering_certification.py
===========================================
Verifies Phase 5 & 6 MasteringCertifier:
1. Pristine chapter achieves CERTIFIED.
2. Hard technical failure cannot be overridden -> REJECTED.
3. Critical perceptual defect (e.g. out-of-phase) -> REJECTED.
4. Unexplained book inconsistency or perceptual uncertainty -> REVIEW_REQUIRED.
5. Non-critical acoustic warnings -> WARNINGS.
6. Targeted HumanReviewItem generation for REVIEW_REQUIRED and REJECTED cases.
"""

import unittest
from audiobook_factory.mastering_contracts import (
    MasteringQCResult,
    DialogueProtectionReport,
    ChapterConsistencyAudit,
    PerceptualEvaluation,
    PerceptualIssue,
    ReferenceComparisonResult,
)
from audiobook_factory.mastering_certification import MasteringCertifier


class TestMasteringCertification(unittest.TestCase):
    """Unit tests for MasteringCertifier."""

    def setUp(self):
        self.certifier = MasteringCertifier()

    def test_pristine_audio_achieves_certified(self):
        """Verify all passing pillars produce a CERTIFIED deliverable."""
        qc = MasteringQCResult(status="PASS", passed=True)
        dialogue = DialogueProtectionReport(chapter_id="c1", status="PASS", masking_risk="NONE")
        consistency = ChapterConsistencyAudit(chapter_id="c1", overall_status="PASS")
        perceptual = PerceptualEvaluation(overall="PASS", scores={"intelligibility": 0.95})

        cert = self.certifier.certify(
            chapter_id="c1",
            qc_result=qc,
            dialogue_report=dialogue,
            consistency_audit=consistency,
            perceptual_eval=perceptual,
        )

        self.assertEqual(cert.certification, "CERTIFIED")
        self.assertEqual(len(cert.warnings), 0)
        self.assertEqual(len(cert.review_items), 0)

    def test_technical_failure_overrides_all_to_rejected(self):
        """Verify Technical QC failure immediately yields REJECTED, regardless of perceptual scores."""
        qc_fail = MasteringQCResult(
            status="FAIL",
            passed=False,
            failures=["true_peak_overshoot_dbtp"],
        )
        # Even if perceptual score was high
        perceptual_pass = PerceptualEvaluation(overall="PASS", scores={"intelligibility": 1.0})

        cert = self.certifier.certify(
            chapter_id="c2",
            qc_result=qc_fail,
            perceptual_eval=perceptual_pass,
        )

        self.assertEqual(cert.certification, "REJECTED")
        self.assertGreater(len(cert.review_items), 0)
        self.assertEqual(cert.review_items[0]["category"], "technical_qc")

    def test_critical_perceptual_defect_yields_rejected(self):
        """Verify critical perceptual defect (severe phase cancellation) yields REJECTED."""
        qc_pass = MasteringQCResult(status="PASS", passed=True)
        crit_issue = PerceptualIssue(
            dimension="spatial_coherence",
            severity="CRITICAL",
            description="Mono cancellation detected (phase correlation = -0.6).",
        )
        perceptual_crit = PerceptualEvaluation(
            overall="REVIEW",
            issues=[crit_issue],
            scores={"spatial_coherence": 0.15},
        )

        cert = self.certifier.certify(
            chapter_id="c3",
            qc_result=qc_pass,
            perceptual_eval=perceptual_crit,
        )

        self.assertEqual(cert.certification, "REJECTED")
        self.assertEqual(cert.review_items[0]["severity"], "CRITICAL")

    def test_unexplained_inconsistency_yields_review_required(self):
        """Verify unexplained book consistency deviation triggers REVIEW_REQUIRED with targeted review items."""
        qc_pass = MasteringQCResult(status="PASS", passed=True)
        consistency_rev = ChapterConsistencyAudit(
            chapter_id="c4",
            overall_status="REVIEW",
            is_intentional_variation=False,
            confidence=0.85,
        )
        perceptual_pass = PerceptualEvaluation(overall="PASS")

        cert = self.certifier.certify(
            chapter_id="c4",
            qc_result=qc_pass,
            consistency_audit=consistency_rev,
            perceptual_eval=perceptual_pass,
        )

        self.assertEqual(cert.certification, "REVIEW_REQUIRED")
        self.assertEqual(len(cert.review_items), 1)
        self.assertEqual(cert.review_items[0]["category"], "book_consistency")

    def test_non_critical_warnings_yield_warnings_status(self):
        """Verify non-blocking warnings yield WARNINGS certification."""
        qc_warn = MasteringQCResult(status="PASS", passed=True, warnings=["mild_subsonic_activity"])
        perceptual_warn = PerceptualEvaluation(
            overall="WARN",
            scores={"fatigue_risk": 0.70},
            issues=[PerceptualIssue(dimension="fatigue_risk", severity="MINOR", description="Elevated centroid.")],
        )

        cert = self.certifier.certify(
            chapter_id="c5",
            qc_result=qc_warn,
            perceptual_eval=perceptual_warn,
        )

        self.assertEqual(cert.certification, "WARNINGS")
        self.assertGreater(len(cert.warnings), 0)
        self.assertEqual(len(cert.review_items), 0)


if __name__ == "__main__":
    unittest.main()
