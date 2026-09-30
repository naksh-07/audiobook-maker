#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Test Suite: test_cinematic_mix_judge.py
Tests MixJudge, 12 Category Evaluators, Automatic Diagnosis, and Bounded Remix Loop.
"""

import unittest
import tempfile
import wave
from pathlib import Path
import numpy as np

from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.attention_map import AttentionMap, AttentionEvent
from audiobook_factory.cinematic_mix.automation import MixAutomation, AutomationEvent
from audiobook_factory.cinematic_mix.perspective import AcousticPerspective
from audiobook_factory.cinematic_mix.silence import SilenceEvent
from audiobook_factory.cinematic_mix.impact import ImpactEvent
from audiobook_factory.cinematic_mix.judge import (
    MixJudge,
    MixJudgeResult,
    CategoryResult,
    MixDiagnosis,
    RemixPlan,
    RemixAction,
)
from audiobook_factory.cinematic_mix.remix_loop import RemixController


def _create_synthetic_wav(
    filepath: Path,
    duration_sec: float = 2.0,
    frequency_hz: float = 440.0,
    amplitude: float = 0.50,
    sample_rate: int = 48000,
) -> Path:
    """Generates a simple 16-bit PCM stereo WAV file."""
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0.0, duration_sec, num_samples, endpoint=False, dtype=np.float32)
    waveform = (amplitude * np.sin(2.0 * np.pi * frequency_hz * t)).astype(np.float32)
    waveform_clamped = np.clip(waveform, -1.0, 1.0)
    samples_int16 = (waveform_clamped * 32767.0).astype(np.int16)
    stereo = np.column_stack([samples_int16, samples_int16])

    filepath.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(stereo.tobytes())
    return filepath


class TestMixJudgeTechnicalSafety(unittest.TestCase):
    """Test technical audio safety checks, clipping detection, silence dropouts, and phase correlation."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        self.judge = MixJudge()

    def tearDown(self):
        self.td.cleanup()

    def test_technical_safety_clean_pass(self):
        wav = _create_synthetic_wav(self.tmp_dir / "clean_premaster.wav", amplitude=0.40)
        res = self.judge.evaluate(premaster_path=wav)
        tech_cat = next(c for c in res.category_results if c.name == "technical_safety")
        self.assertEqual(tech_cat.status, "PASS")
        self.assertEqual(tech_cat.score, 1.0)

    def test_technical_safety_missing_file_hard_fail(self):
        missing = self.tmp_dir / "non_existent_file.wav"
        res = self.judge.evaluate(premaster_path=missing)
        self.assertEqual(res.status, "FAIL")
        self.assertIn("premaster_missing_or_corrupt", res.failures[0].lower() + res.category_results[0].reason.lower())

    def test_technical_safety_total_silence_dropout_hard_fail(self):
        silent_wav = _create_synthetic_wav(self.tmp_dir / "silent_premaster.wav", amplitude=0.0)
        res = self.judge.evaluate(premaster_path=silent_wav)
        tech_cat = next(c for c in res.category_results if c.name == "technical_safety")
        self.assertEqual(tech_cat.status, "FAIL")
        self.assertIn("silence", tech_cat.reason.lower())


class TestMixJudgeDialogueAndMusicCategories(unittest.TestCase):
    """Test dialogue focus, vocal corridor masking, and music integration."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        self.judge = MixJudge()

    def tearDown(self):
        self.td.cleanup()

    def test_dialogue_focus_pass_when_clear(self):
        dx_wav = _create_synthetic_wav(self.tmp_dir / "dx.wav", frequency_hz=350.0, amplitude=0.60)
        mx_wav = _create_synthetic_wav(self.tmp_dir / "mx.wav", frequency_hz=220.0, amplitude=0.05)
        premaster = _create_synthetic_wav(self.tmp_dir / "premaster.wav", amplitude=0.50)

        stems = {"DX": dx_wav, "MX": mx_wav}
        res = self.judge.evaluate(
            stems=stems,
            premaster_path=premaster,
            scene_intent=SceneMixIntent(focus="dialogue"),
        )
        dx_cat = next(c for c in res.category_results if c.name == "dialogue_focus")
        self.assertEqual(dx_cat.status, "PASS")
        self.assertGreater(dx_cat.score, 0.85)

    def test_dialogue_focus_remix_when_whisper_buried(self):
        # Soft whisper vs loud music
        dx_wav = _create_synthetic_wav(self.tmp_dir / "dx_whisper.wav", frequency_hz=2800.0, amplitude=0.08)
        mx_wav = _create_synthetic_wav(self.tmp_dir / "mx_loud.wav", frequency_hz=440.0, amplitude=0.50)
        premaster = _create_synthetic_wav(self.tmp_dir / "premaster.wav", amplitude=0.50)

        stems = {"DX": dx_wav, "MX": mx_wav}
        attn = AttentionMap(events=[
            AttentionEvent(start=0.2, end=1.8, focus_target="dialogue", priority=0.95, reason="Intimate whisper")
        ])
        res = self.judge.evaluate(
            stems=stems,
            premaster_path=premaster,
            scene_intent=SceneMixIntent(focus="dialogue"),
            attention_map=attn,
        )
        self.assertEqual(res.status, "REMIX")
        dx_diag = next(d for d in res.diagnosis if d.category == "dialogue_focus")
        self.assertEqual(dx_diag.status, "REMIX")
        self.assertIn("insufficient_dialogue_protection", dx_diag.reason)
        self.assertIsNotNone(res.remix_plan)

    def test_music_led_scene_allows_prominent_score(self):
        # Score is loud, dialogue is soft, but focus was 'music'
        dx_wav = _create_synthetic_wav(self.tmp_dir / "dx_soft.wav", amplitude=0.15)
        mx_wav = _create_synthetic_wav(self.tmp_dir / "mx_prominent.wav", amplitude=0.55)
        premaster = _create_synthetic_wav(self.tmp_dir / "premaster.wav", amplitude=0.60)

        stems = {"DX": dx_wav, "MX": mx_wav}
        attn = AttentionMap(events=[
            AttentionEvent(start=0.0, end=2.0, focus_target="music", priority=0.90, reason="Heroic theme climax")
        ])
        res = self.judge.evaluate(
            stems=stems,
            premaster_path=premaster,
            scene_intent=SceneMixIntent(focus="music", music_priority=0.90, dialogue_priority=0.20),
            attention_map=attn,
        )
        dx_cat = next(c for c in res.category_results if c.name == "dialogue_focus")
        # Must NOT fail when music is intentionally leading
        self.assertEqual(dx_cat.status, "PASS")

    def test_music_integration_fader_pumping_detected(self):
        # Generate rapid oscillating gain automation
        events = []
        for i in range(8):
            events.append(
                AutomationEvent(
                    start=round(i * 0.20, 2),
                    end=round(i * 0.20 + 0.10, 2),
                    target="MX",
                    parameter="gain",
                    value=-12.0,
                    start_value=0.0,
                    curve="smooth",
                )
            )
        auto = MixAutomation(events=events, total_duration_sec=2.0)
        mx_wav = _create_synthetic_wav(self.tmp_dir / "mx.wav", amplitude=0.25)
        premaster = _create_synthetic_wav(self.tmp_dir / "premaster.wav", amplitude=0.30)

        res = self.judge.evaluate(
            stems={"MX": mx_wav},
            premaster_path=premaster,
            mix_automation=auto,
        )
        mx_cat = next(c for c in res.category_results if c.name == "music_integration")
        self.assertEqual(mx_cat.status, "REMIX")
        self.assertIn("pumping", mx_cat.reason.lower())


class TestMixJudgeBehaviorAndRemixPlan(unittest.TestCase):
    """Test silence behavior, ambience naturalism, perspective, and RemixPlan generation."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        self.judge = MixJudge()

    def tearDown(self):
        self.td.cleanup()

    def test_ambience_sterilization_triggers_remix(self):
        dx_wav = _create_synthetic_wav(self.tmp_dir / "dx.wav", amplitude=0.50)
        # AMB is practically digital black (amplitude 0.0001 -> < -75 dB)
        amb_wav = _create_synthetic_wav(self.tmp_dir / "amb_dead.wav", amplitude=0.00005)
        premaster = _create_synthetic_wav(self.tmp_dir / "premaster.wav", amplitude=0.50)

        stems = {"DX": dx_wav, "AMB": amb_wav}
        res = self.judge.evaluate(
            stems=stems,
            premaster_path=premaster,
            scene_intent=SceneMixIntent(focus="dialogue"),
        )
        amb_cat = next(c for c in res.category_results if c.name == "ambience_naturalism")
        self.assertEqual(amb_cat.status, "REMIX")
        self.assertIn("sterilized", amb_cat.reason.lower())

        # Check actionable remediation in RemixPlan
        self.assertIsNotNone(res.remix_plan)
        preserve_act = next(a for a in res.remix_plan.actions if a.target == "AMB")
        self.assertEqual(preserve_act.action_code, "preserve_room_tone")

    def test_perspective_mismatch_triggers_remix(self):
        # Declared door occlusion but automation has zero lowpass filter
        persp = AcousticPerspective(distance="near", occlusion="door")
        auto = MixAutomation(events=[], total_duration_sec=2.0)
        premaster = _create_synthetic_wav(self.tmp_dir / "premaster.wav", amplitude=0.30)

        res = self.judge.evaluate(
            premaster_path=premaster,
            acoustic_perspective=persp,
            mix_automation=auto,
        )
        sp_cat = next(c for c in res.category_results if c.name == "spatial_coherence")
        self.assertEqual(sp_cat.status, "REMIX")
        self.assertIn("door", sp_cat.reason.lower())

    def test_remix_controller_bounded_cycle_converges(self):
        controller = RemixController(judge=self.judge, max_attempts=2)

        # Mock render function that improves on attempt 2
        call_count = [0]
        def mock_render(auto: MixAutomation):
            call_count[0] += 1
            if call_count[0] == 1:
                # Attempt 1: bad mix (low dx, loud mx) -> triggers REMIX
                dx = _create_synthetic_wav(self.tmp_dir / "dx_1.wav", amplitude=0.08)
                mx = _create_synthetic_wav(self.tmp_dir / "mx_1.wav", amplitude=0.50)
            else:
                # Attempt 2: remediation applied (good dx, ducked mx) -> PASS
                dx = _create_synthetic_wav(self.tmp_dir / "dx_2.wav", amplitude=0.60)
                mx = _create_synthetic_wav(self.tmp_dir / "mx_2.wav", amplitude=0.05)
            pm = _create_synthetic_wav(self.tmp_dir / f"pm_{call_count[0]}.wav", amplitude=0.40)
            return {"DX": dx, "MX": mx}, pm

        init_auto = MixAutomation(events=[], total_duration_sec=2.0)
        cycle_res = controller.execute_bounded_cycle(
            render_fn=mock_render,
            initial_automation=init_auto,
            scene_intent=SceneMixIntent(focus="dialogue"),
        )
        self.assertTrue(cycle_res.converged)
        self.assertEqual(cycle_res.total_attempts, 2)
        self.assertIn(cycle_res.final_result.status, ("PASS", "PASS_WITH_WARNINGS"))

    def test_remix_controller_halts_on_hard_fail(self):
        controller = RemixController(judge=self.judge, max_attempts=2)

        # Render function returns missing premaster (hard fail)
        def mock_render(auto: MixAutomation):
            return {}, self.tmp_dir / "missing.wav"

        init_auto = MixAutomation(events=[], total_duration_sec=2.0)
        cycle_res = controller.execute_bounded_cycle(
            render_fn=mock_render,
            initial_automation=init_auto,
        )
        # Must halt immediately on attempt 1 without retrying faders
        self.assertFalse(cycle_res.converged)
        self.assertEqual(cycle_res.total_attempts, 1)
        self.assertEqual(cycle_res.final_result.status, "FAIL")


if __name__ == "__main__":
    unittest.main()
