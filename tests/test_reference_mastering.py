#!/usr/bin/env python3
"""
Test Suite: test_reference_mastering.py
=======================================
Verifies Phase 2 ReferenceMasteringAuditor:
1. Canonical reference profile availability.
2. Accurate profile extraction from audio facts.
3. Matching comparison outcome (MATCH).
4. Mild and significant deviation outcomes.
5. Inappropriate comparison rejection (e.g. whisper vs action).
6. Graceful degradation when reference is None.
"""

import unittest
from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    ReferenceProfile,
)
from audiobook_factory.reference_mastering import (
    ReferenceMasteringAuditor,
    CANONICAL_REFERENCE_PROFILES,
)


class TestReferenceMastering(unittest.TestCase):
    """Unit tests for ReferenceMasteringAuditor."""

    def setUp(self):
        self.auditor = ReferenceMasteringAuditor()

    def test_canonical_reference_profiles_registered(self):
        """Verify standard studio reference profiles are pre-registered."""
        self.assertIn("narration", CANONICAL_REFERENCE_PROFILES)
        self.assertIn("dialogue", CANONICAL_REFERENCE_PROFILES)
        self.assertIn("intimate", CANONICAL_REFERENCE_PROFILES)
        self.assertIn("action", CANONICAL_REFERENCE_PROFILES)
        self.assertIn("quiet", CANONICAL_REFERENCE_PROFILES)

        narration = CANONICAL_REFERENCE_PROFILES["narration"]
        self.assertEqual(narration.target_lufs, -19.0)
        self.assertEqual(narration.version, "1.0.0")

    def test_profile_extraction_from_facts(self):
        """Verify extracting a ReferenceProfile from ground-truth audio facts."""
        facts = MasteringAnalysisFacts(
            filepath="/studio/ref_hero.wav",
            duration_sec=30.0,
            integrated_lufs=-19.2,
            dynamic_range_db=8.0,
            crest_factor_db=9.5,
            spectral_centroid_hz=1180.0,
            phase_correlation=0.99,
            is_valid_audio=True,
        )

        ref = self.auditor.extract_reference_profile(
            facts=facts,
            reference_type="narration",
            reference_id="custom_hero_ref",
            metadata={"source": "Approved Studio Master"},
        )

        self.assertEqual(ref.reference_id, "custom_hero_ref")
        self.assertEqual(ref.target_lufs, -19.2)
        self.assertEqual(ref.crest_factor_db, 9.5)
        self.assertEqual(ref.version, "1.0.0")

    def test_matching_audio_comparison(self):
        """Verify audio within tolerances returns MATCH."""
        ref = CANONICAL_REFERENCE_PROFILES["narration"]
        facts = MasteringAnalysisFacts(
            filepath="/dummy/master.wav",
            duration_sec=10.0,
            integrated_lufs=-19.2,  # delta = -0.2 LU (tolerance is 1.0)
            crest_factor_db=9.8,   # delta = +0.3 dB (tolerance is 2.5)
            spectral_centroid_hz=1160.0,
            phase_correlation=1.0,
            is_valid_audio=True,
        )

        res = self.auditor.compare_to_reference(facts, ref, scene_type="NORMAL")

        self.assertIsNotNone(res)
        self.assertEqual(res.comparison_status, "MATCH")
        self.assertTrue(res.is_appropriate)
        self.assertEqual(res.deviations["lufs_delta"], -0.2)

    def test_inappropriate_comparison_rejection(self):
        """Verify comparing a quiet whisper scene to an action reference is flagged as inappropriate."""
        ref_action = CANONICAL_REFERENCE_PROFILES["action"]
        facts = MasteringAnalysisFacts(
            filepath="/dummy/whisper.wav",
            duration_sec=5.0,
            integrated_lufs=-22.0,
            crest_factor_db=7.0,
            is_valid_audio=True,
        )

        res = self.auditor.compare_to_reference(facts, ref_action, scene_type="INTIMATE")

        self.assertIsNotNone(res)
        self.assertEqual(res.comparison_status, "INAPPROPRIATE_COMPARISON")
        self.assertFalse(res.is_appropriate)
        self.assertIn("Inappropriate comparison", res.notes[0])

    def test_graceful_fallback_when_reference_omitted(self):
        """Verify compare_to_reference returns None safely when reference is None."""
        facts = MasteringAnalysisFacts(
            filepath="/dummy/master.wav",
            duration_sec=5.0,
            integrated_lufs=-19.0,
            is_valid_audio=True,
        )

        res = self.auditor.compare_to_reference(facts, reference=None)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
