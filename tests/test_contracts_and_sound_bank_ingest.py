#!/usr/bin/env python3
"""
Unit and Integration Tests for Phase 3 (Contracts) & Phase 5 (Universal Sound Bank Ingester).
Tests:
1. Pydantic v2 Contracts (ProjectConfig, CharacterProfile, CharacterRoster, SceneSource,
   MusicCue, FoleyCue, AmbienceScene, MasteringConfig, CreativeManifest).
2. UniversalSoundBankIngester (Format probe, EBU R128 & spectral metrics, taxonomy classification,
   SQLite sound_assets table, FTS5 virtual table synchronization, and search).
"""

import sys
import json
import wave
import tempfile
import unittest
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.contracts import (
    ProjectConfig,
    CharacterProfile,
    CharacterRoster,
    SceneSource,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    CreativeManifest,
    ManifestValidationError,
)
from audiobook_factory.sound_bank_ingest import UniversalSoundBankIngester


class TestPydanticContracts(unittest.TestCase):
    """Verify Phase 3 Pydantic v2 Contracts & Schema Invariants."""

    def test_01_project_config(self):
        """Verify ProjectConfig defaults, valid values, and validation bounds."""
        cfg = ProjectConfig(
            project_id="novel_witcher",
            title="The Last Wish",
            author="Andrzej Sapkowski",
            source_language="en",
            assets_dir="/path/to/assets",
        )
        self.assertEqual(cfg.project_id, "novel_witcher")
        self.assertEqual(cfg.target_language, "hi-IN")
        self.assertEqual(cfg.ebu_r128_lufs, -19.0)
        self.assertEqual(cfg.true_peak_db, -1.5)

        # Rejection of invalid LUFS or True Peak
        with self.assertRaises(ValueError):
            ProjectConfig(
                project_id="p1", title="T", author="A", source_language="en",
                assets_dir=".", ebu_r128_lufs=5.0  # Above 0 LUFS is invalid
            )
        with self.assertRaises(ValueError):
            ProjectConfig(
                project_id="p1", title="T", author="A", source_language="en",
                assets_dir=".", true_peak_db=1.0  # Above 0 dBTP is invalid
            )

    def test_02_character_roster_zero_hardcoding(self):
        """Verify dynamic character profile and roster management with zero hardcoding."""
        roster = CharacterRoster(project_id="proj_fantasy")
        self.assertEqual(len(roster.characters), 0)

        c1 = CharacterProfile(
            character_uuid="char_001",
            display_name="Geralt of Rivia",
            gender="male",
            assigned_voice_id="Charon",
            pitch_shift=-1.5,
            speed_multiplier=0.95,
        )
        c2 = CharacterProfile(
            character_uuid="char_002",
            display_name="Yennefer",
            gender="female",
            assigned_voice_id="Kore",
            pitch_shift=0.5,
            speed_multiplier=1.05,
        )
        roster.add_character(c1)
        roster.add_character(c2)

        self.assertEqual(len(roster.characters), 2)
        # Lookup by UUID
        self.assertEqual(roster.get_by_id("char_001").display_name, "Geralt of Rivia")
        self.assertIsNone(roster.get_by_id("char_999"))

        # Lookup by Name (case-insensitive)
        self.assertEqual(roster.get_by_name("yennefer").assigned_voice_id, "Kore")
        self.assertEqual(roster.get_by_name("GERALT OF RIVIA").assigned_voice_id, "Charon")

        # Fallback voice resolution for uncast characters
        self.assertEqual(roster.get_voice_for_character("Geralt of Rivia"), "Charon")
        self.assertEqual(roster.get_voice_for_character("Random Guard", fallback_voice="Puck"), "Puck")

    def test_03_scene_source_gate_1(self):
        """Verify SceneSource Gate 1 SHA-256 generation and dialogue integrity."""
        scene = SceneSource.create_with_hash(
            scene_id=1,
            narrative_act="ACT_I_INTRO",
            text_chunks=["The tavern door opened slowly, letting the cold mountain wind howl inside."],
            dialogue_lines=[
                {"speaker": "Innkeeper", "text": "Who is there?"},
                {"speaker": "Witcher", "text": "A traveler seeking a room."},
            ],
            emotion_tags=["mysterious", "tense"],
        )
        self.assertEqual(scene.scene_id, 1)
        self.assertEqual(scene.narrative_act, "ACT_I_INTRO")
        self.assertGreater(scene.word_count, 10)
        self.assertEqual(len(scene.source_hash), 64)  # Valid SHA-256 hex string
        self.assertEqual(scene.emotion_tags, ["mysterious", "tense"])

    def test_04_music_cue_and_normalization(self):
        """Verify MusicCue properties and automatic normalization of legacy cue types."""
        cue = MusicCue(
            cue_id="mc_01",
            cue_type="TRANSITION_BRIDGE",
            track_id=42,
            track_name="The White Wolf",
            section_name="INTRO_BED",
            start_ms=1000,
            duration_ms=4000,
            fade_in_ms=1500,
            fade_out_ms=2500,
            volume_db=-16.0,
            dramatic_justification="Introductory tone setter",
        )
        self.assertEqual(cue.cue_type, "TRANSITION_BRIDGE")
        self.assertEqual(cue.duration_ms, 4000)

        # Verify normalization of CLIMACTIC_COMBAT -> CLIMACTIC_ACTION_CUE
        cue_combat = MusicCue(
            cue_id="mc_02",
            cue_type="CLIMACTIC_COMBAT",
            track_id=43,
            track_name="Silver for Monsters",
            section_name="CLIMAX_DROP",
            start_ms=5000,
            duration_ms=8000,
        )
        self.assertEqual(cue_combat.cue_type, "CLIMACTIC_ACTION_CUE")

        # Rejection of negative durations
        with self.assertRaises(ValueError):
            MusicCue(
                cue_id="mc_bad",
                cue_type="EMOTIONAL_UNDERSCORE",
                track_name="Track",
                section_name="BED",
                start_ms=0,
                duration_ms=-100,  # Negative duration invalid
            )

    def test_05_foley_cue_azimuth_bounds(self):
        """Verify FoleyCue azimuth pan validation constraint between -0.8 and +0.8."""
        fc_center = FoleyCue(
            cue_id="fc_01",
            segment_index=2,
            anchor_word="sword",
            pre_roll_ms=80,
            asset_id=7,
            asset_path="/assets/sword_clash.wav",
            gain_dbfs=-14.0,
            azimuth_pan=0.0,
        )
        self.assertEqual(fc_center.azimuth_pan, 0.0)

        fc_left = FoleyCue(
            cue_id="fc_02",
            segment_index=3,
            anchor_word="footstep",
            pre_roll_ms=50,
            asset_path="/assets/footstep.wav",
            gain_dbfs=-18.0,
            azimuth_pan=-0.8,
        )
        self.assertEqual(fc_left.azimuth_pan, -0.8)

        # Reject out-of-bounds azimuth pan
        with self.assertRaises(ValueError):
            FoleyCue(
                cue_id="fc_bad",
                segment_index=1,
                anchor_word="blast",
                asset_path="/assets/blast.wav",
                gain_dbfs=-10.0,
                azimuth_pan=0.95,  # Exceeds 0.8
            )

    def test_06_ambience_scene_time_bounds(self):
        """Verify AmbienceScene time boundaries."""
        amb = AmbienceScene(
            scene_id=1,
            start_ms=0,
            end_ms=12000,
            asset_path="/assets/wind.ogg",
            target_lufs=-30.0,
            reverb_preset="wood_hall",
        )
        self.assertEqual(amb.reverb_preset, "wood_hall")
        self.assertEqual(amb.end_ms, 12000)

        # Reject end_ms <= start_ms
        with self.assertRaises(ValueError):
            AmbienceScene(
                scene_id=2,
                start_ms=5000,
                end_ms=4000,  # end before start
                asset_path="/assets/wind.ogg",
            )

    def test_07_mastering_config(self):
        """Verify MasteringConfig broadcast settings."""
        m_cfg = MasteringConfig(
            target_lufs=-19.0,
            true_peak_dbtp=-1.5,
            ducking_attenuation_db=-16.0,
            ducking_attack_ms=15,
            ducking_release_ms=350,
            spectral_carve_hz=2200,
            spectral_carve_gain_db=-5.5,
        )
        self.assertEqual(m_cfg.ducking_attenuation_db, -16.0)
        self.assertEqual(m_cfg.spectral_carve_hz, 2200)

        # Verify true_peak_db alias
        m_cfg_alias = MasteringConfig(true_peak_db=-2.0)
        self.assertEqual(m_cfg_alias.true_peak_dbtp, -2.0)

    def test_08_creative_manifest_silence_rule(self):
        """Verify CreativeManifest silence rule validation (>= 60.0% required)."""
        manifest = CreativeManifest(
            project_id="proj_witcher",
            chapter_id="chapter_001",
            silence_percentage=65.0,
            total_duration_ms=100000,
            music_cues=[
                MusicCue(
                    cue_id="mc_01",
                    cue_type="EMOTIONAL_UNDERSCORE",
                    track_name="Solemn",
                    section_name="INTRO_BED",
                    start_ms=0,
                    duration_ms=25000,
                )
            ],
        )
        self.assertEqual(manifest.manifest_version, "3.0")
        self.assertEqual(manifest.silence_percentage, 65.0)

        # Verify serialization and deserialization
        manifest_dict = manifest.to_dict()
        self.assertIn("music_cues", manifest_dict)
        manifest_restored = CreativeManifest.from_dict(manifest_dict)
        self.assertEqual(manifest_restored.chapter_id, "chapter_001")

        # JSON serialization
        j_str = manifest.to_json()
        manifest_from_json = CreativeManifest.from_json(j_str)
        self.assertEqual(manifest_from_json.silence_percentage, 65.0)

        # Silence violation (< 60.0%) must raise validation error
        with self.assertRaises(ValueError):
            CreativeManifest(
                project_id="p1",
                chapter_id="ch_violator",
                silence_percentage=45.0,  # Violates 60% rule
            )


class TestUniversalSoundBankIngester(unittest.TestCase):
    """Verify Phase 5 Universal Sound Bank Ingester with real audio synthesis and SQLite FTS5."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)
        self.db_path = self.tmp_path / "test_sound_bank.db"
        self.audio_dir = self.tmp_path / "sounds"
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.ingester = UniversalSoundBankIngester(db_path=self.db_path, bank_root=self.tmp_path)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _create_synthetic_audio(self, filename: str, duration_sec: float = 1.0, sample_rate: int = 48000) -> Path:
        """Generate a valid WAV audio file with PCM 16-bit audio for ingestion testing."""
        file_path = self.audio_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        num_samples = int(duration_sec * sample_rate)
        # Create subtle 440Hz test tone
        import math
        frames = bytearray()
        for i in range(num_samples):
            val = int(8000 * math.sin(2 * math.pi * 440.0 * (i / sample_rate)))
            frames.extend(val.to_bytes(2, byteorder="little", signed=True))
            frames.extend(val.to_bytes(2, byteorder="little", signed=True))  # stereo

        with wave.open(str(file_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(frames)
        return file_path

    def test_01_db_schema_initialization(self):
        """Verify sound_assets table and sound_assets_fts virtual table are created."""
        with self.ingester._get_conn() as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
            self.assertIn("sound_assets", tables)
            self.assertIn("sound_assets_fts", tables)

    def test_02_classify_semantics(self):
        """Verify semantic taxonomy classifier on diverse sound asset filenames."""
        res_sword = self.ingester.classify_semantics("foley/weapons/sword_clash_metal_01.wav")
        self.assertEqual(res_sword["category"], "foley")
        self.assertEqual(res_sword["action_type"], "clash")
        self.assertEqual(res_sword["exciter"], "steel")

        res_wind = self.ingester.classify_semantics("ambience/exterior/mountain_wind_howl.ogg")
        self.assertEqual(res_wind["category"], "ambience")
        self.assertEqual(res_wind["action_type"], "howl")
        self.assertEqual(res_wind["exciter"], "wind")

        res_music = self.ingester.classify_semantics("music/stems/theme_orchestral_bed.mp3")
        self.assertEqual(res_music["category"], "music")

    def test_03_probe_and_ingest_single_file(self):
        """Verify probe_format, probe_audio_metrics, and ingest_file on synthetic audio."""
        wav_path = self._create_synthetic_audio("sword_draw_steel.wav", duration_sec=1.5)
        aid = self.ingester.ingest_file(wav_path)
        self.assertIsNotNone(aid)

        asset = self.ingester.get_asset_by_id(aid)
        self.assertIsNotNone(asset)
        self.assertEqual(asset["filename"], "sword_draw_steel.wav")
        self.assertAlmostEqual(asset["duration_sec"], 1.5, delta=0.2)
        self.assertEqual(asset["sample_rate"], 48000)
        self.assertEqual(asset["channels"], 2)
        self.assertEqual(asset["action_type"], "draw")
        self.assertEqual(asset["exciter"], "steel")
        self.assertGreater(asset["integrated_lufs"], -70.0)

    def test_04_batch_directory_ingestion(self):
        """Verify recursive batch ingestion of multiple audio files."""
        self._create_synthetic_audio("foley/boots_leather_step_01.wav", duration_sec=0.5)
        self._create_synthetic_audio("foley/boots_leather_step_02.wav", duration_sec=0.6)
        self._create_synthetic_audio("ambience/tavern_room_tone.wav", duration_sec=2.0)

        stats = self.ingester.ingest_directory(self.audio_dir, recursive=True, max_workers=2)
        self.assertEqual(stats["scanned"], 3)
        self.assertEqual(stats["ingested"], 3)
        self.assertEqual(stats["failed"], 0)
        self.assertGreater(stats["total_duration_sec"], 2.5)

    def test_05_fts5_full_text_search(self):
        """Verify SQLite FTS5 search and taxonomy filtering."""
        self._create_synthetic_audio("sword_hit_iron.wav", duration_sec=1.0)
        self._create_synthetic_audio("boots_mud_step.wav", duration_sec=0.8)
        self._create_synthetic_audio("campfire_burn_crackle.wav", duration_sec=3.0)

        self.ingester.ingest_directory(self.audio_dir, recursive=True, max_workers=2)

        # Search by keyword
        sword_results = self.ingester.search("sword")
        self.assertEqual(len(sword_results), 1)
        self.assertEqual(sword_results[0]["filename"], "sword_hit_iron.wav")

        # Search by exciter
        fire_results = self.ingester.search("burn", exciter="fire")
        self.assertEqual(len(fire_results), 1)
        self.assertEqual(fire_results[0]["filename"], "campfire_burn_crackle.wav")

        # Search by action_type
        step_results = self.ingester.search("", action_type="footstep")
        self.assertEqual(len(step_results), 1)
        self.assertEqual(step_results[0]["filename"], "boots_mud_step.wav")

    def test_06_catalog_stats_aggregation(self):
        """Verify get_stats aggregates catalog metrics accurately."""
        self._create_synthetic_audio("coin_clink_gold.wav", duration_sec=1.0)
        self._create_synthetic_audio("wind_storm_howl.wav", duration_sec=2.0)
        self.ingester.ingest_directory(self.audio_dir, recursive=True, max_workers=2)

        stats = self.ingester.get_stats()
        self.assertGreaterEqual(stats["total_assets"], 2)
        self.assertGreater(stats["total_duration_minutes"], 0.0)
        self.assertIn("by_category", stats)
        self.assertIn("top_actions", stats)


if __name__ == "__main__":
    unittest.main()
