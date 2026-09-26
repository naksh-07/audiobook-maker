#!/usr/bin/env python3
"""
Adversarial Audit Remediation Test Suite for Dialogue Editorial Layer (DE-01 - DE-04).
Verifies that all P0, P1, and P2 defects uncovered by the 3-panel expert audit are completely remediated.
"""

import math
import wave
import pytest
import numpy as np
from pathlib import Path

from audiobook_factory.dialogue_editing import (
    DialogueEditor,
    DialogueEditPlan,
    DialogueEditorialConfig,
    DialogueQCReport,
)
from audiobook_factory.dialogue_editing.endpoint_editor import EndpointEditor
from audiobook_factory.dialogue_editing.breath_editor import BreathEditor
from audiobook_factory.dialogue_editing.pause_editor import PauseEditor
from audiobook_factory.dialogue_editing.qc import DialogueEditingQC
from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    PerformanceEvidence,
    BreathEvidence,
    AcousticEvidence,
)
from audiobook_factory.alignment_contracts import AlignmentResult, WordAlignment


class TestAudioDSPRemediations:
    """Verifies Audio DSP, bit depth, zero-crossing, and micro-fade remediations."""

    def test_24bit_and_32bit_float_wav_ingestion_not_zeroed(self, tmp_path: Path):
        """P0-1 Fix: 24-bit packed PCM and 32-bit float audio must not load as pure digital silence."""
        editor = DialogueEditor()

        # 1. Create a 32-bit float WAV with a 440Hz tone
        f32_wav = tmp_path / "tone_32f.wav"
        sr = 24000
        t = np.linspace(0, 1.0, sr, endpoint=False, dtype=np.float32)
        sine_f32 = (0.5 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

        with wave.open(str(f32_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(4)
            wf.setframerate(sr)
            wf.writeframes(sine_f32.tobytes())

        samples_32, loaded_sr = editor._load_wav_samples(f32_wav)
        assert loaded_sr == sr
        assert len(samples_32) == sr
        # Must NOT be digital silence! Peak should be around 0.5 * 32768 = 16384
        peak = float(np.max(np.abs(samples_32)))
        assert peak > 10000.0, f"Expected non-zero audio, got peak {peak}"

        # 2. Create a 24-bit PCM WAV
        f24_wav = tmp_path / "tone_24pcm.wav"
        # 24-bit int range is [-8388608, 8388607]
        sine_i24 = (0.5 * 8388607.0 * np.sin(2 * np.pi * 440.0 * t)).astype(np.int32)
        # Pack into 3 bytes per sample little-endian
        packed_bytes = bytearray()
        for val in sine_i24:
            b = int(val).to_bytes(4, byteorder="little", signed=True)
            packed_bytes.extend(b[:3])

        with wave.open(str(f24_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(3)
            wf.setframerate(sr)
            wf.writeframes(packed_bytes)

        samples_24, loaded_sr_24 = editor._load_wav_samples(f24_wav)
        assert loaded_sr_24 == sr
        assert len(samples_24) == sr
        peak_24 = float(np.max(np.abs(samples_24)))
        assert peak_24 > 10000.0, f"Expected non-zero audio for 24-bit, got peak {peak_24}"

    def test_stereo_wav_downmixed_to_mono(self, tmp_path: Path):
        """P1-2 Fix: Multi-channel (stereo) takes downmix cleanly to mono without pitch distortion."""
        editor = DialogueEditor()
        stereo_wav = tmp_path / "stereo.wav"
        sr = 24000
        t = np.linspace(0, 0.5, sr // 2, endpoint=False, dtype=np.float32)
        left = (0.4 * 32767.0 * np.sin(2 * np.pi * 440.0 * t)).astype(np.int16)
        right = (0.4 * 32767.0 * np.sin(2 * np.pi * 440.0 * t)).astype(np.int16)
        stereo = np.empty((len(t) * 2,), dtype=np.int16)
        stereo[0::2] = left
        stereo[1::2] = right

        with wave.open(str(stereo_wav), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(stereo.tobytes())

        samples, loaded_sr = editor._load_wav_samples(stereo_wav)
        assert len(samples) == len(t)  # Exactly half second mono, NOT double length!
        assert loaded_sr == sr

    def test_float_zero_crossing_snapping_precision(self):
        """P0-6 Fix: Zero-crossing snap returns float ms preserving sub-millisecond sample accuracy."""
        endpoint_editor = EndpointEditor()
        sr = 48000
        # Create a 440Hz sine wave where a zero crossing occurs at non-integer millisecond
        t = np.arange(4800) / sr  # 100ms
        sine = (16000.0 * np.sin(2 * np.pi * 440.0 * t)).astype(np.float32)

        # Snap a 40.5ms target
        snapped_head_ms = endpoint_editor._snap_trim_to_zero_crossing(sine, sr, 40.5, is_head=True)
        assert isinstance(snapped_head_ms, float)
        # Convert snapped float ms back to sample index
        sample_idx = int(round(snapped_head_ms / 1000.0 * sr))
        # The sample index must be right at a zero crossing (adjacent sign change)
        assert sine[sample_idx] * sine[sample_idx + 1] <= 0.0 or abs(sine[sample_idx]) < 100.0

    def test_gain_adjustment_db_applied_during_rendering(self, tmp_path: Path):
        """P1-4 Fix: gain_adjustment_db is applied directly to waveform samples."""
        editor = DialogueEditor()
        sr = 24000
        t = np.linspace(0, 0.5, sr // 2, endpoint=False, dtype=np.float32)
        raw_samples = (10000.0 * np.sin(2 * np.pi * 440.0 * t)).astype(np.int16)

        inp_wav = tmp_path / "raw.wav"
        with wave.open(str(inp_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(raw_samples.tobytes())

        out_wav = tmp_path / "boosted.wav"
        # Apply +6 dB gain (should roughly double amplitude)
        plan = DialogueEditPlan(
            segment_uid="gain_test",
            gain_adjustment_db=6.0,
            crossfade_in_ms=2.0,
            crossfade_out_ms=2.0,
        )
        editor.apply_edit_plan(inp_wav, plan, out_wav)

        with wave.open(str(out_wav), "rb") as wf:
            out_samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)

        raw_peak = np.max(np.abs(raw_samples[100:-100]))
        out_peak = np.max(np.abs(out_samples[100:-100]))
        ratio = out_peak / raw_peak
        assert 1.90 <= ratio <= 2.10, f"Expected ~2.0x amplitude ratio for +6dB, got {ratio}"

    def test_whisper_tail_dynamic_speech_floor(self):
        """P1-3 Fix: Dynamic speech floor preserves quiet whispered decays down to -50 dBFS."""
        endpoint_editor = EndpointEditor()
        sr = 24000
        n_samples = int(2.0 * sr)
        samples = np.zeros(n_samples, dtype=np.float32)

        # Quiet whispered line: peak around -38 dBFS, decaying to -48 dBFS at 1.4s
        t_speech = np.arange(int(1.4 * sr)) / sr
        speech_env = np.linspace(350.0, 120.0, len(t_speech))  # ~ -39 dBFS down to -48 dBFS
        samples[:len(t_speech)] = speech_env * np.sin(2 * np.pi * 300.0 * t_speech)

        speech_start_ms, speech_end_ms = endpoint_editor._resolve_speech_bounds(samples, sr, alignment=None)
        # Should not prematurely truncate at 0.5s or 0.8s
        assert speech_end_ms >= 1200, f"Expected whisper tail preserved past 1200ms, got {speech_end_ms}ms"


class TestDramaturgicalRemediations:
    """Verifies Dramaturgy, aposiopesis, vocal status, and breath rules."""

    def test_em_dash_aposiopesis_preserves_dramatic_freeze(self):
        """P0-3 Fix: Em-dash endings do NOT crush emotional freeze / grief into 35ms cutoffs."""
        pause_editor = PauseEditor()
        direction = PerformanceDirection(
            index=1,
            speaker="Kabir",
            silence_type="emotional_freeze",
            surface_emotion="grief",
            character_state="trauma",
        )
        # Tragic line ending in em-dash
        res = pause_editor.realize_pause(
            text="Maine socha tum mar chuke ho, John—",
            speaker="Kabir",
            direction=direction,
        )
        assert res["pause_classification"] == "EMOTIONAL_PAUSE"
        assert res["pause_after_ms"] >= 1200, f"Expected grief freeze >= 1200ms, got {res['pause_after_ms']}ms"

    def test_external_interruption_em_dash_applies_tight_cutoff(self):
        """Em-dash without dramatic freeze or grief applies tight authentic cutoff (35ms)."""
        pause_editor = PauseEditor()
        direction = PerformanceDirection(
            index=1,
            speaker="Kabir",
            silence_type="interruption_cut",
            surface_emotion="neutral",
        )
        res = pause_editor.realize_pause(
            text="Lekin tum toh wahan gaye hi nahi—",
            speaker="Kabir",
            direction=direction,
        )
        assert res["pause_classification"] == "INTERRUPTED_TURN"
        assert res["pause_after_ms"] <= 50

    def test_conversational_power_dynamics_polarity(self):
        """P1-1 Fix: Subordinate answers dominant authority promptly; dominant authority owns silence."""
        pause_editor = PauseEditor()

        # Dominant character (e.g. King) finishes speaking: subordinate responds promptly
        king_dir = PerformanceDirection(index=1, speaker="King", power_position="dominant")
        res_king = pause_editor.realize_pause(
            text="I will hear no further excuses.",
            speaker="King",
            next_speaker="Guard",
            direction=king_dir,
        )

        # Submissive character (e.g. Guard) finishes speaking: King takes his time to reply
        guard_dir = PerformanceDirection(index=2, speaker="Guard", power_position="submissive")
        res_guard = pause_editor.realize_pause(
            text="As you command, your majesty.",
            speaker="Guard",
            next_speaker="King",
            direction=guard_dir,
        )

        # Guard responds to King faster than King responds to Guard
        assert res_king["pause_after_ms"] < res_guard["pause_after_ms"], (
            f"Expected subordinate to answer faster than authority. "
            f"King pause: {res_king['pause_after_ms']}ms, Guard pause: {res_guard['pause_after_ms']}ms"
        )

    def test_iron_restraint_with_suppressed_sob_preserved(self):
        """P1-7 Fix: Suppressed sobbing intake on high-restraint line is NOT deleted as vocoder click."""
        breath_editor = BreathEditor()
        sr = 24000
        samples = np.zeros(sr, dtype=np.float32)
        # 150ms sharp intake breath before speech
        b_samples = int(0.15 * sr)
        samples[:b_samples] = 12000.0 * np.sin(np.linspace(0, np.pi, b_samples))
        # Speech follows
        samples[b_samples:] = 16000.0 * np.sin(2 * np.pi * 300.0 * np.arange(sr - b_samples) / sr)

        direction = PerformanceDirection(
            index=1,
            speaker="Kabir",
            restraint=0.90,  # Iron restraint
            surface_emotion="grief",  # Holding back tears / sobbing
            character_state="trauma",
        )
        action, gain, conf, reasons = breath_editor._evaluate_pre_breath(
            samples=samples,
            sample_rate=sr,
            speech_start_ms=150,
            speech_db=-18.0,
            direction=direction,
            evidence=None,
        )
        # Must KEEP or REDUCE, NEVER REMOVE (-36dB)
        assert action in ("KEEP", "REDUCE")


class TestSystemsAndQCRemediations:
    """Verifies fail-closed QC safety, contract validation, and orchestrator synchronization."""

    def test_qc_report_passed_forced_false_on_hard_failures(self):
        """P2-1 Fix: DialogueQCReport.passed is automatically False when hard_failures exist."""
        diag = {
            "code": "TEST_HARD_FAIL",
            "severity": "HARD_FAILURE",
            "message": "Critical failure",
        }
        report = DialogueQCReport(
            chapter_num=1,
            hard_failures=[diag],
            passed=True,  # Attempting to declare passed=True with hard failures
        )
        assert report.passed is False
        assert report.has_hard_failures is True

    def test_corrupt_empty_audio_fails_closed(self, tmp_path: Path):
        """P0-7 Fix: Corrupt/empty WAV triggers hard failure with confidence=0.0."""
        empty_wav = tmp_path / "empty.wav"
        empty_wav.write_bytes(b"")  # 0-byte corrupt file

        editor = DialogueEditor()
        plan = editor.plan_segment_edit(
            audio_path=empty_wav,
            segment_uid="s_corrupt",
            speaker="Narrator",
            text="Hello world.",
        )
        assert plan.confidence == 0.0
        assert "[HARD_FAILURE]" in plan.decision_reason
        assert plan.metadata.get("corrupt") is True

    def test_nan_and_inf_audio_samples_fail_closed_in_qc(self):
        """P1-8 Fix: NaN/Inf samples trigger HARD_FAILURE in DialogueEditingQC."""
        qc = DialogueEditingQC()
        plan = DialogueEditPlan(segment_uid="nan_test", speech_start_ms=0, speech_end_ms=1000)
        # Create audio with NaN
        samples_with_nan = np.ones(2400, dtype=np.float32)
        samples_with_nan[100] = np.nan

        diags = qc.audit_segment_plan(plan, total_audio_ms=1000, samples=samples_with_nan)
        hard_fails = [d for d in diags if d.severity == "HARD_FAILURE"]
        assert any(d.code == "NUMERICAL_INSTABILITY_NAN_INF" for d in hard_fails)


    def test_plan_metadata_contains_segment_index(self, tmp_path: Path):
        """P2-2 Fix: DialogueEditPlan.metadata includes segment_index for mastering lookup."""
        valid_wav = tmp_path / "c001_s0004_test.wav"
        sr = 24000
        samples = (8000.0 * np.sin(2 * np.pi * 440.0 * np.arange(sr) / sr)).astype(np.int16)
        with wave.open(str(valid_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(samples.tobytes())

        editor = DialogueEditor()
        plan = editor.plan_segment_edit(
            audio_path=valid_wav,
            segment_uid="c001_s0004",
            speaker="Dev",
            text="This is a clean line.",
            segment_index=4,
        )
        assert plan.metadata.get("segment_index") == 4
