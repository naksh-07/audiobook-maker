#!/usr/bin/env python3
"""
Unit tests for Dialogue Editorial DSP and Timeline Assembler (DE-01 - DE-07).
Tests Hann micro-fades, speech floor silence trimming, highpass filtering,
and monotonic timeline assembly.
"""

from pathlib import Path
import pytest
import numpy as np

from audiobook_factory.contracts.screenplay import ScreenplaySegment
from audiobook_factory.core.cache.take_bank import TakeBank
from audiobook_factory.core.dialogue_editorial.dsp import (
    apply_hann_fades,
    apply_highpass_filter,
    generate_silence_padding,
    trim_silence_speech_floor,
)
from audiobook_factory.core.dialogue_editorial.editor import (
    DialogueEditorialEngine,
    EditorialPlan,
)
from tests.core.test_take_bank import create_dummy_wav


class TestDialogueEditorialDSP:
    def test_hann_micro_fades(self):
        sr = 48000
        # Constant amplitude buffer
        data = np.ones(4800, dtype=np.float32)  # 100ms
        faded = apply_hann_fades(data, sample_rate=sr, fade_in_ms=12.0, fade_out_ms=18.0)

        # Start should start near zero
        assert faded[0] == pytest.approx(0.0, abs=1e-3)
        # End should end near zero
        assert faded[-1] == pytest.approx(0.0, abs=1e-3)
        # Middle should remain 1.0
        assert faded[2400] == pytest.approx(1.0, abs=1e-3)

    def test_silence_trimming(self):
        sr = 48000
        # 50ms silence + 50ms tone + 50ms silence
        silence = np.zeros(2400, dtype=np.float32)
        tone = np.sin(2 * np.pi * 440 * np.arange(2400) / sr).astype(np.float32) * 0.5
        audio = np.concatenate([silence, tone, silence])

        trimmed = trim_silence_speech_floor(audio, sample_rate=sr, threshold_dbfs=-52.0, padding_ms=5.0)
        # Trimmed length should be significantly smaller than original 150ms
        assert len(trimmed) < len(audio)
        assert len(trimmed) >= len(tone)

    def test_highpass_filter(self):
        sr = 48000
        # DC bias + 10 Hz tone
        dc_and_rumble = np.ones(4800, dtype=np.float32) * 0.5
        filtered = apply_highpass_filter(dc_and_rumble, sample_rate=sr, cutoff_hz=40.0)

        # After transient, DC component should be strongly attenuated
        assert np.abs(filtered[-100:]).mean() < 0.1

    def test_timeline_stem_assembly(self, tmp_path: Path):
        cache_dir = tmp_path / "cache"
        take_bank = TakeBank(cache_dir=cache_dir)
        engine = DialogueEditorialEngine(EditorialPlan(default_pause_ms=200))

        # Create two segments and store takes
        seg1 = ScreenplaySegment(
            segment_uid="s01",
            beat_ref="b01",
            speaker="Geralt",
            voice_id="Charon",
            text="Line 1 text.",
            post_speech_pause_ms=250,
        )
        seg2 = ScreenplaySegment(
            segment_uid="s02",
            beat_ref="b01",
            speaker="Narrator",
            voice_id="Aoede",
            text="Line 2 text.",
            post_speech_pause_ms=400,
        )

        wav1 = create_dummy_wav(tmp_path / "t1.wav", duration_sec=1.0)
        wav2 = create_dummy_wav(tmp_path / "t2.wav", duration_sec=2.0)

        take_bank.store_take(seg1, wav1)
        take_bank.store_take(seg2, wav2)

        out_stem = tmp_path / "master_dialogue.wav"
        out_path, ledger = engine.assemble_dialogue_stem(
            segments=[seg1, seg2],
            take_bank=take_bank,
            output_wav_path=out_stem,
            chapter_id=3,
        )

        assert out_path.exists()
        assert ledger.chapter_id == 3
        assert len(ledger.cues) == 2
        assert ledger.cues[0].speaker == "Geralt"
        assert ledger.cues[1].speaker == "Narrator"
        assert ledger.cues[0].start_time_sec == 0.0
        # Check monotonic timestamps
        assert ledger.cues[1].start_time_sec > ledger.cues[0].end_time_sec
        assert ledger.total_duration_sec > 3.0
