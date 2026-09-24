#!/usr/bin/env python3
"""
Audiobook Factory - Neural Vocoder Restoration & C2PA Elimination Module (ADR-027).
Eradicates container-level Dirac spikes ("ftt/pops"), C2PA digital watermark screech ("zzz"),
and neural vocoder noise-floor hiss ("hiss") through non-destructive demuxing, zero-crossing
boundary snapping, and studio-grade DSP polishing.
"""

import io
import math
import wave
import struct
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, Optional, Union
import numpy as np

from audiobook_factory.logger import logger


def get_ffmpeg() -> str:
    """Resolve FFmpeg binary path safely across Windows and Linux."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    fallbacks = [
        Path("C:/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/ProgramData/chocolatey/bin/ffmpeg.exe"),
    ]
    for fb in fallbacks:
        if fb.exists():
            return str(fb)
    return "ffmpeg"


def extract_clean_pcm_from_gemini_container(raw_bytes: bytes) -> Tuple[bytes, int, int]:
    """
    Extracts pure PCM speech frames from Gemini's WAV payload, stripping both:
    1. The 44-byte RIFF/WAVE header (which causes +18,770 Dirac impulse clicks).
    2. The trailing 6,020-byte C2PA digital watermark metadata (which causes
       125.4ms of +28,000 amplitude electronic screech static).

    Handles nested double-wrapping (where WAV frames themselves were saved as a WAV).
    Returns: (clean_pcm_bytes, sample_rate, num_frames)
    """
    if not raw_bytes:
        return b"", 24000, 0

    curr = raw_bytes
    framerate = 24000
    nframes = len(curr) // 2

    # Unpack nested containers up to 3 levels if necessary
    for _ in range(3):
        if curr.startswith(b"RIFF") and len(curr) > 44:
            try:
                bio = io.BytesIO(curr)
                with wave.open(bio, "rb") as wf:
                    channels = wf.getnchannels()
                    framerate = wf.getframerate()
                    nframes = wf.getnframes()
                    curr = wf.readframes(nframes)
                    if channels > 1:
                        arr = np.frombuffer(curr, dtype=np.int16).reshape(-1, channels)
                        curr = np.mean(arr, axis=1).astype(np.int16).tobytes()
            except Exception as e:
                logger.debug(f"Demux pass encountered non-wave structure: {e}")
                break
        else:
            break

    return curr, framerate, len(curr) // 2


def read_surgically_cleaned_chunk(
    chunk_path: Union[Path, str],
    target_sample_rate: int = 24000,
    safety_buffer_ms: float = 40.0,
    fade_in_ms: float = 12.0,
    fade_out_ms: float = 18.0
) -> Tuple[bytes, int]:
    """
    Non-destructively reads audio from chunk_path, demuxes the container,
    and applies Layer 2 surgical dead-air clamping and zero-crossing Hann micro-fades.
    Returns: (clean_pcm_bytes, trimmed_dead_air_ms)
    """
    p = Path(chunk_path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Audio chunk not found: {p}")

    raw_file_bytes = p.read_bytes()
    clean_pcm, src_rate, _ = extract_clean_pcm_from_gemini_container(raw_file_bytes)

    if src_rate != target_sample_rate:
        ffmpeg_bin = get_ffmpeg()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-v", "error",
            "-f", "s16le",
            "-ar", str(src_rate),
            "-ac", "1",
            "-i", "pipe:0",
            "-ar", str(target_sample_rate),
            "-ac", "1",
            "-f", "s16le",
            "pipe:1"
        ]
        proc = subprocess.run(cmd, input=clean_pcm, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        clean_pcm = proc.stdout

    from audiobook_factory.audio_qc_agent import AudioQCAgent
    agent = AudioQCAgent(sample_rate=target_sample_rate, safety_buffer_ms=safety_buffer_ms)
    clean_bytes, trimmed_ms, _ = agent.surgical_clean_chunk(
        clean_pcm,
        fade_in_ms=fade_in_ms,
        fade_out_ms=fade_out_ms
    )
    return clean_bytes, trimmed_ms


def read_clean_chunk_pcm(chunk_path: Union[Path, str], target_sample_rate: int = 24000) -> bytes:
    """
    Non-destructively reads audio from chunk_path, stripping container metadata,
    and applying surgical dead-air clamping (ADR-028).
    The original file on disk is never altered.
    """
    pcm, _ = read_surgically_cleaned_chunk(chunk_path, target_sample_rate=target_sample_rate)
    return pcm


def apply_zero_crossing_micro_fades(
    pcm_bytes: bytes,
    sample_rate: int = 24000,
    fade_in_ms: float = 12.0,
    fade_out_ms: float = 18.0,
    snap_zero_crossing: bool = True
) -> bytes:
    """
    Applies zero-crossing boundary snapping and raised-cosine (Hann) micro-fades.
    Guarantees:
    - Initial sample: 0.0 (0.0000% Dirac discontinuity)
    - Final sample: 0.0 (0.0000% trailing step pop)
    - Smooth, continuous waveform transitions between dialogue lines.
    """
    if not pcm_bytes or len(pcm_bytes) < 4:
        return pcm_bytes

    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    n = len(samples)
    if n < 8:
        return pcm_bytes

    # 1. DC bias normalization
    dc_bias = np.mean(samples)
    samples -= dc_bias

    # 2. Zero-crossing search in the initial 5ms window
    if snap_zero_crossing and n > 120:
        search_window = min(int(sample_rate * 0.005), n // 4)
        for idx in range(search_window - 1):
            if samples[idx] * samples[idx + 1] <= 0.0:
                # Snap leading slice to start at zero crossing
                samples = samples[idx:]
                n = len(samples)
                break

    # 3. Zero-crossing search in the trailing 5ms window
    if snap_zero_crossing and n > 120:
        search_window = min(int(sample_rate * 0.005), n // 4)
        for offset in range(search_window - 1):
            idx = n - 1 - offset
            if samples[idx] * samples[idx - 1] <= 0.0:
                samples = samples[:idx + 1]
                n = len(samples)
                break

    # 4. Raised-Cosine Hann Micro-Fades
    fade_in_samples = max(2, min(int(sample_rate * (fade_in_ms / 1000.0)), n // 2))
    fade_out_samples = max(2, min(int(sample_rate * (fade_out_ms / 1000.0)), n // 2))

    fade_in_curve = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_in_samples)))
    fade_out_curve = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, fade_out_samples)))

    samples[:fade_in_samples] *= fade_in_curve
    samples[-fade_out_samples:] *= fade_out_curve

    # 5. Strict boundary zero-pinning
    samples[0] = 0.0
    samples[-1] = 0.0

    return np.clip(np.round(samples), -32768, 32767).astype(np.int16).tobytes()


def apply_studio_restoration_filter(
    input_wav: Union[Path, str],
    output_wav: Union[Path, str],
    sample_rate: int = 24000,
    noise_reduction_db: float = 8.0,
    noise_floor_db: float = -52.0
) -> Path:
    """
    Executes the 6-stage studio audio restoration DSP filter chain via FFmpeg:
    1. adeclick=w=20:o=75 (Removes impulsive phase clicks)
    2. afftdn=nr=8:nf=-52:tn=1 (Gentle 8dB spectral de-hissing preserving vocal formants)
    3. highpass=f=40 (Removes subsonic rumble and DC drift)
    4. lowpass=f=11200 (Eliminates 12kHz Nyquist boundary metallic whistle)
    5. deesser=i=0.20:m=0.5:f=0.5:s=o (Smooths harsh 's/sh' sibilance sizzle)
    6. agate=threshold=0.005:range=0.15:attack=15:release=120 (Downward expander:
       attenuates background vocoder hiss by -16dB in natural speech pauses)
    """
    inp = Path(input_wav).resolve()
    out = Path(output_wav).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    filter_graph = (
        "adeclick=w=20:o=75,"
        f"afftdn=nr={noise_reduction_db}:nf={noise_floor_db}:tn=1,"
        "highpass=f=40,"
        "lowpass=f=11200,"
        "deesser=i=0.20:m=0.5:f=0.5:s=o,"
        "agate=threshold=0.005:range=0.15:attack=15:release=120"
    )

    ffmpeg_bin = get_ffmpeg()
    cmd = [
        ffmpeg_bin,
        "-y",
        "-v", "error",
        "-i", str(inp),
        "-af", filter_graph,
        "-ar", str(sample_rate),
        "-ac", "1",
        str(out)
    ]

    subprocess.run(cmd, check=True)
    return out
