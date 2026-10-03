#!/usr/bin/env python3
"""
Audiobook Factory - Thread-safe Token Bucket Rate Limiter with Anti-Bot Organic Jitter.
Enforces studio pacing and organic traffic profiles across synthesis worker threads.
"""

from __future__ import annotations
import time
import random
import threading
from audiobook_factory.logger import logger
from audiobook_factory.tts.constants import DEFAULT_RPM


class TokenBucketRateLimiter:
    """
    Thread-safe Token Bucket Rate Limiter with Anti-Bot Organic Jitter.
    Enforces precise request rates (e.g. 15 RPM = 1 dispatch every 4.0s) across concurrent workers.
    Injects random uniform jitter (0.35s - 0.85s) to emulate natural, human-paced API traffic
    and prevent automated bot-detection heuristics.
    """

    def __init__(self, rate_rpm: float = DEFAULT_RPM, capacity: float = 2.0):
        self.rate_per_sec = rate_rpm / 60.0
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self.lock = threading.Lock()
        self.pause_event = threading.Event()
        self.pause_event.set()

    def acquire(self):
        # Wait if globally paused due to 429 quota backoff
        self.pause_event.wait()

        with self.lock:
            now = time.monotonic()
            elapsed = max(0.0, now - self.last_update)
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_sec)

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate_per_sec
                self.tokens = 0.0
            else:
                self.tokens -= 1.0
                wait_time = 0.0
            self.last_update = now

        # Organic anti-bot jitter: random delay between 350ms and 850ms
        jitter = random.uniform(0.35, 0.85)
        total_wait = wait_time + jitter
        if total_wait > 0:
            time.sleep(total_wait)

    def trigger_global_pause(self, pause_seconds: float):
        """Pauses all worker threads simultaneously during an HTTP 429 backoff."""
        with self.lock:
            if not self.pause_event.is_set():
                return
            self.pause_event.clear()

        logger.warning(f"  [GLOBAL PAUSE] 429 backoff: Pausing all TTS workers for {pause_seconds:.1f}s...")

        def _resume():
            time.sleep(pause_seconds)
            with self.lock:
                self.last_update = time.monotonic()
                self.tokens = 0.0
                self.pause_event.set()
            logger.info("  [GLOBAL RESUME] TTS workers resumed after quota backoff.")

        threading.Thread(target=_resume, daemon=True).start()
