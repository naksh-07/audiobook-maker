#!/usr/bin/env python3
"""
Audiobook Factory - Wave 2 Voice Identity & Drift Defense Test Suite.
Tests:
1. VoiceDNA 4-layer schema (Identity, Behavior, Emotional, Forbidden) and synthesis.
2. VoiceDNABank persistence and case-insensitive resolution.
3. ReferenceVoiceBank reference take registration and acoustic signature extraction.
4. VoiceIdentityAnalyzer acoustic comparison, pitch drift detection, and emotional tolerance calibration.
5. PerformanceEvaluationResult integration with voice identity score.
"""

import json
import wave
import struct
import math
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.identity import (
    VoiceDNA,
    VoiceDNAIdentityLayer,
    VoiceDNABehaviorLayer,
    VoiceDNAEmotionalLayer,
    VoiceDNAForbiddenLayer,
    VoiceDNABank,
    AcousticSignature,
    ReferenceVoiceBank,
    VoiceIdentityAnalyzer,
)
from audiobook_factory.casting import CharacterCastingProfile
from audiobook_factory.performance.contracts import PerformanceEvaluationResult, EvaluationDimensionScore


def generate_synthetic_take(path: Path, f0_hz: float = 140.0, dur_sec: float = 1.5, sample_rate: int = 24000, amp: int = 8000):
    """Generates synthetic harmonic audio file with specified F0 pitch."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(sample_rate * dur_sec)
    samples = []
    for i in range(num_frames):
        t = i / sample_rate
        # Harmonics
        val = amp * (0.6 * math.sin(2.0 * math.pi * f0_hz * t) +
                     0.3 * math.sin(4.0 * math.pi * f0_hz * t) +
                     0.1 * math.sin(6.0 * math.pi * f0_hz * t))
        samples.append(int(val))
    pcm = struct.pack(f"<{num_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return path


class TestWave2VoiceIdentity(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_voice_dna_structure_and_synthesis(self):
        """Verifies VoiceDNA 4-layer structure and synthesis from casting metadata."""
        profile = CharacterCastingProfile(
            character_id="heroic_ranger",
            canonical_name="Ranger",
            gender="male",
            perceived_age="mature_adult",
            sociolect_archetype="COLD_CYNIC",
            vocal_weight="heavy",
            restraint=0.75,
            pace=0.92,
            articulation="crisp",
            forbidden_styles=["cartoon panic", "high-pitched whine"],
        )

        catalog_meta = {
            "display_name": "Algenib",
            "sex": "male",
            "perceived_age": "mature_adult",
            "pitch_category": "low",
            "invariant_timbre": "Gravelly, raspy chest resonance, heavy vocal weight",
            "elasticity": {
                "styles_supported": ["cold suppressed menace", "gravelly battle roar"],
                "forbidden_styles": ["high-pitched bubbly youth"],
            },
        }

        dna = VoiceDNA.synthesize_from_casting(
            character_id="heroic_ranger",
            character_name="Ranger",
            voice_id="algenib",
            catalog_voice_meta=catalog_meta,
            casting_profile=profile,
        )

        # 1. Identity Layer
        self.assertEqual(dna.identity.base_pitch_category, "low")
        self.assertEqual(dna.identity.vocal_weight, "heavy")
        self.assertEqual(dna.identity.resonance, "chest")
        self.assertIn("Gravelly", dna.identity.base_timbre)

        # 2. Behavior Layer
        self.assertEqual(dna.behavior.baseline_pace, 0.92)
        self.assertEqual(dna.behavior.restraint, 0.75)
        self.assertEqual(dna.behavior.articulation, "crisp")

        # 3. Emotional Layer
        self.assertTrue(len(dna.emotional.anger) > 0)
        self.assertTrue(len(dna.emotional.fear) > 0)

        # 4. Forbidden Layer
        self.assertIn("cartoon panic", dna.forbidden.forbidden_behaviors)
        self.assertIn("high-pitched bubbly youth", dna.forbidden.forbidden_behaviors)

    def test_02_voice_dna_bank_persistence(self):
        """Verifies VoiceDNABank stores, loads, and resolves VoiceDNA."""
        bank = VoiceDNABank(self.project_dir)
        dna = VoiceDNA(
            character_id="wise_elder",
            character_name="Wise Elder",
            voice_id="achernar",
            identity=VoiceDNAIdentityLayer(base_timbre="weathered gravel", base_pitch_category="low"),
            behavior=VoiceDNABehaviorLayer(baseline_pace=0.88, restraint=0.80),
        )
        bank.register_dna(dna)

        # Re-load bank from disk
        reloaded = VoiceDNABank(self.project_dir)
        resolved = reloaded.get_dna("wise_elder")
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.character_name, "Wise Elder")
        self.assertEqual(resolved.voice_id, "achernar")

        # Case-insensitive / normalized lookup
        resolved_by_name = reloaded.get_dna("Wise Elder")
        self.assertIsNotNone(resolved_by_name)
        self.assertEqual(resolved_by_name.character_id, "wise_elder")

    def test_03_reference_voice_bank_signature_extraction(self):
        """Verifies ReferenceVoiceBank registers takes and computes accurate acoustic signature."""
        ref_bank = ReferenceVoiceBank(self.project_dir)

        # Generate 2 synthetic reference recordings (140Hz nominal F0)
        char_dir = self.project_dir / "temp_refs"
        ref_neutral = generate_synthetic_take(char_dir / "neutral.wav", f0_hz=140.0)
        ref_conv = generate_synthetic_take(char_dir / "conv.wav", f0_hz=142.0)

        ref_bank.register_reference_take("sentinel", "charon", "neutral", ref_neutral)
        ref_bank.register_reference_take("sentinel", "charon", "conversational", ref_conv)

        sig = ref_bank.get_signature("sentinel")
        self.assertIsNotNone(sig)
        self.assertEqual(sig.character_id, "sentinel")
        self.assertEqual(sig.num_reference_takes, 2)
        # Estimated F0 should be very close to 140Hz
        self.assertAlmostEqual(sig.f0_median_hz, 140.0, delta=8.0)
        self.assertGreater(sig.spectral_centroid_hz, 200.0)

    def test_04_voice_identity_analyzer_pass_and_drift_detection(self):
        """Verifies VoiceIdentityAnalyzer passes consistent takes and detects acoustic drift."""
        test_dir = self.project_dir / "test_takes"
        ref_bank = ReferenceVoiceBank(self.project_dir)
        ref_wav = generate_synthetic_take(test_dir / "ref_neutral.wav", f0_hz=135.0)
        ref_bank.register_reference_take("detective", "algenib", "neutral", ref_wav)
        sig = ref_bank.get_signature("detective")
        self.assertIsNotNone(sig)

        analyzer = VoiceIdentityAnalyzer()

        # 1. Consistent take (F0=138Hz -> ~2% shift)
        good_wav = generate_synthetic_take(test_dir / "take_good.wav", f0_hz=138.0)
        good_res = analyzer.analyze_take_identity("take_001", good_wav, signature=sig)
        self.assertFalse(good_res.drift_detected)
        self.assertGreaterEqual(good_res.similarity_score, 0.80)
        self.assertEqual(good_res.recommendation, "pass")

        # 2. Severe Drift take (F0=230Hz -> ~70% shift, e.g. wrong speaker voice generated)
        drift_wav = generate_synthetic_take(test_dir / "take_drift.wav", f0_hz=230.0)
        drift_res = analyzer.analyze_take_identity("take_002", drift_wav, signature=sig)
        self.assertTrue(drift_res.drift_detected)
        self.assertLess(drift_res.similarity_score, 0.65)
        self.assertIn(drift_res.recommendation, ["regenerate", "downgrade"])
        self.assertTrue(any("Excessive pitch divergence" in d for d in drift_res.diagnostics))

        # 3. Dynamic Tolerance: Anger scene accommodates legitimate higher pitch
        anger_wav = generate_synthetic_take(test_dir / "take_anger.wav", f0_hz=185.0)
        anger_res = analyzer.analyze_take_identity(
            "take_003",
            anger_wav,
            signature=sig,
            dramatic_emotion="anger",
            intensity="explosive",
        )
        # 185Hz is ~37% above 135Hz, which is allowed under explosive anger tolerance (up to 50%)
        self.assertFalse(anger_res.drift_detected)
        self.assertEqual(anger_res.recommendation, "pass")

    def test_05_performance_evaluation_result_contract_field(self):
        """Verifies PerformanceEvaluationResult accommodates voice identity fields."""
        ev = PerformanceEvaluationResult(
            take_id="take_test_01",
            overall_score=0.88,
            passed=True,
            voice_identity_score=0.92,
            voice_drift_detected=False,
        )
        self.assertEqual(ev.voice_identity_score, 0.92)
        self.assertFalse(ev.voice_drift_detected)


if __name__ == "__main__":
    unittest.main()
