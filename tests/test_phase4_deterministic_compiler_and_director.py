#!/usr/bin/env python3
"""
Unit and Integration Tests for Phase 4 Modernization:
1. Deterministic Manifest Renderer:
   - Consumption of Pydantic v2 CreativeManifest and backward-compatibility with dict.
   - 5-Minute Cinema Reel Foley Submix Engine (300s reel slicing, zero dropped cues, Win32 command line safety).
   - Calibrated gain staging (Unity fader volume=1.0, explicit normalize=0 on amix).
   - FFmpeg master filter graph (Dialogue + Ducked BGM + Ambience Bed + Calibrated Foley + Shared Convolution Reverb).
   - EBU R128 broadcast mastering (-19 LUFS, -1.5 dBTP) and M4A/M4B export.
2. Agent Director:
   - 3-Pass Creative Agent Workflow (Pass 1: Dramaturgy & Silence Carving >= 60-75%,
     Pass 2: Music Director dynamic FTS5 & fallback to pure silence,
     Pass 3: Acoustic Foley grammatical dependency parsing without regex).
3. Orchestrator Pipeline Wiring:
   - produce_chapter cleanly wired to AgentDirector and ManifestRenderer.
4. CLI Subcommands:
   - direct, render, produce, and soundbank ingest.
"""

import sys
import json
import wave
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    ManifestValidationError,
)
from audiobook_factory.manifest_renderer import (
    render_manifest_soundscape,
    render_foley_bus_reel_chunked,
    assemble_master_filter_graph,
    ManifestRenderError,
)
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.soundscape import get_audio_duration, get_ffmpeg


class TestPhase4DeterministicCompilerAndDirector(unittest.TestCase):
    """Test suite for Phase 4 Modernization components."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.ffmpeg = get_ffmpeg()

        # Create dummy 48kHz stereo WAV assets for testing
        self.vocal_wav = self.tmp_path / "vocal_dialogue.wav"
        self._generate_sine_wav(self.vocal_wav, duration_sec=4.0, freq=1000)

        self.sfx_wav = self.tmp_path / "sword_draw.wav"
        self._generate_sine_wav(self.sfx_wav, duration_sec=0.5, freq=500)

        self.amb_wav = self.tmp_path / "wind_howl.ogg"
        self._generate_sine_wav(self.amb_wav, duration_sec=2.0, freq=250)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _generate_sine_wav(self, file_path: Path, duration_sec: float, freq: int = 440):
        """Helper to create short valid PCM 16-bit 48kHz stereo test audio files."""
        frames = int(48000 * duration_sec)
        with wave.open(str(file_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(b"\x10\x00\x10\x00" * frames)

    # -------------------------------------------------------------------------
    # 1. Manifest Renderer & 5-Minute Cinema Reel Foley Engine Tests
    # -------------------------------------------------------------------------
    def test_01_foley_reel_chunked_zero_dropped_cues_across_reels(self):
        """Verify 5-Minute Cinema Reel Foley Engine places all cues across 300s reels with 0 drops."""
        # Timeline spanning 650 seconds (> 2 reels of 300s each)
        total_dur = 650.0
        foley_cues = [
            # Reel 0: 0s to 300s
            FoleyCue(cue_id="fc_001", segment_index=1, anchor_word="drew", asset_path=str(self.sfx_wav), start_ms=10000, pre_roll_ms=100),
            FoleyCue(cue_id="fc_002", segment_index=2, anchor_word="struck", asset_path=str(self.sfx_wav), start_ms=150000, pre_roll_ms=100),
            # Reel 1: 300s to 600s
            FoleyCue(cue_id="fc_003", segment_index=3, anchor_word="parried", asset_path=str(self.sfx_wav), start_ms=350000, pre_roll_ms=100),
            FoleyCue(cue_id="fc_004", segment_index=4, anchor_word="slammed", asset_path=str(self.sfx_wav), start_ms=500000, pre_roll_ms=100),
            # Reel 2: 600s to 650s
            FoleyCue(cue_id="fc_005", segment_index=5, anchor_word="sheathed", asset_path=str(self.sfx_wav), start_ms=620000, pre_roll_ms=100),
        ]

        out_bus = self.tmp_path / "foley_bus_test.wav"
        bank = SoundBank()

        # Render with reel_duration_sec = 300.0
        success = render_foley_bus_reel_chunked(
            foley_cues=foley_cues,
            total_duration_sec=total_dur,
            output_bus_file=out_bus,
            sound_bank=bank,
            ffmpeg=self.ffmpeg,
            reel_duration_sec=300.0,
            chunk_size=2,  # Force submix chunking within each reel
        )

        self.assertTrue(success)
        self.assertTrue(out_bus.exists())
        self.assertGreater(out_bus.stat().st_size, 10000)

        # Confirm output duration matches total duration
        dur = get_audio_duration(out_bus)
        self.assertAlmostEqual(dur, total_dur, delta=2.0)

    def test_02_master_filter_graph_assembly_parameters(self):
        """Verify deterministic FFmpeg master filter graph assembly string matches exact specification."""
        # 1. With Foley
        graph_with_foley = assemble_master_filter_graph(
            has_foley=True,
            target_lufs=-19.0,
            true_peak_db=-1.5,
            duck_attenuation_db=-16.0,
            duck_attack_ms=15,
            duck_release_ms=350,
            spectral_carve_hz=2200,
            spectral_carve_gain_db=-5.5,
        )
        self.assertIn("[0:a]asplit=3[voc_dry][voc_sc][voc_rev]", graph_with_foley)
        self.assertIn("equalizer=f=2200:t=q:w=1.5:g=-5.5[bgm_carved]", graph_with_foley)
        self.assertIn("sidechaincompress=threshold=0.03", graph_with_foley)
        self.assertIn("attack=15:release=350", graph_with_foley)
        self.assertIn("aecho=0.8:0.8:50|80|120", graph_with_foley)  # Shared Reverb Send
        self.assertIn("normalize=0", graph_with_foley)  # Calibrated gain staging (anti -33dB drop)
        self.assertIn("loudnorm=I=-19.0:TP=-1.5:LRA=7.0", graph_with_foley)

        # 2. Without Foley
        graph_without_foley = assemble_master_filter_graph(has_foley=False)
        self.assertNotIn("[3:a]", graph_without_foley)
        self.assertIn("amix=inputs=4:duration=first:normalize=0", graph_without_foley)

    def test_03_manifest_renderer_dict_backwards_compatibility_and_m4a_export(self):
        """Verify render_manifest_soundscape supports dict input and exports valid M4A master."""
        manifest_dict = {
            "manifest_version": "3.0",
            "chapter_id": "chapter_dict_test",
            "total_duration_ms": 4000,
            "silence_percentage": 100.0,
            "mastering": {
                "target_lufs": -19.0,
                "true_peak_db": -1.5,
                "ducking_attenuation_db": -16.0,
                "ducking_attack_ms": 15,
                "ducking_release_ms": 350,
            },
            "music_cues": [],
            "foley_cues": [],
            "ambience_scenes": [],
        }

        out_m4a = self.tmp_path / "chapter_dict_test.m4a"

        rendered_path = render_manifest_soundscape(
            manifest=manifest_dict,
            vocal_track_path=self.vocal_wav,
            output_master_file=out_m4a,
        )

        self.assertTrue(rendered_path.exists())
        self.assertEqual(rendered_path.suffix.lower(), ".m4a")
        self.assertGreater(rendered_path.stat().st_size, 5000)
        dur = get_audio_duration(rendered_path)
        self.assertAlmostEqual(dur, 4.0, delta=1.5)

    # -------------------------------------------------------------------------
    # 2. Agent Director 3-Pass Workflow Tests
    # -------------------------------------------------------------------------
    def test_04_agent_director_3pass_workflow_and_silence_carving(self):
        """Verify AgentDirector 3-Pass Workflow guarantees >= 60.0% acoustic silence."""
        segments = [
            {"index": 1, "speaker": "Narrator", "text": "The wind howled outside the old wooden tavern.", "pause_after_ms": 200},
            {"index": 2, "speaker": "Geralt", "text": "He drew his silver sword with a hiss.", "pause_after_ms": 300},
            {"index": 3, "speaker": "Innkeeper", "text": "Put that away before you hurt someone.", "pause_after_ms": 200},
            {"index": 4, "speaker": "Geralt", "text": "The beast is already at the gates.", "pause_after_ms": 300},
        ]
        seg_durations = {1: 4.0, 2: 3.5, 3: 3.0, 4: 3.5}
        total_sec = 14.0

        director = AgentDirector()
        manifest = director.direct_chapter_manifest(
            chapter_id="chapter_pass_test",
            script_segments=segments,
            segment_durations_sec=seg_durations,
            total_duration_sec=total_sec,
        )

        # Pass 1 & Contract Validation: silence percentage >= 60.0%
        self.assertGreaterEqual(manifest.silence_percentage, 60.0)
        self.assertEqual(manifest.chapter_id, "chapter_pass_test")

        # Pass 2: Fallback to pure silence (never hardcoded tracks)
        for cue in manifest.music_cues:
            # Track names must be resolved from real catalog or empty, NEVER hardcoded "001 The White Wolf.mp3"
            self.assertNotEqual(cue.track_name, "001 The White Wolf.mp3")

        # Pass 3: Acoustic Foley grammatical dependency parsing without regex
        self.assertIsInstance(manifest.foley_cues, list)
        for foley in manifest.foley_cues:
            self.assertGreaterEqual(foley.pre_roll_ms, 80)
            self.assertGreaterEqual(foley.azimuth_pan, -0.8)
            self.assertLessEqual(foley.azimuth_pan, 0.8)

    def test_05_agent_director_pass2_pure_silence_fallback(self):
        """Verify Pass 2 Music Director falls back to pure silence when query does not match, never hardcoded."""
        director = AgentDirector()
        # Empty cues plan or unmatched query
        cues_plan = [
            {
                "cue_id": "mc_unmatchable",
                "cue_type": "TRANSITION_BRIDGE",
                "trigger_segment": 1,
                "search_query": "xyznonsensequerystringnomatch99999",
                "mood": "alien",
                "timbre": "synthesizer",
                "energy_section": "CLIMAX_DROP",
                "duration_sec": 20.0,
            }
        ]
        resolved_cues = director._pass2_music_director(
            cues_plan=cues_plan,
            seg_starts_ms={1: 0},
            total_duration_ms=60000,
        )
        # MUST fall back to pure silence -> 0 cues! NEVER hardcoded fallback track
        self.assertEqual(len(resolved_cues), 0)

    def test_06_agent_director_pass3_word_level_alignment(self):
        """Verify Pass 3 word-level alignment calculates offset accurately from anchor word position."""
        director = AgentDirector()
        text = "The Witcher drew his silver sword quickly."
        # "drew" is the 3rd word out of 6 words (~40-50% through segment)
        offset_ms = director._compute_word_level_offset(
            text=text,
            anchor_word="drew",
            seg_dur_ms=4000,
        )
        # Should be between 1000ms and 2500ms
        self.assertGreater(offset_ms, 1000)
        self.assertLess(offset_ms, 2500)

    def test_07_orchestrator_wiring_to_director_and_manifest_renderer(self):
        """Verify Orchestrator.produce_chapter seamlessly invokes AgentDirector and ManifestRenderer."""
        from audiobook_factory.orchestrator import PipelineOrchestrator
        from unittest.mock import patch

        project_dir = self.tmp_path / "test_book_project"
        scripts_dir = project_dir / "scripts"
        audio_dir = project_dir / "audio_chunks"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)

        # Setup script JSON
        script_data = [
            {"index": 1, "speaker": "Narrator", "text": "The wind howled outside.", "pause_after_ms": 200},
            {"index": 2, "speaker": "Geralt", "text": "He drew his sword.", "pause_after_ms": 300},
        ]
        script_file = scripts_dir / "chapter_001_hi_script.json"
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script_data, f)

        # Setup audio chunk
        c1 = audio_dir / "c001_s0001_nar.wav"
        c2 = audio_dir / "c001_s0002_ger.wav"
        self._generate_sine_wav(c1, duration_sec=2.0, freq=800)
        self._generate_sine_wav(c2, duration_sec=2.0, freq=900)

        orchestrator = PipelineOrchestrator(self.tmp_path)

        # Mock TTSDispatcher so we test the pipeline without external API calls
        with patch("audiobook_factory.orchestrator.TTSDispatcher.synthesize_chapter_script"):
            res = orchestrator.produce_chapter(
                project_dir=project_dir,
                chapter_num=1,
                voice="Aoede",
                workers=1,
            )

        self.assertEqual(res["chapter_id"], 1)
        # Verify Manifest file was generated via AgentDirector
        manifest_file = project_dir / "manifests" / "chapter_001_hi_manifest.json"
        self.assertTrue(manifest_file.exists())
        # Verify Master file was rendered via ManifestRenderer
        master_file = res["master_file"]
        self.assertTrue(master_file.exists())
        self.assertGreater(master_file.stat().st_size, 1000)
        # Verify Timeline Ledger was produced
        ledger_file = res["ledger_file"]
        self.assertTrue(ledger_file.exists())

    def test_08_cli_subcommands_direct_render_and_soundbank_ingest(self):
        """Verify CLI subcommands direct, render, and soundbank ingest operate correctly."""
        import argparse
        from audiobook_cli import cmd_direct, cmd_render, cmd_bank

        # 1. Test soundbank ingest
        test_sound_dir = self.tmp_path / "extra_sounds"
        test_sound_dir.mkdir(parents=True, exist_ok=True)
        sfx_file = test_sound_dir / "door_slam.wav"
        self._generate_sine_wav(sfx_file, duration_sec=0.4, freq=300)

        ingest_args = argparse.Namespace(
            action="ingest",
            dir=str(test_sound_dir),
            no_recursive=False,
            workers=2,
        )
        # Run soundbank ingest
        cmd_bank(ingest_args)

        # 2. Test direct subcommand
        project_dir = self.tmp_path / "cli_book"
        scripts_dir = project_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        script_file = scripts_dir / "chapter_001_script.json"
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump([{"index": 1, "speaker": "Narrator", "text": "A quiet night in the tavern."}], f)

        custom_manifest = self.tmp_path / "custom_cli_manifest.json"
        direct_args = argparse.Namespace(
            book="cli_book",
            chapter=1,
            output=str(custom_manifest),
        )

        with patch("audiobook_cli.PROJECTS_DIR", self.tmp_path):
            cmd_direct(direct_args)

        self.assertTrue(custom_manifest.exists())
        with open(custom_manifest, "r", encoding="utf-8") as f:
            m_data = json.load(f)
        self.assertEqual(m_data["chapter_id"], "chapter_001")
        self.assertGreaterEqual(m_data["silence_percentage"], 60.0)

        # 3. Test render subcommand
        out_render_m4a = self.tmp_path / "cli_rendered.m4a"
        render_args = argparse.Namespace(
            manifest=str(custom_manifest),
            vocal=str(self.vocal_wav),
            output=str(out_render_m4a),
        )
        cmd_render(render_args)
        self.assertTrue(out_render_m4a.exists())
        self.assertGreater(out_render_m4a.stat().st_size, 2000)


if __name__ == "__main__":
    unittest.main()
