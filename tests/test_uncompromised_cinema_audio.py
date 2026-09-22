#!/usr/bin/env python3
"""
Unit Tests for Uncompromised Next-Gen Cinema Audio Drama Architecture.
Verifies:
1. Room 1: SonicBible persistence, Leitmotif resolution, and Level 1 Guard.
2. Room 2: 4-Layer SceneSoundscapeManifest and Level 2 Guard.
3. Room 3: AcousticBusMatrix UCS resolution, dynamic ducking, and voice priority stealing.
4. Room 4: CinemaAudioEngine, discrete DME stems, and StemLedger compliance.
5. Adapter Bridge: LegacyCreativeManifestAdapter zero-regression lifting.
6. Quality Gates: Gate 3.5, Gate 5.2, Gate 5.3 validations.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.sonic_bible import (
    SonicBible,
    LeitmotifDefinition,
    WorldAcousticProfile,
    GlobalLoudnessPolicy,
)
from audiobook_factory.scene_acoustics import (
    SceneSoundscapeManifest,
    SceneAcousticProfile,
    AmbienceLayer,
)
from audiobook_factory.acoustic_bus_matrix import (
    DuckingProfile,
    get_ducking_profile,
    derive_ucs_category,
    filter_concurrency_window,
    get_spectral_pocketing_filter,
    PROFILE_COMBAT,
    PROFILE_INTIMATE,
    PROFILE_STANDARD,
)
from audiobook_factory.cinema_audio_engine import (
    CinemaAudioManifest,
    StemLedger,
    StemMetadata,
    render_discrete_stems,
)
from audiobook_factory.contracts import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    LegacyCreativeManifestAdapter,
)
from audiobook_factory.gate_auditor import (
    audit_gate3_5_acoustic_feasibility,
    audit_gate5_2_spectral_masking,
    audit_gate5_3_stereo_phase,
    AuditResult,
)


class TestSonicBibleRoom1(unittest.TestCase):
    """Test Room 1: Sonic Bible & Leitmotif Registry."""

    def setUp(self):
        self.bible = SonicBible(
            book_title="The Witcher: The Last Wish",
            project_id="witcher_book_01",
        )
        self.geralt_motif = LeitmotifDefinition(
            motif_id="lm_geralt_destiny",
            entity_type="character",
            associated_entity="Geralt of Rivia",
            track_id="001 The White Wolf.mp3",
            track_name="The White Wolf (Destiny Theme)",
            primary_instrument="solo cello / hurdy-gurdy",
            canonical_tempo_bpm=88,
            dramatic_intent="Weary moral duty and solitude",
            priority_level=10,
        )
        self.crypt_space = WorldAcousticProfile(
            env_id="crypt_tomb",
            display_name="Ancient Subterranean Crypt",
            space_type="subterranean",
            estimated_rt60_ms=2800,
            high_freq_damping=0.45,
            early_reflections_level_db=-12.0,
            reverb_tail_level_db=-15.0,
            ir_preset="cave",
        )
        self.bible.register_leitmotif(self.geralt_motif)
        self.bible.register_space(self.crypt_space)

    def test_leitmotif_and_space_resolution(self):
        """Verify dynamic lookup of leitmotifs and spaces."""
        motif = self.bible.resolve_theme_for_character("Geralt")
        self.assertIsNotNone(motif)
        self.assertEqual(motif.motif_id, "lm_geralt_destiny")
        self.assertEqual(motif.primary_instrument, "solo cello / hurdy-gurdy")

        space = self.bible.resolve_acoustic_space("crypt_tomb")
        self.assertIsNotNone(space)
        self.assertEqual(space.space_type, "subterranean")
        self.assertEqual(space.estimated_rt60_ms, 2800)

    def test_sonic_bible_persistence(self):
        """Verify dedicated sound_bible.json persistence and loading."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "sound_bible.json"
            self.bible.save_to_disk(target)
            self.assertTrue(target.exists())

            loaded = SonicBible.load_from_disk(target)
            self.assertEqual(loaded.book_title, self.bible.book_title)
            self.assertIn("geralt of rivia", loaded.leitmotifs)
            self.assertIn("crypt_tomb", loaded.acoustic_spaces)

    def test_level_1_guard_audit(self):
        """Verify Level 1 Sonic Bible Integrity Guard."""
        audit = self.bible.audit_sonic_bible_integrity()
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["checked_motifs"], 1)
        self.assertEqual(audit["checked_spaces"], 1)

        # Introduce corruption (empty instrument)
        corrupted_motif = LeitmotifDefinition(
            motif_id="lm_bad_instrument",
            entity_type="faction",
            associated_entity="Bandits",
            track_id="dummy.mp3",
            track_name="Dummy",
            primary_instrument="   ",  # Empty instrument!
            canonical_tempo_bpm=100,
            dramatic_intent="Action",
        )
        self.bible.register_leitmotif(corrupted_motif)
        audit_fail = self.bible.audit_sonic_bible_integrity()
        self.assertFalse(audit_fail["passed"])
        self.assertIn("empty primary_instrument", audit_fail["errors"][0])


class TestSceneAcousticsRoom2(unittest.TestCase):
    """Test Room 2: 4-Stem Decoupled Scene Soundscapes."""

    def test_scene_soundscape_manifest_creation_and_guard(self):
        """Verify creation, validation, and Level 2 Guard for scene soundscapes."""
        manifest = SceneSoundscapeManifest(chapter_id="chapter_008")

        # Create 4-layer scene
        layers = [
            AmbienceLayer(layer_type="base_room_tone", asset_path="wind_howl.ogg", target_lufs=-32.0),
            AmbienceLayer(layer_type="weather_elements", asset_path="rain_thunder.ogg", target_lufs=-28.0),
            AmbienceLayer(layer_type="crowd_wallah", asset_path="tavern_crowd_murmur.ogg", target_lufs=-34.0),
            AmbienceLayer(layer_type="spot_stochastic", asset_path="dungeon_cave_bed.ogg", target_lufs=-36.0),
        ]
        scene = SceneAcousticProfile(
            scene_id="sc_001_tavern_hearth",
            act_index=1,
            start_ms=0,
            end_ms=45000,
            environment_id="castle_hall",
            ir_preset="wood_hall",
            layers=layers,
            crossfade_ms=3000,
        )
        manifest.add_scene(scene)

        # Level 2 Guard audit
        audit = manifest.audit_scene_acoustics_integrity()
        self.assertTrue(audit["passed"])
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["total_scenes"], 1)
        self.assertEqual(audit["total_layers"], 4)

        # Test persistence
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "chapter_008_scene_acoustics.json"
            manifest.save_to_disk(target)
            self.assertTrue(target.exists())

            loaded = SceneSoundscapeManifest.load_from_disk(target)
            self.assertEqual(loaded.chapter_id, "chapter_008")
            self.assertEqual(len(loaded.scenes[0].layers), 4)

    def test_enforce_max_4_layers_rule(self):
        """Verify strict enforcement of max 4 layers per scene."""
        layers = [
            AmbienceLayer(layer_type="base_room_tone", asset_path="1.ogg"),
            AmbienceLayer(layer_type="weather_elements", asset_path="2.ogg"),
            AmbienceLayer(layer_type="crowd_wallah", asset_path="3.ogg"),
            AmbienceLayer(layer_type="spot_stochastic", asset_path="4.ogg"),
            AmbienceLayer(layer_type="base_room_tone", asset_path="5.ogg"),  # 5th layer!
        ]
        with self.assertRaises(ValueError):
            SceneAcousticProfile(
                scene_id="sc_bad",
                start_ms=0,
                end_ms=10000,
                layers=layers,
            )


class TestAcousticBusMatrixRoom3(unittest.TestCase):
    """Test Room 3: Dynamic Ducking, UCS taxonomy, and voice limiter."""

    def test_ucs_taxonomy_resolution(self):
        """Verify UCS category code derivation from action beat cues."""
        self.assertEqual(derive_ucs_category("Geralt drew his silver sword", "scabbard"), "WEAPSwd")
        self.assertEqual(derive_ucs_category("he parried the clash of steel", "blade"), "WEAPSwd")
        self.assertEqual(derive_ucs_category("slow footstep on gravel"), "FOLEFoot")
        self.assertEqual(derive_ucs_category("heavy body thud stone fall"), "IMPTBody")
        self.assertEqual(derive_ucs_category("cast igni fire flame burst"), "MAGCSpell")
        self.assertEqual(derive_ucs_category("unknown obscure gesture"), "MISCGnl")

    def test_ducking_profile_resolution(self):
        """Verify dynamic ducking profile resolution."""
        prof_combat = get_ducking_profile("CLIMACTIC_COMBAT")
        self.assertEqual(prof_combat.profile_name, "combat_shouting")
        self.assertEqual(prof_combat.attenuation_db, -22.0)

        prof_intimate = get_ducking_profile("whisper_confession")
        self.assertEqual(prof_intimate.profile_name, "intimate_dialogue")
        self.assertEqual(prof_intimate.attenuation_db, -10.0)

        prof_default = get_ducking_profile("narrative_exposition")
        self.assertEqual(prof_default.profile_name, "standard_speech")

    def test_voice_limiter_priority_stealing(self):
        """Verify voice limiter prevents transient clutter by dropping weak collisions."""
        cues = [
            FoleyCue(cue_id="c1", segment_index=0, anchor_word="a", start_ms=1000, gain_dbfs=-12.0),
            FoleyCue(cue_id="c2", segment_index=0, anchor_word="b", start_ms=1050, gain_dbfs=-15.0),
            FoleyCue(cue_id="c3", segment_index=0, anchor_word="c", start_ms=1100, gain_dbfs=-18.0),
            FoleyCue(cue_id="c4", segment_index=0, anchor_word="d", start_ms=1120, gain_dbfs=-24.0),  # Weakest!
            FoleyCue(cue_id="c5", segment_index=0, anchor_word="e", start_ms=1140, gain_dbfs=-10.0),  # Loudest priority steal!
        ]
        # Window 200ms, max concurrency 3
        filtered = filter_concurrency_window(cues, window_ms=200, max_concurrency=3)
        self.assertLessEqual(len(filtered), 4)
        filtered_ids = [c.cue_id for c in filtered]
        self.assertIn("c5", filtered_ids)  # Must keep loud cue
        self.assertNotIn("c4", filtered_ids)  # Weakest dropped

    def test_spectral_pocketing_filter(self):
        """Verify FFmpeg spectral notch filter string."""
        f_str = get_spectral_pocketing_filter(notch_hz=2400, depth_db=-6.0, q=1.5)
        self.assertEqual(f_str, "equalizer=f=2400:width_type=q:w=1.50:g=-6.00")


class TestLegacyAdapterBridge(unittest.TestCase):
    """Test Adapter Bridge: Lifting Legacy CreativeManifest to CinemaAudioManifest."""

    def test_lift_legacy_manifest_to_cinema(self):
        """Verify seamless lifting of Chapter 5/6 legacy manifest without data loss."""
        legacy = CreativeManifest(
            project_id="test_project",
            chapter_id="chapter_005",
            silence_percentage=68.5,
            total_duration_ms=60000,
            mastering=MasteringConfig(
                ducking_attenuation_db=-15.0,
                ducking_attack_ms=20,
                ducking_release_ms=400,
                spectral_carve_hz=2200,
                spectral_carve_gain_db=-5.0,
            ),
            ambience_scenes=[
                AmbienceScene(
                    scene_id=1,
                    start_ms=0,
                    end_ms=60000,
                    asset_path="wind_howl.ogg",
                    target_lufs=-30.0,
                    reverb_preset="room",
                )
            ],
            music_cues=[
                MusicCue(
                    cue_id="mc_01",
                    cue_type="BGM_MAIN",
                    track_name="001 The White Wolf.mp3",
                    section_name="INTRO_BED",
                    start_ms=5000,
                    duration_ms=15000,
                )
            ],
            foley_cues=[
                FoleyCue(
                    cue_id="fc_01",
                    segment_index=1,
                    anchor_word="draw",
                    asset_path="sword_draw_scabbard.wav",
                    start_ms=5200,
                )
            ],
        )

        cinema_manifest = LegacyCreativeManifestAdapter.lift_legacy_manifest_to_cinema(legacy)
        self.assertEqual(cinema_manifest.manifest_version, "4.0")
        self.assertEqual(cinema_manifest.chapter_id, "chapter_005")
        self.assertEqual(cinema_manifest.silence_percentage, 68.5)
        self.assertEqual(cinema_manifest.total_duration_sec, 60.0)
        self.assertEqual(len(cinema_manifest.music_cues), 1)
        self.assertEqual(len(cinema_manifest.foley_cues), 1)
        self.assertIsNotNone(cinema_manifest.scene_acoustics)
        self.assertEqual(len(cinema_manifest.scene_acoustics.scenes), 1)
        self.assertEqual(cinema_manifest.scene_acoustics.scenes[0].layers[0].asset_path, "wind_howl.ogg")


class TestCinemaQualityGates(unittest.TestCase):
    """Test Quality Gates: Gate 3.5, Gate 5.2, Gate 5.3."""

    def test_gate3_5_acoustic_feasibility(self):
        """Verify Gate 3.5 catches missing assets or invalid slicing."""
        manifest = CinemaAudioManifest(
            chapter_id="ch_gate_test",
            music_cues=[
                MusicCue(
                    cue_id="mc_valid",
                    cue_type="CLIMACTIC_ACTION_CUE",
                    track_name="witcher_sign_igni_fire_burst.wav",
                    section_name="INTRO_BED",
                    section_start_sec=0.5,
                    start_ms=1000,
                    duration_ms=1500,
                )
            ],
            foley_cues=[
                FoleyCue(
                    cue_id="fc_valid",
                    segment_index=0,
                    anchor_word="igni",
                    asset_path="witcher_sign_igni_fire_burst.wav",
                    start_ms=1200,
                )
            ],
        )

        res = audit_gate3_5_acoustic_feasibility(manifest)
        self.assertTrue(res.passed, f"Gate 3.5 failed unexpectedly: {res.errors}")
        self.assertEqual(res.status, "PASS")

        # Test with non-existent asset
        bad_manifest = CinemaAudioManifest(
            chapter_id="ch_gate_bad",
            music_cues=[
                MusicCue(
                    cue_id="mc_ghost",
                    cue_type="BGM_MAIN",
                    track_name="non_existent_ghost_audio_file_999.wav",
                    section_name="INTRO_BED",
                    start_ms=0,
                    duration_ms=5000,
                )
            ],
        )
        bad_res = audit_gate3_5_acoustic_feasibility(bad_manifest)
        self.assertFalse(bad_res.passed)
        self.assertEqual(bad_res.status, "FAIL")
        self.assertIn("asset not found on disk", bad_res.errors[0])

    def test_gate5_2_spectral_masking(self):
        """Verify Gate 5.2 evaluates dialogue vs music DMR in vocal corridor."""
        with tempfile.TemporaryDirectory() as td:
            d_file = Path(td) / "dialogue.wav"
            m_file = Path(td) / "music.wav"
            # Create dummy files
            d_file.write_bytes(b"RIFF" + b"\x00" * 2000)
            m_file.write_bytes(b"RIFF" + b"\x00" * 2000)

            with patch("audiobook_factory.gate_auditor.subprocess.run") as mock_run:
                # Mock FFmpeg output for dialogue -20 LUFS, music -35 LUFS -> DMR = +15 dB
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stderr="Integrated loudness:   I:   -20.0 LUFS",
                )
                res = audit_gate5_2_spectral_masking(d_file, m_file, min_dmr_db=12.0)
                # Since mock returned same for both, DMR = 0.0 -> fail
                self.assertFalse(res.passed)

                # Now mock dialogue -18 LUFS, music -34 LUFS
                def _mock_side_effect(cmd, **kwargs):
                    if str(d_file) in cmd:
                        return MagicMock(returncode=0, stderr="Integrated loudness:   I:   -18.0 LUFS")
                    return MagicMock(returncode=0, stderr="Integrated loudness:   I:   -34.0 LUFS")

                mock_run.side_effect = _mock_side_effect
                res_pass = audit_gate5_2_spectral_masking(d_file, m_file, min_dmr_db=12.0)
                self.assertTrue(res_pass.passed)
                self.assertEqual(res_pass.details["measured_dmr_db"], 16.0)

    def test_gate5_3_stereo_phase(self):
        """Verify Gate 5.3 evaluates Pearson stereo phase correlation."""
        with tempfile.TemporaryDirectory() as td:
            master_file = Path(td) / "master.wav"
            master_file.write_bytes(b"RIFF" + b"\x00" * 2000)

            with patch("audiobook_factory.gate_auditor.subprocess.run") as mock_run:
                # In-phase stereo (phase = 0.85)
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stderr="[Parsed_ametadata] lavfi.aphasemeter.phase=0.850000\n[Parsed_ametadata] lavfi.aphasemeter.phase=0.860000",
                )
                res = audit_gate5_3_stereo_phase(master_file, min_phase_correlation=0.20)
                self.assertTrue(res.passed)
                self.assertGreaterEqual(res.details["mean_phase_correlation"], 0.20)

                # Anti-phase stereo (phase = -0.45)
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stderr="[Parsed_ametadata] lavfi.aphasemeter.phase=-0.450000",
                )
                res_anti = audit_gate5_3_stereo_phase(master_file, min_phase_correlation=0.20)
                self.assertFalse(res_anti.passed)
                self.assertIn("Stereo phase cancellation hazard", res_anti.errors[0])


class TestCinemaStemLedger(unittest.TestCase):
    """Test discrete stem ledger serialization and validation."""

    def test_stem_ledger_roundtrip(self):
        """Verify StemLedger persistence and compliance reporting."""
        with tempfile.TemporaryDirectory() as td:
            ledger_file = Path(td) / "chapter_008_stem_ledger.json"
            stems = {
                "DX": StemMetadata(stem_type="DX", filepath="dx.wav", duration_sec=120.0, integrated_lufs=-19.2, true_peak_dbtp=-2.1),
                "MX": StemMetadata(stem_type="MX", filepath="mx.wav", duration_sec=120.0, integrated_lufs=-28.5, true_peak_dbtp=-6.0),
                "FX": StemMetadata(stem_type="FX", filepath="fx.wav", duration_sec=120.0, integrated_lufs=-22.0, true_peak_dbtp=-3.5),
                "AMB": StemMetadata(stem_type="AMB", filepath="amb.wav", duration_sec=120.0, integrated_lufs=-32.0, true_peak_dbtp=-12.0),
                "ME": StemMetadata(stem_type="ME", filepath="me.wav", duration_sec=120.0, integrated_lufs=-21.5, true_peak_dbtp=-3.0),
                "FULL_MASTER": StemMetadata(stem_type="FULL_MASTER", filepath="master.wav", duration_sec=120.0, integrated_lufs=-19.0, true_peak_dbtp=-1.5),
            }
            ledger = StemLedger(
                chapter_id="chapter_008",
                stems=stems,
                master_lufs=-19.0,
                master_peak=-1.5,
                compliance_status=True,
            )
            ledger.save_to_disk(ledger_file)
            self.assertTrue(ledger_file.exists())

            loaded = StemLedger.load_from_disk(ledger_file)
            self.assertEqual(loaded.chapter_id, "chapter_008")
            self.assertTrue(loaded.compliance_status)
            self.assertEqual(len(loaded.stems), 6)
            self.assertEqual(loaded.stems["DX"].integrated_lufs, -19.2)


if __name__ == "__main__":
    unittest.main()
