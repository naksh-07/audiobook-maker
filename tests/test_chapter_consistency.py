#!/usr/bin/env python3
"""
Unit and Integration Tests for Stage 12: ChapterConsistencyAuditor & ReportBuilder.
===================================================================================
Validates:
1. Multi-dimensional consistency auditing against BookMasterProfile.
2. Invariant: DEVIATION != ERROR (distinguishing intentional scene variation from accidental drift).
3. Context-aware validation for whisper, combat, and suspense scenes.
4. Correct escalation to REVIEW and HIGH priority on unjustified drift.
5. BookConsistencyReport aggregation and Markdown table rendering.
"""

import unittest
from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    BookMasterProfile,
)
from audiobook_factory.chapter_consistency import (
    ChapterConsistencyAuditor,
    BookConsistencyReportBuilder,
)


class DummySceneIntent:
    """Mock SceneMixIntent for contextual testing."""
    def __init__(self, scene_type: str):
        self.scene_type = scene_type


class TestChapterConsistency(unittest.TestCase):
    """Test suite for ChapterConsistencyAuditor and BookConsistencyReportBuilder."""

    def setUp(self):
        self.auditor = ChapterConsistencyAuditor(default_tolerance_lu=0.8)
        self.reporter = BookConsistencyReportBuilder()
        self.profile = BookMasterProfile(
            book_id="book_witcher_master",
            version="1.0.0",
            confidence=1.0,
            sample_count=5,
            target_lufs_median=-19.0,
            target_lufs_iqr=0.4,
            crest_factor_median_db=8.0,
            lra_median=8.5,
            spectral_centroid_median_hz=1200.0,
            dialogue_anchor_median_db=0.0,
            phase_correlation_median=0.95,
        )

    def test_consistent_chapter_passes(self):
        """Verify a chapter matching the book profile within tolerance passes with zero warnings."""
        chapter_facts = MasteringAnalysisFacts(
            filepath="c1.wav",
            duration_sec=3.0,
            integrated_lufs=-19.1,
            crest_factor_db=8.1,
            spectral_centroid_hz=1220.0,
            phase_correlation=0.94,
            is_valid_audio=True,
        )
        audit = self.auditor.audit_chapter(chapter_facts, self.profile, chapter_id="ch01")

        self.assertEqual(audit.overall_status, "PASS")
        self.assertEqual(audit.review_priority, "NONE")
        self.assertFalse(audit.is_intentional_variation)
        self.assertEqual(audit.deviations["loudness"].status, "PASS")

    def test_intentional_dramatic_variation_distinguished(self):
        """Verify intentional combat scene loudness and dynamics are NOT penalized as errors."""
        combat_facts = MasteringAnalysisFacts(
            filepath="c_combat.wav",
            duration_sec=3.0,
            integrated_lufs=-17.2,  # +1.8 LU louder than profile
            crest_factor_db=11.2,   # +3.2 dB dynamic peaks
            spectral_centroid_hz=1750.0,
            phase_correlation=0.90,
            is_valid_audio=True,
        )
        intent = DummySceneIntent(scene_type="combat_action_battle")
        audit = self.auditor.audit_chapter(combat_facts, self.profile, scene_intent=intent, chapter_id="ch03_battle")

        # Must pass because variation is dramatically intentional!
        self.assertEqual(audit.overall_status, "PASS")
        self.assertTrue(audit.is_intentional_variation)
        self.assertEqual(audit.intentional_intent, "combat_action")
        self.assertTrue(audit.deviations["loudness"].is_intentional)
        self.assertIn("combat", audit.deviations["loudness"].rationale.lower())

    def test_accidental_inconsistency_triggers_review(self):
        """Verify unexpected loudness or tonal drift without scene intent triggers REVIEW."""
        drift_facts = MasteringAnalysisFacts(
            filepath="c_drift.wav",
            duration_sec=3.0,
            integrated_lufs=-16.5,  # +2.5 LU hotter without justification
            crest_factor_db=8.0,
            spectral_centroid_hz=1200.0,
            phase_correlation=0.92,
            is_valid_audio=True,
        )
        audit = self.auditor.audit_chapter(drift_facts, self.profile, scene_intent=None, chapter_id="ch05_drift")

        self.assertEqual(audit.overall_status, "REVIEW")
        self.assertEqual(audit.review_priority, "HIGH")
        self.assertFalse(audit.is_intentional_variation)
        self.assertEqual(audit.deviations["loudness"].status, "FAIL")

    def test_book_consistency_report_generation(self):
        """Verify aggregated BookConsistencyReport builds markdown and tallies accurately."""
        ch1_facts = MasteringAnalysisFacts(filepath="c1.wav", duration_sec=3.0, integrated_lufs=-19.0, is_valid_audio=True)
        ch2_facts = MasteringAnalysisFacts(filepath="c2.wav", duration_sec=3.0, integrated_lufs=-17.2, is_valid_audio=True)
        ch3_facts = MasteringAnalysisFacts(filepath="c3.wav", duration_sec=3.0, integrated_lufs=-16.5, is_valid_audio=True)

        audit1 = self.auditor.audit_chapter(ch1_facts, self.profile, chapter_id="ch01")
        audit2 = self.auditor.audit_chapter(ch2_facts, self.profile, scene_intent=DummySceneIntent("combat"), chapter_id="ch02")
        audit3 = self.auditor.audit_chapter(ch3_facts, self.profile, scene_intent=None, chapter_id="ch03")

        audits = {"ch01": audit1, "ch02": audit2, "ch03": audit3}
        report = self.reporter.build_report("book_witcher_master", audits, self.profile)

        self.assertEqual(report.total_chapters, 3)
        self.assertEqual(report.passed_count, 2)  # ch01 (normal) + ch02 (intentional combat)
        self.assertEqual(report.review_count, 1)  # ch03 (unjustified drift)
        self.assertIn("# BOOK CONSISTENCY AUDIT REPORT", report.summary_markdown)
        self.assertIn("| **ch01** | `PASS` |", report.summary_markdown)
        self.assertIn("| **ch02** | `PASS` |", report.summary_markdown)
        self.assertIn("| **ch03** | `REVIEW` |", report.summary_markdown)


if __name__ == "__main__":
    unittest.main()
