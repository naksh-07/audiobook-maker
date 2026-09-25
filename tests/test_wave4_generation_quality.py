#!/usr/bin/env python3
"""
Audiobook Factory - Wave 4 Generation Quality Test Suite.
Tests:
1. GenerationStrategyResolver cost and risk-aware strategy allocation.
2. Adaptive TakeBank variant selection based on dramatic uncertainty.
3. PerformanceEvaluator 2.0 acoustic and voice identity checks.
4. IntelligentTakeSelector context-aware weighting and voice drift rejection.
"""

import math
import wave
import struct
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
    PerformanceEvaluationResult,
    EvaluationDimensionScore,
)
from audiobook_factory.performance.strategy_resolver import (
    GenerationStrategyResolver,
    GenerationStrategyPlan,
)
from audiobook_factory.performance.take_bank import TakeBank
from audiobook_factory.performance.evaluator import PerformanceEvaluator
from audiobook_factory.performance.take_selector import IntelligentTakeSelector
from audiobook_factory.identity.reference_bank import AcousticSignature


def create_test_wav(path: Path, f0_hz: float = 140.0, dur_sec: float = 1.0, sample_rate: int = 24000, amp: int = 8000):
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(sample_rate * dur_sec)
    samples = [int(amp * math.sin(2.0 * math.pi * f0_hz * i / sample_rate)) for i in range(num_frames)]
    pcm = struct.pack(f"<{num_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return path


class TestWave4GenerationQuality(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        self.takes_dir = self.project_dir / "takes"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_strategy_resolver_allocations(self):
        """Verifies GenerationStrategyResolver optimizes between chunking, batching, and multi-takes."""
        # 1. Narration -> CHUNKED_NARRATION (1 take)
        pd_narr = PerformanceDirection(
            index=1,
            speaker="Narrator",
            narrative_mode="narrator_exposition",
            intensity="medium",
        )
        plan_narr = GenerationStrategyResolver.resolve_strategy(pd_narr, text="The road was quiet.")
        self.assertEqual(plan_narr.strategy, "CHUNKED_NARRATION")
        self.assertEqual(plan_narr.recommended_takes, 1)

        # 2. Normal dialogue with batching eligibility -> MULTI_SPEAKER_BATCH (1 take)
        pd_dialogue = PerformanceDirection(
            index=2,
            speaker="Traveller",
            surface_emotion="neutral",
            intensity="medium",
        )
        plan_batch = GenerationStrategyResolver.resolve_strategy(
            pd_dialogue,
            text="Can you spare a moment?",
            is_multispeaker_eligible=True,
        )
        self.assertEqual(plan_batch.strategy, "MULTI_SPEAKER_BATCH")
        self.assertEqual(plan_batch.recommended_takes, 1)

        # 3. Critical climax line -> CRITICAL_SCENE_TAKE (3 takes)
        pd_climax = PerformanceDirection(
            index=3,
            speaker="Hero",
            surface_emotion="rage",
            intensity="explosive",
            performance_priority="climactic",
        )
        plan_climax = GenerationStrategyResolver.resolve_strategy(
            pd_climax,
            text="[shouting] Never again will you touch this village!",
        )
        self.assertEqual(plan_climax.strategy, "CRITICAL_SCENE_TAKE")
        self.assertGreaterEqual(plan_climax.recommended_takes, 2)
        self.assertIn("standard", plan_climax.target_variants)

    def test_02_adaptive_take_bank_variants(self):
        """Verifies TakeBank generates uncertainty-targeted adaptive variants."""
        tb = TakeBank(self.takes_dir)
        pd_restrained = PerformanceDirection(
            index=4,
            speaker="King",
            surface_emotion="cold_threat",
            restraint=0.85,
            intensity="explosive",
        )

        variants = tb.get_candidate_variants(pd_restrained, text="[shouting] Do not test me.")
        self.assertIn("standard", variants)
        self.assertIn("more_restrained", variants)

        # Test registration of new adaptive variant
        wav_path = create_test_wav(self.takes_dir / "c001_s0004_more_restrained.wav")
        take_var = tb.create_take(
            segment_uid=pd_restrained.segment_uid,
            segment_index=4,
            variant_type="more_restrained",
            audio_file=wav_path,
            direction=pd_restrained,
        )
        self.assertEqual(take_var.variant_type, "more_restrained")
        self.assertEqual(len(tb.get_takes_for_segment(pd_restrained.segment_uid)), 1)

    def test_03_evaluator_voice_identity_check(self):
        """Verifies PerformanceEvaluator detects voice drift and marks take accordingly."""
        evaluator = PerformanceEvaluator()
        sig = AcousticSignature(
            character_id="hero",
            voice_id="fenrir",
            f0_median_hz=120.0,
            spectral_centroid_hz=1400.0,
        )
        pd = PerformanceDirection(
            index=5,
            speaker="Hero",
            surface_emotion="neutral",
        )

        # 1. Take with matching pitch
        good_wav = create_test_wav(self.takes_dir / "hero_good.wav", f0_hz=122.0)
        res_good = evaluator.evaluate_take(
            take_id="t_good",
            audio_file=good_wav,
            text="I understand.",
            direction=pd,
            signature=sig,
        )
        self.assertTrue(res_good.passed)
        self.assertFalse(res_good.voice_drift_detected)
        self.assertIsNotNone(res_good.voice_identity_score)

        # 2. Take with severe voice drift (240Hz vs 120Hz -> 100% shift)
        drift_wav = create_test_wav(self.takes_dir / "hero_drift.wav", f0_hz=240.0)
        res_drift = evaluator.evaluate_take(
            take_id="t_drift",
            audio_file=drift_wav,
            text="I understand.",
            direction=pd,
            signature=sig,
        )
        self.assertFalse(res_drift.passed)
        self.assertTrue(res_drift.voice_drift_detected)
        self.assertEqual(res_drift.recommendation, "regenerate")

    def test_04_take_selector_rejects_drift_and_applies_context_weights(self):
        """Verifies IntelligentTakeSelector penalizes voice drift and selects superior performance."""
        selector = IntelligentTakeSelector()
        pd = PerformanceDirection(
            index=6,
            speaker="Hero",
            intensity="explosive",
            surface_emotion="rage",
            performance_priority="climactic",
        )

        wav_a = create_test_wav(self.takes_dir / "take_a.wav", f0_hz=120.0)
        wav_b = create_test_wav(self.takes_dir / "take_b.wav", f0_hz=250.0)

        # Take A has good performance and no drift
        take_a = TakeVariant(
            take_id="take_a",
            segment_uid=pd.segment_uid,
            segment_index=6,
            variant_type="more_restrained",
            audio_path=str(wav_a),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="take_a",
                overall_score=0.82,
                passed=True,
                voice_identity_score=0.92,
                voice_drift_detected=False,
                dimensions={
                    "naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.88),
                    "emotional_match": EvaluationDimensionScore(dimension="emotional_match", score=0.85),
                    "subtext": EvaluationDimensionScore(dimension="subtext", score=0.90),
                },
            ),
        )

        # Take B has high base score but suffered voice drift
        take_b = TakeVariant(
            take_id="take_b",
            segment_uid=pd.segment_uid,
            segment_index=6,
            variant_type="exposed",
            audio_path=str(wav_b),
            direction=pd,
            evaluation=PerformanceEvaluationResult(
                take_id="take_b",
                overall_score=0.85,
                passed=False,
                voice_identity_score=0.45,
                voice_drift_detected=True,  # Severe drift
                dimensions={
                    "naturalness": EvaluationDimensionScore(dimension="naturalness", score=0.85),
                    "emotional_match": EvaluationDimensionScore(dimension="emotional_match", score=0.88),
                },
            ),
        )

        winner = selector.select_best_take([take_a, take_b], text="Fight me!", direction=pd)
        # Take A must win despite Take B having slightly higher base score
        self.assertEqual(winner.take_id, "take_a")
        self.assertTrue(winner.is_selected)
        self.assertIn("more_restrained", winner.selection_reason)


if __name__ == "__main__":
    unittest.main()
