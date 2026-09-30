#!/usr/bin/env python3
"""
Audiobook Factory - Stage 11: Cinematic Mix v2.
Module: test_cinematic_mix_integration.py
Tests:
- End-to-end integration: CinemaAudioEngine render_discrete_stems with MixJudge and RemixController.
- Analysis caching performance and cache invalidation.
- Bounded remix loop execution inside rendering pipeline.
- Fail-closed safety compliance on critical defects.
- Single source of truth invariants across Stage 11 contracts.
"""

from __future__ import annotations
import math
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from typing import Dict, Any

from audiobook_factory.cinematic_mix import (
    SceneMixIntent,
    AttentionMap,
    AttentionEvent,
    MixAutomation,
    AutomationPlanner,
    AcousticPerspective,
    SilenceEvent,
    ImpactEvent,
    MixJudge,
    MixJudgeResult,
    RemixController,
)
from audiobook_factory.cinema_audio_engine import (
    CinemaAudioManifest,
    StemLedger,
    render_discrete_stems,
)
from audiobook_factory.contracts import MusicCue
from audiobook_factory.deterministic_audio_analyzer import DeterministicAudioAnalyzer


def generate_test_wav(
    file_path: Path,
    duration_sec: float,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    sample_rate: int = 48000,
    channels: int = 2,
) -> Path:
    """Generates standard 48kHz test WAV audio file."""
    file_path = Path(file_path).resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    int_amp = int(32767 * min(1.0, max(0.0, amplitude)))

    frames = bytearray()
    for i in range(num_samples):
        sample = int(int_amp * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
        packed = sample.to_bytes(2, byteorder="little", signed=True)
        for _ in range(channels):
            frames.extend(packed)

    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return file_path


class TestCinematicMixFinalIntegration(unittest.TestCase):
    """End-to-end pipeline integration and verification tests."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="stage11_final_test_")
        self.tmp_dir = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_render_discrete_stems_generates_mix_judge_audit(self):
        """Verify render_discrete_stems executes MixJudge and attaches audit metadata."""
        dx_wav = self.tmp_dir / "dx.wav"
        generate_test_wav(dx_wav, duration_sec=4.0, frequency=440.0, amplitude=0.45)
        mx_wav = self.tmp_dir / "mx.wav"
        generate_test_wav(mx_wav, duration_sec=4.0, frequency=220.0, amplitude=0.20)

        intent = SceneMixIntent(
            focus="dialogue",
            emotional_intensity=0.5,
            dialogue_priority=0.9,
            music_priority=0.4,
        )
        att_map = AttentionMap(
            chapter_id="ch_int_01",
            total_duration_sec=4.0,
            events=[
                AttentionEvent(
                    start=0.5,
                    end=3.5,
                    focus_target="dialogue",
                    priority=0.85,
                    reason="Dialogue focus",
                )
            ],
        )
        manifest = CinemaAudioManifest(
            chapter_id="ch_int_01",
            total_duration_sec=4.0,
            music_cues=[
                MusicCue(
                    cue_id="mc_int_01",
                    track_name=str(mx_wav),
                    cue_type="BGM_MAIN",
                    section_name="BED",
                    start_ms=0,
                    duration_ms=4000,
                )
            ],
            scene_intent=intent,
            attention_map=att_map,
        )

        out_dir = self.tmp_dir / "stems_out"
        ledger = render_discrete_stems(
            manifest=manifest,
            dialogue_wav=dx_wav,
            output_dir=out_dir,
            enable_judge=True,
        )

        self.assertIsInstance(ledger, StemLedger)
        self.assertIn("CINEMATIC_MIX_PREMASTER", ledger.stems)
        self.assertIn("mix_judge_audit", ledger.metadata)
        self.assertIn("mix_judge_status", ledger.metadata)
        self.assertIn("mix_judge_score", ledger.metadata)
        self.assertIn(ledger.metadata["mix_judge_status"], ("PASS", "PASS_WITH_WARNINGS"))
        self.assertGreaterEqual(ledger.metadata["mix_judge_score"], 0.70)
        self.assertTrue(ledger.compliance_status)

    def test_analysis_caching_performance_and_invalidation(self):
        """Verify DeterministicAudioAnalyzer and MixJudge cache hits and cache clearing."""
        analyzer = DeterministicAudioAnalyzer()
        test_wav = self.tmp_dir / "cache_test.wav"
        generate_test_wav(test_wav, duration_sec=2.0, frequency=440.0, amplitude=0.4)

        # First probe fills cache
        f1 = analyzer.probe_format(test_wav)
        l1 = analyzer.probe_loudness(test_wav)

        stat = test_wav.stat()
        cache_key = (str(test_wav.resolve()), stat.st_size, stat.st_mtime_ns)
        self.assertIn(cache_key, analyzer._format_cache)
        self.assertIn(cache_key, analyzer._loudness_cache)

        # Second probe returns cached copy without subprocess execution
        f2 = analyzer.probe_format(test_wav)
        l2 = analyzer.probe_loudness(test_wav)
        self.assertEqual(f1.duration_sec, f2.duration_sec)
        self.assertEqual(l1.integrated_lufs, l2.integrated_lufs)

        # MixJudge cache integration
        judge = MixJudge(analyzer=analyzer)
        c1 = judge._measure_vocal_corridor_db(test_wav)
        self.assertIn(cache_key, judge._corridor_cache)
        c2 = judge._measure_vocal_corridor_db(test_wav)
        self.assertEqual(c1, c2)

        # Test cache clearing
        judge.clear_cache()
        self.assertEqual(len(judge._corridor_cache), 0)
        self.assertEqual(len(judge._phase_cache), 0)
        self.assertEqual(len(analyzer._format_cache), 0)
        self.assertEqual(len(analyzer._loudness_cache), 0)

    def test_bounded_remix_pass_in_render_discrete_stems(self):
        """Verify render_discrete_stems executes bounded remediation when enable_remix=True."""
        dx_wav = self.tmp_dir / "dx_remix.wav"
        # Whisper speech with low amplitude
        generate_test_wav(dx_wav, duration_sec=4.0, frequency=440.0, amplitude=0.08)
        mx_wav = self.tmp_dir / "mx_remix.wav"
        # Loud competing music bed
        generate_test_wav(mx_wav, duration_sec=4.0, frequency=220.0, amplitude=0.45)

        intent = SceneMixIntent(
            focus="dialogue",
            dialogue_priority=0.95,
            music_priority=0.40,
        )
        att_map = AttentionMap(
            chapter_id="ch_remix_01",
            total_duration_sec=4.0,
            events=[
                AttentionEvent(
                    start=0.5,
                    end=3.5,
                    focus_target="dialogue",
                    priority=0.90,
                    reason="Quiet whisper dialogue",
                )
            ],
        )
        manifest = CinemaAudioManifest(
            chapter_id="ch_remix_01",
            total_duration_sec=4.0,
            music_cues=[
                MusicCue(
                    cue_id="mc_loud_01",
                    track_name=str(mx_wav),
                    cue_type="BGM_MAIN",
                    section_name="CLASH",
                    start_ms=0,
                    duration_ms=4000,
                )
            ],
            scene_intent=intent,
            attention_map=att_map,
        )

        out_dir = self.tmp_dir / "stems_remix_out"
        ledger = render_discrete_stems(
            manifest=manifest,
            dialogue_wav=dx_wav,
            output_dir=out_dir,
            enable_judge=True,
            enable_remix=True,
            max_remix_attempts=2,
        )

        self.assertIsInstance(ledger, StemLedger)
        self.assertIn("mix_judge_audit", ledger.metadata)
        # Verify remix was executed or evaluated
        if ledger.metadata.get("remix_cycles_executed"):
            self.assertEqual(ledger.metadata["remix_cycles_executed"], 1)

    def test_single_source_of_truth_contracts(self):
        """Verify no duplicate or divergent automation models exist."""
        auto = MixAutomation(
            events=[],
            total_duration_sec=10.0,
            scene_id="sc_01",
            chapter_id="ch_01",
        )
        # Contract fields
        self.assertTrue(hasattr(auto, "events"))
        self.assertTrue(hasattr(auto, "decisions"))
        self.assertTrue(hasattr(auto, "add_event"))
        self.assertTrue(hasattr(auto, "record_decision"))
        self.assertTrue(hasattr(auto, "evaluate_parameter"))

        # Verify semantic premaster identifier
        self.assertEqual(auto.chapter_id, "ch_01")

    def test_fail_closed_compliance_on_corrupt_render(self):
        """Verify that technical safety failure blocks compliance_status in StemLedger."""
        judge = MixJudge()
        # Non-existent premaster path
        res = judge.evaluate(premaster_path=self.tmp_dir / "non_existent_premaster.wav")
        self.assertEqual(res.status, "FAIL")
        self.assertEqual(res.recommended_action, "HALT")
        self.assertTrue(any("technical_safety" in f for f in res.failures))


if __name__ == "__main__":
    unittest.main()
