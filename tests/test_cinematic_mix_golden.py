#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Test Suite: test_cinematic_mix_golden.py
Executes the permanent 20-Scenario Golden Cinematic Mix Regression Benchmark.
"""

import unittest
import tempfile
import wave
from pathlib import Path

from audiobook_factory.cinematic_mix.golden_suite import (
    GoldenSuiteRunner,
    build_golden_scenarios,
    generate_scenario_audio_fixtures,
    GoldenScenarioContract,
)
from audiobook_factory.cinematic_mix.judge import MixJudge


EXPECTED_20_SCENARIO_KEYS = [
    "01_intimate_conversation",
    "02_normal_dialogue",
    "03_whisper",
    "04_emotional_confession",
    "05_shouting",
    "06_multi_speaker_conversation",
    "07_dialogue_plus_music",
    "08_music_led_emotional_scene",
    "09_dialogue_plus_ambience",
    "10_dialogue_plus_heavy_fx",
    "11_sudden_impact",
    "12_combat",
    "13_horror_reveal",
    "14_dramatic_silence",
    "15_suspense_build",
    "16_behind_door_distant_voice",
    "17_spatial_movement",
    "18_crowded_layered_scene",
    "19_transition_between_rooms",
    "20_chapter_scene_transition",
]


class TestGoldenCinematicMixSuite(unittest.TestCase):
    """Verifies the complete 20-scenario Golden Cinematic Mix regression benchmark."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        self.runner = GoldenSuiteRunner()

    def tearDown(self):
        self.td.cleanup()

    def test_golden_scenarios_registry_has_exact_20_scenarios(self):
        """Verifies that all 20 canonical scenarios are registered with full contracts."""
        scenarios = build_golden_scenarios()
        self.assertEqual(len(scenarios), 20)
        for expected_key in EXPECTED_20_SCENARIO_KEYS:
            self.assertIn(expected_key, scenarios)
            contract = scenarios[expected_key]
            self.assertEqual(contract.scenario_id, expected_key)
            self.assertGreater(contract.duration_sec, 0.0)
            self.assertIsNotNone(contract.intent)
            self.assertIsNotNone(contract.attention_map)

    def test_synthetic_audio_fixture_generation(self):
        """Verifies that synthetic fixture generation produces valid 48kHz audio files."""
        scenarios = build_golden_scenarios()
        contract = scenarios["01_intimate_conversation"]
        stems = generate_scenario_audio_fixtures(contract, self.tmp_dir)

        self.assertIn("DX", stems)
        self.assertIn("MX", stems)
        self.assertIn("AMB", stems)

        for s_type, s_path in stems.items():
            self.assertTrue(s_path.exists())
            self.assertGreater(s_path.stat().st_size, 1000)
            with wave.open(str(s_path), "rb") as wf:
                self.assertEqual(wf.getframerate(), 48000)
                self.assertEqual(wf.getnchannels(), 2)
                self.assertGreater(wf.getnframes(), 0)

    def test_run_scenario_01_intimate_conversation(self):
        contract, res = self.runner.run_scenario("01_intimate_conversation", self.tmp_dir)
        self.assertIn(res.status, ("PASS", "PASS_WITH_WARNINGS"))
        self.assertGreaterEqual(res.overall_score, contract.min_score)

    def test_run_scenario_03_whisper(self):
        contract, res = self.runner.run_scenario("03_whisper", self.tmp_dir)
        self.assertIn(res.status, ("PASS", "PASS_WITH_WARNINGS"))
        self.assertGreaterEqual(res.overall_score, contract.min_score)

    def test_run_scenario_08_music_led_emotional_scene(self):
        contract, res = self.runner.run_scenario("08_music_led_emotional_scene", self.tmp_dir)
        self.assertIn(res.status, ("PASS", "PASS_WITH_WARNINGS"))
        self.assertGreaterEqual(res.overall_score, contract.min_score)
        # Verify dialogue focus category passed even with music loud
        dx_cat = next(c for c in res.category_results if c.name == "dialogue_focus")
        self.assertEqual(dx_cat.status, "PASS")

    def test_run_scenario_11_sudden_impact(self):
        contract, res = self.runner.run_scenario("11_sudden_impact", self.tmp_dir)
        self.assertIn(res.status, ("PASS", "PASS_WITH_WARNINGS"))
        self.assertGreaterEqual(res.overall_score, contract.min_score)
        imp_cat = next(c for c in res.category_results if c.name == "impact_behavior")
        self.assertEqual(imp_cat.status, "PASS")

    def test_run_scenario_14_dramatic_silence(self):
        contract, res = self.runner.run_scenario("14_dramatic_silence", self.tmp_dir)
        self.assertIn(res.status, ("PASS", "PASS_WITH_WARNINGS"))
        self.assertGreaterEqual(res.overall_score, contract.min_score)
        sil_cat = next(c for c in res.category_results if c.name == "silence_behavior")
        self.assertEqual(sil_cat.status, "PASS")

    def test_run_scenario_16_behind_door_distant_voice(self):
        contract, res = self.runner.run_scenario("16_behind_door_distant_voice", self.tmp_dir)
        self.assertIn(res.status, ("PASS", "PASS_WITH_WARNINGS"))
        self.assertGreaterEqual(res.overall_score, contract.min_score)
        sp_cat = next(c for c in res.category_results if c.name == "spatial_coherence")
        self.assertEqual(sp_cat.status, "PASS")

    def test_run_all_20_golden_scenarios_full_benchmark(self):
        """Runs the complete 20-scenario Golden Cinematic Mix Suite benchmark."""
        report = self.runner.run_all(self.tmp_dir)
        self.assertEqual(report["total_scenarios"], 20)
        self.assertEqual(report["failed"], 0, f"Golden scenarios failed: {[k for k, v in report['results'].items() if not v['passed']]}")
        self.assertEqual(report["passed"], 20)


if __name__ == "__main__":
    unittest.main()
