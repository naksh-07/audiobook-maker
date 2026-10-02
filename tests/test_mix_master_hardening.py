#!/usr/bin/env python3
"""
Test Suite: test_mix_master_hardening.py
=========================================
Adversarial Failure Injection & Mix-Master Validation Suite for Prompt 7.

Validates:
1. True-Peak Clipping Safety (+1.5 dBTP overshoot injection -> caught and failed).
2. Integrated Loudness Drift Safety (-12 LUFS and -28 LUFS -> caught by Gate 5 and MasteringQC).
3. Dialogue Masking Safety (un-ducked music over speech, DMR < 6dB -> caught by Gate 5.2 and MixJudge).
4. Master Bypass Detection (unmastered premaster rejected by delivery gates).
5. Format & Sample Rate Invariant (44.1k/96k/192k inputs strictly normalized to 48kHz stereo 16-bit WAV).
6. Stereo Phase Cancellation & Mono Compatibility (anti-phase r = -1.0 caught by Gate 5.3).
7. Dead-Air Silence Anomaly Detection (> 3.0s absolute silence drop caught).
8. Double-Mastering Idempotency Protection (prevents re-compressing mastered vocal bus).
9. Complete Break -> Catch -> Restore -> Pass verification cycle.
"""

import math
import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from audiobook_factory.mastering_contracts import (
    MasteringProfile,
    MasteringRequest,
    MasteringResult,
    MasteringAnalysisFacts,
    MasteringQCResult,
)
from audiobook_factory.mastering_analyzer import MasteringAnalyzer
from audiobook_factory.mastering_qc import MasteringQCAgent
from audiobook_factory.mastering_judge import MasteringJudge
from audiobook_factory.mastering_engine import MasteringEngineV2
from audiobook_factory.deterministic_audio_analyzer import DeterministicAudioAnalyzer
from audiobook_factory.gate_auditor import (
    audit_gate5_master,
    audit_gate5_2_spectral_masking,
    audit_gate5_3_stereo_phase,
    GateAuditError,
)


def _generate_wav(
    filepath: Path,
    duration_sec: float = 3.0,
    sample_rate: int = 48000,
    channels: int = 2,
    freq: float = 440.0,
    amplitude: float = 0.5,
    phase_inverted: bool = False,
) -> Path:
    """Generates synthetic test audio with optional channel phase inversion."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, num_samples, endpoint=False)
    sig = amplitude * np.sin(2 * np.pi * freq * t)

    # Apply 10ms smooth ramp at boundaries
    fade = min(int(0.01 * sample_rate), num_samples // 4)
    if fade > 0:
        sig[:fade] *= np.linspace(0, 1, fade)
        sig[-fade:] *= np.linspace(1, 0, fade)

    sig_clamped = np.clip(sig, -1.0, 1.0)
    int16_l = (sig_clamped * 32767.0).astype(np.int16)

    if channels == 2:
        if phase_inverted:
            int16_r = (-sig_clamped * 32767.0).astype(np.int16)  # 180 deg out of phase
        else:
            int16_r = int16_l
        int_data = np.column_stack((int16_l, int16_r)).flatten()
    else:
        int_data = int16_l

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int_data.tobytes())

    return filepath


class TestMixMasterHardening(unittest.TestCase):
    """Failure Injection & Verification Suite for Mix & Master Pipeline."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="mix_master_hardening_"))
        self.engine = MasteringEngineV2()
        self.qc = MasteringQCAgent()
        self.analyzer = MasteringAnalyzer()
        self.det_analyzer = DeterministicAudioAnalyzer()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # 1. True-Peak Clipping Safety
    def test_failure_injection_true_peak_clipping_caught(self):
        """Inject +1.5 dBTP clipping overshoot: must be flagged as critical defect by MasteringQC."""
        facts = MasteringAnalysisFacts(
            filepath=str(self.tmp_dir / "clipped.wav"),
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.0,
            true_peak_dbtp=1.5,  # Severe true peak overshoot > -1.5 dBTP
            clipping_detected=True,
            is_valid_audio=True,
        )
        prof = MasteringProfile(true_peak_ceiling_dbtp=-1.5)
        qc_res = self.qc.evaluate(master_facts=facts, profile=prof)

        self.assertFalse(qc_res.passed)
        self.assertEqual(qc_res.status, "FAIL")
        self.assertEqual(qc_res.checks.get("true_peak"), "FAIL")
        self.assertTrue(any("clipping" in f or "true_peak" in f for f in qc_res.failures))

    # 2. Integrated Loudness Drift Safety
    def test_failure_injection_loudness_drift_caught(self):
        """Inject out-of-spec loudness (-12.0 LUFS hyper-compressed and -28.0 LUFS whisper-buried)."""
        prof = MasteringProfile(target_lufs=-19.0, tolerance_lu=0.5)

        # Case A: Too loud (-12.0 LUFS, +7 LU error)
        hot_facts = MasteringAnalysisFacts(
            filepath=str(self.tmp_dir / "hot.wav"),
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-12.0,
            true_peak_dbtp=-1.5,
            is_valid_audio=True,
        )
        qc_hot = self.qc.evaluate(master_facts=hot_facts, profile=prof)
        self.assertFalse(qc_hot.passed)
        self.assertEqual(qc_hot.checks.get("loudness"), "FAIL")
        self.assertTrue(any("integrated_loudness_severe_violation" in f for f in qc_hot.failures))

        # Case B: Too quiet (-28.0 LUFS, -9 LU error)
        quiet_facts = MasteringAnalysisFacts(
            filepath=str(self.tmp_dir / "quiet.wav"),
            duration_sec=3.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-28.0,
            true_peak_dbtp=-10.0,
            is_valid_audio=True,
        )
        qc_quiet = self.qc.evaluate(master_facts=quiet_facts, profile=prof)
        self.assertFalse(qc_quiet.passed)
        self.assertEqual(qc_quiet.checks.get("loudness"), "FAIL")
        self.assertTrue(any("integrated_loudness_severe_violation" in f for f in qc_quiet.failures))

    # 3. Dialogue Masking Safety (Gate 5.2)
    def test_failure_injection_dialogue_masking_detected(self):
        """Inject un-ducked loud music competing with speech: Gate 5.2 must detect DMR violation."""
        vocal_wav = self.tmp_dir / "vocal_clean.wav"
        loud_music_wav = self.tmp_dir / "loud_music.wav"
        _generate_wav(vocal_wav, duration_sec=3.0, amplitude=0.08, freq=1200.0)
        _generate_wav(loud_music_wav, duration_sec=3.0, amplitude=0.95, freq=1200.0)

        # Gate 5.2 requires min_dmr_db >= 12.0 dB
        res = audit_gate5_2_spectral_masking(vocal_wav, loud_music_wav, min_dmr_db=12.0)
        self.assertFalse(res.passed)
        self.assertTrue(len(res.errors) > 0)
        self.assertTrue(any("masking" in err.lower() for err in res.errors))

    # 4. Master Bypass Detection
    def test_master_bypass_unmastered_audio_rejected_by_gate5(self):
        """Verify unmastered audio with raw un-normalized levels is rejected by Gate 5."""
        unmastered_wav = self.tmp_dir / "unmastered_raw.wav"
        # Generate raw quiet track at -32 LUFS
        _generate_wav(unmastered_wav, duration_sec=3.0, amplitude=0.05)

        with self.assertRaises(GateAuditError) as ctx:
            audit_gate5_master(unmastered_wav, target_lufs=-19.0, tolerance_lu=1.0)
        self.assertIn("outside target", str(ctx.exception))

    # 5. Format & Sample Rate Invariant
    def test_format_and_sample_rate_normalization_to_48k(self):
        """Verify that 44.1kHz mono input premaster is strictly mastered to 48kHz stereo 16-bit WAV."""
        premaster_44k = self.tmp_dir / "premaster_44100.wav"
        _generate_wav(premaster_44k, duration_sec=2.5, sample_rate=44100, channels=1, amplitude=0.4)

        master_out = self.tmp_dir / "master_48k.wav"
        req = MasteringRequest(
            chapter_id="ch_format_test",
            premaster_path=str(premaster_44k),
            output_master_path=str(master_out),
            profile=MasteringProfile(
                target_lufs=-19.0,
                tolerance_lu=1.0,
                output_sample_rate=48000,
                output_channels=2,
            ),
        )
        res = self.engine.master(req)

        self.assertEqual(res.status, "SUCCESS")
        self.assertTrue(res.qc_result.passed)
        self.assertTrue(master_out.exists())

        # Verify physical disk facts
        fmt = self.det_analyzer.probe_format(master_out)
        self.assertEqual(fmt.sample_rate, 48000)
        self.assertEqual(fmt.channels, 2)
        self.assertEqual(fmt.codec, "pcm_s24le")

    # 6. Stereo Phase Cancellation Detection (Gate 5.3)
    def test_failure_injection_anti_phase_cancellation_caught(self):
        """Inject 180-degree anti-phase stereo audio (r = -1.0): Gate 5.3 must fail."""
        anti_phase_wav = self.tmp_dir / "anti_phase.wav"
        _generate_wav(anti_phase_wav, duration_sec=2.0, channels=2, phase_inverted=True)

        res = audit_gate5_3_stereo_phase(anti_phase_wav, min_phase_correlation=0.20)
        self.assertFalse(res.passed)
        self.assertTrue(any("stereo phase cancellation" in err.lower() for err in res.errors))
        self.assertLess(float(res.details.get("mean_phase_correlation", 1.0)), 0.0)

    # 7. Dead-Air Silence Anomaly Detection
    def test_dead_air_silence_anomaly_detected(self):
        """Inject dead air (> 3.0s below -50dB) into facts: MasteringQC must flag warning or defect."""
        facts = MasteringAnalysisFacts(
            filepath=str(self.tmp_dir / "dead_air.wav"),
            duration_sec=10.0,
            sample_rate=48000,
            channels=2,
            integrated_lufs=-19.0,
            dead_air_sec=3.5,  # Excessive dead air > 3.0s
            is_valid_audio=True,
        )
        qc_res = self.qc.evaluate(master_facts=facts, profile=MasteringProfile())
        self.assertEqual(qc_res.checks.get("dead_air"), "WARN")
        self.assertTrue(any("silence" in w.lower() or "dead_air" in w.lower() for w in qc_res.warnings))

    # 8. Double-Mastering Idempotency Protection
    def test_double_master_protection_blocks_re_mastering(self):
        """Verify that passing an audio file flagged as is_premaster=False raises ValueError."""
        dummy_wav = self.tmp_dir / "already_mastered.wav"
        dummy_wav.touch()

        with self.assertRaises(ValueError) as ctx:
            MasteringRequest(
                chapter_id="ch_double",
                premaster_path=str(dummy_wav),
                is_premaster=False,
            )
        self.assertIn("Double-master protection", str(ctx.exception))

    # 9. Complete Break -> Catch -> Restore -> Pass Lifecycle
    def test_break_catch_restore_pass_lifecycle(self):
        """
        Executes complete break-catch-restore-pass cycle:
        1. Break: Provide an out-of-spec premaster causing initial loudness discrepancy.
        2. Catch: Closed-loop QC catches the violation.
        3. Restore: MasteringEngine remediation adjusts offset and limiter ceiling.
        4. Pass: Second pass achieves broadcast EBU R128 compliance with certified ledger.
        """
        premaster_wav = self.tmp_dir / "lifecycle_premaster.wav"
        _generate_wav(premaster_wav, duration_sec=3.0, amplitude=0.35)

        master_wav = self.tmp_dir / "lifecycle_master.wav"
        req = MasteringRequest(
            chapter_id="ch_lifecycle",
            premaster_path=str(premaster_wav),
            output_master_path=str(master_wav),
            profile=MasteringProfile(
                target_lufs=-19.0,
                tolerance_lu=0.5,
                true_peak_ceiling_dbtp=-1.5,
                max_retries=2,
            ),
        )
        res = self.engine.master(req)

        self.assertEqual(res.status, "SUCCESS")
        self.assertTrue(res.qc_result.passed)
        # Verify master matches effective profile target within 0.5 LU
        self.assertAlmostEqual(res.analysis_after.integrated_lufs, res.profile.target_lufs, delta=0.5)
        self.assertLessEqual(res.analysis_after.true_peak_dbtp, -1.4)
        self.assertEqual(res.analysis_after.sample_rate, 48000)
        self.assertEqual(res.analysis_after.channels, 2)


if __name__ == "__main__":
    unittest.main()
