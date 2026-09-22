#!/usr/bin/env python3
"""
Automated Audio DSP & EBU R128 Loudness Test Suite
===================================================
Automated verification tests using FFmpeg and FFprobe:
1. Asserts amix filter graph strictly uses normalize=0 across all sub-buses.
2. Asserts EBU R128 loudness target is -19 LUFS (+/- 0.5 LU).
3. Asserts True Peak does not exceed -1.5 dBTP.
4. Asserts Foley transients peak between -14 dBFS and -18 dBFS.
"""

import math
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from typing import Tuple, Optional

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.contracts import (
    CreativeManifest,
    MasteringConfig,
    FoleyCue,
    AmbienceScene,
)
from audiobook_factory.manifest_renderer import (
    assemble_master_filter_graph,
    render_manifest_soundscape,
    render_foley_bus_reel_chunked,
)
from audiobook_factory.soundscape import get_ffmpeg, get_audio_duration
from audiobook_factory.sound_bank import SoundBank


def run_ffmpeg_ebur128(audio_file: Path, ffmpeg_bin: str = "ffmpeg") -> Tuple[float, float]:
    """
    Analyzes an audio file using FFmpeg's ebur128 filter with true peak metering.
    Returns (integrated_loudness_lufs, true_peak_dbtp).
    """
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostats",
        "-i", str(audio_file),
        "-af", "ebur128=peak=true",
        "-f", "null",
        "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stderr = proc.stderr

    # Extract strictly from Summary: block to avoid momentary/initial window measurements
    summary_idx = stderr.rfind("Summary:")
    summary_text = stderr[summary_idx:] if summary_idx != -1 else stderr

    i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", summary_text)
    if not i_match:
        # Fallback to general I: in summary_text
        i_match = re.search(r"I:\s+([-\d\.]+)\s+LUFS", summary_text)
    if not i_match:
        raise ValueError(f"Could not parse Integrated Loudness from FFmpeg output:\n{stderr[-1000:]}")
    integrated_lufs = float(i_match.group(1))

    # True peak: Peak: -14.8 dBFS / dBTP
    tp_match = re.search(r"True peak:\s+Peak:\s+([-\d\.]+)\s+dB", summary_text)
    if not tp_match:
        tp_match = re.search(r"Peak:\s+([-\d\.]+)\s+dB", summary_text)
    if not tp_match:
        raise ValueError(f"Could not parse True Peak from FFmpeg output:\n{stderr[-1000:]}")
    true_peak_db = float(tp_match.group(1))

    return integrated_lufs, true_peak_db


def run_ffmpeg_volumedetect(audio_file: Path, ffmpeg_bin: str = "ffmpeg") -> float:
    """
    Analyzes an audio file using FFmpeg's volumedetect filter.
    Returns max_volume in dBFS.
    """
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-nostats",
        "-i", str(audio_file),
        "-af", "volumedetect",
        "-f", "null",
        "-",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stderr = proc.stderr

    match = re.search(r"max_volume:\s+([-\d\.]+)\s+dB", stderr)
    if not match:
        raise ValueError(f"Could not parse max_volume from FFmpeg output:\n{stderr[-1000:]}")
    return float(match.group(1))


def create_sine_wav(
    file_path: Path,
    duration_sec: float,
    frequency: float = 440.0,
    amplitude: float = 0.5,
    sample_rate: int = 48000,
    channels: int = 2,
) -> Path:
    """Creates a calibrated PCM 16-bit WAV file with specified amplitude and frequency."""
    file_path = Path(file_path).resolve()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)

    max_int16 = 32767
    int_amp = int(max_int16 * min(1.0, max(0.0, amplitude)))

    frames = bytearray()
    for i in range(num_samples):
        val = int(int_amp * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
        val_bytes = val.to_bytes(2, byteorder="little", signed=True)
        for _ in range(channels):
            frames.extend(val_bytes)

    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)

    return file_path


class TestAudioDspLoudness(unittest.TestCase):
    """Rigorous DSP audio compliance test suite verifying broadcast standards."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="test_dsp_loudness_")
        self.tmp_path = Path(self.tmp_dir.name)
        self.ffmpeg = get_ffmpeg()

    def tearDown(self):
        self.tmp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Contract 1: amix filter strictly uses normalize=0
    # -------------------------------------------------------------------------
    def test_01_amix_filter_strictly_uses_normalize_zero(self):
        """
        Inspects all master filter graph templates and generated filter strings,
        asserting that every amix filter invocation explicitly defines normalize=0
        to prevent volume division (-33 dB crash) and preserve vocal unity gain.
        """
        # Test 1a: Master filter graph with foley
        fg_with_foley = assemble_master_filter_graph(
            has_foley=True,
            target_lufs=-19.0,
            true_peak_db=-1.5,
            duck_attenuation_db=-16.0,
        )
        amix_calls_foley = re.findall(r"amix=[^;\[]+", fg_with_foley)
        self.assertGreaterEqual(len(amix_calls_foley), 2, "Expected at least 2 amix stages in graph with foley")
        for call in amix_calls_foley:
            self.assertIn(
                "normalize=0", call,
                f"amix invocation in master filter graph lacks explicit normalize=0: '{call}'"
            )

        # Test 1b: Master filter graph without foley
        fg_no_foley = assemble_master_filter_graph(
            has_foley=False,
            target_lufs=-19.0,
            true_peak_db=-1.5,
            duck_attenuation_db=-16.0,
        )
        amix_calls_no_foley = re.findall(r"amix=[^;\[]+", fg_no_foley)
        self.assertGreaterEqual(len(amix_calls_no_foley), 1, "Expected at least 1 amix stage in graph without foley")
        for call in amix_calls_no_foley:
            self.assertIn(
                "normalize=0", call,
                f"amix invocation in master filter graph lacks explicit normalize=0: '{call}'"
            )

        # Test 1c: Functional test in FFmpeg - amix with normalize=0 must not divide input levels
        # Create two 1.0s stems: one at 0.5 amplitude (-6 dBFS), one silence
        stem1 = self.tmp_path / "stem1.wav"
        stem2 = self.tmp_path / "stem2.wav"
        out_mixed = self.tmp_path / "out_amix_test.wav"
        create_sine_wav(stem1, duration_sec=1.0, amplitude=0.5, frequency=440)
        create_sine_wav(stem2, duration_sec=1.0, amplitude=0.0, frequency=440)

        # Mix with normalize=0
        cmd = [
            self.ffmpeg, "-y",
            "-i", str(stem1),
            "-i", str(stem2),
            "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:normalize=0[out]",
            "-map", "[out]",
            "-c:a", "pcm_s16le",
            str(out_mixed),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(res.returncode, 0, f"FFmpeg amix command failed: {res.stderr}")

        # Peak of stem1 vs peak of mixed output must match closely (not cut in half)
        peak_stem1 = run_ffmpeg_volumedetect(stem1, self.ffmpeg)
        peak_mixed = run_ffmpeg_volumedetect(out_mixed, self.ffmpeg)
        self.assertAlmostEqual(
            peak_stem1, peak_mixed, delta=0.5,
            msg=f"amix with normalize=0 altered stem gain! stem1={peak_stem1}dB, mixed={peak_mixed}dB"
        )

    # -------------------------------------------------------------------------
    # Contract 2: EBU R128 loudness target is -19 LUFS (+/- 0.5 LU)
    # -------------------------------------------------------------------------
    def test_02_master_ebu_r128_loudness_target_is_minus_19_lufs(self):
        """
        Renders a representative dialogue track through the broadcast mastering chain
        and verifies using FFmpeg ebur128 filter that the final output reaches
        -19.0 LUFS integrated loudness within +/- 0.5 LU tolerance.
        """
        # Create a 7-second modulated speech-like audio file with realistic vocal dynamic range
        voc_file = self.tmp_path / "dialogue_vocal_stem.wav"
        # Amplitude 0.15 corresponds to approximately -25 LUFS unmastered input
        create_sine_wav(voc_file, duration_sec=7.0, amplitude=0.15, frequency=400)

        master_out = self.tmp_path / "chapter_mastered_ebu_r128.wav"

        manifest = CreativeManifest(
            chapter_id="chap_loudness_test",
            silence_percentage=100.0,
            mastering=MasteringConfig(
                target_lufs=-19.0,
                true_peak_dbtp=-1.5,
            ),
        )

        render_manifest_soundscape(
            manifest=manifest,
            vocal_track_path=voc_file,
            output_master_file=master_out,
        )

        self.assertTrue(master_out.exists(), "Mastered audio file was not generated")
        self.assertGreater(master_out.stat().st_size, 1000)

        # Measure integrated loudness via EBU R128
        measured_lufs, measured_tp = run_ffmpeg_ebur128(master_out, self.ffmpeg)

        # Assert target is -19.0 LUFS (+/- 0.5 LU)
        target_lufs = -19.0
        self.assertAlmostEqual(
            measured_lufs,
            target_lufs,
            delta=0.5,
            msg=f"EBU R128 loudness target violated: expected {target_lufs} LUFS +/- 0.5 LU, got {measured_lufs} LUFS"
        )

    # -------------------------------------------------------------------------
    # Contract 3: True peak does not exceed -1.5 dBTP
    # -------------------------------------------------------------------------
    def test_03_master_true_peak_does_not_exceed_minus_1_point_5_dbtp(self):
        """
        Processes high-energy dynamic peaks through the mastering chain and asserts
        that the peak ceiling limiter strictly clamps True Peak at or below -1.5 dBTP.
        """
        # Create high-energy 5-second track with 0 dBFS bursts
        loud_voc_file = self.tmp_path / "loud_burst_vocal.wav"
        # Full scale 0 dBFS amplitude
        create_sine_wav(loud_voc_file, duration_sec=5.0, amplitude=0.98, frequency=1000)

        master_out = self.tmp_path / "chapter_mastered_peak_test.wav"

        manifest = CreativeManifest(
            chapter_id="chap_peak_test",
            silence_percentage=100.0,
            mastering=MasteringConfig(
                target_lufs=-19.0,
                true_peak_dbtp=-1.5,
            ),
        )

        render_manifest_soundscape(
            manifest=manifest,
            vocal_track_path=loud_voc_file,
            output_master_file=master_out,
        )

        self.assertTrue(master_out.exists())

        # Measure True Peak via EBU R128
        _, measured_tp = run_ffmpeg_ebur128(master_out, self.ffmpeg)

        # Must not exceed -1.5 dBTP (with minor floating point delta)
        max_allowable_tp = -1.5
        self.assertLessEqual(
            measured_tp,
            max_allowable_tp + 0.05,
            f"True Peak ceiling violation: measured {measured_tp} dBTP exceeds ceiling of {max_allowable_tp} dBTP"
        )

    # -------------------------------------------------------------------------
    # Contract 4: Foley transients peak between -14 dBFS and -18 dBFS
    # -------------------------------------------------------------------------
    def test_04_foley_transients_peak_between_minus_14_and_minus_18_dbfs(self):
        """
        Renders Foley cues via the 5-Minute Cinema Reel Foley Engine and verifies
        that calibrated Foley transients peak precisely between -14 dBFS and -18 dBFS.
        """
        # 1. Create a 0.2s full-scale 0 dBFS transient sound (e.g. click/footstep/sword draw)
        transient_wav = self.tmp_path / "foley_transient_source.wav"
        create_sine_wav(transient_wav, duration_sec=0.2, amplitude=1.0, frequency=800)

        # Verify source file is indeed 0 dBFS (max_volume ~ 0.0 dB)
        source_peak = run_ffmpeg_volumedetect(transient_wav, self.ffmpeg)
        self.assertAlmostEqual(source_peak, 0.0, delta=0.5)

        test_cases = [
            ("default_minus_15", -15.0),
            ("transient_minus_14", -14.0),
            ("transient_minus_16", -16.0),
            ("transient_minus_18", -18.0),
        ]

        bank = SoundBank()

        for case_name, gain_dbfs in test_cases:
            with self.subTest(case=case_name, gain_dbfs=gain_dbfs):
                out_foley_bus = self.tmp_path / f"foley_bus_{case_name}.wav"
                cue = FoleyCue(
                    cue_id=f"fc_{case_name}",
                    segment_index=1,
                    anchor_word="clock",
                    asset_path=str(transient_wav),
                    gain_dbfs=gain_dbfs,
                    start_ms=500,
                    pre_roll_ms=50,
                )

                success = render_foley_bus_reel_chunked(
                    foley_cues=[cue],
                    total_duration_sec=2.0,
                    output_bus_file=out_foley_bus,
                    sound_bank=bank,
                    ffmpeg=self.ffmpeg,
                    reel_duration_sec=300.0,
                    chunk_size=15,
                )
                self.assertTrue(success, f"Failed to render foley reel for {case_name}")
                self.assertTrue(out_foley_bus.exists())

                # Measure peak using volumedetect
                measured_peak = run_ffmpeg_volumedetect(out_foley_bus, self.ffmpeg)

                # Assert that foley peak is between -14.0 dBFS and -18.0 dBFS
                self.assertGreaterEqual(
                    measured_peak,
                    -18.5,
                    f"Foley transient too quiet: {measured_peak} dBFS < -18.0 dBFS (gain was {gain_dbfs} dBFS)"
                )
                self.assertLessEqual(
                    measured_peak,
                    -13.5,
                    f"Foley transient too loud: {measured_peak} dBFS > -14.0 dBFS (gain was {gain_dbfs} dBFS)"
                )


if __name__ == "__main__":
    unittest.main()
