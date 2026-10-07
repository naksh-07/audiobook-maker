#!/usr/bin/env python3
"""
Audiobook Factory - Thread-safe Multi-Model Token Bucket Rate Limiter with Anti-Bot Organic Jitter.
Enforces studio pacing, multi-model RPM/TPM ceilings, and organic traffic profiles across workers.
"""

from __future__ import annotations
import time
import random
import threading
import contextlib
from typing import Optional, Dict, Any

from audiobook_factory.logger import logger
from audiobook_factory.tts.constants import DEFAULT_RPM
from audiobook_factory.guard_shield import resolve_model_profile, HardwareVRAMGuard


class TokenBucketRateLimiter:
    """
    Thread-safe Multi-Model Token Bucket Rate Limiter with Anti-Bot Organic Jitter.
    Enforces precise request rates (e.g. 15 RPM = 1 dispatch every 4.0s) and TPM limits across workers.
    Injects random uniform jitter (0.35s - 0.85s) to emulate natural, human-paced API traffic.
    Supports model-isolated and key-isolated pausing so a single 429 does not halt unrelated models!
    """

    def __init__(self, rate_rpm: float = DEFAULT_RPM, capacity: float = 2.0):
        self.rate_per_sec = rate_rpm / 60.0
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self.lock = threading.Lock()
        self.pause_event = threading.Event()
        self.pause_event.set()

        # Model-specific token buckets and pause events
        self._model_buckets: Dict[str, Dict[str, Any]] = {}
        self._model_pauses: Dict[str, threading.Event] = {}
        # Key-specific pause events
        self._key_pauses: Dict[str, threading.Event] = {}
        self._sub_lock = threading.Lock()

    def _get_model_bucket(self, model: str) -> Dict[str, Any]:
        with self._sub_lock:
            if model not in self._model_buckets:
                prof = resolve_model_profile(model)
                self._model_buckets[model] = {
                    "rate_per_sec": prof.rpm_limit / 60.0,
                    "tokens": prof.max_concurrency * 1.5,
                    "capacity": prof.max_concurrency * 1.5,
                    "last_update": time.monotonic(),
                    "tpm_rate_per_sec": prof.tpm_limit / 60.0,
                    "tpm_tokens": prof.tpm_limit / 10.0,
                    "tpm_capacity": prof.tpm_limit / 10.0,
                    "tpm_last_update": time.monotonic(),
                    "profile": prof,
                }
            return self._model_buckets[model]

    def acquire(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        estimated_tokens: int = 0,
    ):
        """
        Acquires rate limiter tokens.
        If called without arguments (legacy callers), operates on base global limiter.
        If called with model, applies per-model RPM and TPM rate curves.
        Always releases internal locks prior to sleeping.
        """
        # 1. Wait if globally paused due to 429 quota backoff
        self.pause_event.wait()

        # 2. Wait if model-specific pause is active
        if model:
            ev = None
            with self._sub_lock:
                ev = self._model_pauses.get(model)
            if ev:
                ev.wait()

        # 3. Wait if key-specific pause is active
        if api_key:
            kev = None
            with self._sub_lock:
                kev = self._key_pauses.get(api_key)
            if kev:
                kev.wait()

        # 4. Global Base Limiter Token Acquisition (Maintains strict legacy test contracts)
        wait_time = 0.0
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

        # 5. Model-Specific Multi-Dimensional Limits
        model_wait = 0.0
        if model:
            mb = self._get_model_bucket(model)
            with self._sub_lock:
                now_m = time.monotonic()
                # RPM Check
                el_m = max(0.0, now_m - mb["last_update"])
                mb["tokens"] = min(mb["capacity"], mb["tokens"] + el_m * mb["rate_per_sec"])
                if mb["tokens"] < 1.0:
                    model_wait = max(model_wait, (1.0 - mb["tokens"]) / mb["rate_per_sec"])
                    mb["tokens"] = 0.0
                else:
                    mb["tokens"] -= 1.0
                mb["last_update"] = now_m

                # TPM Check
                if estimated_tokens > 0:
                    el_t = max(0.0, now_m - mb["tpm_last_update"])
                    mb["tpm_tokens"] = min(mb["tpm_capacity"], mb["tpm_tokens"] + el_t * mb["tpm_rate_per_sec"])
                    if mb["tpm_tokens"] < float(estimated_tokens):
                        tpm_wait = (float(estimated_tokens) - mb["tpm_tokens"]) / mb["tpm_rate_per_sec"]
                        model_wait = max(model_wait, tpm_wait)
                        mb["tpm_tokens"] = 0.0
                    else:
                        mb["tpm_tokens"] -= float(estimated_tokens)
                    mb["tpm_last_update"] = now_m

        # 6. Sleep outside all locks with organic anti-bot jitter
        eff_wait = max(wait_time, model_wait)
        jitter = random.uniform(0.35, 0.85)
        total_wait = eff_wait + jitter
        if total_wait > 0:
            time.sleep(total_wait)

    @contextlib.contextmanager
    def guard(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        estimated_tokens: int = 0,
    ):
        """Context manager acquiring rate-limits and releasing hardware GPU VRAM if local."""
        self.acquire(model=model, api_key=api_key, estimated_tokens=estimated_tokens)
        is_gpu = False
        if model:
            prof = resolve_model_profile(model)
            if prof.is_local_gpu:
                is_gpu = True
                HardwareVRAMGuard.acquire(f"model_run_{model}")
        try:
            yield
        finally:
            if is_gpu:
                HardwareVRAMGuard.release(f"model_run_{model}")

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

    def trigger_model_pause(self, model: str, pause_seconds: float):
        """Pauses workers calling this specific model without halting other models or workers."""
        with self._sub_lock:
            if model not in self._model_pauses:
                self._model_pauses[model] = threading.Event()
                self._model_pauses[model].set()
            ev = self._model_pauses[model]
            if not ev.is_set():
                return
            ev.clear()

        logger.warning(f"  [MODEL PAUSE] Model '{model}' cooling off for {pause_seconds:.1f}s...")

        def _resume_model():
            time.sleep(pause_seconds)
            with self._sub_lock:
                if model in self._model_buckets:
                    self._model_buckets[model]["last_update"] = time.monotonic()
                    self._model_buckets[model]["tokens"] = 0.0
                ev.set()
            logger.info(f"  [MODEL RESUME] Model '{model}' resumed.")

        threading.Thread(target=_resume_model, daemon=True).start()

    def trigger_key_pause(self, api_key: str, pause_seconds: float):
        """Pauses workers using this specific key without halting other keys."""
        preview = f"...{api_key[-6:]}" if len(api_key) > 6 else api_key
        with self._sub_lock:
            if api_key not in self._key_pauses:
                self._key_pauses[api_key] = threading.Event()
                self._key_pauses[api_key].set()
            kev = self._key_pauses[api_key]
            if not kev.is_set():
                return
            kev.clear()

        logger.warning(f"  [KEY PAUSE] Key {preview} cooling off for {pause_seconds:.1f}s...")

        def _resume_key():
            time.sleep(pause_seconds)
            with self._sub_lock:
                kev.set()
            logger.info(f"  [KEY RESUME] Key {preview} backoff expired.")

        threading.Thread(target=_resume_key, daemon=True).start()
