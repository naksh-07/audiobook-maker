#!/usr/bin/env python3
"""
Test Suite: test_perceptual_critic.py
====================================
Verifies Phase 1 PerceptualCritic across:
1. Clean narration audio evaluation (PASS).
2. Hyper-compression / low crest factor detection (naturalness penalty).
3. Speech masking detection (intelligibility penalty).
4. Out-of-phase audio detection (spatial coherence critical defect).
5. Confidence scoring and evidence ledger completeness.
6. Deterministic repeated evaluation.
"""

import unittest
from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    MasteringIssue,
    DialogueProtectionReport,
    BookMasterProfile,
)
from audiobook_factory.perceptual_critic import PerceptualCritic


class TestPerceptualCritic(unittest.TestCase):
    """Unit tests for PerceptualCritic."""

    def setUp(self):
        self.critic = PerceptualCritic()

    def test_clean_audio_evaluation_passes(self):
        """Verify pristine broadcast audio achieves PASS with high dimension scores."""
        facts = MasteringAnalysisFacts(
            filepath="/dummy/master.wav",
            duration_sec=10.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.1,
            true_peak_dbtp=-1.55,
            dynamic_range_db=8.5,
            crest_factor_db=9.2,
            spectral_centroid_hz=1250.0,
            phase_correlation=0.98,
            mono_compatible=True,
            clipping_detected=False,
            is_valid_audio=True,
        )

        peval = self.critic.evaluate(facts)

        self.assertEqual(peval.overall, "PASS")
        self.assertGreaterEqual(peval.scores["intelligibility"], 0.90)
        self.assertGreaterEqual(peval.scores["naturalness"], 0.90)
        self.assertGreaterEqual(peval.scores["spatial_coherence"], 0.95)
        self.assertGreaterEqual(peval.confidence, 0.70)
        self.assertGreater(len(peval.evidence), 0)

    def test_hyper_compression_triggers_naturalness_warning(self):
        """Verify audio with collapsed crest factor triggers naturalness and fatigue warnings."""
        facts = MasteringAnalysisFacts(
            filepath="/dummy/master.wav",
            duration_sec=8.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-16.8,  # aggressive loudness
            true_peak_dbtp=-0.5,
            dynamic_range_db=2.5,
            crest_factor_db=2.3,  # severe brickwalling (< 2.5 dB)
            spectral_centroid_hz=2950.0,
            phase_correlation=0.95,
            is_valid_audio=True,
        )

        peval = self.critic.evaluate(facts)

        self.assertIn(peval.overall, ("WARN", "REVIEW"))
        self.assertLess(peval.scores["naturalness"], 0.75)
        self.assertLess(peval.scores["fatigue_risk"], 0.70)

        issue_dims = [i.dimension for i in peval.issues]
        self.assertIn("naturalness", issue_dims)

    def test_severe_speech_masking_triggers_intelligibility_review(self):
        """Verify dialogue protection report indicating severe masking degrades intelligibility."""
        facts = MasteringAnalysisFacts(
            filepath="/dummy/master.wav",
            duration_sec=6.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
            dynamic_range_db=7.0,
            crest_factor_db=8.5,
            spectral_centroid_hz=1200.0,
            phase_correlation=0.95,
            is_valid_audio=True,
        )

        dialogue_report = DialogueProtectionReport(
            chapter_id="ch_01",
            dialogue_lufs=-25.0,
            mix_lufs=-19.0,
            dialogue_anchor_ratio_db=-6.0,
            masking_risk="SEVERE",
            clarity_score=0.45,
            dynamic_contrast_preserved=False,
            status="FAIL",
        )

        peval = self.critic.evaluate(facts, dialogue_report=dialogue_report)

        self.assertEqual(peval.overall, "REVIEW")
        self.assertLessEqual(peval.scores["intelligibility"], 0.60)
        self.assertLessEqual(peval.scores["emotional_preservation"], 0.75)

    def test_out_of_phase_audio_triggers_critical_spatial_review(self):
        """Verify negative phase correlation triggers critical spatial defect and review."""
        facts = MasteringAnalysisFacts(
            filepath="/dummy/master.wav",
            duration_sec=5.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
            phase_correlation=-0.45,  # severe out-of-phase cancellation
            is_valid_audio=True,
        )

        peval = self.critic.evaluate(facts)

        self.assertEqual(peval.overall, "REVIEW")
        self.assertLessEqual(peval.scores["spatial_coherence"], 0.25)
        crit_issues = [i for i in peval.issues if i.severity == "CRITICAL"]
        self.assertEqual(len(crit_issues), 1)
        self.assertEqual(crit_issues[0].dimension, "spatial_coherence")

    def test_confidence_scoring_and_determinism(self):
        """Verify confidence increases with context availability and evaluations are deterministic."""
        facts_short = MasteringAnalysisFacts(
            filepath="/dummy/short.wav",
            duration_sec=0.8,
            sample_rate=48000,
            integrated_lufs=-19.0,
            is_valid_audio=True,
        )
        peval_short = self.critic.evaluate(facts_short)
        self.assertLess(peval_short.confidence, 0.50)

        facts_full = MasteringAnalysisFacts(
            filepath="/dummy/full.wav",
            duration_sec=15.0,
            sample_rate=48000,
            integrated_lufs=-19.0,
            is_valid_audio=True,
        )
        book_prof = BookMasterProfile(book_id="b1", target_lufs_median=-19.0)
        peval_full1 = self.critic.evaluate(facts_full, book_profile=book_prof)
        peval_full2 = self.critic.evaluate(facts_full, book_profile=book_prof)

        self.assertGreaterEqual(peval_full1.confidence, 0.75)
        # Determinism check
        self.assertEqual(peval_full1.scores, peval_full2.scores)
        self.assertEqual(peval_full1.overall, peval_full2.overall)


if __name__ == "__main__":
    unittest.main()
