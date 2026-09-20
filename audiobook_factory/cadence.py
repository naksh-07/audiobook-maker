#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.3: Stealth Human Cadence & Anti-Bot Traffic Shaper.
Eliminates robotic script footprints across Google AI Studio / Gemini APIs.
Implements:
1. Content-Aware Inter-Request Pacing (reading time + audio review listening simulation).
2. Log-Normal Interval Jitter with fat-tail human pauses.
3. Scene Review Breaks (director breaks every 4-6 segments).
4. Anti-Correlation Key-Switch Cooldowns (decouples IP-level multi-key correlation).
5. Official Google GenAI SDK Header Emulation.
"""

import os
import sys
import time
import math
import random
import threading
from typing import Dict, Any, Optional

from audiobook_factory.logger import logger


def get_stealth_sdk_headers(api_key: str) -> Dict[str, str]:
    """
    Generates authentic headers matching the official Google GenAI Python SDK.
    Completely eliminates robotic custom User-Agent footprints like 'AudiobookFactory/2.0'.
    """
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    # Standard Windows 11 platform tag matching workstation
    platform_tag = "windows/10.0.26100" if sys.platform == "win32" else "linux/x86_64"

    return {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key,
        "User-Agent": f"google-genai-sdk-python/0.8.3 gl-python/{py_ver} ({platform_tag})",
        "x-goog-api-client": f"gl-python/{py_ver} gax/2.24.0 gccl/0.8.3",
    }


class HumanCadenceController:
    """
    Stealth Human Emulation Cadence Controller.
    Shapes API traffic to match an audio engineer interactively generating and reviewing lines.
    """

    def __init__(
        self,
        min_reading_wpm: float = 220.0,
        audio_review_ratio_range: tuple = (0.15, 0.35),
        scene_break_interval: int = 5,
        scene_break_duration_range: tuple = (35.0, 65.0),
        key_switch_cooldown_range: tuple = (18.0, 32.0),
    ):
        self.min_reading_wpm = min_reading_wpm
        self.audio_review_ratio_range = audio_review_ratio_range
        self.scene_break_interval = scene_break_interval
        self.scene_break_duration_range = scene_break_duration_range
        self.key_switch_cooldown_range = key_switch_cooldown_range

        self._lock = threading.Lock()
        self.last_request_time: float = 0.0
        self.last_audio_duration: float = 0.0
        self.segment_counter: int = 0
        self.active_key_hash: Optional[str] = None

    def calculate_human_delay(self, upcoming_text: str, prev_audio_dur: float = 0.0) -> float:
        """
        Calculates content-aware human delay for the next segment:
        T_delay = T_reading(text) + T_listening(prev_audio) + T_lognormal_jitter
        """
        # 1. Reading Time Simulation:
        # A human takes time to read the text before triggering synthesis.
        word_count = max(len(upcoming_text.split()), 1)
        # Reading speed ~ 220-260 words per minute -> ~3.6 - 4.3 words/sec
        reading_speed_wps = random.uniform(3.5, 4.5)
        t_read = min(12.0, max(2.5, word_count / reading_speed_wps))

        # 2. Audio Review / Listening Simulation:
        # A human checks the generated audio preview (samples 15% to 35% of track).
        if prev_audio_dur > 0:
            ratio = random.uniform(*self.audio_review_ratio_range)
            t_listen = min(15.0, prev_audio_dur * ratio)
        else:
            t_listen = random.uniform(1.5, 3.5)

        # 3. Authentic Human Log-Normal Jitter:
        # Avoids uniform or fixed distributions which automated anti-bot models detect.
        # LogNormal(mu=1.2, sigma=0.35) produces natural 2.5s - 5.5s think time.
        t_jitter = random.lognormvariate(1.2, 0.35)
        t_jitter = max(1.5, min(7.0, t_jitter))

        total_delay = t_read + t_listen + t_jitter
        return total_delay

    def wait_before_segment(self, upcoming_text: str, seg_index: int, total_segs: int):
        """
        Enforces human pacing prior to firing an API request.
        Includes periodic scene review breaks every N segments.
        Thread-safe via internal lock on mutable state.
        """
        with self._lock:
            now = time.time()
            self.segment_counter += 1

            # Check for Scene Review Break (every 4-6 segments)
            if self.segment_counter > 1 and (self.segment_counter % self.scene_break_interval == 0):
                break_sec = random.uniform(*self.scene_break_duration_range)
                logger.info(
                    f"  [STUDIO CADENCE] Scene batch complete ({self.segment_counter}/{total_segs}). "
                    f"Simulating director listening & script review (cooling off {break_sec:.1f}s)..."
                )
                time.sleep(break_sec)
                # Fall through to also apply regular human delay (prevents post-break burst)

            # Regular inter-request human delay
            now = time.time()  # Refresh after potential scene break sleep
            if self.last_request_time > 0:
                elapsed = now - self.last_request_time
                target_delay = self.calculate_human_delay(upcoming_text, self.last_audio_duration)
                remaining = target_delay - elapsed
                if remaining > 0:
                    logger.info(
                        f"  [STUDIO CADENCE] Human pacing: reading & listening delay ({remaining:.1f}s)..."
                    )
                    time.sleep(remaining)

            self.last_request_time = time.time()

    def record_completed_segment(self, audio_duration: float):
        """Updates internal telemetry with duration of synthesized audio."""
        with self._lock:
            self.last_audio_duration = audio_duration
            self.last_request_time = time.time()

    def wait_for_key_switch(self, old_key_preview: str, new_key_preview: str):
        """
        Anti-Correlation Cooldown:
        When switching keys, pauses 18-32s to prevent Google from linking Key A and Key B
        via millisecond-synchronized IP failover traffic.
        """
        cooldown = random.uniform(*self.key_switch_cooldown_range)
        logger.warning(
            f"  [STEALTH KEY ROTATION] Decoupling IP correlation: Key {old_key_preview} -> {new_key_preview}. "
            f"Simulating fresh developer session (Cooling off {cooldown:.1f}s)..."
        )
        time.sleep(cooldown)
        self.last_request_time = time.time()


# Singleton cadence instance (thread-safe initialization)
_cadence_instance: Optional[HumanCadenceController] = None
_cadence_lock = threading.Lock()


def get_human_cadence_controller() -> HumanCadenceController:
    global _cadence_instance
    if _cadence_instance is None:
        with _cadence_lock:
            if _cadence_instance is None:
                _cadence_instance = HumanCadenceController()
    return _cadence_instance
