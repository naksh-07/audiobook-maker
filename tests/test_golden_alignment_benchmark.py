#!/usr/bin/env python3
"""
Audiobook Factory - Golden Alignment Benchmark Suite (Wave A).
Dedicated regression test matrix covering all 17 linguistic and acoustic scenarios:
 1. Normal English narration
 2. Hindi narration
 3. Hindi dialogue
 4. Hinglish code-switching
 5. Foreign named entities
 6. Fantasy invented terminology
 7. Whisper / close-mic intimate
 8. Shouting / high projection
 9. Fast dialogue
10. Slow dialogue
11. Dramatic pause
12. Interruption / abrupt cutoff
13. Long silence / suspicious dead air
14. Short sentence
15. Long sustained monologue
16. Text / audio mismatch detection
17. Fallback alignment transparency
"""

import math
import wave
import struct
import tempfile
from pathlib import Path
import pytest
import numpy as np

from audiobook_factory.forced_aligner import (
    WorkstationForcedAligner,
    transliterate_devanagari_to_roman,
    normalize_text_for_alignment,
)
from audiobook_factory.alignment_contracts import (
    AlignmentResult,
    WordAlignment,
    PauseInterval,
    AlignmentCalibrationConfig,
)
from audiobook_factory.performance.contracts import PerformanceDirection


def create_acoustic_wav(
    filepath: Path,
    duration_sec: float,
    sample_rate: int = 16000,
    amplitude: float = 0.5,
    speech_intervals: list = None,
    f0: float = 160.0,
) -> Path:
    """
    Creates a deterministic synthetic WAV file with speech bursts and silence intervals.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)
    num_samples = int(sample_rate * duration_sec)
    samples = np.zeros(num_samples, dtype=np.int16)

    if speech_intervals is None:
        speech_intervals = [(0.0, duration_sec)]

    for (start_t, end_t) in speech_intervals:
        s_idx = max(0, int(start_t * sample_rate))
        e_idx = min(num_samples, int(end_t * sample_rate))
        dur_samples = e_idx - s_idx
        if dur_samples <= 0:
            continue

        t = np.arange(dur_samples) / float(sample_rate)
        # Multi-harmonic vocal tone
        signal = (
            math.sin(0)
            + 0.6 * np.sin(2 * np.pi * f0 * t)
            + 0.3 * np.sin(2 * np.pi * 2 * f0 * t)
            + 0.15 * np.sin(2 * np.pi * 3 * f0 * t)
        )
        # Apply 15ms onset / offset ramp
        ramp_len = min(int(0.015 * sample_rate), dur_samples // 4)
        if ramp_len > 0:
            ramp_up = np.linspace(0.0, 1.0, ramp_len)
            ramp_down = np.linspace(1.0, 0.0, ramp_len)
            signal[:ramp_len] *= ramp_up
            signal[-ramp_len:] *= ramp_down

        pcm = (signal * amplitude * 28000.0).clip(-32767, 32767).astype(np.int16)
        samples[s_idx:e_idx] = pcm

    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())

    return filepath


@pytest.fixture(scope="module")
def aligner():
    # Use GPU if available, else CPU
    return WorkstationForcedAligner(use_cuda=True)


@pytest.fixture(scope="module")
def temp_bench_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


class TestGoldenAlignmentBenchmarkSuite:
    """17-case comprehensive alignment test matrix."""

    # 1. Normal English Narration
    def test_01_normal_english_narration(self, temp_bench_dir, aligner):
        text = "The ancient stone fortress stood proudly upon the stormy northern cliffs."
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_01.wav",
            duration_sec=3.5,
            speech_intervals=[(0.1, 3.4)],
            f0=140.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_01")
        assert res.segment_uid == "bench_01"
        assert res.confidence > 0.0
        assert len(res.words) == len(text.split())
        assert res.words[0].token == "The"
        assert res.words[-1].token == "cliffs."
        assert res.end_ms > res.start_ms

    # 2. Hindi Narration (Devanagari)
    def test_02_hindi_narration(self, temp_bench_dir, aligner):
        text = "यह रात बहुत अंधेरी और खामोश थी।"
        raw, rom = normalize_text_for_alignment(text)
        assert len(raw) == len(rom)
        assert "raat" in rom or "rat" in rom or "raata" in rom

        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_02.wav",
            duration_sec=2.8,
            speech_intervals=[(0.1, 2.7)],
            f0=150.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_02")
        assert res.language == "hi"
        assert len(res.words) == len(text.split())
        assert res.confidence > 0.0

    # 3. Hindi Dialogue (Rustic / Colloquial)
    def test_03_hindi_dialogue(self, temp_bench_dir, aligner):
        text = "अरे भाई, तुम इस वक्त यहाँ क्या कर रहे हो?"
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_03.wav",
            duration_sec=3.0,
            speech_intervals=[(0.05, 2.9)],
            f0=165.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_03")
        assert res.language == "hi"
        assert len(res.words) == len(text.split())
        assert res.confidence_category in ("HIGH", "MEDIUM", "LOW")

    # 4. Hinglish Code-Switching
    def test_04_hinglish_code_switching(self, temp_bench_dir, aligner):
        text = "Main usse milne gaya tha, but the door was locked."
        raw, rom = normalize_text_for_alignment(text)
        assert len(raw) == len(rom)
        assert "main" in rom
        assert "locked" in rom

        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_04.wav",
            duration_sec=3.2,
            speech_intervals=[(0.1, 3.1)],
            f0=145.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_04")
        assert len(res.words) == len(text.split())

    # 5. Foreign Names
    def test_05_foreign_names(self, temp_bench_dir, aligner):
        text = "Geralt of Rivia approached the gates of Blaviken."
        raw, rom = normalize_text_for_alignment(text)
        assert "geralt" in rom
        assert "blaviken" in rom

        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_05.wav",
            duration_sec=2.9,
            speech_intervals=[(0.05, 2.85)],
            f0=120.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_05")
        assert len(res.words) == len(text.split())

    # 6. Fantasy Invented Terminology
    def test_06_fantasy_invented_terminology(self, temp_bench_dir, aligner):
        text = "The witcher cast Aard and drew his silver sword against the Kikimore."
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_06.wav",
            duration_sec=3.8,
            speech_intervals=[(0.1, 3.7)],
            f0=130.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_06")
        assert len(res.words) == len(text.split())
        assert any(w.token == "Kikimore." for w in res.words)

    # 7. Whisper / Close-Mic Intimate
    def test_07_whisper_close_mic(self, temp_bench_dir, aligner):
        text = "[whispers] Do not make a sound, they are listening right outside."
        # Whisper: soft amplitude 0.15
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_07.wav",
            duration_sec=2.8,
            amplitude=0.15,
            speech_intervals=[(0.15, 2.7)],
            f0=110.0,
        )
        p_dir = PerformanceDirection(index=1, speaker="Renfri", surface_emotion="whispering", proximity="close_mic")
        res = aligner.align_segment(wav_path, text, segment_uid="bench_07", direction=p_dir)
        # Bracketed cue [whispers] must not appear in word alignments
        assert not any("whisper" in w.token.lower() for w in res.words)
        assert len(res.words) == len("Do not make a sound, they are listening right outside.".split())

    # 8. Shouting / High Projection
    def test_08_shouting_projection(self, temp_bench_dir, aligner):
        text = "Run! Get to the castle before they breach the gates!"
        # Shouting: high amplitude 0.90, higher F0
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_08.wav",
            duration_sec=2.5,
            amplitude=0.90,
            speech_intervals=[(0.05, 2.45)],
            f0=240.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_08")
        assert len(res.words) == len(text.split())
        assert res.confidence > 0.0

    # 9. Fast Dialogue
    def test_09_fast_dialogue(self, temp_bench_dir, aligner):
        text = "Quick quick we have no time to explain get moving now!"
        # 11 words in 1.8 seconds (~6 words/sec)
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_09.wav",
            duration_sec=1.8,
            speech_intervals=[(0.02, 1.78)],
            f0=170.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_09")
        assert len(res.words) == len(text.split())
        # Word durations should be short but valid
        for w in res.words:
            assert w.duration_ms >= aligner.config.min_word_duration_ms

    # 10. Slow Dialogue
    def test_10_slow_dialogue(self, temp_bench_dir, aligner):
        text = "Death comes slowly to all men."
        # 6 words in 4.0 seconds (~1.5 words/sec)
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_10.wav",
            duration_sec=4.0,
            speech_intervals=[(0.2, 3.8)],
            f0=100.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_10")
        assert len(res.words) == len(text.split())

    # 11. Dramatic Pause Preservation
    def test_11_dramatic_pause(self, temp_bench_dir, aligner):
        text = "I loved you once. But that was a lifetime ago."
        # Audio has speech from 0.0-1.0s, silence 1.0-2.0s (1000ms pause), speech 2.0-3.2s
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_11.wav",
            duration_sec=3.2,
            speech_intervals=[(0.0, 1.0), (2.0, 3.2)],
            f0=140.0,
        )
        p_dir = PerformanceDirection(index=1, speaker="Geralt", surface_emotion="grief", restraint=0.85)
        res = aligner.align_segment(wav_path, text, segment_uid="bench_11", direction=p_dir)
        # Should detect a pause
        assert len(res.pauses) >= 1
        dramatic_pauses = [p for p in res.pauses if p.classification == "dramatic_pause"]
        assert len(dramatic_pauses) >= 1
        assert dramatic_pauses[0].duration_ms >= 600

    # 12. Interruption / Abrupt Cutoff
    def test_12_interruption_cutoff(self, temp_bench_dir, aligner):
        text = "I was about to tell you the entire secret when—"
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_12.wav",
            duration_sec=1.5,
            speech_intervals=[(0.0, 1.46)],
            f0=160.0,
        )
        p_dir = PerformanceDirection(
            index=1,
            speaker="Jaskier",
            surface_emotion="fear",
            interruption_behavior="abrupt_cut",
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_12", direction=p_dir)
        assert len(res.words) > 0

    # 13. Long Silence / Suspicious Dead Air Detection
    def test_13_long_suspicious_dead_air(self, temp_bench_dir, aligner):
        text = "Hello there."
        # 2 words in 0.8s, followed by 2.2s of unmotivated trailing dead air
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_13.wav",
            duration_sec=3.0,
            speech_intervals=[(0.0, 0.8)],
            f0=150.0,
        )
        p_dir = PerformanceDirection(index=1, speaker="Narrator", performance_priority="standard", restraint=0.4)
        res = aligner.align_segment(wav_path, text, segment_uid="bench_13", direction=p_dir)
        # Must detect dead air pause
        dead_air = [p for p in res.pauses if p.classification == "dead_air"]
        assert len(dead_air) >= 1
        assert any(d.code == "UNEXPECTED_LONG_SILENCE" for d in res.diagnostics)

    # 14. Short Sentence
    def test_14_short_sentence(self, temp_bench_dir, aligner):
        text = "No."
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_14.wav",
            duration_sec=0.8,
            speech_intervals=[(0.1, 0.7)],
            f0=120.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_14")
        assert len(res.words) == 1
        assert res.words[0].token == "No."
        assert res.words[0].duration_ms > 0

    # 15. Long Sustained Monologue
    def test_15_long_monologue(self, temp_bench_dir, aligner):
        text = (
            "The evil is evil, Stregobor. Lesser, greater, middling, it makes no difference. "
            "The degree is arbitrary, the definition's blurred. If I'm to choose between one evil "
            "and another, I'd rather not choose at all."
        )
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_15.wav",
            duration_sec=8.5,
            speech_intervals=[(0.1, 8.4)],
            f0=130.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_15")
        assert len(res.words) == len(text.split())
        assert res.end_ms > res.start_ms

    # 16. Text / Audio Mismatch Detection
    def test_16_text_audio_mismatch(self, temp_bench_dir, aligner):
        # 15 words in text, but audio is only 0.25 seconds long
        text = "This is an extremely long dialogue sentence that could not possibly fit in a quarter second of audio."
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_16.wav",
            duration_sec=0.25,
            speech_intervals=[(0.0, 0.25)],
            f0=150.0,
        )
        res = aligner.align_segment(wav_path, text, segment_uid="bench_16")
        # Must detect mismatch or impossible word duration or low confidence
        diag_codes = res.get_diagnostic_codes()
        assert (
            "IMPOSSIBLE_WORD_DURATION" in diag_codes
            or "TEXT_AUDIO_MISMATCH" in diag_codes
            or res.confidence_category in ("LOW", "FAILED_REVIEW_REQUIRED")
        )

    # 17. Fallback Alignment Transparency
    def test_17_fallback_alignment_transparency(self, temp_bench_dir):
        # Force fallback aligner with MMS_FA disabled
        fallback_aligner = WorkstationForcedAligner(use_cuda=False)
        fallback_aligner._init_done = True
        fallback_aligner._model = None  # Force fallback

        text = "First word second word third word."
        wav_path = create_acoustic_wav(
            temp_bench_dir / "case_17.wav",
            duration_sec=2.0,
            speech_intervals=[(0.0, 2.0)],
            f0=140.0,
        )
        res = fallback_aligner.align_segment(wav_path, text, segment_uid="bench_17")
        assert res.method == "energy_fallback"
        assert res.confidence <= 0.55
        assert any(d.code == "FALLBACK_ALIGNMENT" for d in res.diagnostics)
        assert len(res.words) == len(text.split())
        for w in res.words:
            assert w.pronunciation_status == "fallback"
            assert w.source == "energy_proportional"

    # Calibration Configurability Test
    def test_calibration_configurability(self, temp_bench_dir):
        custom_cfg = AlignmentCalibrationConfig(
            dead_air_min_ms=1000,  # lower threshold to 1000ms
            min_pause_ms=40,
        )
        custom_aligner = WorkstationForcedAligner(use_cuda=False, config=custom_cfg)
        assert custom_aligner.config.dead_air_min_ms == 1000
        assert custom_aligner.config.min_pause_ms == 40
