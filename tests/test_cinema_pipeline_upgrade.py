#!/usr/bin/env python3
"""
Test Suite: Cinema Audio Pipeline Upgrade (Hollywood / Audible Benchmark)
==========================================================================
Verifies the production upgrades inspired by Audible/Pottermore's Harry Potter:
1. Dynamic micro-pauses and breath pre-rolls in mastering (pause_after_ms & pre_roll_breath_ms).
2. Multi-scene, multi-layer environmental ambience compositor.
3. Hardened quality gates (Gate 1 with List[CharacterProfile], Gate 5 fail-hard, Gate 5.3 mono/phase).
4. Safe Auto-Janitor preserving dialogue masters and discrete DME stems.
5. Pipeline orchestrator cutover to discrete stems.
"""

import json
import math
import os
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    CharacterProfile,
    CharacterRoster,
    LegacyCreativeManifestAdapter,
)
from audiobook_factory.scene_acoustics import (
    SceneSoundscapeManifest,
    SceneAcousticProfile,
    AmbienceLayer,
)
from audiobook_factory.acoustic_bus_matrix import DuckingProfile, PROFILE_STANDARD
from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.cinema_audio_engine import (
    render_discrete_stems,
    CinemaAudioManifest,
    StemLedger,
)
from audiobook_factory.gate_auditor import (
    audit_gate1_roster,
    audit_gate5_master,
    audit_gate5_3_stereo_phase,
    audit_gate3_5_acoustic_feasibility,
    GateAuditError,
    AuditResult,
)
from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.soundscape import get_ffmpeg, get_audio_duration
from audiobook_factory.orchestrator import PipelineOrchestrator


def generate_synthetic_wav(
    file_path: Path,
    duration_sec: float,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    sample_rate: int = 48000,
    channels: int = 2,
) -> Path:
    """Helper to generate standard 48kHz WAV files for audio testing."""
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


class TestMasteringDynamicPauses(unittest.TestCase):
    """Test dynamic micro-pause and breath injection in concatenate_and_master_chapter."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def test_dynamic_pause_and_breath_injection(self):
        """Verify pauses vary according to pause_after_ms and pre_roll_breath_ms."""
        seg1 = self.tmp_dir / "c001_s0001_nar.wav"
        seg2 = self.tmp_dir / "c001_s0002_cha.wav"
        generate_synthetic_wav(seg1, duration_sec=1.0, frequency=400.0)
        generate_synthetic_wav(seg2, duration_sec=1.0, frequency=500.0)

        out_wav = self.tmp_dir / "mastered_dialogue.wav"

        script_segments = [
            {"index": 1, "speaker": "Narrator", "pause_after_ms": 1200, "pre_roll_breath_ms": 0},
            {"index": 2, "speaker": "Character", "pause_after_ms": 800, "pre_roll_breath_ms": 250},
        ]

        concatenate_and_master_chapter([seg1, seg2], out_wav, script_segments=script_segments)
        self.assertTrue(out_wav.exists())
        dur = get_audio_duration(out_wav)
        # Expected duration:
        # seg1 (1.0s) + pause_after 1200ms (1.2s) + breath 250ms (0.25s) + seg2 (1.0s) = ~3.45s
        self.assertAlmostEqual(dur, 3.45, delta=0.25)


class TestHardenedQualityGates(unittest.TestCase):
    """Test quality gate hardening against fail-open bugs and format variations."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)

    def tearDown(self):
        self.td.cleanup()

    def test_gate1_accepts_list_of_character_profiles(self):
        """Verify Gate 1 handles List[CharacterProfile] input without crashing."""
        profiles = [
            CharacterProfile(
                character_uuid="char_001",
                display_name="Harry",
                gender="male",
                assigned_voice_id="Puck",
                pitch_shift=0.0,
                speed_multiplier=1.0,
            ),
            CharacterProfile(
                character_uuid="char_002",
                display_name="Hermione",
                gender="female",
                assigned_voice_id="Aoede",
                pitch_shift=1.0,
                speed_multiplier=1.05,
            ),
        ]

        registry_file = self.tmp_dir / "voice_registry.json"
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump({
                "Harry": {"voice": "Puck", "pitch": 0.0, "speed": 1.0},
                "Hermione": {"voice": "Aoede", "pitch": 1.0, "speed": 1.05},
            }, f)

        res = audit_gate1_roster(profiles, registry_file, active_characters=["Harry", "Hermione"])
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["active_roles"], 2)

    def test_gate5_master_raises_on_probe_crash(self):
        """Verify Gate 5 raises GateAuditError when FFmpeg probe fails rather than assuming compliance."""
        dummy_file = self.tmp_dir / "corrupted_master.wav"
        dummy_file.write_bytes(b"RIFF" + b"\x00" * 2000)

        with patch("audiobook_factory.gate_auditor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="Invalid data found when processing input")
            with self.assertRaises(GateAuditError) as ctx:
                audit_gate5_master(dummy_file)
            self.assertIn("Gate 5 Failed", str(ctx.exception))

    def test_gate5_3_stereo_phase_detects_mono_and_anti_phase(self):
        """Verify Gate 5.3 recognizes mono audio as r=1.0 and rejects anti-phase."""
        # Genuine mono audio
        mono_file = self.tmp_dir / "mono.wav"
        generate_synthetic_wav(mono_file, duration_sec=1.0, channels=1)

        res_mono = audit_gate5_3_stereo_phase(mono_file, min_phase_correlation=0.20)
        self.assertTrue(res_mono.passed)
        self.assertEqual(res_mono.details.get("channel_layout"), "mono")
        self.assertEqual(res_mono.details.get("mean_phase_correlation"), 1.0)

        # Anti-phase stereo
        stereo_file = self.tmp_dir / "stereo.wav"
        generate_synthetic_wav(stereo_file, duration_sec=1.0, channels=2)

        with patch("audiobook_factory.gate_auditor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stderr="[Parsed_ametadata] lavfi.aphasemeter.phase=-0.800000",
            )
            res_anti = audit_gate5_3_stereo_phase(stereo_file, min_phase_correlation=0.20)
            self.assertFalse(res_anti.passed)
            self.assertIn("Stereo phase cancellation hazard", res_anti.errors[0])


class TestMultiSceneAmbienceCompositor(unittest.TestCase):
    """Test multi-scene ambience compositor in cinema_audio_engine.py."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)

        # Create two ambient sound files
        self.amb1 = self.tmp_dir / "tavern_amb.wav"
        self.amb2 = self.tmp_dir / "dungeon_amb.wav"
        generate_synthetic_wav(self.amb1, duration_sec=4.0, frequency=150.0, amplitude=0.2)
        generate_synthetic_wav(self.amb2, duration_sec=4.0, frequency=100.0, amplitude=0.2)

        # Dialogue wav
        self.dialogue = self.tmp_dir / "dialogue.wav"
        generate_synthetic_wav(self.dialogue, duration_sec=6.0, frequency=440.0, amplitude=0.4)

    def tearDown(self):
        self.td.cleanup()

    def test_multi_scene_rendering(self):
        """Verify render_discrete_stems mixes multiple scenes across chapter timeline."""
        scenes = [
            SceneAcousticProfile(
                scene_id="scene_001",
                start_ms=0,
                end_ms=3000,
                layers=[AmbienceLayer(layer_type="base_room_tone", asset_path=str(self.amb1), target_lufs=-32.0)],
            ),
            SceneAcousticProfile(
                scene_id="scene_002",
                start_ms=3000,
                end_ms=6000,
                layers=[AmbienceLayer(layer_type="base_room_tone", asset_path=str(self.amb2), target_lufs=-32.0)],
            ),
        ]
        scene_manifest = SceneSoundscapeManifest(chapter_id="chapter_multi_scene", scenes=scenes)

        manifest = CinemaAudioManifest(
            manifest_version="4.0",
            chapter_id="chapter_multi_scene",
            scene_acoustics=scene_manifest,
            total_duration_sec=6.0,
            ducking_policy=PROFILE_STANDARD,
        )

        out_dir = self.tmp_dir / "stems_out"
        stem_ledger = render_discrete_stems(
            manifest=manifest,
            dialogue_wav=self.dialogue,
            output_dir=out_dir,
        )

        self.assertIsInstance(stem_ledger, StemLedger)
        self.assertEqual(stem_ledger.chapter_id, "chapter_multi_scene")

        # Verify all discrete stems exist
        amb_file = out_dir / "chapter_multi_scene_stem_AMB.wav"
        me_file = out_dir / "chapter_multi_scene_stem_ME.wav"
        master_file = out_dir / "chapter_multi_scene_cinema_master.wav"
        ledger_file = out_dir / "chapter_multi_scene_stem_ledger.json"

        self.assertTrue(amb_file.exists())
        self.assertTrue(me_file.exists())
        self.assertTrue(master_file.exists())
        self.assertTrue(ledger_file.exists())

        amb_dur = get_audio_duration(amb_file)
        self.assertGreaterEqual(amb_dur, 5.0)


class TestOrchestratorCinemaCutover(unittest.TestCase):
    """Test orchestrator produce_chapter with discrete stems, quality gates, and safe auto-janitor."""

    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.td.name)
        self.project_dir = self.tmp_dir / "potter_novel"

        self.scripts_dir = self.project_dir / "scripts"
        self.audio_dir = self.project_dir / "audio_chunks"
        self.mastered_dir = self.project_dir / "mastered"
        self.manifests_dir = self.project_dir / "manifests"
        self.bgm_dir = self.project_dir / "soundscapes"
        self.sound_dir = self.project_dir / "sounds"

        for d in (self.scripts_dir, self.audio_dir, self.mastered_dir,
                  self.manifests_dir, self.bgm_dir, self.sound_dir):
            d.mkdir(parents=True, exist_ok=True)

        # 1. Script
        self.script_data = [
            {"index": 1, "type": "narration", "speaker": "Narrator", "text": "Mr. and Mrs. Dursley of number four Privet Drive.", "pause_after_ms": 600},
            {"index": 2, "type": "dialogue", "speaker": "Vernon", "text": "Little tyke!", "pause_after_ms": 400},
        ]
        self.script_file = self.scripts_dir / "chapter_001_hi_script.json"
        with open(self.script_file, "w", encoding="utf-8") as f:
            json.dump(self.script_data, f)

        # 2. Audio chunks
        self.chunk1 = self.audio_dir / "c001_s0001_nar.wav"
        self.chunk2 = self.audio_dir / "c001_s0002_ver.wav"
        generate_synthetic_wav(self.chunk1, duration_sec=1.5, frequency=300.0)
        generate_synthetic_wav(self.chunk2, duration_sec=1.5, frequency=450.0)

        # 3. Sound bank
        self.amb_asset = self.sound_dir / "privet_drive_amb.wav"
        generate_synthetic_wav(self.amb_asset, duration_sec=8.0, frequency=200.0, amplitude=0.2)
        self.sound_db = self.project_dir / "test_bank.db"
        self.bank = SoundBank(db_path=self.sound_db, bank_root=self.sound_dir)
        with self.bank._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sound_catalog (filename, filepath, category, subcategory, mood, tags, duration_sec) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("privet_drive_amb.wav", str(self.amb_asset), "AMB", "Suburbs", "calm", "wind suburb calm room tone", 8.0)
            )

    def tearDown(self):
        self.td.cleanup()

    def test_orchestrator_produce_chapter_preserves_dialogue_and_stems(self):
        """Verify produce_chapter generates stems, stem ledger, and preserves dialogue WAV."""
        orchestrator = PipelineOrchestrator(self.tmp_dir)

        with patch("audiobook_factory.orchestrator.TTSDispatcher.synthesize_chapter_script"):
            with patch("audiobook_factory.orchestrator.get_sound_bank", return_value=self.bank):
                with patch("audiobook_factory.agent_director.get_sound_bank", return_value=self.bank):
                    res = orchestrator.produce_chapter(
                        project_dir=self.project_dir,
                        chapter_num=1,
                    )

        # Master deliverable (.m4a)
        master_m4a = res["master_file"]
        self.assertTrue(master_m4a.exists())

        # Dialogue WAV must NOT be purged by Auto-Janitor!
        vocal_wav = self.mastered_dir / "chapter_001_dialogue.wav"
        if not vocal_wav.exists():
            vocal_wav = self.mastered_dir / "chapter_001_hi_dialogue.wav"
        self.assertTrue(vocal_wav.exists(), "Auto-Janitor prematurely deleted dialogue master WAV!")

        # Stem Ledger must exist
        stem_ledger_path = res["stem_ledger"]
        self.assertTrue(stem_ledger_path.exists())

        # Temporary segment chunks in audio_chunks should be purged
        remaining_chunks = list(self.audio_dir.glob("c001_*.wav"))
        self.assertEqual(len(remaining_chunks), 0, "Auto-Janitor did not purge temporary audio chunks!")


if __name__ == "__main__":
    unittest.main()
