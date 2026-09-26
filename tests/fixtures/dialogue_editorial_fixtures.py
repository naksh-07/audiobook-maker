#!/usr/bin/env python3
"""
Audiobook Factory - Golden Mini Fixtures for Dialogue Editorial Layer (DE-01 - DE-04).
Generates deterministic synthetic audio waveforms with exact acoustic properties
representing the 7 canonical dialogue scenarios:
1. normal_conversation
2. rapid_exchange
3. emotional_line (grief / emotional release tail)
4. breath_heavy_line (combat exertion / pre-roll breath)
5. long_trailing_silence (TTS dead air carrier)
6. hesitation (ellipses / reaction gap)
7. realization_reaction (suspense / cognitive absorption)
"""

from __future__ import annotations
import math
import wave
from pathlib import Path
from typing import Dict, Any, Tuple
import numpy as np

from audiobook_factory.contracts import ScreenplaySegment
from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    PerformanceEvidence,
    BreathEvidence,
    AcousticEvidence,
)
from audiobook_factory.alignment_contracts import AlignmentResult, WordAlignment, PauseInterval, SpeechRegion


def generate_scenario_waveform(
    filepath: Path | str,
    duration_sec: float,
    speech_start_sec: float,
    speech_end_sec: float,
    sample_rate: int = 24000,
    has_pre_breath: bool = False,
    has_post_breath: bool = False,
    is_emotional_decay: bool = False,
    trailing_burst: bool = False,
    amplitude: float = 0.5,
) -> Path:
    """
    Synthesizes a deterministic 16-bit mono PCM WAV conforming to precise scenario timing.
    """
    target = Path(filepath).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    n_samples = int(duration_sec * sample_rate)
    samples = np.zeros(n_samples, dtype=np.float32)

    # 1. Active Speech Region (440Hz voiced formant + harmonic)
    s_start_idx = int(speech_start_sec * sample_rate)
    s_end_idx = int(speech_end_sec * sample_rate)
    speech_len = max(0, s_end_idx - s_start_idx)

    if speech_len > 0:
        t = np.arange(speech_len) / sample_rate
        # Formant-like harmonic structure
        speech_wave = (
            np.sin(2 * np.pi * 220.0 * t)
            + 0.5 * np.sin(2 * np.pi * 440.0 * t)
            + 0.25 * np.sin(2 * np.pi * 880.0 * t)
        )
        samples[s_start_idx:s_end_idx] = speech_wave * (amplitude * 24000.0)

    # 2. Pre-roll breath intake (soft noise / breath envelope in pre-speech region)
    if has_pre_breath and s_start_idx > 100:
        b_len = min(s_start_idx, int(0.20 * sample_rate))
        b_start = s_start_idx - b_len
        # Low-amplitude respiratory intake
        t_b = np.linspace(0, np.pi, b_len)
        breath_wave = np.sin(t_b) * (0.08 * 24000.0)
        samples[b_start:s_start_idx] += breath_wave

    # 3. Post-roll emotional exhale / decay
    if is_emotional_decay and s_end_idx < n_samples:
        decay_len = min(n_samples - s_end_idx, int(0.25 * sample_rate))
        t_d = np.linspace(0, 1.0, decay_len)
        decay_envelope = np.exp(-4.0 * t_d)
        decay_wave = np.sin(2 * np.pi * 220.0 * (t_d * decay_len / sample_rate)) * decay_envelope
        samples[s_end_idx : s_end_idx + decay_len] += decay_wave * (amplitude * 12000.0)

    elif has_post_breath and s_end_idx < n_samples:
        b_len = min(n_samples - s_end_idx, int(0.18 * sample_rate))
        t_b = np.linspace(0, np.pi, b_len)
        samples[s_end_idx : s_end_idx + b_len] += np.sin(t_b) * (0.06 * 24000.0)

    # 4. Trailing vocoder / C2PA artifact burst (high amplitude late burst after silence valley)
    if trailing_burst and s_end_idx < n_samples - int(0.1 * sample_rate):
        burst_start = n_samples - int(0.08 * sample_rate)
        samples[burst_start:] = 28000.0 * np.sign(np.sin(2 * np.pi * 1000.0 * np.arange(n_samples - burst_start)))

    # Clip to int16 range
    int16_samples = np.clip(samples, -32768.0, 32767.0).astype(np.int16)

    with wave.open(str(target), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_samples.tobytes())

    return target


def create_scenario_fixtures(base_dir: Path | str) -> Dict[str, Dict[str, Any]]:
    """
    Creates the complete golden set of 7 dialogue scenarios.
    """
    b_dir = Path(base_dir).resolve()
    b_dir.mkdir(parents=True, exist_ok=True)

    scenarios: Dict[str, Dict[str, Any]] = {}

    # 1. Normal Conversation
    wav_1 = generate_scenario_waveform(
        filepath=b_dir / "c001_s0001_normal.wav",
        duration_sec=2.4,
        speech_start_sec=0.04,
        speech_end_sec=2.32,
    )
    dir_1 = PerformanceDirection(
        index=1,
        speaker="Dev",
        surface_emotion="neutral",
        character_state="neutral",
        actioning="inform",
        pause_after_ms=360,
    )
    align_1 = AlignmentResult(
        words=[
            WordAlignment(token="hum", normalized_token="hum", start_ms=40, end_ms=600),
            WordAlignment(token="kalse", normalized_token="kalse", start_ms=650, end_ms=1300),
            WordAlignment(token="niklenge", normalized_token="niklenge", start_ms=1350, end_ms=2320),
        ],
        start_ms=40,
        end_ms=2320,
    )
    scenarios["normal_conversation"] = {
        "audio_path": wav_1,
        "direction": dir_1,
        "alignment": align_1,
        "text": "हम कल से निकलेंगे।",
        "speaker": "Dev",
    }

    # 2. Rapid Exchange (Eager counter, high tension)
    wav_2 = generate_scenario_waveform(
        filepath=b_dir / "c001_s0002_rapid.wav",
        duration_sec=1.2,
        speech_start_sec=0.02,
        speech_end_sec=1.18,
    )
    dir_2 = PerformanceDirection(
        index=2,
        speaker="Kabir",
        surface_emotion="anger",
        character_state="escalation",
        turn_taking_behavior="eager_counter",
        tension_after=0.85,
        pause_after_ms=180,
    )
    align_2 = AlignmentResult(
        words=[
            WordAlignment(token="nahi", normalized_token="nahi", start_ms=20, end_ms=400),
            WordAlignment(token="aaj", normalized_token="aaj", start_ms=420, end_ms=1180),
        ],
        start_ms=20,
        end_ms=1180,
    )
    scenarios["rapid_exchange"] = {
        "audio_path": wav_2,
        "direction": dir_2,
        "alignment": align_2,
        "text": "नहीं, आज ही!",
        "speaker": "Kabir",
    }

    # 3. Emotional Line (Grief / emotional vocal decay)
    wav_3 = generate_scenario_waveform(
        filepath=b_dir / "c001_s0003_emotional.wav",
        duration_sec=3.0,
        speech_start_sec=0.05,
        speech_end_sec=2.40,
        is_emotional_decay=True,
    )
    dir_3 = PerformanceDirection(
        index=3,
        speaker="Ananya",
        surface_emotion="grief",
        character_state="grief",
        silence_type="emotional_freeze",
        post_roll_breath_ms=250,
        pause_after_ms=1400,
    )
    align_3 = AlignmentResult(
        words=[
            WordAlignment(token="sab", normalized_token="sab", start_ms=50, end_ms=800),
            WordAlignment(token="khatam", normalized_token="khatam", start_ms=850, end_ms=1600),
            WordAlignment(token="ho", normalized_token="ho", start_ms=1650, end_ms=2000),
            WordAlignment(token="gaya", normalized_token="gaya", start_ms=2020, end_ms=2400),
        ],
        start_ms=50,
        end_ms=2400,
    )
    scenarios["emotional_line"] = {
        "audio_path": wav_3,
        "direction": dir_3,
        "alignment": align_3,
        "text": "सब खत्म हो गया...",
        "speaker": "Ananya",
    }

    # 4. Breath-Heavy Line (Combat exertion / pre-roll breath)
    wav_4 = generate_scenario_waveform(
        filepath=b_dir / "c001_s0004_breath_heavy.wav",
        duration_sec=2.5,
        speech_start_sec=0.25,
        speech_end_sec=2.35,
        has_pre_breath=True,
    )
    dir_4 = PerformanceDirection(
        index=4,
        speaker="Vikram",
        physical_state="combat_strain",
        breath_behavior="labored",
        pre_roll_breath_ms=240,
        pause_after_ms=350,
    )
    ev_4 = PerformanceEvidence(
        breath=BreathEvidence(
            physical_state="combat_strain",
            pre_roll_breath_detected=True,
            physical_strain_match=0.92,
        )
    )
    align_4 = AlignmentResult(
        words=[
            WordAlignment(token="woh", normalized_token="woh", start_ms=250, end_ms=900),
            WordAlignment(token="aa", normalized_token="aa", start_ms=950, end_ms=1600),
            WordAlignment(token="hain", normalized_token="hain", start_ms=1650, end_ms=2350),
        ],
        start_ms=250,
        end_ms=2350,
    )
    scenarios["breath_heavy_line"] = {
        "audio_path": wav_4,
        "direction": dir_4,
        "evidence": ev_4,
        "alignment": align_4,
        "text": "[gasp] वो आ रहे हैं!",
        "speaker": "Vikram",
    }

    # 5. Long Trailing Silence (TTS model dead air carrier)
    wav_5 = generate_scenario_waveform(
        filepath=b_dir / "c001_s0005_dead_air.wav",
        duration_sec=3.5,
        speech_start_sec=0.03,
        speech_end_sec=2.00,
    )
    dir_5 = PerformanceDirection(
        index=5,
        speaker="Dev",
        surface_emotion="neutral",
        pause_after_ms=350,
    )
    align_5 = AlignmentResult(
        words=[
            WordAlignment(token="theek", normalized_token="theek", start_ms=30, end_ms=800),
            WordAlignment(token="hai", normalized_token="hai", start_ms=850, end_ms=2000),
        ],
        start_ms=30,
        end_ms=2000,
    )
    scenarios["long_trailing_silence"] = {
        "audio_path": wav_5,
        "direction": dir_5,
        "alignment": align_5,
        "text": "ठीक है।",
        "speaker": "Dev",
    }

    # 6. Hesitation (Ellipses / reluctance)
    wav_6 = generate_scenario_waveform(
        filepath=b_dir / "c001_s0006_hesitation.wav",
        duration_sec=2.2,
        speech_start_sec=0.04,
        speech_end_sec=2.10,
    )
    dir_6 = PerformanceDirection(
        index=6,
        speaker="Ananya",
        hesitation_ms=450,
        silence_type="hesitation",
        turn_taking_behavior="delayed_reaction",
        pause_after_ms=580,
    )
    align_6 = AlignmentResult(
        words=[
            WordAlignment(token="shayad", normalized_token="shayad", start_ms=40, end_ms=1100),
            WordAlignment(token="nahi", normalized_token="nahi", start_ms=1300, end_ms=2100),
        ],
        start_ms=40,
        end_ms=2100,
    )
    scenarios["hesitation"] = {
        "audio_path": wav_6,
        "direction": dir_6,
        "alignment": align_6,
        "text": "शायद... नहीं।",
        "speaker": "Ananya",
    }

    # 7. Realization / Reaction Pause
    wav_7 = generate_scenario_waveform(
        filepath=b_dir / "c001_s0007_realization.wav",
        duration_sec=2.0,
        speech_start_sec=0.04,
        speech_end_sec=1.90,
    )
    dir_7 = PerformanceDirection(
        index=7,
        speaker="Kabir",
        actioning="realize",
        silence_type="dramatic_silence",
        tension_after=0.68,
        pause_after_ms=1200,
    )
    align_7 = AlignmentResult(
        words=[
            WordAlignment(token="toh", normalized_token="toh", start_ms=40, end_ms=600),
            WordAlignment(token="tumne", normalized_token="tumne", start_ms=650, end_ms=1200),
            WordAlignment(token="kiya", normalized_token="kiya", start_ms=1250, end_ms=1900),
        ],
        start_ms=40,
        end_ms=1900,
    )
    scenarios["realization_reaction"] = {
        "audio_path": wav_7,
        "direction": dir_7,
        "alignment": align_7,
        "text": "तो तुमने किया...",
        "speaker": "Kabir",
    }

    return scenarios
