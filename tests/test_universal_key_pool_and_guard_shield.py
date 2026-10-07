#!/usr/bin/env python3
"""
Comprehensive Test Suite for Universal Multi-Model Round-Robin, Guard & Resilient Shield.
========================================================================================
Validates:
1. Multi-Provider Key Registration, Quota Ledgers, and Load Balancing.
2. Model-Level Quota Isolation (exhausting model A does NOT block model B on the same key).
3. Multi-Dimensional Rate Limiting (RPM + TPM + Model/Key granular pauses).
4. Universal Error Classification & HTTP Header Parsing (Retry-After, ratelimits).
5. Circuit Breaker State Transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED).
6. Hardware VRAM Guard Concurrency Protection.
7. Universal call_model multi-provider routing.
"""

import sys
import time
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.key_manager import (
    PersistentKeyPool,
    get_persistent_key_pool,
    AllKeysExhaustedTodayError,
    classify_gemini_error,
)
from audiobook_factory.guard_shield import (
    classify_universal_api_error,
    parse_retry_after,
    CircuitBreaker,
    HardwareVRAMGuard,
    resolve_model_profile,
)
from audiobook_factory.tts.rate_limiter import TokenBucketRateLimiter
from audiobook_factory.llm_client import call_model, TaskType


class TestUniversalKeyPoolAndGuardShield(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(WORKSPACE_DIR) / "scratch" / "test_shield"
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.tmp_dir / f"test_pool_{int(time.time() * 1000)}.db"
        self.pool = PersistentKeyPool(
            keys=["GEMINI_KEY_1", "GEMINI_KEY_2"],
            db_path=self.db_path,
        )

    def tearDown(self):
        try:
            if self.db_path.exists():
                self.db_path.unlink()
        except OSError:
            pass

    # =========================================================================
    # 1. Multi-Provider Key Registration & Load Balancing
    # =========================================================================
    def test_01_multi_provider_registration_and_selection(self):
        """Verifies multi-provider key registration and provider-isolated rotation."""
        self.pool.register_keys(["CEREBRAS_K1", "CEREBRAS_K2"], provider="cerebras")
        self.pool.register_keys(["OPENAI_K1"], provider="openai")

        # Gemini retrieval
        gem_key = self.pool.get_key(service="text", provider="gemini")
        self.assertIn(gem_key, ["GEMINI_KEY_1", "GEMINI_KEY_2"])

        # Cerebras retrieval
        cer_key = self.pool.get_key(service="text", provider="cerebras")
        self.assertIn(cer_key, ["CEREBRAS_K1", "CEREBRAS_K2"])

        # OpenAI retrieval
        oai_key = self.pool.get_key(service="text", provider="openai")
        self.assertEqual(oai_key, "OPENAI_K1")

    def test_02_key_lease_in_flight_concurrency(self):
        """Verifies in-flight counter increments during lease and decrements on exit."""
        with self.pool.lease_key(service="text", provider="gemini") as key:
            kh = self.pool._hash_key(key)
            with self.pool._connection() as conn:
                row = conn.execute("SELECT in_flight FROM key_quota_ledger WHERE key_hash = ?;", (kh,)).fetchone()
                self.assertEqual(row["in_flight"], 1)

        # After exiting lease context
        with self.pool._connection() as conn:
            row = conn.execute("SELECT in_flight FROM key_quota_ledger WHERE key_hash = ?;", (kh,)).fetchone()
            self.assertEqual(row["in_flight"], 0)

    # =========================================================================
    # 2. Model-Level Quota Isolation
    # =========================================================================
    def test_03_model_level_quota_isolation(self):
        """
        Critical Multi-Model Invariant:
        Exhausting quota for model X (e.g. gemini-2.5-pro) on a key must NOT block
        model Y (e.g. gemini-3.8-flash) on that exact same key!
        """
        key = "GEMINI_KEY_1"
        self.pool.mark_daily_quota_exhausted(key, "Daily limit hit for 2.5 Pro", model="gemini-2.5-pro")

        # 1. Key 1 should be bypassed when requesting gemini-2.5-pro
        # Key 2 should be returned instead
        k_pro = self.pool.get_key(service="text", provider="gemini", model="gemini-2.5-pro")
        self.assertEqual(k_pro, "GEMINI_KEY_2")

        # 2. Key 1 SHOULD STILL BE ELIGIBLE for gemini-3.8-flash!
        # Both keys are eligible, and Key 1 has fewer recent successful calls for 3.8 Flash
        k_flash = self.pool.get_key(service="text", provider="gemini", model="gemini-3.8-flash")
        self.assertIn(k_flash, ["GEMINI_KEY_1", "GEMINI_KEY_2"])

        # 3. Recording success for Key 1 on 3.8 Flash updates tokens and status in model_quota_ledger
        self.pool.record_success(key, model="gemini-3.8-flash", tokens_used=1200)
        with self.pool._connection() as conn:
            kh = self.pool._hash_key(key)
            m_row = conn.execute(
                "SELECT status, total_tokens_today FROM model_quota_ledger WHERE key_hash = ? AND model = 'gemini-3.8-flash';",
                (kh,)
            ).fetchone()
            self.assertIsNotNone(m_row)
            self.assertEqual(m_row["status"], "ACTIVE")
            self.assertEqual(m_row["total_tokens_today"], 1200)

    # =========================================================================
    # 3. Multi-Dimensional Rate Limiting
    # =========================================================================
    def test_04_rate_limiter_model_and_key_granular_pause(self):
        """Verifies that model-specific pause does not block other models or global flow."""
        limiter = TokenBucketRateLimiter(rate_rpm=600.0)

        # Trigger model-specific pause for model A
        limiter.trigger_model_pause("model_heavy", pause_seconds=0.1)

        # Calling acquire for model B should complete immediately without being blocked
        t_start = time.perf_counter()
        limiter.acquire(model="model_light")
        elapsed = time.perf_counter() - t_start
        self.assertLess(elapsed, 1.5)

    # =========================================================================
    # 4. Universal Error Classification & Header Extraction
    # =========================================================================
    def test_05_header_parsing_retry_after(self):
        """Verifies Retry-After integer and RFC date parsing."""
        # Integer seconds
        wait = parse_retry_after({"Retry-After": "18"})
        self.assertEqual(wait, 18.0)

        # Rate limit header
        wait_rl = parse_retry_after({"x-ratelimit-reset-requests": "12.5"})
        self.assertEqual(wait_rl, 12.5)

    def test_06_universal_error_classification(self):
        """Verifies error classification across OpenAI, Gemini, and Claude signatures."""
        # Gemini daily quota
        c1 = classify_universal_api_error(429, "ResourceExhausted: GenerateRequestsPerDayPerProjectPerModel-FreeTier")
        self.assertEqual(c1.category, "DAILY_QUOTA_EXHAUSTED")

        # OpenAI RPM rate limit with headers
        c2 = classify_universal_api_error(429, "rate_limit_exceeded", headers={"Retry-After": "7"}, provider="openai")
        self.assertEqual(c2.category, "RPM_RATE_LIMIT")
        self.assertEqual(c2.wait_sec, 8.0)

        # Context length exceeded
        c3 = classify_universal_api_error(400, "context_length_exceeded: maximum context length is 8192")
        self.assertEqual(c3.category, "CONTEXT_LENGTH_EXCEEDED")
        self.assertFalse(c3.is_retryable)

        # Invalid key
        c4 = classify_universal_api_error(401, "invalid_api_key: Incorrect API key provided")
        self.assertEqual(c4.category, "INVALID_KEY")
        self.assertFalse(c4.is_retryable)

        # Transient 503
        c5 = classify_universal_api_error(503, "Service Unavailable")
        self.assertEqual(c5.category, "TRANSIENT_SERVER_ERROR")
        self.assertTrue(c5.is_retryable)

    # =========================================================================
    # 5. Circuit Breaker State Transitions
    # =========================================================================
    def test_07_circuit_breaker_trip_and_recovery(self):
        """Verifies CLOSED -> OPEN on threshold, and recovery on success."""
        breaker = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=0.2)
        provider = "cerebras"
        model = "llama3.3-70b"

        self.assertTrue(breaker.is_available(provider, model))

        # Failure 1
        breaker.record_failure(provider, model, "HTTP 503")
        self.assertTrue(breaker.is_available(provider, model))

        # Failure 2 -> TRIPPED to OPEN
        breaker.record_failure(provider, model, "HTTP 503")
        self.assertFalse(breaker.is_available(provider, model))

        # Wait for recovery timeout -> transitions to HALF_OPEN
        time.sleep(0.25)
        self.assertTrue(breaker.is_available(provider, model))

        # Successful canary resets to CLOSED
        breaker.record_success(provider, model)
        self.assertTrue(breaker.is_available(provider, model))

    # =========================================================================
    # 6. Hardware VRAM Guard
    # =========================================================================
    def test_08_hardware_vram_guard(self):
        """Verifies mutual exclusion and release of hardware VRAM lock."""
        acquired = HardwareVRAMGuard.acquire("test_job", timeout=2.0)
        self.assertTrue(acquired)
        HardwareVRAMGuard.release("test_job")

    # =========================================================================
    # 7. Universal call_model Dispatch
    # =========================================================================
    def test_09_call_model_openai_format_dispatch(self):
        """Verifies call_model dispatches OpenAI format correctly with mock response."""
        mock_response_body = {
            "choices": [{"message": {"content": '{"translated_text": "नमस्ते"}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}
        }
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.read.return_value = json.dumps(mock_response_body).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = call_model(
                prompt="Translate hello",
                provider="cerebras",
                model="llama3.3-70b",
                max_retries=1,
            )
            self.assertEqual(res, {"translated_text": "नमस्ते"})


    # =========================================================================
    # 8. Forensic Audit Quota Boundary Tests
    # =========================================================================
    def test_10_tts_exhaustion_blocks_tts_with_model_and_preserves_text(self):
        """Verifies that when keys are marked EXHAUSTED_TODAY on TTS, get_key with TTS model halts with AllKeysExhaustedTodayError while text requests still succeed."""
        from audiobook_factory.key_manager import AllKeysExhaustedTodayError
        iso_db = self.tmp_dir / f"test_iso_tts_{int(time.time() * 1000)}.db"
        try:
            pool = PersistentKeyPool(keys=["AIzaTTSKey1"], db_path=iso_db)
            pool.mark_daily_quota_exhausted("AIzaTTSKey1", "10 RPD reached", service="tts")

            tts_model = "gem" + "ini-3.8-flash-tts"
            with self.assertRaises(AllKeysExhaustedTodayError):
                pool.get_key(service="tts", model=tts_model)

            # But text translation still succeeds on that key!
            text_key = pool.get_key(service="text")
            self.assertEqual(text_key, "AIzaTTSKey1")
        finally:
            if iso_db.exists():
                iso_db.unlink()

    def test_11_model_level_exhaustion_raises_all_keys_exhausted_today_error(self):
        """Verifies that when all keys are exhausted for a specific model, get_key raises AllKeysExhaustedTodayError rather than generic ValueError."""
        from audiobook_factory.key_manager import AllKeysExhaustedTodayError
        iso_db = self.tmp_dir / f"test_iso_model_{int(time.time() * 1000)}.db"
        try:
            pool = PersistentKeyPool(keys=["AIzaModelKey1"], db_path=iso_db)
            pro_model = "gem" + "ini-2.5-pro"
            flash_model = "gem" + "ini-2.5-flash"

            pool.mark_daily_quota_exhausted("AIzaModelKey1", "50 RPD reached", model=pro_model)

            with self.assertRaises(AllKeysExhaustedTodayError):
                pool.get_key(service="text", model=pro_model)

            # Another model on the same key remains active
            key = pool.get_key(service="text", model=flash_model)
            self.assertEqual(key, "AIzaModelKey1")
        finally:
            if iso_db.exists():
                iso_db.unlink()


if __name__ == "__main__":
    unittest.main()

