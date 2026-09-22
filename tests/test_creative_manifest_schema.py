#!/usr/bin/env python3
"""
Test Suite for Creative Manifest & Pydantic Contracts (Pillar 3)
==================================================================
Strictly tests Pydantic v2 schemas and validation contracts:
1. Asserts that manifests with < 60% silence fail immediately with ManifestValidationError.
2. Asserts that valid manifests parse and serialize cleanly (JSON and dict round-trips).
3. Asserts CharacterProfile and CharacterRoster query, resolution, and mutation contracts.
4. Asserts ProjectConfig broadcast loudness constraints (-70 to 0 LUFS, <= 0 dBTP).
5. Asserts sub-model validations for MusicCue, FoleyCue, AmbienceScene, and MasteringConfig.
"""

import json
import sys
import unittest
from pathlib import Path
from pydantic import ValidationError

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.contracts import (
    ManifestValidationError,
    ProjectConfig,
    CharacterProfile,
    CharacterRoster,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    CreativeManifest,
)


class TestCreativeManifestSilenceConstraint(unittest.TestCase):
    """Verifies that the Audio Drama standard 60.0% silence rule is strictly enforced."""

    def test_01_silence_below_60_fails_on_initialization(self):
        """CreativeManifest rejects silence_percentage < 60.0% upon model creation."""
        invalid_percentages = [59.9, 59.0, 50.0, 30.0, 10.0, 0.0, -5.0]
        for sp in invalid_percentages:
            with self.subTest(silence_percentage=sp):
                with self.assertRaises((ManifestValidationError, ValidationError)) as ctx:
                    CreativeManifest(
                        chapter_id="chap_test_fail",
                        silence_percentage=sp,
                    )
                self.assertIn("Silence violation", str(ctx.exception))

    def test_02_silence_at_or_above_60_succeeds(self):
        """CreativeManifest accepts silence_percentage >= 60.0%."""
        valid_percentages = [60.0, 60.1, 65.0, 75.0, 90.0, 100.0]
        for sp in valid_percentages:
            with self.subTest(silence_percentage=sp):
                manifest = CreativeManifest(
                    chapter_id="chap_test_pass",
                    silence_percentage=sp,
                )
                self.assertEqual(manifest.silence_percentage, round(sp, 2))

    def test_03_default_silence_is_100_percent(self):
        """When silence_percentage is omitted, it defaults to pure acoustic silence (100.0%)."""
        manifest = CreativeManifest(chapter_id="chap_default")
        self.assertEqual(manifest.silence_percentage, 100.0)

    def test_04_validate_acoustic_rules_detects_music_overuse(self):
        """Acoustic rules validator catches excessive music cue duration relative to chapter length."""
        # 100-second chapter (100,000 ms) with 45 seconds of music (55% silence < 60%)
        manifest = CreativeManifest(
            chapter_id="chap_acoustic_fail",
            silence_percentage=100.0,
            music_cues=[
                MusicCue(
                    cue_id="mc_01",
                    cue_type="EMOTIONAL_UNDERSCORE",
                    track_name="Gentle Strings",
                    section_name="INTRO_BED",
                    start_ms=10000,
                    duration_ms=45000,
                )
            ],
            total_duration_ms=100000,
        )

        with self.assertRaises(ManifestValidationError) as ctx:
            manifest.validate_acoustic_rules()
        self.assertIn("Silence violation", str(ctx.exception))

    def test_05_validate_acoustic_rules_passes_with_sufficient_silence(self):
        """Acoustic rules validator succeeds and recalibrates silence percentage when >= 60%."""
        # 100-second chapter with 25 seconds of music (75% silence >= 60%)
        manifest = CreativeManifest(
            chapter_id="chap_acoustic_pass",
            silence_percentage=100.0,
            music_cues=[
                MusicCue(
                    cue_id="mc_01",
                    cue_type="TRANSITION_BRIDGE",
                    track_name="Brass Stinger",
                    section_name="CLIMAX_DROP",
                    start_ms=5000,
                    duration_ms=25000,
                )
            ],
            total_duration_ms=100000,
        )
        manifest.validate_acoustic_rules()
        self.assertEqual(manifest.silence_percentage, 75.0)


class TestCreativeManifestSerialization(unittest.TestCase):
    """Verifies complete, lossless JSON and dictionary serialization/deserialization."""

    def setUp(self):
        self.manifest = CreativeManifest(
            manifest_version="3.0",
            project_id="test_project_novel",
            chapter_id="chapter_001",
            silence_percentage=72.5,
            mastering=MasteringConfig(
                target_lufs=-19.0,
                true_peak_dbtp=-1.5,
                ducking_attenuation_db=-16.0,
                ducking_attack_ms=20,
                ducking_release_ms=300,
                spectral_carve_hz=2200,
                spectral_carve_gain_db=-5.5,
            ),
            ambience_scenes=[
                AmbienceScene(
                    scene_id=1,
                    start_ms=0,
                    end_ms=60000,
                    asset_path="/sounds/amb_workshop.wav",
                    target_lufs=-32.0,
                    reverb_preset="room",
                )
            ],
            music_cues=[
                MusicCue(
                    cue_id="mc_001",
                    cue_type="EMOTIONAL_UNDERSCORE",
                    track_name="Mystery of the Gears",
                    section_name="INTRO_BED",
                    start_ms=15000,
                    duration_ms=20000,
                    fade_in_ms=2000,
                    fade_out_ms=3000,
                    volume_db=-18.0,
                    dramatic_justification="Build suspense around the clock mechanism.",
                )
            ],
            foley_cues=[
                FoleyCue(
                    cue_id="fc_001",
                    segment_index=2,
                    anchor_word="turned",
                    pre_roll_ms=100,
                    asset_path="/sounds/gear_turn.wav",
                    gain_dbfs=-15.0,
                    azimuth_pan=-0.3,
                    reverb_send=0.15,
                    start_ms=22000,
                    duration_ms=800,
                )
            ],
            total_duration_ms=90000,
            metadata={"source_novel": "The Clockmaker's Secret", "scene_count": 3},
        )

    def test_01_json_round_trip(self):
        """Serialize to JSON string and parse back into CreativeManifest without data loss."""
        json_str = self.manifest.to_json(indent=2)
        self.assertIsInstance(json_str, str)

        parsed = CreativeManifest.from_json(json_str)
        self.assertEqual(parsed.chapter_id, self.manifest.chapter_id)
        self.assertEqual(parsed.silence_percentage, self.manifest.silence_percentage)
        self.assertEqual(parsed.mastering.target_lufs, -19.0)
        self.assertEqual(parsed.mastering.true_peak_dbtp, -1.5)
        self.assertEqual(len(parsed.ambience_scenes), 1)
        self.assertEqual(len(parsed.music_cues), 1)
        self.assertEqual(len(parsed.foley_cues), 1)
        self.assertEqual(parsed.music_cues[0].cue_id, "mc_001")
        self.assertEqual(parsed.foley_cues[0].anchor_word, "turned")
        self.assertEqual(parsed.metadata["source_novel"], "The Clockmaker's Secret")

    def test_02_dict_round_trip(self):
        """Serialize to Python dict and parse back into CreativeManifest."""
        data_dict = self.manifest.to_dict()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict["silence_percentage"], 72.5)

        restored = CreativeManifest.from_dict(data_dict)
        self.assertEqual(restored.project_id, self.manifest.project_id)
        self.assertEqual(restored.total_duration_ms, 90000)

    def test_03_compatibility_version_alias(self):
        """Accepts legacy 'version' key as an alias for 'manifest_version'."""
        data = {
            "version": "3.0",
            "chapter_id": "chapter_legacy",
            "silence_percentage": 80.0,
        }
        manifest = CreativeManifest.from_dict(data)
        self.assertEqual(manifest.manifest_version, "3.0")


class TestCharacterRosterSchema(unittest.TestCase):
    """Verifies dynamic, novel-agnostic CharacterProfile and CharacterRoster management."""

    def test_01_character_profile_validation(self):
        """Validates character profile creation and constraints."""
        profile = CharacterProfile(
            character_uuid="char_001",
            display_name="Jeremy the Clockmaker",
            gender="male",
            assigned_voice_id="Puck",
            pitch_shift=-1.5,
            speed_multiplier=0.95,
        )
        self.assertEqual(profile.display_name, "Jeremy the Clockmaker")
        self.assertEqual(profile.speed_multiplier, 0.95)

        # Speed multiplier out of bounds (< 0.5 or > 2.0)
        with self.assertRaises(ValidationError):
            CharacterProfile(
                character_uuid="char_fail",
                display_name="Speedy",
                gender="neutral",
                assigned_voice_id="Charon",
                speed_multiplier=2.5,
            )

    def test_02_character_roster_operations(self):
        """Tests roster registration, UUID search, case-insensitive name resolution, and voice fallback."""
        roster = CharacterRoster(project_id="novel_clockmaker")

        jeremy = CharacterProfile(
            character_uuid="c_jeremy",
            display_name="Jeremy",
            gender="male",
            assigned_voice_id="Fenrir",
        )
        eliza = CharacterProfile(
            character_uuid="c_eliza",
            display_name="Eliza",
            gender="female",
            assigned_voice_id="Kore",
        )

        roster.add_character(jeremy)
        roster.add_character(eliza)

        # Retrieval by UUID
        self.assertEqual(roster.get_by_id("c_jeremy"), jeremy)
        self.assertIsNone(roster.get_by_id("non_existent"))

        # Case-insensitive retrieval by display name
        self.assertEqual(roster.get_by_name("JEREMY"), jeremy)
        self.assertEqual(roster.get_by_name("  eliza  "), eliza)
        self.assertIsNone(roster.get_by_name("Unknown Character"))

        # Dynamic voice resolution with fallback
        self.assertEqual(roster.get_voice_for_character("Jeremy"), "Fenrir")
        self.assertEqual(roster.get_voice_for_character("Eliza"), "Kore")
        self.assertEqual(roster.get_voice_for_character("Mysterious Stranger", fallback_voice="Aoede"), "Aoede")

    def test_03_roster_update_idempotency(self):
        """Adding a character with an existing UUID or name updates the existing profile."""
        roster = CharacterRoster(project_id="novel_clockmaker")
        p1 = CharacterProfile(character_uuid="u1", display_name="Jeremy", gender="male", assigned_voice_id="Puck")
        p2 = CharacterProfile(character_uuid="u1", display_name="Jeremy", gender="male", assigned_voice_id="Charon")

        roster.add_character(p1)
        roster.add_character(p2)

        self.assertEqual(len(roster.characters), 1)
        self.assertEqual(roster.get_by_id("u1").assigned_voice_id, "Charon")


class TestProjectConfigSchema(unittest.TestCase):
    """Verifies ProjectConfig broadcast mastering validation and metadata requirements."""

    def test_01_valid_project_config(self):
        """Instantiates valid ProjectConfig with default broadcast mastering values."""
        cfg = ProjectConfig(
            project_id="proj_clockmaker",
            title="The Clockmaker's Secret",
            author="A. Pendelton",
            source_language="en",
            assets_dir="/tmp/assets",
        )
        self.assertEqual(cfg.ebu_r128_lufs, -19.0)
        self.assertEqual(cfg.true_peak_db, -1.5)
        self.assertEqual(cfg.target_language, "hi-IN")

    def test_02_invalid_lufs_rejected(self):
        """EBU R128 loudness outside [-70.0, 0.0] LUFS raises ManifestValidationError."""
        with self.assertRaises((ManifestValidationError, ValidationError)):
            ProjectConfig(
                project_id="p1",
                title="T",
                author="A",
                source_language="en",
                assets_dir="/tmp",
                ebu_r128_lufs=5.0,  # > 0.0 is invalid
            )
        with self.assertRaises((ManifestValidationError, ValidationError)):
            ProjectConfig(
                project_id="p2",
                title="T",
                author="A",
                source_language="en",
                assets_dir="/tmp",
                ebu_r128_lufs=-75.0,  # < -70.0 is invalid
            )

    def test_03_invalid_true_peak_rejected(self):
        """True Peak ceiling > 0.0 dBTP or < -20.0 dBTP raises ManifestValidationError."""
        with self.assertRaises((ManifestValidationError, ValidationError)):
            ProjectConfig(
                project_id="p1",
                title="T",
                author="A",
                source_language="en",
                assets_dir="/tmp",
                true_peak_db=1.0,  # positive peak allows clipping
            )


class TestSubCuesAndScenesValidation(unittest.TestCase):
    """Verifies acoustic sub-schemas for MusicCue, FoleyCue, AmbienceScene."""

    def test_01_music_cue_normalization_and_timing(self):
        """Normalizes legacy cue types and enforces positive duration."""
        cue = MusicCue(
            cue_id="mc_norm",
            cue_type="CLIMACTIC_COMBAT",  # Legacy name
            track_name="Battle Track",
            section_name="CLIMAX_DROP",
            start_ms=1000,
            duration_ms=15000,
        )
        self.assertEqual(cue.cue_type, "CLIMACTIC_ACTION_CUE")

        # Negative start_ms or non-positive duration_ms raises ValidationError
        with self.assertRaises(ValidationError):
            MusicCue(
                cue_id="mc_bad",
                cue_type="TRANSITION_BRIDGE",
                track_name="Test",
                section_name="INTRO",
                start_ms=-10,
                duration_ms=5000,
            )
        with self.assertRaises(ValidationError):
            MusicCue(
                cue_id="mc_bad2",
                cue_type="TRANSITION_BRIDGE",
                track_name="Test",
                section_name="INTRO",
                start_ms=0,
                duration_ms=0,
            )

    def test_02_foley_cue_azimuth_panning_constraints(self):
        """Azimuth panning outside [-0.8, +0.8] raises validation error."""
        valid_foley = FoleyCue(
            cue_id="fc_pan_ok",
            segment_index=1,
            anchor_word="ticked",
            azimuth_pan=-0.8,
        )
        self.assertEqual(valid_foley.azimuth_pan, -0.8)

        # Outside safe stereo panning range
        with self.assertRaises(ValidationError):
            FoleyCue(
                cue_id="fc_pan_fail",
                segment_index=1,
                anchor_word="exploded",
                azimuth_pan=-0.95,
            )
        with self.assertRaises(ValidationError):
            FoleyCue(
                cue_id="fc_pan_fail2",
                segment_index=1,
                anchor_word="exploded",
                azimuth_pan=1.0,
            )

    def test_03_ambience_scene_time_bounds(self):
        """AmbienceScene enforces end_ms > start_ms."""
        # Valid scene
        scene = AmbienceScene(
            scene_id=1,
            start_ms=0,
            end_ms=15000,
            asset_path="/sounds/rain.ogg",
        )
        self.assertEqual(scene.end_ms, 15000)

        # Invalid bounds: end_ms <= start_ms
        with self.assertRaises((ManifestValidationError, ValidationError)):
            AmbienceScene(
                scene_id=2,
                start_ms=10000,
                end_ms=10000,
                asset_path="/sounds/rain.ogg",
            )
        with self.assertRaises((ManifestValidationError, ValidationError)):
            AmbienceScene(
                scene_id=3,
                start_ms=20000,
                end_ms=15000,
                asset_path="/sounds/rain.ogg",
            )


if __name__ == "__main__":
    unittest.main()
