import unittest
import tempfile
import wave
from pathlib import Path

from audiobook_factory.creative_manifest import (
    CreativeManifest,
    MusicCue,
    FoleyCue,
    AmbienceScene,
    MasteringConfig,
    ManifestValidationError,
)
from audiobook_factory.manifest_renderer import render_manifest_soundscape
from audiobook_factory.soundscape import get_audio_duration


class TestCreativeManifestAndRenderer(unittest.TestCase):
    """Test suite for Creative Manifest Schema and Layer 1 Deterministic Audio Engine."""

    def test_01_manifest_schema_and_validation(self):
        """Verify CreativeManifest serializes, deserializes, and validates properly."""
        manifest = CreativeManifest(
            chapter_id="chapter_004",
            total_duration_ms=60000,
            mastering=MasteringConfig(target_lufs=-19.0, true_peak_db=-1.5),
            music_cues=[
                MusicCue(
                    cue_id="cue_01",
                    cue_type="TRANSITION_BRIDGE",
                    track_name="001 The White Wolf.mp3",
                    section_name="INTRO_BED",
                    start_ms=5000,
                    duration_ms=10000,
                    volume_db=-18.0,
                    dramatic_justification="Arrival at the mysterious manor gates"
                )
            ],
            foley_cues=[
                FoleyCue(
                    cue_id="fol_01",
                    segment_index=1,
                    anchor_word="खींची",
                    asset_name="sword_draw",
                    asset_path="weapons/sword_draw.wav",
                    start_ms=2000,
                    gain_dbfs=-15.0,
                )
            ],
            ambience_scenes=[
                AmbienceScene(
                    scene_id=1,
                    start_ms=0,
                    end_ms=60000,
                    asset_name="wind_howl.ogg",
                    asset_path="ambience/wind_howl.ogg",
                    target_lufs=-32.0,
                )
            ]
        )

        manifest.validate()
        self.assertGreaterEqual(manifest.silence_percentage, 80.0)

        # JSON Roundtrip
        json_data = manifest.to_json()
        restored = CreativeManifest.from_json(json_data)
        self.assertEqual(restored.chapter_id, "chapter_004")
        self.assertEqual(len(restored.music_cues), 1)
        self.assertEqual(len(restored.foley_cues), 1)

    def test_02_silence_mandate_enforcement(self):
        """Verify that wall-to-wall music violates the Silence Mandate."""
        manifest = CreativeManifest(
            chapter_id="chapter_004",
            total_duration_ms=10000,
            music_cues=[
                # 9 seconds of music on 10 seconds total -> 90% music, only 10% silence!
                MusicCue(
                    cue_id="bad_cue",
                    cue_type="TRANSITION_BRIDGE",
                    track_name="track.mp3",
                    section_name="INTRO_BED",
                    start_ms=0,
                    duration_ms=9000,
                )
            ]
        )
        with self.assertRaises(ManifestValidationError) as ctx:
            manifest.validate()
        self.assertIn("Silence violation", str(ctx.exception))

    def test_03_deterministic_multitrack_render(self):
        """Verify end-to-end rendering of a valid manifest with vocal track."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            vocal_wav = tmp_path / "vocal.wav"
            out_master = tmp_path / "mastered.wav"

            # Create a 3.0s stereo vocal test file at 48kHz
            with wave.open(str(vocal_wav), "wb") as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                # 3 seconds of 48000 frames
                wf.writeframes(b"\x00\x00\x00\x00" * 48000 * 3)

            manifest = CreativeManifest(
                chapter_id="test_ch",
                total_duration_ms=3000,
                music_cues=[],  # Pure acoustic silence
                foley_cues=[],
                ambience_scenes=[],
            )

            res_path = render_manifest_soundscape(
                manifest=manifest,
                vocal_track_path=vocal_wav,
                output_master_file=out_master,
            )

            self.assertTrue(res_path.exists())
            self.assertGreater(res_path.stat().st_size, 10000)
            dur = get_audio_duration(res_path)
            self.assertAlmostEqual(dur, 3.0, delta=1.5)


if __name__ == "__main__":
    unittest.main()
