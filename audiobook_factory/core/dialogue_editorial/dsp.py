#!/usr/bin/env python3
"""
Audiobook Factory - Dialogue Editorial DSP Rules (DE-01 - DE-07).
Standard: v6.0-ENTERPRISE-DAG
Implements Hann micro-fades (12ms/18ms), speech floor silence trimming (-52 dBFS),
sub-bass highpass filter (40Hz), and pause/overlap generators.
"""

from __future__ import annotations
import math
import numpy as np
from typing import Tuple


def apply_hann_fades(
    audio_data: np.ndarray,
    sample_rate: int,
    fade_in_ms: float = 12.0,
    fade_out_ms: float = 18.0,
) -> np.ndarray:
    """
    Applies DE-02 Hann micro-fades (12ms pre-speech fade-in / 18ms post-speech fade-out)
    to eliminate boundary clicks, clicks at speech zero-crossings, and breath artifacts.
    """
    if audio_data is None or len(audio_data) == 0:
        return audio_data

    out = np.copy(audio_data).astype(np.float32)
    total_samples = len(out)

    fade_in_samples = int(fade_in_ms * sample_rate / 1000.0)
    fade_out_samples = int(fade_out_ms * sample_rate / 1000.0)

    # Ensure fade lengths do not exceed half the total buffer
    fade_in_samples = min(fade_in_samples, total_samples // 2)
    fade_out_samples = min(fade_out_samples, total_samples // 2)

    if fade_in_samples > 0:
        # Half-Hann rising curve from 0 to 1
        hann_in = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade_in_samples, dtype=np.float32) / fade_in_samples))
        if out.ndim == 1:
            out[:fade_in_samples] *= hann_in
        else:
            out[:fade_in_samples, :] *= hann_in[:, np.newaxis]

    if fade_out_samples > 0:
        # Half-Hann falling curve from 1 to 0
        hann_out = 0.5 * (1.0 + np.cos(np.pi * np.arange(fade_out_samples, dtype=np.float32) / fade_out_samples))
        if out.ndim == 1:
            out[-fade_out_samples:] *= hann_out
        else:
            out[-fade_out_samples:, :] *= hann_out[:, np.newaxis]

    return out


def trim_silence_speech_floor(
    audio_data: np.ndarray,
    sample_rate: int,
    threshold_dbfs: float = -52.0,
    padding_ms: float = 10.0,
) -> np.ndarray:
    """
    DE-01 Endpoint Zero-Crossing Snip: Trims leading and trailing silence below
    -52 dBFS speech floor with a safety margin.
    """
    if audio_data is None or len(audio_data) == 0:
        return audio_data

    threshold_amp = 10.0 ** (threshold_dbfs / 20.0)
    if audio_data.ndim == 1:
        abs_data = np.abs(audio_data)
    else:
        abs_data = np.max(np.abs(audio_data), axis=1)

    above_threshold = np.where(abs_data >= threshold_amp)[0]
    if len(above_threshold) == 0:
        return audio_data

    pad_samples = int(padding_ms * sample_rate / 1000.0)
    start_idx = max(0, above_threshold[0] - pad_samples)
    end_idx = min(len(audio_data), above_threshold[-1] + pad_samples)

    return audio_data[start_idx:end_idx]


def apply_highpass_filter(
    audio_data: np.ndarray,
    sample_rate: int,
    cutoff_hz: float = 40.0,
) -> np.ndarray:
    """
    DE-03 Sub-Bass DC Offset Cleanup: 2nd-order Butterworth Highpass filter at 40 Hz
    eliminating microphone boom, DC bias, and sub-bass rumble.
    """
    if audio_data is None or len(audio_data) == 0:
        return audio_data

    # Biquad filter coefficients calculation for Butterworth Highpass
    w0 = 2.0 * math.pi * cutoff_hz / sample_rate
    cos_w0 = math.cos(w0)
    alpha = math.sin(w0) / (2.0 * (1.0 / math.sqrt(2.0)))

    b0 = (1.0 + cos_w0) / 2.0
    b1 = -(1.0 + cos_w0)
    b2 = (1.0 + cos_w0) / 2.0
    a0 = 1.0 + alpha
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha

    # Normalize coefficients
    b0_norm, b1_norm, b2_norm = b0 / a0, b1 / a0, b2 / a0
    a1_norm, a2_norm = a1 / a0, a2 / a0

    out = np.zeros_like(audio_data, dtype=np.float32)

    # 1D single channel filtering
    if audio_data.ndim == 1:
        x1 = x2 = y1 = y2 = 0.0
        for i in range(len(audio_data)):
            x0 = float(audio_data[i])
            y0 = b0_norm * x0 + b1_norm * x1 + b2_norm * x2 - a1_norm * y1 - a2_norm * y2
            out[i] = y0
            x2, x1 = x1, x0
            y2, y1 = y1, y0
    else:
        for ch in range(audio_data.shape[1]):
            x1 = x2 = y1 = y2 = 0.0
            for i in range(len(audio_data)):
                x0 = float(audio_data[i, ch])
                y0 = b0_norm * x0 + b1_norm * x1 + b2_norm * x2 - a1_norm * y1 - a2_norm * y2
                out[i, ch] = y0
                x2, x1 = x1, x0
                y2, y1 = y1, y0

    return out


def generate_silence_padding(
    duration_ms: int,
    sample_rate: int,
    channels: int = 1,
) -> np.ndarray:
    """
    DE-04 Contextual Pause Realization: Generates sample-accurate silence buffer.
    """
    if duration_ms <= 0:
        return np.zeros((0,) if channels == 1 else (0, channels), dtype=np.float32)

    n_samples = int(duration_ms * sample_rate / 1000.0)
    if channels == 1:
        return np.zeros(n_samples, dtype=np.float32)
    return np.zeros((n_samples, channels), dtype=np.float32)
