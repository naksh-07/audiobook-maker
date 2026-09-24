#!/usr/bin/env python3
"""
Audiobook Factory - Generate 20-Second A/B Comparison Sample (ADR-027).
Compares Condition A (Legacy Raw with clicks, C2PA screech, and vocoder hiss)
against Condition B (Restored Clean with container demuxing, zero-crossing Hann fades, and DSP polish).
"""

import io
import json
import wave
import struct
import shutil
import subprocess
from pathlib import Path
import numpy as np

from audiobook_factory.restoration import (
    extract_clean_pcm_from_gemini_container,
    read_clean_chunk_pcm,
    apply_zero_crossing_micro_fades,
    apply_studio_restoration_filter,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = ROOT_DIR / "audiobooks" / "projects" / "witcher1"
CHUNKS_DIR = PROJECT_DIR / "audio_chunks"
LEDGER_PATH = PROJECT_DIR / "scripts" / "chapter_012_timeline_ledger.json"
SAMPLES_DIR = ROOT_DIR / "audiobooks" / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


def measure_audio_metrics(wav_path: Path) -> dict:
    """Computes peak amplitudes, boundary Dirac step jumps, and pause noise floors."""
    with wave.open(str(wav_path), "rb") as wf:
        rate = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    s0 = abs(samples[0])
    s_end = abs(samples[-1])

    # Calculate step jumps (derivatives)
    diffs = np.abs(np.diff(samples))
    max_jump = np.max(diffs)

    # Calculate high-frequency energy ratio (>11.5 kHz)
    fft_vals = np.abs(np.fft.rfft(samples))
    freqs = np.fft.rfftfreq(len(samples), 1.0 / rate)
    total_energy = np.sum(fft_vals ** 2)
    hf_energy = np.sum(fft_vals[freqs >= 11500] ** 2)
    hf_ratio = (hf_energy / total_energy) * 100.0 if total_energy > 0 else 0.0

    # Pause window RMS noise floor (minimum 50ms window RMS)
    win_size = int(rate * 0.05)
    min_rms = 999999.0
    for i in range(0, len(samples) - win_size, win_size):
        w = samples[i:i + win_size]
        rms = np.sqrt(np.mean(w ** 2))
        if rms < min_rms:
            min_rms = rms

    min_rms_dbfs = 20 * np.log10(max(min_rms, 1e-5) / 32768.0)

    return {
        "duration_sec": round(nframes / rate, 2),
        "s0_edge_amplitude": int(s0),
        "send_edge_amplitude": int(s_end),
        "max_step_jump": int(max_jump),
        "hf_nyquist_ratio_pct": round(hf_ratio, 3),
        "pause_noise_floor_dbfs": round(min_rms_dbfs, 1),
    }


def main():
    ledger_data = json.load(open(LEDGER_PATH, "r", encoding="utf-8"))
    segments = ledger_data.get("segments", [])

    # Pick sequence with Narrator, Dandelion, and Geralt (indices 16 to 20)
    # Includes c012_s0016 which contains the 18,770 start click and trailing C2PA screech!
    banter_segs = [s for s in segments if s.get("segment_index") in range(16, 21)]

    print(f"[*] Selected {len(banter_segs)} segments for A/B testing:")
    for s in banter_segs:
        print(f"    - #{s['segment_index']} {s['speaker']}: {s['audio_file']}")

    # =========================================================================
    # 1. Condition A: Legacy Raw Stitching (Before)
    # =========================================================================
    before_wav = SAMPLES_DIR / "ch12_banter_before_legacy.wav"
    raw_frames = []
    sample_rate = 24000

    for i, s in enumerate(banter_segs):
        p = CHUNKS_DIR / s["audio_file"]
        if not p.exists():
            matches = list(CHUNKS_DIR.glob(s["audio_file"].split("_")[0] + "_*.wav"))
            p = matches[0]

        # Naively read frames without container demuxing (the old buggy way)
        with wave.open(str(p), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
        raw_frames.append(frames)

        # Naive silence padding
        pause_after = s.get("pause_after_ms", 400)
        silence_samples = int(sample_rate * (pause_after / 1000.0))
        raw_frames.append(b"\x00\x00" * silence_samples)

    with wave.open(str(before_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(raw_frames))

    print(f"[+] Rendered Condition A (Before): {before_wav.name}")

    # =========================================================================
    # 2. Condition B: Restored Studio Polish (After)
    # =========================================================================
    after_wav = SAMPLES_DIR / "ch12_banter_after_clean.wav"
    clean_frames = []

    for i, s in enumerate(banter_segs):
        p = CHUNKS_DIR / s["audio_file"]
        if not p.exists():
            matches = list(CHUNKS_DIR.glob(s["audio_file"].split("_")[0] + "_*.wav"))
            p = matches[0]

        # 1. Non-destructively demux container and apply Layer 2 surgical dead-air clamping (ADR-028)
        from audiobook_factory.restoration import read_surgically_cleaned_chunk
        clean_pcm, trimmed_ms = read_surgically_cleaned_chunk(
            p,
            target_sample_rate=sample_rate,
            fade_in_ms=12.0,
            fade_out_ms=18.0
        )
        clean_frames.append(clean_pcm)

        # 2. Clean silence padding with strict timeline synchronization (ADR-028)
        pause_after = s.get("pause_after_ms", 400)
        total_pause_ms = pause_after + trimmed_ms
        silence_samples = int(sample_rate * (total_pause_ms / 1000.0))
        clean_frames.append(b"\x00\x00" * silence_samples)

    tmp_unfiltered = SAMPLES_DIR / "ch12_banter_tmp_unfiltered.wav"
    with wave.open(str(tmp_unfiltered), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(clean_frames))

    # 4. Apply 6-stage studio DSP filter chain
    apply_studio_restoration_filter(tmp_unfiltered, after_wav, sample_rate=sample_rate)
    if tmp_unfiltered.exists():
        tmp_unfiltered.unlink()

    print(f"[+] Rendered Condition B (After): {after_wav.name}")

    # =========================================================================
    # 3. Acoustic Verification & Quantitative Delta Metrics
    # =========================================================================
    m_before = measure_audio_metrics(before_wav)
    m_after = measure_audio_metrics(after_wav)

    print("\n" + "=" * 65)
    print("   QUANTITATIVE A/B COMPARISON METRICS (ADR-027 VERIFICATION)")
    print("=" * 65)
    print(f"{'Metric':<30} | {'Condition A (Before)':<16} | {'Condition B (After)':<16}")
    print("-" * 65)
    print(f"{'Initial Edge (t=0) Amp':<30} | {m_before['s0_edge_amplitude']:<16} | {m_after['s0_edge_amplitude']:<16}")
    print(f"{'Trailing Edge Amp':<30} | {m_before['send_edge_amplitude']:<16} | {m_after['send_edge_amplitude']:<16}")
    print(f"{'Max Step Discontinuity Jump':<30} | {m_before['max_step_jump']:<16} | {m_after['max_step_jump']:<16}")
    print(f"{'Pause Noise Floor (dBFS)':<30} | {m_before['pause_noise_floor_dbfs']:<16} | {m_after['pause_noise_floor_dbfs']:<16}")
    print(f"{'Nyquist (>11.5kHz) Whistle %':<30} | {m_before['hf_nyquist_ratio_pct']:<16} | {m_after['hf_nyquist_ratio_pct']:<16}")
    print("=" * 65)


if __name__ == "__main__":
    main()
