import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import shutil
import wave
import struct

from audiobook_factory.gate_auditor import (
    audit_gate5_master,
    audit_gate5_2_spectral_masking,
    audit_gate5_3_stereo_phase,
    GateAuditError,
    AuditResult,
)


def _create_dummy_wav(path: Path, num_channels: int = 1, sample_rate: int = 44100, duration_sec: float = 0.5):
    """Helper to generate a valid PCM WAV file on disk."""
    num_samples = int(sample_rate * duration_sec)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        # 16-bit silence/low tone
        data = struct.pack(f"<{num_samples * num_channels}h", *([0] * (num_samples * num_channels)))
        wf.writeframes(data)


class TestFailClosedGate5Master(unittest.TestCase):
    """Rigorous fail-closed verification for audit_gate5_master."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tmp = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_file_raises_gate_audit_error(self):
        missing = self.tmp / "non_existent_master.wav"
        with self.assertRaises(GateAuditError) as ctx:
            audit_gate5_master(missing)
        self.assertIn("missing", str(ctx.exception).lower())

    def test_truncated_file_raises_gate_audit_error(self):
        truncated = self.tmp / "truncated.wav"
        truncated.write_bytes(b"RIFF" + b"\x00" * 200)  # < 1000 bytes
        with self.assertRaises(GateAuditError) as ctx:
            audit_gate5_master(truncated)
        self.assertIn("truncated", str(ctx.exception).lower())

    @patch("subprocess.run")
    def test_ffmpeg_probe_nonzero_exit_raises_gate_audit_error(self, mock_run):
        master = self.tmp / "master.wav"
        master.write_bytes(b"RIFF" + b"\x00" * 2000)

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stderr = "Error: Invalid audio stream or corrupt header"
        mock_run.return_value = mock_proc

        with self.assertRaises(GateAuditError) as ctx:
            audit_gate5_master(master)
        self.assertIn("error code 1", str(ctx.exception).lower())

    @patch("subprocess.run")
    def test_unparseable_output_raises_gate_audit_error(self, mock_run):
        master = self.tmp / "master.wav"
        master.write_bytes(b"RIFF" + b"\x00" * 2000)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = "ffmpeg version 6.0 ... finished with no ebur128 log"
        mock_run.return_value = mock_proc

        with self.assertRaises(GateAuditError) as ctx:
            audit_gate5_master(master)
        self.assertIn("could not parse integrated loudness", str(ctx.exception).lower())

    @patch("subprocess.run")
    def test_loudness_outside_tolerance_raises_gate_audit_error(self, mock_run):
        master = self.tmp / "master.wav"
        master.write_bytes(b"RIFF" + b"\x00" * 2000)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = "Integrated loudness:   I:   -12.5 LUFS\nTrue peak:   Peak:   -1.8 dBFS"
        mock_run.return_value = mock_proc

        # Target -19.0 LUFS +/- 1.0 -> -12.5 LUFS must fail
        with self.assertRaises(GateAuditError) as ctx:
            audit_gate5_master(master, target_lufs=-19.0, tolerance_lu=1.0)
        self.assertIn("outside target", str(ctx.exception).lower())

    @patch("subprocess.run")
    def test_true_peak_violation_raises_gate_audit_error(self, mock_run):
        master = self.tmp / "master.wav"
        master.write_bytes(b"RIFF" + b"\x00" * 2000)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = "Integrated loudness:   I:   -19.0 LUFS\nTrue peak:   Peak:   -0.5 dBFS"
        mock_run.return_value = mock_proc

        # Ceiling -1.4 dBTP -> -0.5 must fail
        with self.assertRaises(GateAuditError) as ctx:
            audit_gate5_master(master, target_lufs=-19.0, max_true_peak=-1.4)
        self.assertIn("exceeds ceiling", str(ctx.exception).lower())

    @patch("subprocess.run")
    def test_compliant_master_passes(self, mock_run):
        master = self.tmp / "master.wav"
        master.write_bytes(b"RIFF" + b"\x00" * 2000)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = "Integrated loudness:   I:   -19.1 LUFS\nTrue peak:   Peak:   -1.6 dBFS"
        mock_run.return_value = mock_proc

        res = audit_gate5_master(master, target_lufs=-19.0, tolerance_lu=1.0, max_true_peak=-1.4)
        self.assertEqual(res["status"], "PASS")
        self.assertAlmostEqual(res["integrated_lufs"], -19.1)
        self.assertAlmostEqual(res["true_peak_dbtp"], -1.6)


class TestFailClosedGate52SpectralMasking(unittest.TestCase):
    """Rigorous fail-closed verification for audit_gate5_2_spectral_masking."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tmp = Path(self.temp_dir)
        self.dialogue = self.tmp / "dialogue.wav"
        self.music = self.tmp / "music.wav"
        self.dialogue.write_bytes(b"RIFF" + b"\x00" * 2000)
        self.music.write_bytes(b"RIFF" + b"\x00" * 2000)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("subprocess.run")
    def test_clear_separation_passes(self, mock_run):
        # Dialogue -19.0 LUFS, Music -35.0 LUFS -> DMR +16.0 dB >= 12.0 dB
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr="Integrated loudness:\n  I: -19.0 LUFS"),
            MagicMock(returncode=0, stderr="Integrated loudness:\n  I: -35.0 LUFS"),
        ]
        res = audit_gate5_2_spectral_masking(self.dialogue, self.music, min_dmr_db=12.0)
        self.assertTrue(res.passed)
        self.assertEqual(res.status, "PASS")
        self.assertAlmostEqual(res.details["measured_dmr_db"], 16.0)

    @patch("subprocess.run")
    def test_spectral_masking_violation_fails(self, mock_run):
        # Dialogue -22.0 LUFS, Music -24.0 LUFS -> DMR +2.0 dB < 12.0 dB
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr="Integrated loudness:\n  I: -22.0 LUFS"),
            MagicMock(returncode=0, stderr="Integrated loudness:\n  I: -24.0 LUFS"),
        ]
        res = audit_gate5_2_spectral_masking(self.dialogue, self.music, min_dmr_db=12.0)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "FAIL")
        self.assertIn("spectral masking violation", res.errors[0].lower())

    @patch("subprocess.run")
    def test_ffmpeg_probe_error_fails_closed_never_silent_pass(self, mock_run):
        # When probe on music fails with exit code 1, it must FAIL (never report dmr=99.0 false pass)
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr="Integrated loudness:\n  I: -19.0 LUFS"),
            MagicMock(returncode=1, stderr="Error: filter ebur128 failed"),
        ]
        res = audit_gate5_2_spectral_masking(self.dialogue, self.music, min_dmr_db=12.0)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "FAIL")
        self.assertTrue(any("probe failed" in err.lower() for err in res.errors))

    @patch("subprocess.run")
    def test_ffmpeg_probe_exception_fails_closed(self, mock_run):
        mock_run.side_effect = RuntimeError("Subprocess timeout or OS error")
        res = audit_gate5_2_spectral_masking(self.dialogue, self.music, min_dmr_db=12.0)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "FAIL")
        self.assertTrue(len(res.errors) > 0)


class TestFailClosedGate53StereoPhase(unittest.TestCase):
    """Rigorous fail-closed verification for audit_gate5_3_stereo_phase."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tmp = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_missing_file_fails(self):
        missing = self.tmp / "missing.wav"
        res = audit_gate5_3_stereo_phase(missing)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "FAIL")
        self.assertIn("does not exist", res.errors[0])

    def test_mono_wav_passes_with_perfect_correlation(self):
        mono_wav = self.tmp / "mono_test.wav"
        _create_dummy_wav(mono_wav, num_channels=1, duration_sec=0.2)
        res = audit_gate5_3_stereo_phase(mono_wav)
        self.assertTrue(res.passed)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.details["channel_layout"], "mono")
        self.assertEqual(res.details["mean_phase_correlation"], 1.0)

    @patch("subprocess.run")
    def test_stereo_high_phase_correlation_passes(self, mock_run):
        stereo_wav = self.tmp / "stereo_test.wav"
        _create_dummy_wav(stereo_wav, num_channels=2, duration_sec=0.2)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = "\n".join([
            "lavfi.aphasemeter.phase=0.88",
            "lavfi.aphasemeter.phase=0.85",
            "lavfi.aphasemeter.phase=0.90",
        ])
        mock_run.return_value = mock_proc

        res = audit_gate5_3_stereo_phase(stereo_wav, min_phase_correlation=0.20)
        self.assertTrue(res.passed)
        self.assertEqual(res.status, "PASS")
        self.assertGreaterEqual(res.details["mean_phase_correlation"], 0.8)

    @patch("subprocess.run")
    def test_stereo_phase_cancellation_hazard_fails(self, mock_run):
        stereo_wav = self.tmp / "stereo_test.wav"
        _create_dummy_wav(stereo_wav, num_channels=2, duration_sec=0.2)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stderr = "\n".join([
            "lavfi.aphasemeter.phase=-0.80",
            "lavfi.aphasemeter.phase=-0.60",
            "lavfi.aphasemeter.phase=-0.50",
        ])
        mock_run.return_value = mock_proc

        res = audit_gate5_3_stereo_phase(stereo_wav, min_phase_correlation=0.20)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "FAIL")
        self.assertIn("cancellation hazard", res.errors[0].lower())

    @patch("subprocess.run")
    def test_aphasemeter_crash_fails_closed(self, mock_run):
        stereo_wav = self.tmp / "stereo_test.wav"
        _create_dummy_wav(stereo_wav, num_channels=2, duration_sec=0.2)

        mock_run.side_effect = RuntimeError("FFmpeg aphasemeter crash or SIGSEGV")
        res = audit_gate5_3_stereo_phase(stereo_wav, min_phase_correlation=0.20)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "FAIL")
        self.assertTrue(any("probe crashed" in err.lower() for err in res.errors))


if __name__ == "__main__":
    unittest.main()
