#!/usr/bin/env python3
"""
Audiobook Factory - Alignment Engine: Audio I/O & WAV Utilities.
Provides robust standard library wave loaders and duration analyzers that bypass
C++ backend dependencies (soundfile/sox) on Windows.
"""

from __future__ import annotations
import wave
import numpy as np
from pathlib import Path
from typing import Tuple

from audiobook_factory.logger import logger


def _load_wav_tensor_safely(audio_path: Path):
    """
    Loads 16-bit PCM WAV into a normalized PyTorch tensor directly via standard library wave,
    bypassing torchaudio C++ backend dependencies (soundfile/sox) that fail on Windows.
    """
    import torch
    with wave.open(str(audio_path), "rb") as wf:
        sample_rate = wf.getframerate()
        n_channels = wf.getnchannels()
        n_frames = wf.getnframes()
        dur_est = n_frames / float(sample_rate) if sample_rate > 0 else 0.0
        if dur_est > 600.0:
            raise ValueError(f"WAV duration {dur_est:.1f}s exceeds bounded alignment limit of 600.0s")
        frames = wf.readframes(n_frames)
        raw_tensor = torch.frombuffer(bytearray(frames), dtype=torch.int16).to(torch.float32) / 32768.0
        waveform = raw_tensor.view(-1, n_channels).t()
        if n_channels > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        return waveform, sample_rate


def _read_pcm_samples(audio_path: Path) -> Tuple[np.ndarray, int]:
    """Reads raw 16-bit PCM samples safely into a NumPy array."""
    try:
        with wave.open(str(audio_path), "rb") as wf:
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            dur_est = n_frames / float(sample_rate) if sample_rate > 0 else 0.0
            if dur_est > 600.0:
                raise ValueError(f"WAV duration {dur_est:.1f}s exceeds bounded limit of 600.0s")
            raw = wf.readframes(n_frames)
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        return samples, sample_rate
    except Exception as e:
        logger.warning(f"  [!] WorkstationForcedAligner: Could not read PCM samples: {e}")
        return np.array([], dtype=np.float32), 24000


def _get_wav_duration_ms(audio_path: Path) -> int:
    """Reads exact duration of a WAV file in milliseconds."""
    try:
        with wave.open(str(audio_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return int((frames / float(rate)) * 1000)
    except Exception:
        size = audio_path.stat().st_size
        return max(500, int((size / 48000.0) * 1000))
