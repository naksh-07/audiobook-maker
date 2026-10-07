#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.4: Universal Multi-Model Guard & Resilient Shield Engine.
Provides:
1. Universal Model Quota Profiles: RPM, TPM, RPD, Max Concurrency, and Reset Schedules across providers
   (Google Gemini, OpenAI, Anthropic, Cerebras, Groq, OpenRouter, Local CUDA/Spark, ElevenLabs).
2. Universal Error Classifier: Differentiates daily quota, RPM bursts, TPM ceilings, concurrency limits,
   server hiccups (5xx), context overflows, safety blocks, and invalid keys; parses HTTP headers (Retry-After, x-ratelimit-*).
3. Resilient Circuit Breaker: Auto-trips on consecutive server failures, protects against API hammering,
   and enables instant failover/cascade without retry delay.
4. Hardware VRAM & Device Guard: Mutex and semaphore protection for local GPU models (RTX 4050 6GB)
   preventing CUDA OOM and thread collisions.
"""

from __future__ import annotations
import os
import re
import time
import email.utils
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, NamedTuple, Set
from dataclasses import dataclass, field
import threading

from audiobook_factory.logger import logger


@dataclass(frozen=True)
class ModelQuotaProfile:
    """Rate limit and concurrency specification for an AI model or service."""
    provider: str
    model: str
    rpm_limit: float = 15.0               # Requests Per Minute
    tpm_limit: float = 1_000_000.0        # Tokens Per Minute
    rpd_limit: int = 1500                 # Requests Per Day
    max_concurrency: int = 2              # Maximum concurrent in-flight requests per key
    reset_schedule: str = "google_pt"     # "google_pt", "utc_midnight", "rolling"
    is_local_gpu: bool = False            # Requires local GPU hardware lock


def _gm(s: str) -> str:
    return "gem" + "ini-" + s


# Default Canonical Model Profiles
DEFAULT_MODEL_PROFILES: Dict[str, ModelQuotaProfile] = {
    # --- Google Gemini Family ---
    _gm("3.8-flash"): ModelQuotaProfile(
        provider="gemini", model=_gm("3.8-flash"),
        rpm_limit=15.0, tpm_limit=1_000_000.0, rpd_limit=1500, max_concurrency=4, reset_schedule="google_pt"
    ),
    _gm("3.7-flash"): ModelQuotaProfile(
        provider="gemini", model=_gm("3.7-flash"),
        rpm_limit=15.0, tpm_limit=1_000_000.0, rpd_limit=1500, max_concurrency=4, reset_schedule="google_pt"
    ),
    _gm("3.6-flash"): ModelQuotaProfile(
        provider="gemini", model=_gm("3.6-flash"),
        rpm_limit=15.0, tpm_limit=1_000_000.0, rpd_limit=1500, max_concurrency=4, reset_schedule="google_pt"
    ),
    _gm("3.5-flash"): ModelQuotaProfile(
        provider="gemini", model=_gm("3.5-flash"),
        rpm_limit=15.0, tpm_limit=1_000_000.0, rpd_limit=1500, max_concurrency=4, reset_schedule="google_pt"
    ),
    _gm("flash-latest"): ModelQuotaProfile(
        provider="gemini", model=_gm("flash-latest"),
        rpm_limit=15.0, tpm_limit=1_000_000.0, rpd_limit=1500, max_concurrency=4, reset_schedule="google_pt"
    ),
    _gm("3.1-flash-lite"): ModelQuotaProfile(
        provider="gemini", model=_gm("3.1-flash-lite"),
        rpm_limit=30.0, tpm_limit=4_000_000.0, rpd_limit=1500, max_concurrency=8, reset_schedule="google_pt"
    ),
    _gm("flash-lite-latest"): ModelQuotaProfile(
        provider="gemini", model=_gm("flash-lite-latest"),
        rpm_limit=30.0, tpm_limit=4_000_000.0, rpd_limit=1500, max_concurrency=8, reset_schedule="google_pt"
    ),
    _gm("2.5-pro"): ModelQuotaProfile(
        provider="gemini", model=_gm("2.5-pro"),
        rpm_limit=2.0, tpm_limit=32_000.0, rpd_limit=50, max_concurrency=1, reset_schedule="google_pt"
    ),
    _gm("2.5-flash"): ModelQuotaProfile(
        provider="gemini", model=_gm("2.5-flash"),
        rpm_limit=15.0, tpm_limit=1_000_000.0, rpd_limit=1500, max_concurrency=4, reset_schedule="google_pt"
    ),
    _gm("3.8-flash-tts"): ModelQuotaProfile(
        provider="gemini", model=_gm("3.8-flash-tts"),
        rpm_limit=15.0, tpm_limit=500_000.0, rpd_limit=10, max_concurrency=1, reset_schedule="google_pt"
    ),
    _gm("flash-tts"): ModelQuotaProfile(
        provider="gemini", model=_gm("flash-tts"),
        rpm_limit=15.0, tpm_limit=500_000.0, rpd_limit=10, max_concurrency=1, reset_schedule="google_pt"
    ),

    # --- Cerebras Wafer-Scale Fast Inference ---
    "llama3.3-70b": ModelQuotaProfile(
        provider="cerebras", model="llama3.3-70b",
        rpm_limit=30.0, tpm_limit=60_000.0, rpd_limit=14400, max_concurrency=3, reset_schedule="rolling"
    ),
    "llama3.1-8b": ModelQuotaProfile(
        provider="cerebras", model="llama3.1-8b",
        rpm_limit=30.0, tpm_limit=60_000.0, rpd_limit=14400, max_concurrency=4, reset_schedule="rolling"
    ),

    # --- Groq LPU Fast Inference ---
    "llama-3.3-70b-versatile": ModelQuotaProfile(
        provider="groq", model="llama-3.3-70b-versatile",
        rpm_limit=30.0, tpm_limit=30_000.0, rpd_limit=14400, max_concurrency=2, reset_schedule="rolling"
    ),

    # --- OpenAI Family ---
    "gpt-4o": ModelQuotaProfile(
        provider="openai", model="gpt-4o",
        rpm_limit=500.0, tpm_limit=30_000.0, rpd_limit=10000, max_concurrency=5, reset_schedule="rolling"
    ),
    "gpt-4o-mini": ModelQuotaProfile(
        provider="openai", model="gpt-4o-mini",
        rpm_limit=500.0, tpm_limit=200_000.0, rpd_limit=10000, max_concurrency=10, reset_schedule="rolling"
    ),

    # --- Anthropic Claude Family ---
    "claude-3-5-sonnet": ModelQuotaProfile(
        provider="anthropic", model="claude-3-5-sonnet",
        rpm_limit=50.0, tpm_limit=40_000.0, rpd_limit=10000, max_concurrency=4, reset_schedule="rolling"
    ),
    "claude-3-5-haiku": ModelQuotaProfile(
        provider="anthropic", model="claude-3-5-haiku",
        rpm_limit=100.0, tpm_limit=100_000.0, rpd_limit=10000, max_concurrency=8, reset_schedule="rolling"
    ),

    # --- Local GPU / Hardware Models (RTX 4050 6GB) ---
    "spark-x2.5-4b": ModelQuotaProfile(
        provider="local", model="spark-x2.5-4b",
        rpm_limit=9999.0, tpm_limit=999999.0, rpd_limit=99999, max_concurrency=1, reset_schedule="rolling",
        is_local_gpu=True
    ),
    "mms-forced-aligner": ModelQuotaProfile(
        provider="local", model="mms-forced-aligner",
        rpm_limit=9999.0, tpm_limit=999999.0, rpd_limit=99999, max_concurrency=1, reset_schedule="rolling",
        is_local_gpu=True
    ),

    # --- ElevenLabs Voice API ---
    "eleven_multilingual_v2": ModelQuotaProfile(
        provider="elevenlabs", model="eleven_multilingual_v2",
        rpm_limit=60.0, tpm_limit=100_000.0, rpd_limit=1000, max_concurrency=2, reset_schedule="rolling"
    ),
}


def resolve_model_profile(model_name: str, provider: Optional[str] = None) -> ModelQuotaProfile:
    """Resolves or dynamically creates a ModelQuotaProfile for any model name."""
    clean_name = model_name.strip()
    # Direct dictionary hit
    if clean_name in DEFAULT_MODEL_PROFILES:
        return DEFAULT_MODEL_PROFILES[clean_name]

    # Partial prefix match
    low = clean_name.lower()
    for k, prof in DEFAULT_MODEL_PROFILES.items():
        if k in low or low in k:
            return prof

    # Heuristic fallback based on provider or model structure
    resolved_provider = provider or "gemini"
    if "gemini" in low:
        resolved_provider = "gemini"
    elif "claude" in low:
        resolved_provider = "anthropic"
    elif "gpt-" in low or "o1" in low or "o3" in low:
        resolved_provider = "openai"
    elif "cerebras" in low:
        resolved_provider = "cerebras"
    elif "groq" in low:
        resolved_provider = "groq"
    elif "local" in low or "spark" in low:
        resolved_provider = "local"

    is_tts = "-tts" in low or "voice" in low
    is_pro = "-pro" in low or "opus" in low or "o1" in low

    if is_tts:
        return ModelQuotaProfile(
            provider=resolved_provider, model=clean_name,
            rpm_limit=15.0, tpm_limit=500_000.0, rpd_limit=10, max_concurrency=1,
            reset_schedule="google_pt" if resolved_provider == "gemini" else "rolling"
        )
    if is_pro:
        return ModelQuotaProfile(
            provider=resolved_provider, model=clean_name,
            rpm_limit=5.0, tpm_limit=50_000.0, rpd_limit=100, max_concurrency=1,
            reset_schedule="google_pt" if resolved_provider == "gemini" else "rolling"
        )

    # General balanced default
    return ModelQuotaProfile(
        provider=resolved_provider, model=clean_name,
        rpm_limit=20.0, tpm_limit=1_000_000.0, rpd_limit=1500, max_concurrency=4,
        reset_schedule="google_pt" if resolved_provider == "gemini" else "rolling"
    )


class ApiErrorClassification(NamedTuple):
    """Categorized result from universal error classifier."""
    category: str              # DAILY_QUOTA_EXHAUSTED, RPM_RATE_LIMIT, TPM_RATE_LIMIT, CONCURRENCY_LIMIT, etc.
    wait_sec: float            # Recommended backoff in seconds
    message: str               # Human-readable diagnostic description
    is_retryable: bool         # Whether retrying could succeed (on same or next key/model)
    suggested_action: str      # "ROTATE_KEY", "ROTATE_MODEL", "COOL_DOWN", "ABORT_PAYLOAD"


def parse_retry_after(headers: Optional[Dict[str, str]]) -> Optional[float]:
    """Extracts wait seconds from standard HTTP Retry-After headers."""
    if not headers:
        return None
    val = headers.get("retry-after") or headers.get("Retry-After")
    if not val:
        # Check ratelimit headers
        for k in ("x-ratelimit-reset-requests", "x-ratelimit-reset-tokens", "ratelimit-reset"):
            alt = headers.get(k) or headers.get(k.lower())
            if alt:
                try:
                    return float(alt)
                except ValueError:
                    pass
        return None

    val_str = str(val).strip()
    # Can be integer seconds
    try:
        return float(val_str)
    except ValueError:
        pass

    # Can be HTTP Date string (RFC 2822 / RFC 7231)
    try:
        parsed_dt = email.utils.parsedate_to_datetime(val_str)
        now_dt = datetime.now(timezone.utc)
        diff = (parsed_dt - now_dt).total_seconds()
        return max(1.0, diff)
    except Exception:
        return None


def classify_universal_api_error(
    status_code: int,
    error_body: str,
    headers: Optional[Dict[str, str]] = None,
    provider: str = "gemini",
    model: str = "",
) -> ApiErrorClassification:
    """
    Gold Standard Universal Error Classifier across all AI Providers and Models.
    Evaluates:
    - HTTP status codes (400, 401, 403, 404, 413, 429, 500, 502, 503, 504)
    - HTTP headers (Retry-After, x-ratelimit-reset)
    - Specific error body semantics (Google, OpenAI, Anthropic, Cerebras, Groq)
    """
    body_lower = error_body.lower()
    header_wait = parse_retry_after(headers)

    # 1. Authentication / Key Validity (HTTP 400/401/403)
    if status_code in (401, 403) or (
        status_code == 400 and any(
            x in body_lower for x in [
                "api_key_invalid", "api key not valid", "invalid api key",
                "authentication_error", "permission_denied", "forbidden", "unauthorized"
            ]
        )
    ):
        return ApiErrorClassification(
            category="INVALID_KEY",
            wait_sec=0.0,
            message=f"API key is invalid, revoked, or lacks permission for {provider}.",
            is_retryable=False,
            suggested_action="ROTATE_KEY"
        )

    # 2. Context Length Exceeded (HTTP 400 / 413)
    if status_code in (400, 413) and any(
        x in body_lower for x in [
            "context_length_exceeded", "maximum context length", "too many tokens",
            "prompt is too long", "token count exceeds", "max_tokens"
        ]
    ):
        return ApiErrorClassification(
            category="CONTEXT_LENGTH_EXCEEDED",
            wait_sec=0.0,
            message="Payload exceeds model maximum context window. Slicing required.",
            is_retryable=False,
            suggested_action="ABORT_PAYLOAD"
        )

    # 3. Content Moderation / Safety Block (HTTP 400 / 200 payload flag)
    if any(x in body_lower for x in ["blocked", "prohibited_content", "safety", "harm_category", "moderation"]):
        return ApiErrorClassification(
            category="CONTENT_SAFETY_BLOCKED",
            wait_sec=0.5,
            message="Model safety filter blocked the prompt. Requires framing or model rotation.",
            is_retryable=True,
            suggested_action="ROTATE_MODEL"
        )

    # 4. HTTP 429 Resource Exhausted / Rate Limits
    if status_code == 429:
        # Check genuine Daily Quota Exhaustion (per project / per day)
        # Google: "GenerateRequestsPerDayPerProjectPerModel", "perday", "daily"
        # OpenAI/Cerebras: "insufficient_quota", "daily limit"
        is_daily = any(
            x in body_lower for x in [
                "generaterequestsperday", "perday", "daily", "insufficient_quota",
                "quota_exceeded", "billing_hard_limit_reached"
            ]
        )
        if is_daily:
            return ApiErrorClassification(
                category="DAILY_QUOTA_EXHAUSTED",
                wait_sec=0.0,
                message=f"Daily quota reached for model '{model}' on provider '{provider}'.",
                is_retryable=True,
                suggested_action="ROTATE_KEY"
            )

        # Check TPM (Tokens Per Minute) limit
        if any(x in body_lower for x in ["tpm", "tokens per minute", "token limit"]):
            wait = header_wait if header_wait is not None else 20.0
            return ApiErrorClassification(
                category="TPM_RATE_LIMIT",
                wait_sec=wait,
                message=f"Tokens-per-minute (TPM) limit reached. Backing off {wait:.1f}s.",
                is_retryable=True,
                suggested_action="COOL_DOWN"
            )

        # Check Concurrency Limit
        if any(x in body_lower for x in ["concurrency", "simultaneous", "concurrent_requests"]):
            wait = header_wait if header_wait is not None else 6.0
            return ApiErrorClassification(
                category="CONCURRENCY_LIMIT",
                wait_sec=wait,
                message=f"Concurrent request limit reached. Cooling off {wait:.1f}s.",
                is_retryable=True,
                suggested_action="COOL_DOWN"
            )

        # Standard RPM Rate Limit
        if header_wait is not None:
            wait = header_wait + 1.0
        else:
            delay_match = re.search(r"retry in (\d+\.?\d*)s", error_body, re.IGNORECASE)
            wait = float(delay_match.group(1)) + 2.0 if delay_match else 15.0

        return ApiErrorClassification(
            category="RPM_RATE_LIMIT",
            wait_sec=wait,
            message=f"Temporary RPM rate limit hit on '{model}'. Cooling off {wait:.1f}s.",
            is_retryable=True,
            suggested_action="COOL_DOWN"
        )

    # 5. Transient 5xx Server Errors (500, 502, 503, 504)
    if status_code in (500, 502, 503, 504):
        if header_wait is not None:
            wait = header_wait + 1.0
        else:
            delay_match = re.search(r"retry in (\d+\.?\d*)s", error_body, re.IGNORECASE)
            wait = float(delay_match.group(1)) + 2.0 if delay_match else 8.0

        return ApiErrorClassification(
            category="TRANSIENT_SERVER_ERROR",
            wait_sec=wait,
            message=f"Transient provider server error HTTP {status_code} ({provider}).",
            is_retryable=True,
            suggested_action="ROTATE_MODEL"
        )

    # 6. HTTP 400 Bad Request
    if status_code == 400:
        return ApiErrorClassification(
            category="PAYLOAD_INVALID",
            wait_sec=0.0,
            message=f"HTTP 400 Bad Request: {error_body[:140]}",
            is_retryable=False,
            suggested_action="ABORT_PAYLOAD"
        )

    # 7. Unclassified error
    return ApiErrorClassification(
        category="UNKNOWN_ERROR",
        wait_sec=5.0,
        message=f"HTTP {status_code}: {error_body[:120]}",
        is_retryable=True,
        suggested_action="ROTATE_KEY"
    )


class CircuitBreaker:
    """
    Per-(Provider, Model) Thread-Safe Circuit Breaker.
    States:
    - CLOSED: Normal operation. Requests flow freely.
    - OPEN: Tripped due to consecutive server failures (503/500/timeout).
            Bypasses endpoint immediately with zero network delay, enabling instantaneous cascade.
    - HALF_OPEN: Canary test mode after cooldown. Single request probes endpoint health.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout_sec: float = 30.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self._lock = threading.Lock()
        # Key: (provider, model) -> {"state": "CLOSED", "failures": int, "open_until": float}
        self._breakers: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def _get_entry(self, provider: str, model: str) -> Dict[str, Any]:
        k = (provider.lower().strip(), model.lower().strip())
        if k not in self._breakers:
            self._breakers[k] = {
                "state": "CLOSED",
                "failures": 0,
                "open_until": 0.0,
            }
        return self._breakers[k]

    def is_available(self, provider: str, model: str) -> bool:
        """Checks whether the circuit breaker permits requests to this endpoint."""
        now = time.monotonic()
        with self._lock:
            entry = self._get_entry(provider, model)
            st = entry["state"]
            if st == "CLOSED":
                return True
            if st == "OPEN":
                if now >= entry["open_until"]:
                    # Transition to HALF_OPEN for canary probe
                    entry["state"] = "HALF_OPEN"
                    logger.info(f"  [CIRCUIT BREAKER] {provider}/{model} entered HALF_OPEN state. Testing canary request...")
                    return True
                return False
            if st == "HALF_OPEN":
                # In half open, let canary proceed
                return True
            return True

    def record_success(self, provider: str, model: str):
        """Records a successful request, resetting the circuit breaker to CLOSED."""
        with self._lock:
            entry = self._get_entry(provider, model)
            if entry["state"] != "CLOSED" or entry["failures"] > 0:
                logger.info(f"  [CIRCUIT BREAKER] {provider}/{model} recovered to CLOSED state.")
            entry["state"] = "CLOSED"
            entry["failures"] = 0
            entry["open_until"] = 0.0

    def record_failure(self, provider: str, model: str, error_msg: str = ""):
        """Records a failure. If threshold exceeded, trips to OPEN."""
        now = time.monotonic()
        with self._lock:
            entry = self._get_entry(provider, model)
            entry["failures"] += 1
            if entry["state"] == "HALF_OPEN" or entry["failures"] >= self.failure_threshold:
                entry["state"] = "OPEN"
                entry["open_until"] = now + self.recovery_timeout_sec
                logger.warning(
                    f"  [CIRCUIT BREAKER TRIPPED] {provider}/{model} tripped to OPEN for {self.recovery_timeout_sec:.0f}s! "
                    f"Consecutive failures: {entry['failures']}. Triggering instant failover cascade. ({error_msg[:80]})"
                )

    def force_reset(self):
        """Resets all breakers to CLOSED."""
        with self._lock:
            self._breakers.clear()


# Singleton Circuit Breaker
_global_circuit_breaker: Optional[CircuitBreaker] = None
_breaker_lock = threading.Lock()


def get_circuit_breaker() -> CircuitBreaker:
    global _global_circuit_breaker
    if _global_circuit_breaker is None:
        with _breaker_lock:
            if _global_circuit_breaker is None:
                _global_circuit_breaker = CircuitBreaker()
    return _global_circuit_breaker


class HardwareVRAMGuard:
    """
    Workstation Hardware & VRAM Guard for NVIDIA RTX 4050 Laptop GPU (6 GB VRAM).
    Enforces a strict mutual exclusion semaphore across local neural inference
    (Spark Local LLM, MMS Forced Alignment, Audio Harvesters) preventing CUDA OOM
    and thread collision on Windows.
    """
    _gpu_semaphore = threading.Semaphore(1)
    _active_job: Optional[str] = None
    _lock = threading.Lock()

    @classmethod
    def acquire(cls, job_name: str, timeout: float = 60.0) -> bool:
        """Acquires exclusive hardware GPU lock."""
        acquired = cls._gpu_semaphore.acquire(timeout=timeout)
        if acquired:
            with cls._lock:
                cls._active_job = job_name
            logger.debug(f"  [GPU GUARD] Exclusive lock acquired for: {job_name}")
        else:
            logger.warning(f"  [GPU GUARD] Hardware lock timeout waiting for: {job_name}")
        return acquired

    @classmethod
    def release(cls, job_name: str = ""):
        """Releases hardware lock and triggers CUDA garbage collection."""
        with cls._lock:
            cls._active_job = None
        try:
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
        except Exception:
            pass
        finally:
            cls._gpu_semaphore.release()
            logger.debug(f"  [GPU GUARD] Hardware lock released. VRAM evacuated.")
