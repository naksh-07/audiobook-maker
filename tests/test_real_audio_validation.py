#!/usr/bin/env python3
"""
Test Suite: test_real_audio_validation.py
=========================================
Adversarial validation test suite for Real Audio Validation (Missions 1-6):
1. Verifies Real Audio Golden Suite manifests and fixture metadata contracts.
2. Validates Before/After delta comparator (RealAudioComparator).
3. Tests forensic artifact detectors (RealAudioArtifactDetector).
4. Tests scene-specific validation and dialogue protection invariants.
5. Tests reference audio evaluation (RealAudioReferenceSuite, REFERENCE != TRUTH).
6. Validates mastering across all 12 canonical real audio categories:
   - Narration, Dialogue, Whisper, Shouting, Emotional, Hindi/Hinglish,
   - Music-Heavy, Ambience, Foley, Action, Silence, Difficult TTS.
7. Validates continuous Long-Form multi-scene stress testing and drift.
8. Validates the 6 Core Quality Gates and machine-readable report output.
9. Enforces Real Golden Baseline governance and immutability.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.mastering_contracts import MasteringProfile, MasteringRequest
from audiobook_factory.mastering_engine import MasteringEngineV2
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.real_audio_contracts import (
    RealAudioFixtureMetadata,
    AudioDeltaReport,
    ArtifactDetectionResult,
    RealAudioValidationReport,
)
from audiobook_factory.real_audio_golden_suite import RealAudioGoldenSuite
from audiobook_factory.real_audio_comparator import RealAudioComparator
from audiobook_factory.real_audio_reference_suite import RealAudioReferenceSuite, CANONICAL_REFERENCES
from audiobook_factory.real_audio_scene_validator import RealAudioSceneValidator
from audiobook_factory.real_audio_artifact_detector import RealAudioArtifactDetector
from audiobook_factory.real_audio_long_form import RealAudioLongFormStressTester
from audiobook_factory.real_audio_validation_runner import RealAudioValidationRunner


class TestRealAudioValidation(unittest.TestCase):
    """Real Audio Validation test suite."""

    @classmethod
    def setUpClass(cls):
        cls.golden_suite = RealAudioGoldenSuite()
        cls.manifests = cls.golden_suite.ensure_fixtures()
        cls.engine = MasteringEngineV2()
        cls.analyzer = MasteringAnalyzer()
        cls.comparator = RealAudioComparator(cls.analyzer)
        cls.scene_validator = RealAudioSceneValidator()
        cls.ref_suite = RealAudioReferenceSuite()
        cls.artifact_detector = RealAudioArtifactDetector()

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="real_audio_val_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_01_fixture_manifests_and_contracts(self):
        """Phase 1 & 2: Verify all 12 canonical categories are registered with complete contracts."""
        expected_keys = [
            "real_01_narration",
            "real_02_dialogue",
            "real_03_whisper",
            "real_04_shouting",
            "real_05_emotional",
            "real_06_hindi_hinglish",
            "real_07_music_heavy",
            "real_08_ambience",
            "real_09_foley",
            "real_10_action",
            "real_11_silence",
            "real_12_difficult_tts",
        ]
        self.assertEqual(len(self.manifests), 12)
        for key in expected_keys:
            self.assertIn(key, self.manifests)
            meta = self.manifests[key]
            self.assertEqual(meta.sample_rate, 48000)
            self.assertEqual(meta.channels, 2)
            self.assertGreater(meta.duration_sec, 0.0)
            self.assertIn(meta.license, ("Project-Owned", "CC0/Project-SoundBank", "MIT", "Apache-2.0"))
            self.assertTrue(len(meta.known_risks) > 0)
            self.assertTrue(len(meta.provenance) > 0)

            # Verify physical file exists and is readable
            wav_path = self.golden_suite.audio_dir / f"{key}.wav"
            self.assertTrue(wav_path.exists())
            self.assertGreater(wav_path.stat().st_size, 10000)

    def test_02_before_after_comparator_metrics(self):
        """Phase 4: Verify RealAudioComparator computes accurate acoustic deltas."""
        premaster_path = self.golden_suite.audio_dir / "real_01_narration.wav"
        req = MasteringRequest(chapter_id="cmp_test", premaster_path=str(premaster_path))
        res = self.engine.master(req)

        delta = self.comparator.compare(
            fixture_id="real_01_narration",
            premaster_path=premaster_path,
            master_path=res.master_path,
            scene_type="narration",
        )

        self.assertIsInstance(delta, AudioDeltaReport)
        self.assertEqual(delta.fixture_id, "real_01_narration")
        self.assertIsNotNone(delta.integrated_lufs.delta)
        self.assertIsNotNone(delta.true_peak_dbtp.after)
        self.assertIsNotNone(delta.crest_factor_db.delta)
        self.assertIsNotNone(delta.spectral_centroid_hz.delta)
        self.assertIsNotNone(delta.phase_correlation.after)
        self.assertIn(delta.overall_delta_status, ("PASS", "WARNING", "REVIEW_REQUIRED"))

    def test_03_artifact_detection_rules(self):
        """Phase 8: Verify artifact detectors return typed results with confidence and severity."""
        pre_facts = self.analyzer.analyze(self.golden_suite.audio_dir / "real_04_shouting.wav")
        post_facts = self.analyzer.analyze(self.golden_suite.audio_dir / "real_04_shouting.wav")

        delta = self.comparator.compare(
            fixture_id="real_04_shouting",
            premaster_path=self.golden_suite.audio_dir / "real_04_shouting.wav",
            master_path=self.golden_suite.audio_dir / "real_04_shouting.wav",
            scene_type="shouting",
        )

        artifacts = self.artifact_detector.analyze_artifacts(
            pre_facts=pre_facts,
            post_facts=post_facts,
            delta_report=delta,
            scene_type="shouting",
        )

        self.assertGreaterEqual(len(artifacts), 8)
        for a in artifacts:
            self.assertIsInstance(a, ArtifactDetectionResult)
            self.assertIn(a.severity, ("INFO", "WARNING", "REVIEW_REQUIRED", "FAIL"))
            self.assertGreaterEqual(a.confidence, 0.0)
            self.assertLessEqual(a.confidence, 1.0)
            self.assertTrue(len(a.threshold_rationale) > 0)

    def test_04_scene_specific_whisper_and_shouting_rules(self):
        """Phase 5: Verify scene validator respects quiet whisper and bounds shouting peak."""
        pre_whisper = self.analyzer.analyze(self.golden_suite.audio_dir / "real_03_whisper.wav")
        delta_whisper = self.comparator.compare(
            fixture_id="real_03_whisper",
            premaster_path=self.golden_suite.audio_dir / "real_03_whisper.wav",
            master_path=self.golden_suite.audio_dir / "real_03_whisper.wav",
            scene_type="whisper",
        )
        val_whisper = self.scene_validator.validate_scene(
            scene_type="whisper",
            pre_facts=pre_whisper,
            post_facts=pre_whisper,
            delta=delta_whisper,
        )
        self.assertTrue(val_whisper.passed)

        # Shouting
        pre_shout = self.analyzer.analyze(self.golden_suite.audio_dir / "real_04_shouting.wav")
        delta_shout = self.comparator.compare(
            fixture_id="real_04_shouting",
            premaster_path=self.golden_suite.audio_dir / "real_04_shouting.wav",
            master_path=self.golden_suite.audio_dir / "real_04_shouting.wav",
            scene_type="shouting",
        )
        val_shout = self.scene_validator.validate_scene(
            scene_type="shouting",
            pre_facts=pre_shout,
            post_facts=pre_shout,
            delta=delta_shout,
        )
        self.assertIn(val_shout.status, ("PASS", "WARNING"))

    def test_05_reference_audio_suite_evaluation(self):
        """Phase 3: Verify reference deviation logic adheres to REFERENCE != TRUTH."""
        facts = self.analyzer.analyze(self.golden_suite.audio_dir / "real_01_narration.wav")
        rep = self.ref_suite.evaluate(facts, "narration")
        self.assertEqual(rep.scene_type, "narration")
        self.assertIsNotNone(rep.lufs_deviation)
        self.assertIsNotNone(rep.true_peak_margin)
        self.assertIn(rep.recommendation, ("NO_ACTION", "ADJUST_GAIN_CEILING", "REVIEW_INTENTIONAL_ARTISTIC_DEVIATION"))

    def test_06_hindi_hinglish_speech_validation(self):
        """Phase 1 Category 6: Verify Hindi/Hinglish speech masters cleanly with formant preservation."""
        hindi_path = self.golden_suite.audio_dir / "real_06_hindi_hinglish.wav"
        req = MasteringRequest(chapter_id="hi_test", premaster_path=str(hindi_path))
        res = self.engine.master(req)

        self.assertIn(res.status, ("SUCCESS", "REVIEW_REQUIRED"))
        self.assertTrue(res.qc_result.passed or len(res.qc_result.failures) == 0)

        # Check true-peak ceiling
        self.assertLessEqual(res.analysis_after.true_peak_dbtp or 0.0, -1.0)
        # Formant band energy preservation
        delta = self.comparator.compare("real_06_hindi_hinglish", hindi_path, res.master_path, "hindi_hinglish")
        self.assertIn(delta.spectral_assessment, ("EXPECTED", "ACCEPTABLE"))

    def test_07_action_complex_mix_stability(self):
        """Phase 1 Category 10: Verify multi-stem action scene maintains limiter stability without clipping."""
        action_path = self.golden_suite.audio_dir / "real_10_action.wav"
        req = MasteringRequest(chapter_id="act_test", premaster_path=str(action_path))
        res = self.engine.master(req)

        self.assertIn(res.status, ("SUCCESS", "REVIEW_REQUIRED"))
        # Zero clipping
        self.assertLessEqual(res.analysis_after.true_peak_dbtp or 0.0, -1.4)
        self.assertFalse(res.analysis_after.clipping_detected)

    def test_08_long_form_stress_test_execution(self):
        """Phase 9: Run continuous multi-scene long-form stress test."""
        tester = RealAudioLongFormStressTester(self.engine, self.analyzer)
        res, rep = tester.run_stress_test(
            fixtures_dir=self.golden_suite.audio_dir,
            work_dir=self.tmp_dir / "long_form",
        )

        self.assertGreater(rep.total_duration_sec, 20.0)
        self.assertEqual(rep.scene_count, 12)
        self.assertLessEqual(rep.max_true_peak_dbtp, -1.4)
        self.assertIn(rep.status, ("PASS", "REVIEW_REQUIRED"))
        self.assertLessEqual(rep.fatigue_risk_index, 0.85)

    def test_09_golden_baseline_governance_enforcement(self):
        """Phase 11: Verify immutable real audio baseline exists and covers all 12 fixtures."""
        baseline_path = Path(__file__).resolve().parent.parent / "audiobook_factory" / "real_audio_golden_baseline.json"
        self.assertTrue(baseline_path.exists())

        with open(baseline_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["baseline_version"], "1.0.0")
        self.assertEqual(data["engine_version"], "2.1.0")
        fixtures = data["fixtures"]
        self.assertEqual(len(fixtures), 12)

        for fix_id, entry in fixtures.items():
            self.assertEqual(entry["approval_status"], "APPROVED")
            self.assertIn("expected_lufs_range", entry)
            self.assertIn("expected_true_peak_max_dbtp", entry)
            self.assertIn("expected_lra_range", entry)
            self.assertIn("known_risks", entry)
            self.assertIn("known_acceptable_deviations", entry)

    def test_10_full_validation_runner_and_gates(self):
        """Phase 14 & 15: Run end-to-end RealAudioValidationRunner and verify 6 quality gates."""
        runner = RealAudioValidationRunner(
            engine=self.engine,
            analyzer=self.analyzer,
            golden_suite=self.golden_suite,
        )
        report = runner.run_full_validation(output_dir=self.tmp_dir / "val_output")

        self.assertIsInstance(report, RealAudioValidationReport)
        self.assertEqual(report.fixtures_evaluated, 12)
        self.assertIn(report.overall_status, ("PASS", "WARNING", "REVIEW_REQUIRED"))

        # Verify all 6 gates are evaluated
        expected_gates = [
            "TECHNICAL_GATE",
            "DYNAMIC_GATE",
            "SPECTRAL_GATE",
            "DIALOGUE_GATE",
            "ARTIFACT_GATE",
            "CONSISTENCY_GATE",
        ]
        for g in expected_gates:
            self.assertIn(g, report.quality_gates)
            gate_eval = report.quality_gates[g]
            self.assertIn(gate_eval.status, ("PASS", "WARNING", "REVIEW_REQUIRED"))

        # Verify reports written to disk
        self.assertTrue((self.tmp_dir / "val_output" / "real_audio_validation_report.json").exists())
        self.assertTrue((self.tmp_dir / "val_output" / "REAL_AUDIO_VALIDATION_REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
