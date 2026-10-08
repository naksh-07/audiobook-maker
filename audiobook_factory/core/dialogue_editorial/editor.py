#!/usr/bin/env python3
"""
Audiobook Factory - Dialogue Editorial Assembler Engine.
Standard: v6.0-ENTERPRISE-DAG
Assembles multiple TakeBank takes into a seamless, broadcast-ready master dialogue stem
with synchronized TimelineLedger in < 2.0 seconds with zero network tokens.
"""

from __future__ import annotations
import math
import struct
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from pydantic import BaseModel, Field

from audiobook_factory.contracts.editorial import TimelineCueRecord, TimelineLedger
from audiobook_factory.contracts.screenplay import ScreenplaySegment
from audiobook_factory.core.cache.take_bank import TakeBank
from audiobook_factory.core.dialogue_editorial.dsp import (
    apply_hann_fades,
    apply_highpass_filter,
    generate_silence_padding,
    trim_silence_speech_floor,
)


class EditorialPlan(BaseModel):
    """Configuration for dialogue editorial conditioning and assembly."""
    pre_speech_fade_ms: float = Field(default=12.0, ge=0.0, description="DE-02 Fade-in duration")
    post_speech_fade_ms: float = Field(default=18.0, ge=0.0, description="DE-02 Fade-out duration")
    speech_floor_dbfs: float = Field(default=-52.0, le=0.0, description="DE-01 Silence threshold")
    highpass_freq_hz: float = Field(default=40.0, ge=10.0, description="DE-03 Highpass cutoff")
    default_pause_ms: int = Field(default=400, ge=0, description="DE-04 Default turn pause")
    target_sample_rate: int = Field(default=48000, description="Target stem sample rate")


class DialogueEditorialEngine:
    """
    Assembles synthesized audio takes from TakeBank into a continuous lossless dialogue stem.
    Applies DE-01 through DE-07 DSP rules and emits a certified monotonic TimelineLedger.
    """

    def __init__(self, plan: Optional[EditorialPlan] = None):
        self.plan = plan or EditorialPlan()

    def read_wav_as_float32(self, wav_path: Union[str, Path]) -> Tuple[np.ndarray, int]:
        """Reads a WAV file into a normalized float32 numpy array (-1.0 to 1.0)."""
        with wave.open(str(wav_path), "rb") as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        if sampwidth == 2:
            data = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 3:
            # 24-bit PCM
            raw_array = np.frombuffer(raw_bytes, dtype=np.uint8)
            reshaped = raw_array.reshape(-1, 3)
            # Pad to 32-bit int
            padded = np.column_stack([np.zeros((len(reshaped), 1), dtype=np.uint8), reshaped])
            data = padded.view(dtype=np.int32).squeeze().astype(np.float32) / 2147483648.0
        elif sampwidth == 4:
            data = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            data = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0

        if n_channels > 1:
            data = data.reshape(-1, n_channels)
            # Downmix to mono if multi-channel
            data = np.mean(data, axis=1)

        return data, sample_rate

    def write_float32_as_wav(self, audio_data: np.ndarray, sample_rate: int, output_path: Union[str, Path]) -> Path:
        """Writes normalized float32 array to a standard 16-bit 48kHz PCM WAV."""
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        clipped = np.clip(audio_data, -1.0, 1.0)
        int16_data = (clipped * 32767.0).astype(np.int16)

        with wave.open(str(out_p), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(int16_data.tobytes())

        return out_p

    def condition_take_audio(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
        plan: Optional[EditorialPlan] = None,
    ) -> np.ndarray:
        """Applies DE-01 (trim), DE-03 (highpass), and DE-02 (Hann fades)."""
        active_plan = plan or self.plan

        trimmed = trim_silence_speech_floor(
            audio_data,
            sample_rate=sample_rate,
            threshold_dbfs=active_plan.speech_floor_dbfs,
        )
        filtered = apply_highpass_filter(
            trimmed,
            sample_rate=sample_rate,
            cutoff_hz=active_plan.highpass_freq_hz,
        )
        faded = apply_hann_fades(
            filtered,
            sample_rate=sample_rate,
            fade_in_ms=active_plan.pre_speech_fade_ms,
            fade_out_ms=active_plan.post_speech_fade_ms,
        )
        return faded

    def assemble_dialogue_stem(
        self,
        segments: List[ScreenplaySegment],
        take_bank: TakeBank,
        output_wav_path: Union[str, Path],
        chapter_id: int = 1,
        plan: Optional[EditorialPlan] = None,
    ) -> Tuple[Path, TimelineLedger]:
        """
        Assembles all segment audio takes into a continuous dialogue stem WAV
        and emits the certified TimelineLedger with accurate cue offsets.
        """
        active_plan = plan or self.plan
        sample_rate = active_plan.target_sample_rate
        audio_buffers: List[np.ndarray] = []
        cues: List[TimelineCueRecord] = []
        current_time_sec = 0.0

        for seg in segments:
            take_meta = take_bank.lookup_take(seg)
            if not take_meta or not Path(take_meta.take_wav_path).exists():
                raise FileNotFoundError(
                    f"Take not found in TakeBank for segment {seg.segment_uid} (Speaker: {seg.speaker})"
                )

            raw_audio, sr = self.read_wav_as_float32(take_meta.take_wav_path)
            # Resample if sample rate doesn't match target
            if sr != sample_rate:
                # Basic linear interpolation for rate matching
                new_len = int(len(raw_audio) * sample_rate / sr)
                raw_audio = np.interp(
                    np.linspace(0, len(raw_audio), new_len, endpoint=False),
                    np.arange(len(raw_audio)),
                    raw_audio,
                ).astype(np.float32)

            conditioned = self.condition_take_audio(raw_audio, sample_rate, active_plan)
            seg_dur_sec = len(conditioned) / float(sample_rate)

            # Record Timeline Cue
            start_sec = round(current_time_sec, 4)
            end_sec = round(current_time_sec + seg_dur_sec, 4)
            pause_ms = seg.post_speech_pause_ms if seg.post_speech_pause_ms is not None else active_plan.default_pause_ms
            pause_sec = round(pause_ms / 1000.0, 4)

            cue = TimelineCueRecord(
                segment_uid=seg.segment_uid,
                speaker=seg.speaker,
                start_time_sec=start_sec,
                end_time_sec=end_sec,
                fade_in_ms=active_plan.pre_speech_fade_ms,
                fade_out_ms=active_plan.post_speech_fade_ms,
                pause_after_sec=pause_sec,
            )
            cues.append(cue)

            audio_buffers.append(conditioned)
            current_time_sec += seg_dur_sec

            # Append Pause Silence
            if pause_ms > 0:
                silence = generate_silence_padding(pause_ms, sample_rate)
                audio_buffers.append(silence)
                current_time_sec += pause_sec

        if audio_buffers:
            master_buffer = np.concatenate(audio_buffers)
        else:
            master_buffer = np.zeros(0, dtype=np.float32)

        out_wav = self.write_float32_as_wav(master_buffer, sample_rate, output_wav_path)
        total_duration = round(len(master_buffer) / float(sample_rate), 4)

        ledger = TimelineLedger(
            chapter_id=chapter_id,
            total_duration_sec=total_duration,
            cues=cues,
        )
        return out_wav, ledger
