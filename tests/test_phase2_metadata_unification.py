#!/usr/bin/env python3
"""
Test Suite: Phase 2 Metadata Pipeline & Data Silos Unification.
Verifies:
1. Inline Quality Gate enforcement (Gates 0, 1, 6A, 6C).
2. AgentDirector Sonic Bible & Leitmotif injection (Silo S6).
3. Dynamic intensity-level headroom calibration (Silo S2).
4. Dynamic room reverb parameter derivation from presets (Silo S4 & Finding 2.5).
5. Whisper-safe sidechain ducking threshold at 0.018 linear (-34.9 dBFS) (Finding 2.4).
6. Cinema Audio Engine DX stem formatting to 48kHz stereo.
"""

import sys
import wave
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.gate_auditor import (
    audit_gate0_translation,
    audit_gate1_roster,
    audit_gate6a_voice_continuity,
    audit_gate6c_toc_monotonicity,
    GateAuditError,
)
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.sonic_bible import SonicBible, LeitmotifDefinition
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.manifest_renderer import (
    get_reverb_filter_string,
    assemble_master_filter_graph,
)
from audiobook_factory.cinema_audio_engine import render_discrete_stems
from audiobook_factory.contracts import (
    CreativeManifest,
    AmbienceScene,
    MasteringSettings,
    LegacyCreativeManifestAdapter,
)


class TestPhase2MetadataUnification(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_inline_quality_gates_verification(self):
        """Verify Gate 0, Gate 1, Gate 6A, and Gate 6C execute and validate correctly."""
        # Gate 0: Translation Coverage
        ext_file = self.project_dir / "chapter_001.txt"
        trans_file = self.project_dir / "chapter_001_hi.txt"
        ext_file.write_text("A" * 200, encoding="utf-8")
        trans_file.write_text("B" * 200, encoding="utf-8")

        g0 = audit_gate0_translation(ext_file, trans_file)
        self.assertEqual(g0["status"], "PASS")

        # Empty/short file must fail Gate 0
        short_file = self.project_dir / "short.txt"
        short_file.write_text("Too short", encoding="utf-8")
        with self.assertRaises(GateAuditError):
            audit_gate0_translation(ext_file, short_file)

        # Gate 1: Roster & Voice Collision
        roster = {"characters": {"Harry": {"voice": "Puck"}, "Ron": {"voice": "Charon"}}}
        registry = {"Harry": "Puck", "Ron": "Charon"}
        g1 = audit_gate1_roster(roster, registry)
        self.assertEqual(g1["status"], "PASS")

        # Collision in voice registry must fail Gate 1
        collided_registry = {"Harry": "Puck", "Ron": "Puck"}
        with self.assertRaises(GateAuditError):
            audit_gate1_roster(roster, collided_registry)

        # Gate 6A: Voice Continuity
        scripts_dir = self.project_dir / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        reg_file = self.project_dir / "voice_registry.json"
        reg_file.write_text(json.dumps({"Harry": "Puck", "Ron": "Charon"}), encoding="utf-8")
        s1 = scripts_dir / "chapter_001_script.json"
        s1.write_text(json.dumps({
            "chapter_id": 1,
            "segments": [{"index": 1, "speaker": "Harry", "text": "Hello", "voice_id": "Puck"}]
        }), encoding="utf-8")
        g6a = audit_gate6a_voice_continuity(self.project_dir)
        self.assertTrue(g6a.passed)
        self.assertEqual(g6a.gate, "Gate 6A (Voice Continuity)")

        # Gate 6C: TOC Monotonicity
        mastered_dir = self.project_dir / "mastered"
        mastered_dir.mkdir(parents=True, exist_ok=True)
        chap1 = mastered_dir / "chapter_001_cinematic.m4a"
        chap1.write_bytes(b"\x00" * 2000)
        chap2 = mastered_dir / "chapter_002_cinematic.m4a"
        chap2.write_bytes(b"\x00" * 2000)

        # Pass directory directly to wrapper
        g6c = audit_gate6c_toc_monotonicity(self.project_dir)
        self.assertTrue(g6c.passed)
        self.assertEqual(g6c.gate, "Gate 6C (TOC Integrity)")
        self.assertEqual(g6c.details["total_chapters"], 2)

    def test_02_agent_director_sonic_bible_leitmotif_injection(self):
        """Verify AgentDirector loads project sound_bible.json and injects leitmotifs into prompt and Pass 2."""
        bible = SonicBible(book_title="Test Witcher", project_id="witcher_test")
        motif = LeitmotifDefinition(
            motif_id="lm_geralt_destiny",
            entity_type="character",
            associated_entity="Geralt of Rivia",
            track_id=101,
            track_name="001 White Wolf.mp3",
            primary_instrument="solo cello",
            canonical_tempo_bpm=78,
            dramatic_intent="Fatalistic melancholy",
            default_section_start_sec=12.0,
        )
        bible.register_leitmotif(motif)
        bible.save_to_disk(self.project_dir / "sound_bible.json")

        director = AgentDirector(project_dir=self.project_dir)
        self.assertIsNotNone(director.sonic_bible)
        self.assertIn("lm_geralt_destiny", director.sonic_bible.leitmotifs)

        # Test Pass 2 resolution of leitmotif_ref
        cues_plan = [{
            "cue_id": "cue_01",
            "leitmotif_ref": "lm_geralt_destiny",
            "trigger_segment": 1,
            "duration_sec": 20.0,
        }]
        cues = director._pass2_music_director(
            cues_plan=cues_plan,
            seg_starts_ms={1: 0},
            total_duration_ms=60000,
            sonic_bible=director.sonic_bible,
        )
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].asset_path, "001 White Wolf.mp3")
        self.assertEqual(cues[0].section_start_sec, 12.0)

    def test_03_dynamic_intensity_headroom_calibration(self):
        """Verify concatenate_and_master_chapter adjusts limiter and TP ceiling for explosive intensity."""
        audio_dir = self.project_dir / "chunks"
        audio_dir.mkdir(parents=True, exist_ok=True)
        chunk = audio_dir / "c001_s0001_vocal.wav"
        with wave.open(str(chunk), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00\x00" * 24000)

        out_master = self.project_dir / "dialogue_master.wav"

        def fake_ffmpeg(*args, **kwargs):
            out_master.write_bytes(b"\x00" * 1000)
            res = MagicMock()
            res.returncode = 0
            return res

        # 1. Normal segments: standard limiter limit (0.89) and TP (-1.5)
        script_normal = [{"index": 1, "speaker": "Narrator", "intensity_level": "medium"}]
        with patch("subprocess.run", side_effect=fake_ffmpeg) as mock_sub:
            concatenate_and_master_chapter([chunk], out_master, script_segments=script_normal)
            cmd_args = mock_sub.call_args[0][0]
            filter_str = cmd_args[cmd_args.index("-af") + 1]
            self.assertIn("alimiter=limit=0.89:attack=5", filter_str)
            self.assertIn("TP=-1.5", filter_str)

        # 2. Explosive segments: protective limiter limit (0.82) and TP (-2.0)
        script_explosive = [{"index": 1, "speaker": "Geralt", "intensity_level": "explosive"}]
        with patch("subprocess.run", side_effect=fake_ffmpeg) as mock_sub:
            concatenate_and_master_chapter([chunk], out_master, script_segments=script_explosive)
            cmd_args = mock_sub.call_args[0][0]
            filter_str = cmd_args[cmd_args.index("-af") + 1]
            self.assertIn("alimiter=limit=0.82:attack=2", filter_str)
            self.assertIn("TP=-2.0", filter_str)

    def test_04_dynamic_reverb_presets_mapping(self):
        """Verify dynamic reverb strings and send volumes adapt to acoustic presets."""
        # Cathedral / Crypt: large tail
        cath_filter, cath_vol = get_reverb_filter_string("cathedral_crypt")
        self.assertIn("100|180|260", cath_filter)
        self.assertEqual(cath_vol, 0.32)

        # Open road / Exterior: subtle presence
        ext_filter, ext_vol = get_reverb_filter_string("open_road_forest")
        self.assertIn("20|40", ext_filter)
        self.assertEqual(ext_vol, 0.05)

        # Bedroom / Intimate: tight room
        bed_filter, bed_vol = get_reverb_filter_string("bedroom_study")
        self.assertIn("30|60|90", bed_filter)
        self.assertEqual(bed_vol, 0.18)

        # Graph assembly with cathedral preset
        fg = assemble_master_filter_graph(has_foley=True, reverb_preset="cathedral")
        self.assertIn("100|180|260", fg)
        self.assertIn("volume=0.32", fg)

    def test_05_whisper_safe_sidechain_threshold(self):
        """Verify sidechain threshold at 0.018 linear (-34.9 dBFS) protects whispers."""
        # Configured threshold
        fg_whisper = assemble_master_filter_graph(has_foley=True, sidechain_threshold=0.018)
        self.assertIn("sidechaincompress=threshold=0.018", fg_whisper)

        # Default legacy compatibility threshold
        fg_default = assemble_master_filter_graph(has_foley=True)
        self.assertIn("sidechaincompress=threshold=0.03", fg_default)

    def test_06_cinema_audio_engine_dx_stem_format(self):
        """Verify render_discrete_stems generates a 48kHz stereo DX stem."""
        vocal_wav = self.project_dir / "chapter_001_dialogue.wav"
        with wave.open(str(vocal_wav), "wb") as wf:
            wf.setnchannels(1)  # Mono input
            wf.setsampwidth(2)
            wf.setframerate(24000)  # 24kHz
            wf.writeframes(b"\x00\x00" * 48000)  # 2 seconds

        manifest = CreativeManifest(
            chapter_id="c001_test",
            total_duration_ms=2000,
            silence_percentage=75.0,
            ambience_scenes=[AmbienceScene(scene_id=1, scene_name="forest", asset_path="wind_howl.ogg", start_ms=0, end_ms=2000)],
            mastering=MasteringSettings(),
        )
        cinema_manifest = LegacyCreativeManifestAdapter.lift_legacy_manifest_to_cinema(manifest)

        out_dir = self.project_dir / "mastered"
        out_dir.mkdir(parents=True, exist_ok=True)

        stems = render_discrete_stems(
            manifest=cinema_manifest,
            dialogue_wav=vocal_wav,
            output_dir=out_dir,
        )

        dx_file = out_dir / "c001_test_stem_DX.wav"
        self.assertTrue(dx_file.exists())
        with wave.open(str(dx_file), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 2, "DX stem must be standardized to 2-channel stereo")
            self.assertEqual(wf.getframerate(), 48000, "DX stem must be standardized to 48kHz")


if __name__ == "__main__":
    unittest.main()
