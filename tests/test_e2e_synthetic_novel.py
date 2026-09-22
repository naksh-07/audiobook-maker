#!/usr/bin/env python3
"""
End-to-End Synthetic Novel Pipeline Verification Test
======================================================
Implements a complete autonomous 3-scene audio drama book test:
Book Title  : "The Clockmaker's Secret"
Characters  : 2 Characters ("Jeremy", "Eliza") + Narrator
Assets      : 1 Ambient Background ("clockwork_ambience") + 1 Music Cue ("mystery_underscore") + 1 Foley Cue ("gear_turn")
Standard    : Full autonomous pipeline from text to screenplay to Creative Manifest to broadcast audio compilation.
"""

import json
import math
import shutil
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.contracts import (
    CreativeManifest,
    CharacterProfile,
    CharacterRoster,
    ProjectConfig,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
)
from audiobook_factory.agent_director import AgentDirector
from audiobook_factory.manifest_renderer import render_manifest_soundscape
from audiobook_factory.sound_bank import SoundBank
from audiobook_factory.soundscape import get_ffmpeg, get_audio_duration
from audiobook_factory.timeline_ledger import build_chapter_timeline_ledger
from audiobook_factory.orchestrator import PipelineOrchestrator


def generate_test_wav(
    file_path: Path,
    duration_sec: float,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    sample_rate: int = 48000,
    channels: int = 2,
) -> Path:
    """Helper to generate standard 48kHz stereo WAV files for pipeline testing."""
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


class TestE2ESyntheticNovel(unittest.TestCase):
    """Verifies the complete autonomous pipeline on a synthetic 3-scene novel."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="test_e2e_clockmaker_")
        self.tmp_path = Path(self.tmp_dir.name)
        self.ffmpeg = get_ffmpeg()

        # Project folder structure
        self.project_dir = self.tmp_path / "clockmakers_secret"
        self.scripts_dir = self.project_dir / "scripts"
        self.audio_dir = self.project_dir / "audio_chunks"
        self.sound_dir = self.project_dir / "sounds"
        self.manifests_dir = self.project_dir / "manifests"
        self.mastered_dir = self.project_dir / "mastered"
        self.bgm_dir = self.project_dir / "soundscapes"

        for d in (self.scripts_dir, self.audio_dir, self.sound_dir,
                  self.manifests_dir, self.mastered_dir, self.bgm_dir):
            d.mkdir(parents=True, exist_ok=True)

        # 1. Seed synthetic acoustic assets (1 Ambience, 1 Music, 1 Foley)
        self.amb_asset = self.sound_dir / "clockwork_ambience.ogg"
        generate_test_wav(self.amb_asset, duration_sec=12.0, frequency=220.0, amplitude=0.2)

        self.music_asset = self.sound_dir / "mystery_underscore.wav"
        generate_test_wav(self.music_asset, duration_sec=5.0, frequency=440.0, amplitude=0.3)

        self.foley_asset = self.sound_dir / "gear_turn.wav"
        generate_test_wav(self.foley_asset, duration_sec=0.4, frequency=880.0, amplitude=0.9)

        # 2. Build local SQLite FTS5 SoundBank and index assets
        self.sound_db = self.project_dir / "test_sound_bank.db"
        self.bank = SoundBank(db_path=self.sound_db, bank_root=self.sound_dir)
        with self.bank._get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sound_catalog (filename, filepath, category, subcategory, mood, tags, duration_sec) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("clockwork_ambience.ogg", str(self.amb_asset), "AMB", "Workshop", "mysterious", "clock ticking gears workshop", 12.0)
            )
            conn.execute(
                "INSERT OR REPLACE INTO sound_catalog (filename, filepath, category, subcategory, mood, tags, duration_sec) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("mystery_underscore.wav", str(self.music_asset), "MUS", "Mystery", "tense", "mystery underscore strings suspense", 5.0)
            )
            conn.execute(
                "INSERT OR REPLACE INTO sound_catalog (filename, filepath, category, subcategory, mood, tags, duration_sec) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("gear_turn.wav", str(self.foley_asset), "FOL", "Mechanical", "default", "gear click turn metal brass", 0.4)
            )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_01_character_roster_contract_for_synthetic_novel(self):
        """Verifies character roster configuration for the two characters and narrator."""
        roster = CharacterRoster(project_id="clockmakers_secret")
        jeremy = CharacterProfile(
            character_uuid="char_jeremy_001",
            display_name="Jeremy",
            gender="male",
            assigned_voice_id="Fenrir",
            pitch_shift=-1.0,
            speed_multiplier=0.96,
        )
        eliza = CharacterProfile(
            character_uuid="char_eliza_002",
            display_name="Eliza",
            gender="female",
            assigned_voice_id="Kore",
            pitch_shift=0.5,
            speed_multiplier=1.02,
        )
        roster.add_character(jeremy)
        roster.add_character(eliza)

        self.assertEqual(len(roster.characters), 2)
        self.assertEqual(roster.get_voice_for_character("Jeremy"), "Fenrir")
        self.assertEqual(roster.get_voice_for_character("Eliza"), "Kore")
        self.assertEqual(roster.get_voice_for_character("Narrator", fallback_voice="Aoede"), "Aoede")

    def test_02_e2e_autonomous_pipeline_synthetic_chapter(self):
        """
        Executes complete autonomous pipeline for 'The Clockmaker's Secret':
        - 3 scenes across 6 dialogue segments with 2 characters (Jeremy, Eliza) + Narrator
        - 1 ambient background (clockwork_ambience)
        - 1 music cue (mystery_underscore)
        - 1 foley cue (gear_turn)
        - Asserts >= 60% silence mandate, valid manifest, master audio compilation, and timeline ledger.
        """
        chapter_num = 1

        # Step A: Synthesize 3-Scene Screenplay Script
        script_data = [
            # Scene 1: The Workshop
            {
                "index": 1,
                "speaker": "Narrator",
                "text": "The workshop of Master Jeremy smelled of ancient brass, sweet lamp oil, and cedar shavings.",
                "emotion": "calm_raspy",
                "pause_after_ms": 400,
                "acoustic_env": "quiet_chamber",
            },
            {
                "index": 2,
                "speaker": "Jeremy",
                "text": "Listen closely. Every clock in this city tells a lie, except this one.",
                "emotion": "whispering",
                "pause_after_ms": 500,
                "acoustic_env": "quiet_chamber",
            },
            # Scene 2: The Mysterious Visitor
            {
                "index": 3,
                "speaker": "Narrator",
                "text": "The brass bell above the heavy oak door gave a single sharp ring as Eliza stepped inside.",
                "emotion": "neutral",
                "pause_after_ms": 350,
                "acoustic_env": "quiet_chamber",
            },
            {
                "index": 4,
                "speaker": "Eliza",
                "text": "I brought the timepiece you requested, Jeremy. Its heart beats backwards.",
                "emotion": "tense",
                "pause_after_ms": 450,
                "acoustic_env": "quiet_chamber",
            },
            # Scene 3: The Secret Revealed
            {
                "index": 5,
                "speaker": "Jeremy",
                "text": "Give it here. With one turn of the mainspring, the secret will reveal itself.",
                "emotion": "excited",
                "pause_after_ms": 400,
                "acoustic_env": "quiet_chamber",
            },
            {
                "index": 6,
                "speaker": "Narrator",
                "text": "He turned the gear, and the deep chime echoed into the quiet night.",
                "emotion": "calm_authoritative",
                "pause_after_ms": 600,
                "acoustic_env": "quiet_chamber",
            },
        ]

        script_file = self.scripts_dir / "chapter_001_hi_script.json"
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(script_data, f, indent=2)

        # Step B: Generate synthetic WAV dialogue audio chunks for each segment
        # Durations: ~2.0s per segment -> total ~12.0s dialogue
        for seg in script_data:
            idx = seg["index"]
            speaker = seg["speaker"]
            seg_file = self.audio_dir / f"c{chapter_num:03d}_s{idx:04d}_{speaker.lower()[:3]}.wav"
            freq = 400 if speaker == "Jeremy" else (600 if speaker == "Eliza" else 300)
            generate_test_wav(seg_file, duration_sec=2.0, frequency=freq, amplitude=0.4)

        # Step C: Execute Orchestrator produce_chapter
        # We mock TTSDispatcher so that local unit test does not trigger external API calls
        orchestrator = PipelineOrchestrator(self.tmp_path)

        with patch("audiobook_factory.orchestrator.TTSDispatcher.synthesize_chapter_script"):
            with patch("audiobook_factory.orchestrator.get_sound_bank", return_value=self.bank):
                with patch("audiobook_factory.agent_director.get_sound_bank", return_value=self.bank):
                    res = orchestrator.produce_chapter(
                        project_dir=self.project_dir,
                        chapter_num=chapter_num,
                        voice="Aoede",
                        workers=1,
                    )

        # Step D: Verify Pipeline Output Artifacts
        self.assertEqual(res["chapter_id"], chapter_num)

        # 1. Deterministic Master Audio Compilation delivered by pipeline
        cinematic_out = res["master_file"]
        self.assertTrue(cinematic_out.exists())
        self.assertGreater(cinematic_out.stat().st_size, 2000)

        master_dur = get_audio_duration(cinematic_out)
        self.assertGreaterEqual(master_dur, 10.0)

        # 2. Creative Manifest produced and compliant with contracts
        manifest_file = self.manifests_dir / "chapter_001_hi_manifest.json"
        self.assertTrue(manifest_file.exists())

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_json = f.read()

        manifest = CreativeManifest.from_json(manifest_json)
        self.assertEqual(manifest.chapter_id, "chapter_001")

        # Verify Silence Percentage Mandate (>= 60.0%)
        self.assertGreaterEqual(
            manifest.silence_percentage, 60.0,
            f"Silence mandate violated: got {manifest.silence_percentage}%"
        )

        # 4. Millisecond Timeline Ledger produced and contains all cues
        ledger_file = self.bgm_dir / "chapter_001_hi_timeline_ledger.json"
        self.assertTrue(ledger_file.exists())

        with open(ledger_file, "r", encoding="utf-8") as f:
            ledger_data = json.load(f)

        self.assertIn("timeline", ledger_data)
        self.assertEqual(len(ledger_data["timeline"]), 6)

        # Verify characters represented in ledger
        speakers_found = {seg["speaker"] for seg in ledger_data["timeline"]}
        self.assertIn("Jeremy", speakers_found)
        self.assertIn("Eliza", speakers_found)
        self.assertIn("Narrator", speakers_found)

    def test_03_synthetic_novel_directing_and_rendering_with_cues(self):
        """
        Explicitly exercises AgentDirector and ManifestRenderer with:
        - 1 ambient background (covering the whole 3-scene sequence)
        - 1 surgical music cue (under 40% duration to preserve >= 60% silence)
        - 1 physical foley cue (gear click on anchor word 'turned')
        """
        total_duration = 15.0
        vocal_wav = self.mastered_dir / "direct_vocal_test.wav"
        generate_test_wav(vocal_wav, duration_sec=total_duration, frequency=350, amplitude=0.4)

        # Create calibrated manifest directly conforming to standard
        manifest = CreativeManifest(
            chapter_id="chapter_synthetic_cues",
            silence_percentage=73.3,  # 4s music out of 15s = 26.7% music, 73.3% silence
            mastering=MasteringConfig(
                target_lufs=-19.0,
                true_peak_dbtp=-1.5,
                ducking_attenuation_db=-16.0,
            ),
            ambience_scenes=[
                AmbienceScene(
                    scene_id=1,
                    start_ms=0,
                    end_ms=int(total_duration * 1000),
                    asset_path=str(self.amb_asset),
                    target_lufs=-32.0,
                    reverb_preset="quiet_chamber",
                )
            ],
            music_cues=[
                MusicCue(
                    cue_id="mc_clockmaker_01",
                    cue_type="EMOTIONAL_UNDERSCORE",
                    track_name="Mystery of the Gears",
                    section_name="INTRO_BED",
                    start_ms=5000,
                    duration_ms=4000,
                    fade_in_ms=1000,
                    fade_out_ms=1000,
                    volume_db=-18.0,
                )
            ],
            foley_cues=[
                FoleyCue(
                    cue_id="fc_gear_01",
                    segment_index=5,
                    anchor_word="turned",
                    asset_path=str(self.foley_asset),
                    gain_dbfs=-15.0,
                    azimuth_pan=0.2,
                    start_ms=10000,
                    pre_roll_ms=100,
                )
            ],
            total_duration_ms=int(total_duration * 1000),
        )

        manifest.validate()

        out_master = self.mastered_dir / "synthetic_master_compiled.m4a"
        render_manifest_soundscape(
            manifest=manifest,
            vocal_track_path=vocal_wav,
            output_master_file=out_master,
            sound_bank=self.bank,
        )

        self.assertTrue(out_master.exists())
        self.assertGreater(out_master.stat().st_size, 3000)

        # Duration verification
        compiled_dur = get_audio_duration(out_master)
        self.assertAlmostEqual(compiled_dur, total_duration, delta=1.5)


if __name__ == "__main__":
    unittest.main()
