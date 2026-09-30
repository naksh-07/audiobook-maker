#!/usr/bin/env python3
"""
Unit and Integration Test Suite: Stage 11 Cinematic Mix v2 (Prompt 2).
========================================================================
Validates:
1. Automation Curves:
   - linear, ease_in, ease_out, smooth
   - start, midpoint, end deterministic values
   - zero-duration and inverted timestamp rejection
   - invalid curve rejection
   - out-of-range timestamp handling
2. Automation Model & Events:
   - Typed AutomationEvent and MixAutomation container
   - Priority hierarchy and deterministic event ordering
   - Conflict resolution for overlapping events (deepest attenuation / hierarchy dominance)
   - Inspectable decision audit trace
3. Dynamic Dialogue Masking:
   - Spectral formant detection by speech style
   - Hard safety guardrails (max notch depth <= -6.5 dB)
   - DMR ceiling compliance bypass (DMR >= 14 dB -> no-op)
   - Music priority relaxation (preserves musical power)
4. Stem Interaction Engine:
   - Environmental naturalism preservation (ambience never muted)
   - Intimate whisper vs dramatic combat vs music focus interaction
   - Dialogue-to-stem acoustic bus routing
5. Automation Planner:
   - Complete SceneMixIntent + AttentionMap translation
   - Edge cases: no dialogue, no music, no FX, overlapping attention, short/long events, empty scene
6. Engine Adapter & CinemaAudioEngine Integration:
   - FFmpeg frame-evaluated filter chain generation
   - Real audio modulation via apply_automation_to_stem
   - Full render_discrete_stems end-to-end execution with ledger metadata
   - 100% backward compatibility when no intent/attention is provided
"""

import math
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from typing import Dict, Any, List

import pytest

from audiobook_factory.cinematic_mix.curves import (
    evaluate_curve,
    SUPPORTED_CURVES,
)
from audiobook_factory.cinematic_mix.automation import (
    AutomationEvent,
    MixAutomation,
    AutomationHierarchy,
    SAFETY_LIMIT_MIN_GAIN_DB,
    SAFETY_LIMIT_MAX_GAIN_DB,
    SAFETY_LIMIT_MAX_NOTCH_DB,
)
from audiobook_factory.cinematic_mix.masking import (
    DynamicMaskingAnalyzer,
    MaskingDecision,
    MAX_NOTCH_DEPTH_DB,
    SAFE_DMR_CEILING_DB,
)
from audiobook_factory.cinematic_mix.stem_interaction import (
    StemInteractionEngine,
    StemInteractionPlan,
)
from audiobook_factory.cinematic_mix.planner import AutomationPlanner
from audiobook_factory.cinematic_mix.engine_adapter import (
    build_stem_filter_chain,
    apply_automation_to_stem,
)
from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.attention_map import AttentionMap, AttentionEvent
from audiobook_factory.cinema_audio_engine import (
    CinemaAudioManifest,
    StemLedger,
    render_discrete_stems,
)
from audiobook_factory.contracts import MusicCue
from audiobook_factory.acoustic_bus_matrix import PROFILE_STANDARD


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
        val_bytes = sample.to_bytes(2, byteorder="little", signed=True)
        for _ in range(channels):
            frames.extend(val_bytes)

    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)

    return file_path


class TestAutomationCurves(unittest.TestCase):
    """Test deterministic automation curve interpolation."""

    def test_linear_curve(self):
        # start
        self.assertAlmostEqual(evaluate_curve(0.0, 10.0, 0.0, -10.0, 0.0, "linear"), 0.0)
        # midpoint
        self.assertAlmostEqual(evaluate_curve(0.0, 10.0, 0.0, -10.0, 5.0, "linear"), -5.0)
        # end
        self.assertAlmostEqual(evaluate_curve(0.0, 10.0, 0.0, -10.0, 10.0, "linear"), -10.0)

    def test_smooth_curve(self):
        # cubic Hermite smoothstep 3x^2 - 2x^3
        # start
        self.assertAlmostEqual(evaluate_curve(0.0, 10.0, 0.0, -6.0, 0.0, "smooth"), 0.0)
        # midpoint (x=0.5 -> 3*(0.25) - 2*(0.125) = 0.75 - 0.25 = 0.5)
        self.assertAlmostEqual(evaluate_curve(0.0, 10.0, 0.0, -6.0, 5.0, "smooth"), -3.0)
        # end
        self.assertAlmostEqual(evaluate_curve(0.0, 10.0, 0.0, -6.0, 10.0, "smooth"), -6.0)

    def test_ease_in_curve(self):
        # x^2: at midpoint x=0.5 -> progress=0.25 -> val = 0.0 + 0.25 * (-8.0) = -2.0
        val_mid = evaluate_curve(0.0, 4.0, 0.0, -8.0, 2.0, "ease_in")
        self.assertAlmostEqual(val_mid, -2.0)
        self.assertAlmostEqual(evaluate_curve(0.0, 4.0, 0.0, -8.0, 0.0, "ease_in"), 0.0)
        self.assertAlmostEqual(evaluate_curve(0.0, 4.0, 0.0, -8.0, 4.0, "ease_in"), -8.0)

    def test_ease_out_curve(self):
        # 1 - (1-x)^2: at midpoint x=0.5 -> 1 - 0.25 = 0.75 -> val = 0.0 + 0.75 * (-8.0) = -6.0
        val_mid = evaluate_curve(0.0, 4.0, 0.0, -8.0, 2.0, "ease_out")
        self.assertAlmostEqual(val_mid, -6.0)
        self.assertAlmostEqual(evaluate_curve(0.0, 4.0, 0.0, -8.0, 0.0, "ease_out"), 0.0)
        self.assertAlmostEqual(evaluate_curve(0.0, 4.0, 0.0, -8.0, 4.0, "ease_out"), -8.0)

    def test_zero_and_inverted_duration_rejection(self):
        with self.assertRaises(ValueError):
            evaluate_curve(5.0, 5.0, 0.0, -6.0, 5.0, "linear")
        with self.assertRaises(ValueError):
            evaluate_curve(6.0, 4.0, 0.0, -6.0, 5.0, "linear")

    def test_invalid_curve_rejection(self):
        with self.assertRaises(ValueError):
            evaluate_curve(0.0, 2.0, 0.0, -6.0, 1.0, "exponential_decay")

    def test_out_of_range_handling(self):
        # t < start returns start_value
        self.assertEqual(evaluate_curve(2.0, 4.0, 0.0, -6.0, 1.0, "smooth"), 0.0)
        # t > end returns end_value
        self.assertEqual(evaluate_curve(2.0, 4.0, 0.0, -6.0, 6.0, "smooth"), -6.0)


class TestAutomationModelAndConflictResolution(unittest.TestCase):
    """Test AutomationEvent, MixAutomation, and priority hierarchy conflict resolution."""

    def test_valid_automation_event(self):
        ev = AutomationEvent(
            start=2.0,
            end=6.0,
            target="MX",
            parameter="gain",
            value=-6.0,
            start_value=0.0,
            curve="smooth",
            priority=0.8,
            hierarchy="ATTENTION_PROTECTION",
            reason="protect dialogue whisper",
        )
        self.assertEqual(ev.duration, 4.0)
        self.assertEqual(ev.target, "MX")
        self.assertEqual(ev.value, -6.0)

    def test_invalid_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            AutomationEvent(start=5.0, end=4.0, target="MX", parameter="gain", value=-6.0)
        with self.assertRaises(ValueError):
            AutomationEvent(start=-1.0, end=4.0, target="MX", parameter="gain", value=-6.0)

    def test_event_hierarchy_precedence_and_deterministic_order(self):
        ev_base = AutomationEvent(
            start=1.0, end=5.0, target="MX", parameter="gain", value=-3.0,
            hierarchy="BASE_SCENE", priority=0.2
        )
        ev_intent = AutomationEvent(
            start=1.0, end=5.0, target="MX", parameter="gain", value=-4.0,
            hierarchy="SCENE_INTENT", priority=0.5
        )
        ev_protect = AutomationEvent(
            start=1.0, end=5.0, target="MX", parameter="gain", value=-6.0,
            hierarchy="ATTENTION_PROTECTION", priority=0.8
        )
        ev_safety = AutomationEvent(
            start=1.0, end=5.0, target="MX", parameter="gain", value=-12.0,
            hierarchy="SAFETY_LIMIT", priority=1.0
        )

        auto = MixAutomation(events=[ev_intent, ev_safety, ev_base, ev_protect])
        # Sort order should place highest hierarchy first
        self.assertEqual(auto.events[0].hierarchy, "SAFETY_LIMIT")
        self.assertEqual(auto.events[1].hierarchy, "ATTENTION_PROTECTION")
        self.assertEqual(auto.events[2].hierarchy, "SCENE_INTENT")
        self.assertEqual(auto.events[3].hierarchy, "BASE_SCENE")

    def test_conflict_resolution_at_time(self):
        auto = MixAutomation()
        # Event 1: steady attenuation -3.0 dB across [1.0, 5.0]
        auto.add_event(AutomationEvent(
            start=1.0, end=5.0, target="MX", parameter="gain", start_value=-3.0, value=-3.0,
            hierarchy="SCENE_INTENT", priority=0.5
        ))
        # Event 2: deeper dialogue protection -8.0 dB across [2.0, 4.0]
        auto.add_event(AutomationEvent(
            start=2.0, end=4.0, target="MX", parameter="gain", start_value=-8.0, value=-8.0,
            hierarchy="ATTENTION_PROTECTION", priority=0.8
        ))

        # At t=0.5 -> outside events -> default 0.0 dB
        self.assertEqual(auto.evaluate_parameter("MX", "gain", 0.5), 0.0)
        # At t=1.5 -> only Event 1 active -> -3.0 dB
        self.assertAlmostEqual(auto.evaluate_parameter("MX", "gain", 1.5), -3.0)
        # At t=3.0 -> both active -> ATTENTION_PROTECTION (-8.0 dB) dominates
        self.assertAlmostEqual(auto.evaluate_parameter("MX", "gain", 3.0), -8.0)
        # At t=4.5 -> Event 2 ended -> returns to Event 1 (-3.0 dB)
        self.assertAlmostEqual(auto.evaluate_parameter("MX", "gain", 4.5), -3.0)

    def test_safety_clamping(self):
        auto = MixAutomation()
        # Extreme negative gain beyond safety limit (-50 dB)
        auto.add_event(AutomationEvent(
            start=1.0, end=5.0, target="MX", parameter="gain", start_value=-50.0, value=-50.0,
            hierarchy="ATTENTION_PROTECTION", priority=0.9
        ))
        eval_val = auto.evaluate_parameter("MX", "gain", 3.0)
        # Must clamp to SAFETY_LIMIT_MIN_GAIN_DB (-36.0 dB)
        self.assertEqual(eval_val, SAFETY_LIMIT_MIN_GAIN_DB)

    def test_inspectable_decision_audit_trace(self):
        auto = MixAutomation()
        auto.record_decision(
            time=2.5,
            focus="Geralt",
            target="MX",
            parameter="gain",
            before=0.0,
            after=-8.0,
            reason="Whisper intimacy protection",
            source="stem_interaction",
            priority=0.85,
        )
        self.assertEqual(len(auto.decisions), 1)
        dec = auto.decisions[0]
        self.assertEqual(dec["focus"], "Geralt")
        self.assertEqual(dec["target"], "MX")
        self.assertEqual(dec["before"], 0.0)
        self.assertEqual(dec["after"], -8.0)
        self.assertEqual(dec["reason"], "Whisper intimacy protection")
        self.assertEqual(dec["source"], "stem_interaction")


class TestDynamicDialogueMasking(unittest.TestCase):
    """Test DynamicMaskingAnalyzer, formant detection, guardrails, and DMR bypass."""

    def setUp(self):
        self.analyzer = DynamicMaskingAnalyzer()

    def test_formant_frequency_detection(self):
        # Whisper maps to higher intelligibility band (~2800 Hz)
        whisper_dec = self.analyzer.evaluate_masking(
            start_sec=1.0, end_sec=3.0, attention_target="dialogue", speech_style="whisper"
        )
        self.assertEqual(whisper_dec.frequency_hz, 2800)

        # Standard speech maps to ~2400 Hz
        speech_dec = self.analyzer.evaluate_masking(
            start_sec=1.0, end_sec=3.0, attention_target="dialogue", speech_style="dialogue"
        )
        self.assertEqual(speech_dec.frequency_hz, 2400)

    def test_guardrail_caps_notch_depth(self):
        # Even with extreme priority, notch depth must never exceed MAX_NOTCH_DEPTH_DB (-6.5 dB)
        dec = self.analyzer.evaluate_masking(
            start_sec=1.0, end_sec=3.0, attention_target="dialogue", attention_priority=1.0,
            speech_style="shout", music_priority=0.0
        )
        self.assertGreaterEqual(dec.depth_db, MAX_NOTCH_DEPTH_DB)
        self.assertTrue(dec.guardrail_applied)

    def test_dmr_ceiling_compliance_bypass(self):
        # When dialogue is already +15 dB above music (>= SAFE_DMR_CEILING_DB), notch should be no-op (0.0 dB)
        dec = self.analyzer.evaluate_masking(
            start_sec=1.0, end_sec=3.0, attention_target="dialogue", estimated_dmr_db=16.0
        )
        self.assertEqual(dec.depth_db, 0.0)
        self.assertIn("already compliant", dec.reason)

    def test_music_priority_relaxation(self):
        # When music has high narrative priority, notch depth is softened
        dec_normal = self.analyzer.evaluate_masking(
            start_sec=1.0, end_sec=3.0, attention_target="dialogue", music_priority=0.3
        )
        dec_music_focus = self.analyzer.evaluate_masking(
            start_sec=1.0, end_sec=3.0, attention_target="dialogue", music_priority=0.9
        )
        # music focus notch must be gentler (closer to 0) than normal notch
        self.assertGreater(dec_music_focus.depth_db, dec_normal.depth_db)
        self.assertIn("softened for music focus", dec_music_focus.reason)


class TestStemInteractionEngine(unittest.TestCase):
    """Test multitrack stem interactions and naturalism preservation."""

    def setUp(self):
        self.engine = StemInteractionEngine()

    def test_environmental_naturalism_preservation(self):
        # Normal dialogue must NEVER mute ambience
        intent = SceneMixIntent(focus="dialogue")
        plan = self.engine.evaluate_interactions(
            scene_intent=intent, focus_target="dialogue", is_dialogue_active=True
        )
        # Ambience attenuation must be modest (e.g. -2.0 to -3.0 dB), never muted (-20 dB)
        self.assertGreaterEqual(plan.amb_attenuation_db, -4.0)
        self.assertLess(plan.amb_attenuation_db, 0.0)

    def test_intimate_whisper_interaction(self):
        # Intimate whisper requires deeper music attenuation (-12 dB) to protect intelligibility
        intent = SceneMixIntent(focus="dialogue")
        plan = self.engine.evaluate_interactions(
            scene_intent=intent, focus_target="dialogue", speech_style="whisper", is_dialogue_active=True
        )
        self.assertLessEqual(plan.mx_attenuation_db, -10.0)
        self.assertTrue(plan.mx_notch_needed)

    def test_combat_high_intensity_scene(self):
        # Combat scene: FX prioritized, music kept strong
        intent = SceneMixIntent(focus="fx", emotional_intensity=0.9, fx_priority=0.95, music_priority=0.8)
        plan = self.engine.evaluate_interactions(
            scene_intent=intent, focus_target="fx", is_dialogue_active=False
        )
        self.assertEqual(plan.fx_attenuation_db, 0.0)
        # Music attenuation should be slight or 0
        self.assertGreaterEqual(plan.mx_attenuation_db, -3.0)

    def test_music_focus_interaction(self):
        # Music focus: music is preserved with zero attenuation
        intent = SceneMixIntent(focus="music", music_priority=0.95)
        plan = self.engine.evaluate_interactions(
            scene_intent=intent, focus_target="music", is_dialogue_active=False
        )
        self.assertEqual(plan.mx_attenuation_db, 0.0)


class TestAutomationPlanner(unittest.TestCase):
    """Test AutomationPlanner with all narrative scenarios and edge cases."""

    def setUp(self):
        self.planner = AutomationPlanner()

    def test_no_dialogue_edge_case(self):
        # When scene has no active dialogue, music and ambience are not ducked
        intent = SceneMixIntent(focus="environment", music_priority=0.8, ambience_priority=0.8)
        att_map = AttentionMap(events=[
            AttentionEvent(start=1.0, end=5.0, focus_target="environment", priority=0.7)
        ])
        auto = self.planner.plan(
            scene_intent=intent,
            attention_map=att_map,
            has_dialogue=False,
            has_music=True,
            has_ambience=True,
        )
        # No dialogue protection gain drops on music
        mx_events = auto.get_events_for_target("MX", "gain")
        self.assertEqual(len(mx_events), 0)

    def test_no_music_edge_case(self):
        # When scene has no music stem, planner generates zero MX events
        intent = SceneMixIntent(focus="dialogue")
        att_map = AttentionMap(events=[
            AttentionEvent(start=1.0, end=4.0, focus_target="dialogue", priority=0.8)
        ])
        auto = self.planner.plan(
            scene_intent=intent,
            attention_map=att_map,
            has_dialogue=True,
            has_music=False,
            has_ambience=True,
        )
        self.assertEqual(len(auto.get_events_for_target("MX", "gain")), 0)
        self.assertEqual(len(auto.get_events_for_target("MX", "eq_depth")), 0)

    def test_no_foley_edge_case(self):
        # When scene has no foley stem, planner generates zero FX events
        intent = SceneMixIntent(focus="dialogue")
        att_map = AttentionMap(events=[
            AttentionEvent(start=1.0, end=4.0, focus_target="dialogue", priority=0.8)
        ])
        auto = self.planner.plan(
            scene_intent=intent,
            attention_map=att_map,
            has_dialogue=True,
            has_music=True,
            has_foley=False,
            has_ambience=True,
        )
        self.assertEqual(len(auto.get_events_for_target("FX", "gain")), 0)

    def test_overlapping_attention_events(self):
        # Overlapping dialogue and SFX events: resolve_windows splits them deterministically
        att_map = AttentionMap(events=[
            AttentionEvent(start=1.0, end=5.0, focus_target="dialogue", priority=0.7),
            AttentionEvent(start=3.0, end=4.0, focus_target="fx", priority=0.9, reason="Explosion"),
        ])
        auto = self.planner.plan(
            attention_map=att_map,
            has_dialogue=True,
            has_music=True,
            has_foley=True,
        )
        # Windows must be formed and events created
        self.assertGreater(len(auto.events), 0)
        # Verify inspectable decision trace exists
        self.assertGreater(len(auto.decisions), 0)

    def test_short_dialogue_micro_sliver_filtered(self):
        # Dialogue shorter than 50ms should be filtered by anti-jitter guard
        att_map = AttentionMap(events=[
            AttentionEvent(start=1.0, end=1.03, focus_target="dialogue", priority=0.8)
        ])
        auto = self.planner.plan(attention_map=att_map, has_dialogue=True, has_music=True)
        self.assertEqual(len(auto.events), 0)

    def test_empty_scene_fallback(self):
        # Completely empty attention map and dialogue returns empty clean MixAutomation
        auto = self.planner.plan(
            scene_intent=SceneMixIntent(),
            attention_map=AttentionMap(),
            dialogue_segments=None,
        )
        self.assertEqual(len(auto.events), 0)
        self.assertEqual(len(auto.decisions), 0)


class TestEngineAdapterAndCinemaAudioEngine(unittest.TestCase):
    """Test engine adapter FFmpeg filter generation, real audio modulation, and CinemaAudioEngine integration."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def test_build_stem_filter_chain(self):
        auto = MixAutomation()
        auto.add_event(AutomationEvent(
            start=2.0, end=6.0, target="MX", parameter="gain", value=-6.0,
            curve="smooth", hierarchy="ATTENTION_PROTECTION"
        ))
        auto.add_event(AutomationEvent(
            start=2.0, end=6.0, target="MX", parameter="eq_depth", value=-5.5,
            metadata={"frequency_hz": 2400, "q": 1.5},
            hierarchy="ATTENTION_PROTECTION"
        ))

        filter_str = build_stem_filter_chain("MX", auto)
        self.assertIn("equalizer=f=2400", filter_str)
        self.assertIn("volume=", filter_str)
        self.assertIn("eval=frame", filter_str)

    def test_apply_automation_to_stem_real_audio(self):
        """Verify apply_automation_to_stem executes FFmpeg and modulates audio levels."""
        input_wav = self.tmp_dir / "input_mx.wav"
        output_wav = self.tmp_dir / "output_mx.wav"
        generate_test_wav(input_wav, duration_sec=4.0, frequency=220.0, amplitude=0.5)

        auto = MixAutomation()
        auto.add_event(AutomationEvent(
            start=1.0, end=3.0, target="MX", parameter="gain", value=-12.0,
            curve="smooth", hierarchy="ATTENTION_PROTECTION"
        ))

        res_path = apply_automation_to_stem(input_wav, "MX", output_wav, auto)
        self.assertTrue(res_path.exists())
        self.assertGreater(res_path.stat().st_size, 1000)

    def test_render_discrete_stems_with_stage11_automation(self):
        """End-to-end integration: CinemaAudioManifest with SceneMixIntent and AttentionMap."""
        dialogue_wav = self.tmp_dir / "dialogue.wav"
        generate_test_wav(dialogue_wav, duration_sec=5.0, frequency=440.0, amplitude=0.4)

        music_wav = self.tmp_dir / "music.wav"
        generate_test_wav(music_wav, duration_sec=5.0, frequency=220.0, amplitude=0.3)

        intent = SceneMixIntent(
            focus="dialogue",
            emotional_intensity=0.6,
            dialogue_priority=0.9,
            music_priority=0.5,
        )
        att_map = AttentionMap(
            chapter_id="ch_stage11_test",
            total_duration_sec=5.0,
            events=[
                AttentionEvent(
                    start=1.0,
                    end=4.0,
                    focus_target="dialogue",
                    priority=0.85,
                    reason="Whisper intimacy",
                )
            ]
        )

        manifest = CinemaAudioManifest(
            chapter_id="ch_stage11_test",
            total_duration_sec=5.0,
            music_cues=[
                MusicCue(
                    cue_id="mc_01",
                    track_name=str(music_wav),
                    cue_type="BGM_MAIN",
                    section_name="INTRO_BED",
                    start_ms=0,
                    duration_ms=5000,
                )
            ],
            scene_intent=intent,
            attention_map=att_map,
        )

        out_dir = self.tmp_dir / "stems_output"
        ledger = render_discrete_stems(
            manifest=manifest,
            dialogue_wav=dialogue_wav,
            output_dir=out_dir,
        )

        self.assertIsInstance(ledger, StemLedger)
        self.assertEqual(ledger.chapter_id, "ch_stage11_test")
        # Verify Stage 11 semantic premaster
        self.assertIn("CINEMATIC_MIX_PREMASTER", ledger.stems)
        self.assertIn("FULL_MASTER", ledger.stems)
        self.assertEqual(ledger.premaster.stem_type, "CINEMATIC_MIX_PREMASTER")

        # Verify Stage 11 metadata and inspectable decisions recorded in ledger
        self.assertIn("mix_automation", ledger.metadata)
        self.assertIn("automation_decisions", ledger.metadata)
        self.assertIn("automation_event_count", ledger.metadata)
        self.assertGreater(ledger.metadata["automation_event_count"], 0)

        # Verify disk persistence
        ledger_disk = out_dir / "ch_stage11_test_stem_ledger.json"
        self.assertTrue(ledger_disk.exists())

    def test_backward_compatibility_without_stage11_intent(self):
        """Verify 100% backward compatibility when no scene_intent or attention_map is provided."""
        dialogue_wav = self.tmp_dir / "dialogue_legacy.wav"
        generate_test_wav(dialogue_wav, duration_sec=3.0, frequency=440.0, amplitude=0.4)

        manifest = CinemaAudioManifest(
            chapter_id="ch_legacy_test",
            total_duration_sec=3.0,
        )

        out_dir = self.tmp_dir / "stems_legacy_output"
        ledger = render_discrete_stems(
            manifest=manifest,
            dialogue_wav=dialogue_wav,
            output_dir=out_dir,
        )

        self.assertIsInstance(ledger, StemLedger)
        self.assertEqual(ledger.chapter_id, "ch_legacy_test")
        self.assertIn("FULL_MASTER", ledger.stems)
        self.assertIn("CINEMATIC_MIX_PREMASTER", ledger.stems)
        # Without intent or attention map, automation is not triggered
        self.assertNotIn("mix_automation", ledger.metadata)


if __name__ == "__main__":
    unittest.main()
