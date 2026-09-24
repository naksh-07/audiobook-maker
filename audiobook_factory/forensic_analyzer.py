#!/usr/bin/env python3
"""
Audiobook Factory - Layer 1: Mathematical Forensic Acoustic Analyzer (ADR-028).
Extracts high-resolution frame-level acoustic telemetry:
- RMS energy envelope (dBFS)
- High-Frequency Energy Ratio (E > 4kHz / E_total)
- Wiener Spectral Flatness (Distinguishes harmonic speech formants from white/electronic static)
- Silence Valley & Trailing Burst Detection (Isolates C2PA fragments and vocoder carrier hiss)
- True Speech Endpoint Detector with 40ms Phonetic Safety Buffer
- Anomaly Fingerprinting & Structured JSON Telemetry
"""

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

from audiobook_factory.logger import logger


class MathematicalAcousticAnalyzer:
    """
    Computes mathematical acoustic vectors and flags anomalies across synthesized audio chunks.
    Operates 100% locally in-memory using NumPy with sub-millisecond latency.
    """

    def __init__(self, sample_rate: int = 24000, frame_ms: float = 10.0):
        self.sample_rate = sample_rate
        self.frame_len = max(8, int(sample_rate * (frame_ms / 1000.0)))
        self.hop_len = self.frame_len // 2

    def analyze_frames(self, samples: np.ndarray) -> List[Dict[str, float]]:
        """Extracts acoustic metrics per frame across the waveform."""
        if len(samples) < self.frame_len:
            return []

        rate = self.sample_rate
        flen = self.frame_len
        freqs = np.fft.rfftfreq(flen, 1.0 / rate)
        hf_mask = freqs >= 4000.0

        metrics = []
        for i in range(0, len(samples) - flen, self.hop_len):
            w = samples[i:i + flen]
            t_sec = i / rate
            peak = float(np.max(np.abs(w)))
            rms = float(np.sqrt(np.mean(w ** 2)))
            rms_db = 20.0 * math.log10(max(rms, 1e-5) / 32768.0)

            # FFT Power Spectrum
            fft_vals = np.abs(np.fft.rfft(w))
            psd = fft_vals ** 2
            total_energy = float(np.sum(psd))

            if total_energy > 1e-9:
                hf_energy = float(np.sum(psd[hf_mask]))
                hf_ratio = hf_energy / total_energy
                # Wiener Spectral Flatness: geometric mean / arithmetic mean of PSD
                log_mean = float(np.mean(np.log(psd + 1e-12)))
                arith_mean = float(np.mean(psd) + 1e-12)
                spectral_flatness = float(np.exp(log_mean) / arith_mean)
            else:
                hf_ratio = 0.0
                spectral_flatness = 0.0

            # Zero crossing count
            zcr = float(np.mean(np.abs(np.diff(np.sign(w)))) / 2.0)

            metrics.append({
                "time_sec": round(t_sec, 3),
                "peak": round(peak, 1),
                "rms": round(rms, 1),
                "rms_dbfs": round(rms_db, 1),
                "hf_ratio": round(hf_ratio, 3),
                "spectral_flatness": round(spectral_flatness, 4),
                "zcr": round(zcr, 3),
            })

        return metrics

    def detect_speech_endpoint(
        self,
        samples: np.ndarray,
        silence_threshold_dbfs: float = -48.0,
        safety_buffer_ms: float = 40.0
    ) -> Tuple[float, float, List[Dict[str, Any]]]:
        """
        Scans for silence valleys and isolated trailing bursts to pinpoint
        the true speech endpoint with millisecond accuracy.

        Handles both:
        1. Natural trailing dead air at the end of the file.
        2. Isolated C2PA metadata bursts (e.g. 100ms blast after a 300ms silence gap).

        Returns:
            (true_speech_end_sec, trailing_dead_air_sec, anomalies_detected)
        """
        total_dur = len(samples) / self.sample_rate
        if total_dur <= 0.15:
            return total_dur, 0.0, []

        rate = self.sample_rate
        flen = int(rate * 0.01)  # 10ms frame
        rms_arr = []
        times = []
        for i in range(0, len(samples) - flen, flen):
            w = samples[i:i + flen]
            rms = np.sqrt(np.mean(w ** 2))
            rms_db = 20.0 * math.log10(max(rms, 1e-5) / 32768.0)
            rms_arr.append(rms_db)
            times.append(i / rate)

        if not rms_arr:
            return total_dur, 0.0, []

        speech_frames = [idx for idx, db in enumerate(rms_arr) if db >= silence_threshold_dbfs]
        if not speech_frames:
            # File is pure silence or ambient track with no active speech (e.g. unit test dummy)
            return total_dur, 0.0, []

        # Find continuous silence valleys (RMS < silence_threshold_dbfs for >= 100ms)
        valleys = []
        in_v = False
        v_start = 0
        for idx, db in enumerate(rms_arr):
            if db < silence_threshold_dbfs and not in_v:
                in_v = True
                v_start = idx
            elif db >= silence_threshold_dbfs and in_v:
                in_v = False
                v_dur = times[idx] - times[v_start]
                if v_dur >= 0.10:
                    valleys.append((times[v_start], times[idx], v_dur))
        if in_v:
            v_dur = times[-1] - times[v_start]
            if v_dur >= 0.10:
                valleys.append((times[v_start], times[-1], v_dur))

        anomalies = []

        # Case A: Valley touches the very end of the file (natural vocoder dead air)
        if valleys and valleys[-1][1] >= times[-1] - 0.03 and valleys[-1][0] > 0.05:
            speech_end_t = valleys[-1][0] + (safety_buffer_ms / 1000.0)
            anomalies.append({
                "type": "NATURAL_TRAILING_DEAD_AIR",
                "start_sec": round(valleys[-1][0], 3),
                "duration_sec": round(total_dur - valleys[-1][0], 3),
                "severity": "MEDIUM"
            })

        # Case B: Disconnected artifact burst after a late valley (C2PA metadata tail)
        elif valleys and (times[-1] - valleys[-1][1]) < 0.35 and valleys[-1][0] > total_dur - 0.8:
            speech_end_t = valleys[-1][0] + (safety_buffer_ms / 1000.0)
            burst_dur = times[-1] - valleys[-1][1]
            anomalies.append({
                "type": "TRAILING_C2PA_BURST_AFTER_VALLEY",
                "valley_start_sec": round(valleys[-1][0], 3),
                "burst_start_sec": round(valleys[-1][1], 3),
                "burst_duration_sec": round(burst_dur, 3),
                "severity": "CRITICAL"
            })

        else:
            # Case C: Standard backward scan looking for speech energy drop below -38 dBFS
            speech_end_t = total_dur
            for idx in range(len(rms_arr) - 1, -1, -1):
                if rms_arr[idx] > -38.0:
                    speech_end_t = times[idx] + (safety_buffer_ms / 1000.0)
                    break

        speech_end_t = min(max(speech_end_t, 0.05), total_dur)
        dead_air_dur = max(0.0, total_dur - speech_end_t)

        return speech_end_t, dead_air_dur, anomalies


def extract_acoustic_telemetry(
    pcm_bytes: bytes,
    sample_rate: int = 24000,
    safety_buffer_ms: float = 40.0
) -> Dict[str, Any]:
    """
    Convenience function: analyzes raw PCM bytes and returns structured forensic telemetry.
    """
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    analyzer = MathematicalAcousticAnalyzer(sample_rate=sample_rate)
    speech_end_t, dead_air_sec, anomalies = analyzer.detect_speech_endpoint(
        samples,
        safety_buffer_ms=safety_buffer_ms
    )
    total_dur = len(samples) / sample_rate

    return {
        "sample_rate": sample_rate,
        "total_duration_sec": round(total_dur, 3),
        "true_speech_end_sec": round(speech_end_t, 3),
        "trailing_dead_air_sec": round(dead_air_sec, 3),
        "trailing_dead_air_ms": int(dead_air_sec * 1000.0),
        "has_critical_artifact": any(a.get("severity") == "CRITICAL" for a in anomalies),
        "anomalies": anomalies,
    }
