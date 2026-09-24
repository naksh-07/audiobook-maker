import io
import wave
import struct
import tempfile
from pathlib import Path
import numpy as np
import pytest

from audiobook_factory.restoration import (
    extract_clean_pcm_from_gemini_container,
    read_clean_chunk_pcm,
    apply_zero_crossing_micro_fades,
)


def _create_mock_gemini_wav_payload(n_speech_samples: int = 2400) -> bytes:
    """
    Creates a simulated Gemini TTS base64 payload containing:
    1. 44-byte RIFF/WAVE header
    2. PCM speech samples (e.g. 440Hz sine wave)
    3. Trailing C2PA metadata bytes (e.g. 'cetype/trainedAlgorithmicMedia...')
    """
    t = np.linspace(0, 0.1, n_speech_samples)
    speech_signal = (np.sin(2 * np.pi * 440 * t) * 15000).astype(np.int16)
    pcm_bytes = speech_signal.tobytes()

    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_bytes)

    wav_container_bytes = bio.getvalue()

    # Append 6,020 bytes of mock C2PA metadata
    c2pa_metadata = b"jumb/c2pa" + b"X" * 6000 + b"cetype/trainedAlgorithmicMedia"
    return wav_container_bytes + c2pa_metadata


def test_extract_clean_pcm_strips_riff_and_c2pa():
    payload = _create_mock_gemini_wav_payload(n_speech_samples=2400)
    assert len(payload) > 2400 * 2 + 6000

    clean_pcm, rate, frames = extract_clean_pcm_from_gemini_container(payload)

    assert rate == 24000
    assert frames == 2400
    assert len(clean_pcm) == 2400 * 2
    # Ensure trailing C2PA metadata was completely discarded
    assert b"cetype/trainedAlgorithmicMedia" not in clean_pcm
    assert not clean_pcm.startswith(b"RIFF")


def test_zero_crossing_micro_fades_pins_boundaries():
    # Signal with abrupt start and end (+20000 and -18000)
    samples = np.full(1200, 20000, dtype=np.int16)
    samples[-1] = -18000
    raw_bytes = samples.tobytes()

    smoothed = apply_zero_crossing_micro_fades(
        raw_bytes,
        sample_rate=24000,
        fade_in_ms=12.0,
        fade_out_ms=18.0
    )

    smoothed_samples = np.frombuffer(smoothed, dtype=np.int16)
    assert smoothed_samples[0] == 0
    assert smoothed_samples[-1] == 0


def test_read_clean_chunk_pcm_non_destructive():
    payload = _create_mock_gemini_wav_payload(n_speech_samples=1200)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(payload)
        temp_path = Path(tf.name)

    try:
        clean_pcm = read_clean_chunk_pcm(temp_path, target_sample_rate=24000)
        assert len(clean_pcm) == 1200 * 2

        # Verify disk file is UNTOUCHED (still contains original raw payload and C2PA)
        disk_bytes = temp_path.read_bytes()
        assert disk_bytes == payload
        assert b"cetype/trainedAlgorithmicMedia" in disk_bytes
    finally:
        if temp_path.exists():
            temp_path.unlink()
