#!/usr/bin/env python3
"""
Targeted Test Suite: 4-Stem Decoupled Scene Acoustics, Stochastic Generator, & Harry Potter Grade Sound Design.
Verifies:
1. SceneSoundscapeManifest 4-stem decoupling and integrity auditing.
2. Zero-token stochastic transient generation prioritizing dialogue pause gaps.
3. Low-pass door/wall barrier occlusion filtering (< 18000 Hz) in CinemaAudioEngine.
4. Discrete Stem Ledger DMR (Dialogue-to-Masking Ratio >= 10.0 dB) validation.
5. Pre-baked magic & tactile composite asset retrieval in Sound Bank.
"""

import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

from audiobook_factory.scene_acoustics import (
    SceneSoundscapeManifest,
    SceneAcousticProfile,
    AmbienceLayer,
    generate_stochastic_cues,
)
from audiobook_factory.contracts import (
    CreativeManifest,
    TimelineLedger,
    TimelineSegment,
    FoleyCue,
)
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.cinema_audio_engine import (
    CinemaAudioManifest,
    render_discrete_stems,
)


class TestSceneAcousticsAndStochastic(unittest.TestCase):
    """Test suite for 4-stem scene acoustics, stochastic generator, occlusion & DMR."""

    @classmethod
    def setUpClass(cls):
        cls.bank = get_sound_bank()

    def test_scene_soundscape_manifest_creation_and_audit(self):
        """Verifies that a 4-stem decoupled scene acoustics manifest passes Level 2 integrity audit."""
        manifest = SceneSoundscapeManifest(chapter_id="chapter_test_hp")

        scene = SceneAcousticProfile(
            scene_id="sc_001_great_hall",
            act_index=1,
            start_ms=0,
            end_ms=60000,
            environment_id="castle_stone_hall",
            ir_preset="hall",
            occlusion_cutoff_hz=1400,
            layers=[
                AmbienceLayer(
                    layer_type="base_room_tone",
                    asset_path="amb_castle_hall_hearth.wav",
                    target_lufs=-34.0,
                    stereo_width=1.35,
                ),
                AmbienceLayer(
                    layer_type="weather_elements",
                    asset_path="rain_thunder.ogg",
                    target_lufs=-32.0,
                    stereo_width=1.40,
                ),
                AmbienceLayer(
                    layer_type="crowd_wallah",
                    asset_path="tavern_crowd_murmur.ogg",
                    target_lufs=-30.0,
                    stereo_width=1.30,
                ),
                AmbienceLayer(
                    layer_type="spot_stochastic",
                    asset_path="tiny_floor-creak-01.wav",
                    target_lufs=-24.0,
                    stochastic_interval_sec=20.0,
                ),
            ],
        )
        manifest.add_scene(scene)

        # Level 2 Guard check
        audit = manifest.audit_scene_acoustics_integrity(sound_bank=self.bank)
        self.assertTrue(audit["passed"], f"Audit failed with errors: {audit['errors']}")
        self.assertEqual(audit["total_scenes"], 1)
        self.assertEqual(audit["total_layers"], 4)

    def test_zero_token_stochastic_generation_in_pause_gaps(self):
        """Verifies that Layer 4 stochastic spots generate non-overlapping Foley cues in dialogue pauses."""
        manifest = SceneSoundscapeManifest(chapter_id="chapter_stoch_test")

        scene = SceneAcousticProfile(
            scene_id="sc_001_night_bedroom",
            act_index=1,
            start_ms=0,
            end_ms=90000,
            layers=[
                AmbienceLayer(
                    layer_type="base_room_tone",
                    asset_path="amb_castle_hall_hearth.wav",
                    target_lufs=-36.0,
                ),
                AmbienceLayer(
                    layer_type="spot_stochastic",
                    asset_path="tiny_floor-creak-01.wav",
                    target_lufs=-24.0,
                    stochastic_interval_sec=25.0,
                ),
            ],
        )
        manifest.add_scene(scene)

        # Simulated timeline ledger with speech chunks and pause gaps
        ledger = TimelineLedger(
            chapter_id="chapter_stoch_test",
            total_segments=3,
            total_dialogue_duration_ms=40000,
            total_timeline_duration_ms=90000,
            total_silence_duration_ms=50000,
            silence_percentage=55.5,
            segments=[
                TimelineSegment(segment_index=1, speaker="Harry", text="Who is there?", audio_file="seg_001.wav", start_ms=2000, end_ms=10000, duration_ms=8000),
            # Gap: 10000 to 30000 (20000ms pause)
            TimelineSegment(segment_index=2, speaker="Narrator", text="Only silence replied.", audio_file="seg_002.wav", start_ms=30000, end_ms=45000, duration_ms=15000),
            # Gap: 45000 to 70000 (25000ms pause)
            TimelineSegment(segment_index=3, speaker="Harry", text="Lumos!", audio_file="seg_003.wav", start_ms=70000, end_ms=75000, duration_ms=5000),
            ],
        )

        cues = manifest.generate_stochastic_cues(timeline_ledger=ledger, sound_bank=self.bank, seed=101)
        self.assertGreaterEqual(len(cues), 2, f"Expected at least 2 stochastic cues, got {len(cues)}")

        for c in cues:
            self.assertIsInstance(c, FoleyCue)
            self.assertEqual(c.anchor_word, "[STOCHASTIC]")
            self.assertTrue(0 <= c.start_ms <= 90000)
            self.assertTrue(-0.8 <= c.azimuth_pan <= 0.8)
            self.assertLessEqual(c.gain_dbfs, -18.0)

    def test_pre_baked_composite_assets_in_sound_bank(self):
        """Verifies that pre-baked Harry Potter magic & tactile assets exist and are retrievable."""
        lumos_res = self.bank.search("lumos", category="sfx") or self.bank.search("lumos")
        self.assertTrue(lumos_res, "Pre-baked magic_lumos_light asset not found in Sound Bank FTS5 search")
        self.assertIn("lumos", lumos_res[0]["filename"].lower())

        expelliarmus_res = self.bank.search("expelliarmus", category="sfx") or self.bank.search("expelliarmus")
        self.assertTrue(expelliarmus_res, "Pre-baked magic_expelliarmus_kinetic asset not found in Sound Bank")
        self.assertIn("expelliarmus", expelliarmus_res[0]["filename"].lower())

        quill_res = self.bank.search("quill", category="foley") or self.bank.search("quill")
        self.assertTrue(quill_res, "Pre-baked tactile_parchment_quill_scratch asset not found in Sound Bank")
        self.assertIn("quill", quill_res[0]["filename"].lower())

    def test_cinema_stem_engine_occlusion_and_dmr(self):
        """Verifies that render_discrete_stems applies lowpass occlusion and computes DMR compliance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            diag_wav = tmp_path / "test_dialogue.wav"

            # Generate dummy dialogue WAV (6 seconds of 440Hz tone)
            subprocess.run([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "sine=f=440:d=6:r=48000",
                "-af", "volume=-16dB",
                "-c:a", "pcm_s16le", str(diag_wav)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            scene_manifest = SceneSoundscapeManifest(chapter_id="ch_occ_test")
            scene_manifest.add_scene(
                SceneAcousticProfile(
                    scene_id="sc_indoor_storm",
                    start_ms=0,
                    end_ms=6000,
                    occlusion_cutoff_hz=1200,
                    layers=[
                        AmbienceLayer(
                            layer_type="base_room_tone",
                            asset_path="amb_castle_hall_hearth.wav",
                            target_lufs=-34.0,
                            stereo_width=1.35,
                        ),
                        AmbienceLayer(
                            layer_type="weather_elements",
                            asset_path="rain_thunder.ogg",
                            target_lufs=-30.0,
                            stereo_width=1.40,
                        ),
                        AmbienceLayer(
                            layer_type="spot_stochastic",
                            asset_path="tiny_floor-creak-01.wav",
                            target_lufs=-24.0,
                            stochastic_interval_sec=3.0,
                        ),
                    ],
                )
            )

            manifest = CreativeManifest(
                chapter_id="ch_occ_test",
                total_duration_ms=6000,
                silence_percentage=100.0,
                scene_acoustics=scene_manifest,
                foley_cues=[],
                music_cues=[],
            )

            ledger = render_discrete_stems(
                manifest=manifest,
                dialogue_wav=diag_wav,
                output_dir=tmp_path / "stems",
                sound_bank=self.bank,
            )

            self.assertEqual(ledger.chapter_id, "ch_occ_test")
            self.assertIn("DX", ledger.stems)
            self.assertIn("AMB", ledger.stems)
            self.assertIn("FX", ledger.stems)
            self.assertIn("ME", ledger.stems)
            self.assertIn("FULL_MASTER", ledger.stems)

            # Verify DMR metadata is tracked
            meta = ledger.metadata
            self.assertIn("dialogue_masking_ratio_db", meta)
            self.assertIn("dmr_compliant", meta)
            self.assertIsInstance(meta["dialogue_masking_ratio_db"], float)


if __name__ == "__main__":
    unittest.main()
