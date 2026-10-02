import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import wave
import struct

from audiobook_factory.mastering import concatenate_and_master_chapter
from audiobook_factory.manifest_renderer import get_reverb_filter_string, assemble_master_filter_graph
from audiobook_factory.cinema_audio_engine import PROFILE_STANDARD


def _create_dummy_wav(path: Path, num_channels: int = 1, sample_rate: int = 24000, duration_sec: float = 0.2):
    """Helper to generate a valid PCM WAV file on disk."""
    num_samples = int(sample_rate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        data = struct.pack(f"<{num_samples * num_channels}h", *([0] * (num_samples * num_channels)))
        wf.writeframes(data)


class TestPhase2MetadataSilosAndSpatial(unittest.TestCase):
    """Test suite verifying liquidation of metadata silos and activation of spatial audio."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tmp = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dynamic_reverb_rt60_mapping(self):
        """Verify get_reverb_filter_string dynamically maps physical RT60 times."""
        # Cathedral / Cavern scale (> 2000ms)
        filt_cath, wet_cath = get_reverb_filter_string(rt60_ms=2800)
        self.assertIn("100|180|260", filt_cath)
        self.assertGreaterEqual(wet_cath, 0.30)

        # Stone / Castle Hall (1200ms - 2000ms)
        filt_hall, wet_hall = get_reverb_filter_string(rt60_ms=1500)
        self.assertIn("60|110|160", filt_hall)
        self.assertAlmostEqual(wet_hall, 0.28)

        # Intimate chamber / Dry (< 250ms)
        filt_dry, wet_dry = get_reverb_filter_string(rt60_ms=180)
        self.assertIn("15|30", filt_dry)
        self.assertLessEqual(wet_dry, 0.08)

    def test_sidechain_threshold_calibrated_to_018(self):
        """Verify sidechain threshold is standardized to 0.018 linear (-34.9 dBFS) across renderers."""
        graph = assemble_master_filter_graph(
            has_foley=True,
            duck_attenuation_db=-16.0,
            sidechain_threshold=0.018,
        )
        self.assertIn("threshold=0.018", graph)

    @patch("subprocess.run")
    def test_azimuth_pan_and_speaker_auto_pan_in_mastering(self, mock_run):
        """Verify azimuth_pan resolution and automatic character stereo separation."""
        captured_concat = []

        def fake_run(cmd, *args, **kwargs):
            if cmd and isinstance(cmd, list) and len(cmd) > 1:
                target = Path(cmd[-1])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"RIFF" + b"\x00" * 1000)
                # If command is using concat_list, capture its content
                for i, arg in enumerate(cmd):
                    if arg == "-i" and i + 1 < len(cmd) and "concat_" in str(cmd[i + 1]):
                        c_path = Path(cmd[i + 1])
                        if c_path.exists():
                            captured_concat.append(c_path.read_text(encoding="utf-8"))
            m = MagicMock()
            m.returncode = 0
            return m

        mock_run.side_effect = fake_run

        # Create 4 test audio chunks
        chunks = []
        for i in range(1, 5):
            p = self.tmp / f"c001_s{i:04d}_take.wav"
            _create_dummy_wav(p, num_channels=1, duration_sec=0.2)
            chunks.append(p)

        script_segments = [
            # Segment 1: Narrator (Must stay center 0.0)
            {"index": 1, "speaker": "Narrator", "spatial": {"azimuth_pan": -0.40}, "pause_after_ms": 300},
            # Segment 2: Geralt (Explicit pan +0.25)
            {"index": 2, "speaker": "Geralt", "spatial": {"pan": 0.25}, "pause_after_ms": 200},
            # Segment 3: Yennefer (Neutral pan 0.0 -> Auto-assigned stage left -0.18)
            {"index": 3, "speaker": "Yennefer", "spatial": {"pan": 0.0}, "pause_after_ms": 250},
            # Segment 4: Dandelion (Neutral pan 0.0 -> Auto-assigned stage right +0.18)
            {"index": 4, "speaker": "Dandelion", "pause_after_ms": 500, "pre_roll_breath_ms": 180},
        ]

        out_wav = self.tmp / "mastered_dialogue.wav"

        # Mock wave output for output_chapter_file
        with patch("audiobook_factory.mastering.get_ffmpeg", return_value="ffmpeg"):
            concatenate_and_master_chapter(
                audio_segments=chunks,
                output_chapter_file=out_wav,
                script_segments=script_segments,
                spatial_staging=True,
                loudnorm=False,
            )

        self.assertTrue(len(captured_concat) > 0)
        concat_content = captured_concat[0]

        # 1. Narrator must be forced to 0.0 pan even if spatial specified negative
        self.assertIn("0.00", concat_content)

        # 2. Geralt's explicit pan (+0.25) must be realized in panned file name
        self.assertIn("0.25", concat_content)

        # 3. Yennefer's auto-assigned stage left (-0.18) must be realized
        self.assertIn("-0.18", concat_content)

        # 4. Dandelion's auto-assigned stage right (+0.18) must be realized
        self.assertIn("0.18", concat_content)

        # 5. Pre-roll breath for Dandelion (180ms) must be inserted into concat list
        self.assertIn("180ms.wav", concat_content)

        # 6. Post-segment pauses (300ms, 200ms, 250ms) must be inserted
        self.assertIn("300ms.wav", concat_content)
        self.assertIn("200ms.wav", concat_content)
        self.assertIn("250ms.wav", concat_content)

    @patch("subprocess.run")
    def test_contextual_pause_fallbacks_when_unspecified(self, mock_run):
        """Verify dramatic contextual pauses when pause_after_ms is not explicitly defined."""
        captured_concat = []

        def fake_run(cmd, *args, **kwargs):
            if cmd and isinstance(cmd, list) and len(cmd) > 1:
                target = Path(cmd[-1])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"RIFF" + b"\x00" * 1000)
                for i, arg in enumerate(cmd):
                    if arg == "-i" and i + 1 < len(cmd) and "concat_" in str(cmd[i + 1]):
                        c_path = Path(cmd[i + 1])
                        if c_path.exists():
                            captured_concat.append(c_path.read_text(encoding="utf-8"))
            m = MagicMock()
            m.returncode = 0
            return m

        mock_run.side_effect = fake_run

        chunks = []
        for i in range(1, 4):
            p = self.tmp / f"c002_s{i:04d}_take.wav"
            _create_dummy_wav(p, num_channels=1, duration_sec=0.2)
            chunks.append(p)

        script_segments = [
            # Segment 1: Chapter Header
            {"index": 1, "speaker": "Narrator", "is_chapter_header": True},
            # Segment 2: Explosive Combat Screams
            {"index": 2, "speaker": "Geralt", "intensity_level": "explosive"},
            # Segment 3: Normal end
            {"index": 3, "speaker": "Narrator"},
        ]

        out_wav = self.tmp / "contextual_dialogue.wav"

        concatenate_and_master_chapter(
            audio_segments=chunks,
            output_chapter_file=out_wav,
            script_segments=script_segments,
            spatial_staging=False,
            loudnorm=False,
        )

        self.assertTrue(len(captured_concat) > 0)
        concat_content = captured_concat[0]

        # Chapter header pause fallback: 1400ms
        self.assertIn("1400ms.wav", concat_content)
        # Explosive combat pause fallback: 280ms
        self.assertIn("280ms.wav", concat_content)


if __name__ == "__main__":
    unittest.main()
