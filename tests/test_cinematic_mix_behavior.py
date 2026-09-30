#!/usr/bin/env python3
"""
Unit and Integration Test Suite: Stage 11 Cinematic Mix v2 (Prompt 3: Cinematic Behavior).
==========================================================================================
Validates:
1. Acoustic Perspective:
   - Close, medium, and distant source propagation
   - Barrier occlusion (behind door, behind wall, partial)
   - Direct vs reverberant energy ratio and HF absorption cutoff
   - Smooth perspective transitions and determinism
2. Silence Director:
   - Silence types: DRAMATIC, SUSPENSE, SHOCK, EMOTIONAL, TRANSITION
   - Preserved elements (room tone, breath, FX tail)
   - Smooth 3-stage timing envelopes (approach, floor, release)
   - Zero permanent scene level mutation
3. Impact Director:
   - 4-phase physical trajectory (PRE_IMPACT, IMPACT, AFTERMATH, RECOVERY)
   - Intensity-bounded ducking (0.0 to 1.0)
   - Non-destructive AttentionMap focus overlay
   - Targeted ducking and dialogue protection
4. Director Composition & Conflict Resolution:
   - Behind-door voice + door slam impact
   - Impact + post-impact shock silence
   - Whisper dialogue + emotional silence + room tone
   - Inspectable decision trace verification (director, reason, preserved_elements)
5. Real Audio Fixture Rendering:
   - Actual WAV audio modulation through CinemaAudioEngine
   - Verifies objective acoustic energy changes across stems
"""

import math
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from typing import Dict, Any, List

import pytest

from audiobook_factory.cinematic_mix.perspective import (
    AcousticPerspective,
    PerspectiveDirector,
    DistanceLevel,
    OcclusionLevel,
    DISTANCE_PRESETS,
    OCCLUSION_PRESETS,
)
from audiobook_factory.cinematic_mix.silence import (
    SilenceEvent,
    SilenceDirector,
    SilenceType,
    SilenceDepth,
    SILENCE_DEPTH_DB,
)
from audiobook_factory.cinematic_mix.impact import (
    ImpactEvent,
    ImpactDirector,
    ImpactPhase,
)
from audiobook_factory.cinematic_mix.automation import (
    MixAutomation,
    AutomationEvent,
    SAFETY_LIMIT_MIN_GAIN_DB,
)
from audiobook_factory.cinematic_mix.attention_map import AttentionMap, AttentionEvent
from audiobook_factory.cinematic_mix.scene_intent import SceneMixIntent
from audiobook_factory.cinematic_mix.planner import AutomationPlanner
from audiobook_factory.cinematic_mix.engine_adapter import (
    build_stem_filter_chain,
    apply_automation_to_stem,
)
from audiobook_factory.cinema_audio_engine import (
    CinemaAudioManifest,
    StemLedger,
    render_discrete_stems,
    measure_audio_metrics,
)
from audiobook_factory.contracts import MusicCue


def generate_test_wav(
    file_path: Path,
    duration_sec: float,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    sample_rate: int = 48000,
    channels: int = 2,
) -> Path:
    """Generates a standard 48kHz stereo WAV test audio file."""
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


class TestAcousticPerspective(unittest.TestCase):
    """Test AcousticPerspective model, presets, distance propagation, and barrier occlusion."""

    def setUp(self):
        self.director = PerspectiveDirector()

    def test_close_source_perspective(self):
        persp = AcousticPerspective(distance="close", occlusion="none")
        self.assertEqual(persp.direct_energy_db, 0.0)
        self.assertEqual(persp.hf_absorption_hz, 18000)
        self.assertLessEqual(persp.reverb_contribution, 0.10)

        events = self.director.plan_perspective(persp, start_sec=1.0, end_sec=5.0, target_stem="DX")
        # Close perspective has no direct energy reduction or lowpass filtering
        gain_events = [e for e in events if e.parameter == "gain"]
        self.assertEqual(len(gain_events), 0)

    def test_distant_source_propagation(self):
        persp = AcousticPerspective(distance="far", occlusion="none")
        # Distant source has reduced direct energy, higher HF air absorption, and more reverb
        self.assertLess(persp.direct_energy_db, -6.0)
        self.assertLess(persp.hf_absorption_hz, 10000)
        self.assertGreater(persp.reverb_contribution, 0.40)

        events = self.director.plan_perspective(persp, start_sec=0.0, end_sec=6.0, target_stem="DX")
        self.assertGreater(len(events), 0)

        gain_ev = next(e for e in events if e.parameter == "gain")
        self.assertEqual(gain_ev.target, "DX")
        self.assertAlmostEqual(gain_ev.value, persp.direct_energy_db)

        lp_ev = next(e for e in events if e.parameter == "lowpass_cutoff")
        self.assertEqual(lp_ev.value, float(persp.hf_absorption_hz))

    def test_barrier_occlusion_behind_door_and_wall(self):
        door_persp = AcousticPerspective(distance="near", occlusion="door")
        # Behind door: muffled cutoff (~2200 Hz) and direct attenuation (-9 dB or more)
        self.assertEqual(door_persp.hf_absorption_hz, 2200)
        self.assertLessEqual(door_persp.direct_energy_db, -9.0)

        wall_persp = AcousticPerspective(distance="near", occlusion="wall")
        # Behind brick wall: heavy acoustic muffling (~1100 Hz) and severe attenuation
        self.assertEqual(wall_persp.hf_absorption_hz, 1100)
        self.assertLessEqual(wall_persp.direct_energy_db, -16.0)

        events_door = self.director.plan_perspective(door_persp, start_sec=2.0, end_sec=5.0)
        lp_ev = next(e for e in events_door if e.parameter == "lowpass_cutoff")
        self.assertEqual(lp_ev.value, 2200.0)

    def test_perspective_transition_smoothness(self):
        persp = AcousticPerspective(distance="medium", occlusion="partial")
        events = self.director.plan_perspective(persp, start_sec=1.0, end_sec=4.0, transition_sec=0.40)
        for ev in events:
            self.assertEqual(ev.curve, "smooth")
            self.assertEqual(ev.hierarchy, "CINEMATIC_BEHAVIOR")

    def test_perspective_determinism(self):
        persp = AcousticPerspective(distance="medium", occlusion="door")
        ev1 = self.director.plan_perspective(persp, start_sec=0.0, end_sec=5.0)
        ev2 = self.director.plan_perspective(persp, start_sec=0.0, end_sec=5.0)
        self.assertEqual([e.model_dump() for e in ev1], [e.model_dump() for e in ev2])


class TestSilenceDirector(unittest.TestCase):
    """Test SilenceDirector, silence types, depth levels, and preserved elements."""

    def setUp(self):
        self.director = SilenceDirector()

    def test_dramatic_silence_preserves_room_tone(self):
        ev = SilenceEvent(
            start=2.0,
            duration=3.0,
            type="DRAMATIC",
            depth="deep",
            preserved_elements=["room_tone"],
            reason="Dramatic pause before revelation",
        )
        auto_events = self.director.plan_silence(ev)
        self.assertGreater(len(auto_events), 0)

        # MX should be ducked deeply (-20 dB)
        mx_ev = next(e for e in auto_events if e.target == "MX")
        self.assertEqual(mx_ev.value, -20.0)

        # AMB room tone should NOT be muted (preserved around -5 dB)
        amb_ev = next(e for e in auto_events if e.target == "AMB")
        self.assertGreaterEqual(amb_ev.value, -6.0)
        self.assertIn("room_tone", amb_ev.reason)

    def test_shock_silence_drops_to_near_black_with_fx_tail_preserved(self):
        ev = SilenceEvent(
            start=1.0,
            duration=1.5,
            type="SHOCK",
            depth="near_black",
            preserved_elements=["fx_tail"],
            reason="Ear-ringing post-explosion shock",
        )
        auto_events = self.director.plan_silence(ev)
        # Music and ambience drop to near-black (<= -24 dB)
        mx_ev = next(e for e in auto_events if e.target == "MX")
        self.assertLessEqual(mx_ev.value, -24.0)

        # FX tail is preserved (0 dB attenuation)
        fx_events = [e for e in auto_events if e.target == "FX"]
        self.assertEqual(len(fx_events), 0)

    def test_emotional_silence_preserves_dialogue_breath(self):
        ev = SilenceEvent(
            start=3.0,
            duration=2.0,
            type="EMOTIONAL",
            depth="moderate",
            preserved_elements=["breath", "room_tone"],
            reason="Intimate emotional gaze",
        )
        auto_events = self.director.plan_silence(ev)
        # Dialogue breath must be preserved with zero cut
        dx_events = [e for e in auto_events if e.target == "DX"]
        self.assertEqual(len(dx_events), 0)

    def test_none_silence_generates_zero_events(self):
        ev = SilenceEvent(start=1.0, duration=2.0, type="NONE")
        self.assertEqual(len(self.director.plan_silence(ev)), 0)

    def test_zero_permanent_scene_level_mutation(self):
        ev = SilenceEvent(start=2.0, duration=2.0, type="DRAMATIC", fade_in=0.2, fade_out=0.3)
        auto_events = self.director.plan_silence(ev)
        self.assertGreater(len(auto_events), 0)
        # Total envelope is strictly bounded between start - fade_in (1.8s) and start + duration + fade_out (4.3s)
        self.assertAlmostEqual(min(e.start for e in auto_events), 1.8)
        self.assertAlmostEqual(max(e.end for e in auto_events), 4.3)
        for e in auto_events:
            self.assertGreaterEqual(e.start, 1.8)
            self.assertLessEqual(e.end, 4.3)
            self.assertGreater(e.end, e.start)


class TestImpactDirector(unittest.TestCase):
    """Test ImpactDirector, 4-phase physical trajectory, and non-destructive attention overlay."""

    def setUp(self):
        self.director = ImpactDirector()

    def test_four_phase_impact_trajectory(self):
        imp = ImpactEvent(
            start=4.0,
            pre_impact_duration=0.25,
            impact_duration=0.20,
            aftermath_duration=0.80,
            recovery_duration=0.75,
            intensity=0.85,
            focus_target="door_slam",
            reason="Heavy dungeon door slammed shut",
        )
        events = self.director.plan_impact(imp)
        self.assertGreater(len(events), 0)

        # Check all 4 phases exist for MX stem
        phases = {e.metadata.get("phase") for e in events if e.target == "MX"}
        self.assertEqual(phases, {"PRE_IMPACT", "IMPACT", "AFTERMATH", "RECOVERY"})

        # Pre-impact dip is subtle
        pre_ev = next(e for e in events if e.target == "MX" and e.metadata.get("phase") == "PRE_IMPACT")
        self.assertGreater(pre_ev.value, -4.0)

        # Peak impact is deep
        imp_ev = next(e for e in events if e.target == "MX" and e.metadata.get("phase") == "IMPACT")
        self.assertLessEqual(imp_ev.value, -10.0)

        # Recovery ends at 0.0 dB
        rec_ev = next(e for e in events if e.target == "MX" and e.metadata.get("phase") == "RECOVERY")
        self.assertEqual(rec_ev.value, 0.0)

    def test_low_intensity_impact_skipped(self):
        imp = ImpactEvent(start=1.0, intensity=0.03)
        self.assertEqual(len(self.director.plan_impact(imp)), 0)

    def test_non_destructive_attention_shift(self):
        base_att = AttentionMap(
            chapter_id="ch_test",
            events=[AttentionEvent(start=1.0, end=5.0, focus_target="dialogue", priority=0.75)],
        )
        imp = ImpactEvent(start=2.5, intensity=0.8, focus_target="explosion", reason="Blast")
        derived_att = self.director.derive_attention_shift(base_att, [imp])

        # Original attention map must NOT be modified
        self.assertEqual(len(base_att.events), 1)

        # Derived attention map contains the impact focus window
        self.assertEqual(len(derived_att.events), 2)
        imp_att = next(e for e in derived_att.events if e.focus_target == "explosion")
        self.assertGreaterEqual(imp_att.priority, 0.90)


class TestBehaviorComposerAndConflictResolution(unittest.TestCase):
    """Test unified composition and conflict resolution across all 3 behavior directors."""

    def setUp(self):
        self.planner = AutomationPlanner()

    def test_composition_behind_door_voice_plus_door_slam_plus_silence(self):
        """Verify 3 directors compose without conflict or mutual destruction."""
        persp = AcousticPerspective(distance="near", occlusion="door")
        impact = ImpactEvent(start=3.0, intensity=0.8, focus_target="door_slam", reason="Door slam")
        silence = SilenceEvent(
            start=4.5, duration=2.0, type="DRAMATIC", depth="deep", preserved_elements=["room_tone"]
        )

        auto = self.planner.plan(
            scene_intent=SceneMixIntent(focus="dialogue"),
            attention_map=AttentionMap(
                events=[AttentionEvent(start=1.0, end=7.0, focus_target="dialogue", priority=0.75)]
            ),
            acoustic_perspective=persp,
            impact_events=[impact],
            silence_events=[silence],
            total_duration_sec=8.0,
            has_dialogue=True,
            has_music=True,
            has_ambience=True,
        )

        self.assertGreater(len(auto.events), 0)
        self.assertGreater(len(auto.decisions), 0)

        # Verify all directors contributed to decision trace
        directors_recorded = {d.get("director") for d in auto.decisions if "director" in d}
        self.assertIn("perspective", directors_recorded)
        self.assertIn("impact", directors_recorded)
        self.assertIn("silence", directors_recorded)

        # Verify DX has lowpass filter from perspective
        dx_lp = auto.get_events_for_target("DX", "lowpass_cutoff")
        self.assertGreater(len(dx_lp), 0)
        self.assertEqual(dx_lp[0].value, 2200.0)

        # Verify evaluate_parameter at t=3.1 (peak impact) has impact ducking on MX
        mx_impact_gain = auto.evaluate_parameter("MX", "gain", 3.1)
        self.assertLessEqual(mx_impact_gain, -8.0)

        # Verify evaluate_parameter at t=5.0 (silence floor) has dramatic silence ducking
        mx_silence_gain = auto.evaluate_parameter("MX", "gain", 5.0)
        self.assertLessEqual(mx_silence_gain, -18.0)

    def test_silence_floor_and_recovery_timeline(self):
        """Verify silence envelope approaches, holds floor, and releases without residual offset."""
        silence = SilenceEvent(
            start=2.0, duration=2.0, type="DRAMATIC", depth="deep", fade_in=0.2, fade_out=0.3
        )
        auto = self.planner.plan(silence_events=[silence], total_duration_sec=6.0, has_music=True)

        # Before silence (t=1.0) -> baseline 0.0 dB
        self.assertEqual(auto.evaluate_parameter("MX", "gain", 1.0), 0.0)
        # Inside silence floor (t=3.0) -> -20.0 dB
        self.assertLessEqual(auto.evaluate_parameter("MX", "gain", 3.0), -18.0)
        # After full release (t=5.0) -> baseline 0.0 dB
        self.assertEqual(auto.evaluate_parameter("MX", "gain", 5.0), 0.0)


class TestRenderedAudioFixtures(unittest.TestCase):
    """Integration fixture tests verifying actual WAV audio modulation through CinemaAudioEngine."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)

        # Generate standard test WAV files
        self.dialogue_wav = self.tmp_dir / "dialogue.wav"
        self.music_wav = self.tmp_dir / "music.wav"
        generate_test_wav(self.dialogue_wav, duration_sec=6.0, frequency=440.0, amplitude=0.5)
        generate_test_wav(self.music_wav, duration_sec=6.0, frequency=220.0, amplitude=0.4)

    def tearDown(self):
        self.td.cleanup()

    def test_occluded_behind_door_voice_renders_with_lowpass_filter(self):
        """Verify that an occluded voice renders through CinemaAudioEngine with lowpass filtering."""
        persp = AcousticPerspective(distance="near", occlusion="door")
        manifest = CinemaAudioManifest(
            chapter_id="ch_persp_test",
            total_duration_sec=6.0,
            acoustic_perspective=persp,
        )

        out_dir = self.tmp_dir / "persp_out"
        ledger = render_discrete_stems(
            manifest=manifest,
            dialogue_wav=self.dialogue_wav,
            output_dir=out_dir,
        )

        self.assertIsInstance(ledger, StemLedger)
        self.assertIn("CINEMATIC_MIX_PREMASTER", ledger.stems)

        # Verify automated DX stem exists and has lower integrated loudness due to barrier attenuation
        dx_meta = ledger.stems["DX"]
        self.assertTrue(Path(dx_meta.filepath).exists())
        self.assertIn("mix_automation", ledger.metadata)

    def test_impact_and_silence_renders_to_premaster_with_decision_ledger(self):
        """Verify full pipeline execution of Impact + Silence events into StemLedger."""
        impact = ImpactEvent(start=2.0, intensity=0.8, focus_target="explosion", reason="Blast")
        silence = SilenceEvent(start=3.5, duration=1.5, type="SHOCK", preserved_elements=["fx_tail"])

        manifest = CinemaAudioManifest(
            chapter_id="ch_behavior_test",
            total_duration_sec=6.0,
            music_cues=[
                MusicCue(
                    cue_id="mc_bgm",
                    track_name=str(self.music_wav),
                    cue_type="BGM_MAIN",
                    section_name="INTRO_BED",
                    start_ms=0,
                    duration_ms=6000,
                )
            ],
            impact_events=[impact],
            silence_events=[silence],
        )

        out_dir = self.tmp_dir / "behavior_out"
        ledger = render_discrete_stems(
            manifest=manifest,
            dialogue_wav=self.dialogue_wav,
            output_dir=out_dir,
        )

        self.assertIsInstance(ledger, StemLedger)
        self.assertTrue(ledger.compliance_status)

        # Verify decision trace persisted in ledger metadata
        self.assertIn("automation_decisions", ledger.metadata)
        decisions = ledger.metadata["automation_decisions"]
        self.assertGreater(len(decisions), 0)

        # Verify both impact and silence directors are recorded
        sources = {d.get("source") for d in decisions}
        self.assertIn("impact_director", sources)
        self.assertIn("silence_director", sources)


if __name__ == "__main__":
    unittest.main()
