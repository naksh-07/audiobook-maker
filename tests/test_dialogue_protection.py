#!/usr/bin/env python3
"""
Unit and Integration Tests for Stage 12: DialogueProtectionAgent.
==================================================================
Validates:
1. Forensic evaluation of dialogue anchor ratio (DX vs Mix).
2. Speech masking risk detection (NONE, LOW, MODERATE, SEVERE).
3. Preservation of intended dramatic dynamic contrast (whispers, emotional speech, shouting).
4. Prevention of corporate over-leveling (whispers not forced to standard loudness).
"""

import unittest
from audiobook_factory.mastering_contracts import MasteringAnalysisFacts
from audiobook_factory.dialogue_protection import DialogueProtectionAgent


class DummySceneIntent:
    """Mock SceneMixIntent for contextual testing."""
    def __init__(self, scene_type: str):
        self.scene_type = scene_type


class TestDialogueProtectionAgent(unittest.TestCase):
    """Test suite for DialogueProtectionAgent."""

    def setUp(self):
        self.agent = DialogueProtectionAgent()

    def test_healthy_dialogue_balance_passes(self):
        """Verify standard dialogue with healthy vocal anchor ratio passes with zero masking risk."""
        mix_facts = MasteringAnalysisFacts(
            filepath="mix.wav",
            duration_sec=3.0,
            integrated_lufs=-19.0,
            is_valid_audio=True,
        )
        dialogue_facts = MasteringAnalysisFacts(
            filepath="dx.wav",
            duration_sec=3.0,
            integrated_lufs=-18.5,  # anchor ratio = +0.5 dB
            spectral_centroid_hz=1400.0,
            is_valid_audio=True,
        )
        report = self.agent.evaluate(mix_facts, dialogue_facts, chapter_id="ch01")

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.masking_risk, "NONE")
        self.assertTrue(report.dynamic_contrast_preserved)
        self.assertEqual(report.dialogue_anchor_ratio_db, 0.5)

    def test_severe_speech_masking_in_standard_scene_fails(self):
        """Verify buried dialogue in a normal scene triggers SEVERE masking risk and FAIL."""
        mix_facts = MasteringAnalysisFacts(
            filepath="mix.wav",
            duration_sec=3.0,
            integrated_lufs=-18.0,
            is_valid_audio=True,
        )
        dialogue_facts = MasteringAnalysisFacts(
            filepath="dx.wav",
            duration_sec=3.0,
            integrated_lufs=-23.5,  # anchor ratio = -5.5 dB (buried!)
            spectral_centroid_hz=1200.0,
            is_valid_audio=True,
        )
        report = self.agent.evaluate(mix_facts, dialogue_facts, chapter_id="ch02")

        self.assertEqual(report.status, "FAIL")
        self.assertEqual(report.masking_risk, "SEVERE")
        self.assertFalse(report.dynamic_contrast_preserved)
        self.assertIn("dialogue_boost_db", report.recommended_adjustments)
        self.assertIn("background_attenuation_db", report.recommended_adjustments)

    def test_intimate_whisper_preserves_contrast_without_false_failure(self):
        """Verify an intimate whisper scene is NOT penalized for lower vocal loudness."""
        mix_facts = MasteringAnalysisFacts(
            filepath="mix.wav",
            duration_sec=3.0,
            integrated_lufs=-22.0,  # Ducked quiet mix
            is_valid_audio=True,
        )
        dialogue_facts = MasteringAnalysisFacts(
            filepath="dx.wav",
            duration_sec=3.0,
            integrated_lufs=-24.0,  # -2.0 dB anchor ratio
            spectral_centroid_hz=900.0,
            is_valid_audio=True,
        )
        intent = DummySceneIntent(scene_type="intimate_whisper")
        report = self.agent.evaluate(mix_facts, dialogue_facts, scene_intent=intent, chapter_id="ch03")

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.masking_risk, "LOW")
        self.assertTrue(report.dynamic_contrast_preserved)

    def test_combat_scene_preserves_impactful_transients(self):
        """Verify high-energy combat speech is audited with scene context."""
        mix_facts = MasteringAnalysisFacts(
            filepath="mix.wav",
            duration_sec=3.0,
            integrated_lufs=-17.5,
            is_valid_audio=True,
        )
        dialogue_facts = MasteringAnalysisFacts(
            filepath="dx.wav",
            duration_sec=3.0,
            integrated_lufs=-18.5,  # -1.0 dB anchor ratio
            spectral_centroid_hz=2200.0,
            is_valid_audio=True,
        )
        intent = DummySceneIntent(scene_type="combat_action")
        report = self.agent.evaluate(mix_facts, dialogue_facts, scene_intent=intent, chapter_id="ch04")

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.masking_risk, "LOW")

    def test_missing_dialogue_stem_graceful_fallback(self):
        """Verify missing or silent dialogue facts fall back safely to PASS."""
        mix_facts = MasteringAnalysisFacts(
            filepath="mix.wav",
            duration_sec=3.0,
            integrated_lufs=-19.0,
            is_valid_audio=True,
        )
        report = self.agent.evaluate(mix_facts, dialogue_facts=None, chapter_id="ch05")

        self.assertEqual(report.status, "PASS")
        self.assertEqual(report.masking_risk, "NONE")


if __name__ == "__main__":
    unittest.main()
