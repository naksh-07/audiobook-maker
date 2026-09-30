#!/usr/bin/env python3
"""
Test Suite: test_scene_aware_mastering.py
=========================================
Verifies Phase 3 SceneAwareDecisionEngine:
1. Classification of INTIMATE, ACTION, and NORMAL scenes.
2. Whisper protection: relaxing target LUFS and slowing limiter release.
3. Combat protection: lowering limiter ceiling and fast release for transient punch.
4. Fallback to NORMAL narration when scene metadata is absent.
5. Strict enforcement of SAFETY_BOUNDS when applying adjustments.
"""

import unittest
from audiobook_factory.mastering_contracts import (
    MasteringAnalysisFacts,
    MasteringProfile,
)
from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.scene_aware_engine import SceneAwareDecisionEngine


class TestSceneAwareMastering(unittest.TestCase):
    """Unit tests for SceneAwareDecisionEngine."""

    def setUp(self):
        self.engine = SceneAwareDecisionEngine()

    def test_intimate_whisper_scene_evaluation_and_adjustment(self):
        """Verify intimate scenes relax target loudness and slow limiter release."""
        facts = MasteringAnalysisFacts(
            filepath="/dummy/whisper.wav",
            duration_sec=6.0,
            integrated_lufs=-22.0,
            spectral_centroid_hz=450.0,
            is_valid_audio=True,
        )
        intent = SceneMixIntent(focus="dialogue", dynamic_range_intent="compressed_intimate")

        decision = self.engine.evaluate_scene(facts=facts, scene_intent=intent)

        self.assertEqual(decision.scene_type, "INTIMATE")
        self.assertFalse(decision.requires_review)
        self.assertIn("target_lufs_offset", decision.bounded_adjustments)

        # Apply to base profile
        base = MasteringProfile(target_lufs=-19.0, limiter_release_ms=50)
        adjusted = self.engine.apply_scene_adjustments(base, decision)

        # Target becomes softer (-20.2 LUFS) and release slows (80ms)
        self.assertEqual(adjusted.target_lufs, -20.2)
        self.assertEqual(adjusted.limiter_release_ms, 80)

    def test_action_combat_scene_evaluation_and_adjustment(self):
        """Verify combat scenes lower limiter ceiling to preserve transients without clipping."""
        facts = MasteringAnalysisFacts(
            filepath="/dummy/combat.wav",
            duration_sec=5.0,
            integrated_lufs=-18.0,
            crest_factor_db=12.5,
            loudness_range_lra=9.0,
            is_valid_audio=True,
        )
        intent = SceneMixIntent(focus="fx", dynamic_range_intent="cinematic_wide", emotional_intensity=0.9)

        decision = self.engine.evaluate_scene(facts=facts, scene_intent=intent)

        self.assertEqual(decision.scene_type, "ACTION")
        self.assertIn("limiter_ceiling_offset_db", decision.bounded_adjustments)

        base = MasteringProfile(limiter_ceiling_db=-1.6, limiter_release_ms=50)
        adjusted = self.engine.apply_scene_adjustments(base, decision)

        # Ceiling lowers to -1.9 dBTP and release quickens to 35ms
        self.assertEqual(adjusted.limiter_ceiling_db, -1.9)
        self.assertEqual(adjusted.limiter_release_ms, 35)

    def test_missing_metadata_falls_back_to_normal(self):
        """Verify missing scene metadata falls back safely to NORMAL profile with zero changes."""
        facts = MasteringAnalysisFacts(
            filepath="/dummy/speech.wav",
            duration_sec=10.0,
            integrated_lufs=-19.0,
            is_valid_audio=True,
        )

        decision = self.engine.evaluate_scene(facts=facts, scene_intent=None)

        self.assertEqual(decision.scene_type, "NORMAL")
        self.assertIsNone(decision.recommended_action)

        base = MasteringProfile()
        adjusted = self.engine.apply_scene_adjustments(base, decision)
        self.assertEqual(adjusted.target_lufs, base.target_lufs)
        self.assertEqual(adjusted.limiter_ceiling_db, base.limiter_ceiling_db)

    def test_safety_envelope_clamping(self):
        """Verify extreme offsets are clamped strictly within safety bounds."""
        base = MasteringProfile(target_lufs=-23.5)  # near edge of allowable range
        # Artificially large offset
        decision = self.engine.evaluate_scene(
            facts=MasteringAnalysisFacts(filepath="/d/w.wav", duration_sec=5.0, integrated_lufs=-25.0, is_valid_audio=True),
            scene_intent=SceneMixIntent(focus="dialogue", dynamic_range_intent="compressed_intimate"),
        )
        decision.bounded_adjustments["target_lufs_offset"] = 5.0  # extreme offset

        adjusted = self.engine.apply_scene_adjustments(base, decision)

        # Clamped: offset cannot exceed +1.5, and target cannot go below -24.0
        self.assertGreaterEqual(adjusted.target_lufs, -24.0)
        self.assertLessEqual(adjusted.target_lufs, -16.0)


if __name__ == "__main__":
    unittest.main()
