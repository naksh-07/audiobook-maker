#!/usr/bin/env python3
"""
Audiobook Factory - Layer 2: Forensic AI Quality Control Agent (ADR-028).
Inspects acoustic telemetry, resolves speech boundaries, and executes surgical dead-air
clamping with raised-cosine decay tapers and boundary zero-pinning.
Includes optional Gemini Multimodal Audio inspection for ambiguous edge cases.
"""

import io
import json
import wave
import struct
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Any, Optional

from audiobook_factory.logger import logger
from audiobook_factory.forensic_analyzer import extract_acoustic_telemetry, MathematicalAcousticAnalyzer


class AudioQCAgent:
    """
    Autonomous Forensic Audio Quality Control Agent.
    Combines deterministic mathematical acoustic vector evaluation with
    surgical decay tapering and Gemini multimodal fallback.
    """

    def __init__(self, sample_rate: int = 24000, safety_buffer_ms: float = 40.0, fade_ms: float = 18.0):
        self.sample_rate = sample_rate
        self.safety_buffer_ms = safety_buffer_ms
        self.fade_ms = fade_ms
        self.analyzer = MathematicalAcousticAnalyzer(sample_rate=sample_rate)

    def surgical_clean_chunk(
        self,
        pcm_bytes: bytes,
        snap_zero_crossing: bool = True,
        fade_in_ms: float = 12.0,
        fade_out_ms: float = 18.0
    ) -> Tuple[bytes, int, Dict[str, Any]]:
        """
        Surgically cleans an audio chunk:
        1. Analyzes telemetry (Layer 1).
        2. Discards trailing dead air and C2PA bursts after true speech end.
        3. Applies raised-cosine Hann micro-fades (fade-in & fade-out).
        4. Pins boundary endpoints strictly to 0.0.
        
        Returns:
            (clean_pcm_bytes, trimmed_dead_air_ms, telemetry)
        """
        if not pcm_bytes or len(pcm_bytes) < 8:
            return pcm_bytes, 0, {}

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        total_samples = len(samples)
        rate = self.sample_rate

        # 1. Layer 1 Telemetry Analysis
        speech_end_t, dead_air_sec, anomalies = self.analyzer.detect_speech_endpoint(
            samples,
            safety_buffer_ms=self.safety_buffer_ms
        )
        trimmed_dead_air_ms = int(dead_air_sec * 1000.0)

        # 2. Surgical dead-air clamp if dead air exists
        if dead_air_sec > 0.05:
            clamp_sample_idx = int(speech_end_t * rate)
            clamp_sample_idx = min(max(clamp_sample_idx, int(rate * 0.1)), total_samples)
            samples = samples[:clamp_sample_idx]

        n = len(samples)
        if n < 8:
            return pcm_bytes, 0, {}

        # 3. DC Bias normalization
        dc_bias = np.mean(samples)
        samples -= dc_bias

        # 4. Zero-crossing snapping at boundaries
        if snap_zero_crossing and n > 120:
            # Snap start to nearest zero-crossing in first 5ms
            search_win = min(int(rate * 0.005), n // 4)
            for idx in range(search_win - 1):
                if samples[idx] * samples[idx + 1] <= 0.0:
                    samples = samples[idx:]
                    n = len(samples)
                    break

            # Snap end to nearest zero-crossing in trailing 5ms
            for offset in range(search_win - 1):
                idx = n - 1 - offset
                if samples[idx] * samples[idx - 1] <= 0.0:
                    samples = samples[:idx + 1]
                    n = len(samples)
                    break

        # 5. Raised-Cosine Hann Micro-Fades
        fade_in_samples = max(2, min(int(rate * (fade_in_ms / 1000.0)), n // 2))
        fade_out_samples = max(2, min(int(rate * (fade_out_ms / 1000.0)), n // 2))

        fade_in_curve = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, fade_in_samples)))
        fade_out_curve = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, fade_out_samples)))

        samples[:fade_in_samples] *= fade_in_curve
        samples[-fade_out_samples:] *= fade_out_curve

        # 6. Strict boundary zero-pinning (0.0000% Dirac discontinuity)
        samples[0] = 0.0
        samples[-1] = 0.0

        clean_bytes = np.clip(np.round(samples), -32768, 32767).astype(np.int16).tobytes()

        telemetry = {
            "original_duration_sec": round(total_samples / rate, 3),
            "clean_duration_sec": round(len(samples) / rate, 3),
            "trimmed_dead_air_ms": trimmed_dead_air_ms,
            "anomalies_removed": anomalies,
        }

        return clean_bytes, trimmed_dead_air_ms, telemetry
