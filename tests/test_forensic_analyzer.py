import wave
import numpy as np
import pytest
from pathlib import Path

from audiobook_factory.forensic_analyzer import MathematicalAcousticAnalyzer, extract_acoustic_telemetry
from audiobook_factory.audio_qc_agent import AudioQCAgent


def test_analyzer_detects_c2pa_burst_after_valley():
    sample_rate = 24000
    # Simulate: 2.0s of sine wave speech (440Hz, amp=12000), followed by 0.3s of silence, then 0.1s of clipping noise (amp=32767)
    t_speech = np.linspace(0, 2.0, int(sample_rate * 2.0))
    speech = (np.sin(2 * np.pi * 440 * t_speech) * 12000).astype(np.int16)

    silence = np.zeros(int(sample_rate * 0.30), dtype=np.int16)

    noise_burst = np.full(int(sample_rate * 0.10), 32767, dtype=np.int16)

    combined = np.concatenate([speech, silence, noise_burst])
    total_dur = len(combined) / sample_rate

    analyzer = MathematicalAcousticAnalyzer(sample_rate=sample_rate)
    speech_end_t, dead_air_sec, anomalies = analyzer.detect_speech_endpoint(combined.astype(np.float32))

    # True speech should end near 2.04s (2.0s + 40ms safety buffer)
    assert 2.00 <= speech_end_t <= 2.10
    # Dead air should be approximately 0.40s (0.3s silence + 0.1s noise)
    assert dead_air_sec >= 0.30
    assert any("BURST" in a.get("type", "") for a in anomalies)


def test_audio_qc_agent_clamps_and_pins_boundaries():
    sample_rate = 24000
    # Create signal with dead air and trailing spike
    t_speech = np.linspace(0, 1.5, int(sample_rate * 1.5))
    speech = (np.sin(2 * np.pi * 300 * t_speech) * 10000).astype(np.int16)
    silence = np.zeros(int(sample_rate * 0.25), dtype=np.int16)
    burst = np.full(int(sample_rate * 0.08), 28000, dtype=np.int16)

    signal = np.concatenate([speech, silence, burst]).tobytes()

    agent = AudioQCAgent(sample_rate=sample_rate)
    clean_pcm, trimmed_ms, telemetry = agent.surgical_clean_chunk(signal)

    cleaned_samples = np.frombuffer(clean_pcm, dtype=np.int16)
    # Endpoints must be strictly 0
    assert cleaned_samples[0] == 0
    assert cleaned_samples[-1] == 0

    # Cleaned duration must be shorter than original by approximately trimmed_ms
    assert trimmed_ms >= 250
    assert len(cleaned_samples) < len(np.frombuffer(signal, dtype=np.int16))
