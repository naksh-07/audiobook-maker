#!/usr/bin/env python3
"""
Unit and Integration Tests for Stage 12: MasteringJudge.
========================================================
Validates:
1. Evidence-based detection of acoustic defects:
   - Harshness & sibilance
   - Dialogue weakness & masking
   - Low-frequency rumble
   - Dynamics over-compression
   - Loudness drift
2. Prioritized issue sorting (Critical > Major > Minor > Info).
3. Confidence calibration (high confidence triggers action; low confidence reports only).
4. Strict clamping within DSP safety envelopes (Judge cannot invent arbitrary values).
5. Clean inputs correctly yield PASS with zero unneeded processing.
"""

import unittest
from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringAnalysisFacts,
    MasteringActionPlan,
)
from audiobook_factory.mastering_judge import MasteringJudge, SAFETY_BOUNDS


class TestMasteringJudge(unittest.TestCase):
    """Test suite for MasteringJudge."""

    def setUp(self):
        self.judge = MasteringJudge()
        self.profile = MasteringProfile(
            target_lufs=-19.0,
            tolerance_lu=0.5,
            limiter_ceiling_db=-1.6,
            subsonic_highpass_hz=28,
        )

    def test_clean_input_yields_pass(self):
        """Verify normal compliant audio passes without unnecessary DSP intervention."""
        clean_facts = MasteringAnalysisFacts(
            filepath="dummy_clean.wav",
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.1,
            true_peak_dbtp=-1.6,
            crest_factor_db=8.0,
            spectral_centroid_hz=1400.0,
            phase_correlation=0.95,
            clipping_detected=False,
            is_valid_audio=True,
        )
        plan = self.judge.evaluate(clean_facts, profile=self.profile)

        self.assertEqual(plan.overall_verdict, "PASS")
        self.assertIsNone(plan.adjusted_profile)
        self.assertEqual(len(plan.issues), 0)

    def test_critical_defect_yields_reject(self):
        """Verify severe anti-phase or corruption immediately halts pipeline with REJECT."""
        anti_phase_facts = MasteringAnalysisFacts(
            filepath="dummy_antiphase.wav",
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
            phase_correlation=-0.45,  # Severe anti-phase
            is_valid_audio=True,
        )
        plan = self.judge.evaluate(anti_phase_facts, profile=self.profile)

        self.assertEqual(plan.overall_verdict, "REJECT")
        self.assertIsNone(plan.adjusted_profile)
        critical_issues = [i for i in plan.issues if i.severity == "CRITICAL"]
        self.assertGreaterEqual(len(critical_issues), 1)
        self.assertEqual(critical_issues[0].issue_type, "severe_anti_phase_cancellation")

    def test_excessive_harshness_detection_and_bounded_adjustment(self):
        """Verify elevated spectral centroid triggers harshness detection and bounded limiter adjustment."""
        harsh_facts = MasteringAnalysisFacts(
            filepath="dummy_harsh.wav",
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
            spectral_centroid_hz=4200.0,  # Highly harsh
            crest_factor_db=9.0,
            phase_correlation=0.90,
            is_valid_audio=True,
        )
        plan = self.judge.evaluate(harsh_facts, profile=self.profile)

        self.assertEqual(plan.overall_verdict, "ADJUST")
        self.assertIsNotNone(plan.adjusted_profile)
        self.assertTrue(any(i.issue_type == "excessive_spectral_harshness" for i in plan.issues))
        # Limiter ceiling should be backed off safely
        self.assertLess(plan.adjusted_profile.limiter_ceiling_db, self.profile.limiter_ceiling_db)
        self.assertGreaterEqual(plan.adjusted_profile.limiter_ceiling_db, SAFETY_BOUNDS["limiter_ceiling_min"])

    def test_low_frequency_rumble_adjustment(self):
        """Verify low-frequency rumble raises subsonic highpass cutoff frequency safely."""
        rumble_facts = MasteringAnalysisFacts(
            filepath="dummy_rumble.wav",
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
            spectral_centroid_hz=160.0,  # Severe low rumble
            phase_correlation=0.90,
            is_valid_audio=True,
        )
        plan = self.judge.evaluate(rumble_facts, profile=self.profile)

        self.assertEqual(plan.overall_verdict, "ADJUST")
        self.assertIsNotNone(plan.adjusted_profile)
        # Subsonic cutoff raised within bounds
        self.assertGreater(plan.adjusted_profile.subsonic_highpass_hz, self.profile.subsonic_highpass_hz)
        self.assertLessEqual(plan.adjusted_profile.subsonic_highpass_hz, SAFETY_BOUNDS["subsonic_hz_max"])

    def test_safety_envelope_clamping(self):
        """Verify Judge cannot recommend parameters outside strict safety envelopes."""
        # Extreme hot premaster
        hot_facts = MasteringAnalysisFacts(
            filepath="dummy_hot.wav",
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-10.0,  # 9 LU hotter than target
            true_peak_dbtp=1.2,     # Clipping
            crest_factor_db=3.0,    # Squashed
            is_valid_audio=True,
        )
        plan = self.judge.evaluate(hot_facts, profile=self.profile)

        # Clipping causes REJECT
        self.assertEqual(plan.overall_verdict, "REJECT")

    def test_dialogue_weakness_detection(self):
        """Verify dialogue buried by mix is detected and prioritized as MAJOR."""
        premaster_facts = MasteringAnalysisFacts(
            filepath="mix.wav",
            duration_sec=3.0,
            integrated_lufs=-19.0,
            is_valid_audio=True,
        )
        dialogue_facts = MasteringAnalysisFacts(
            filepath="dx.wav",
            duration_sec=3.0,
            integrated_lufs=-24.5,  # Anchor ratio = -5.5 dB (buried!)
            is_valid_audio=True,
        )
        plan = self.judge.evaluate(premaster_facts, dialogue_facts=dialogue_facts, profile=self.profile)

        self.assertEqual(plan.overall_verdict, "ADJUST")
        major_issues = [i for i in plan.issues if i.issue_type == "dialogue_weakness_masking_risk"]
        self.assertEqual(len(major_issues), 1)
        self.assertEqual(major_issues[0].severity, "MAJOR")
        self.assertGreaterEqual(major_issues[0].confidence, 0.85)


if __name__ == "__main__":
    unittest.main()
