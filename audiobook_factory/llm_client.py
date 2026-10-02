#!/usr/bin/env python3
"""
Audiobook Factory - Centralized Multi-Agent Round-Robin LLM Client.
Enforces non-hammering round-robin key rotation across the 100+ key pool,
dynamic model resolution, stealth headers, permissive BLOCK_NONE creative safety,
exponential backoff with pacing jitter, and fail-closed error handling.
"""

from __future__ import annotations
import os
import json
import time
import random
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Union

import json_repair

from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool, classify_gemini_error
from audiobook_factory.model_manager import get_model_manager, TaskType, LLMUnavailableError
from audiobook_factory.cadence import get_stealth_sdk_headers


class GeminiPayloadError(RuntimeError):
    """Non-transient error indicating prompt payload issue (e.g. MAX_TOKENS or Safety Block)."""
    pass


def call_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    task_type: TaskType = TaskType.UTILITY,
    response_mime_type: str = "application/json",
    temperature: float = 0.2,
    max_output_tokens: int = 4096,
    max_retries: int = 6,
    service: str = "text",
    explicit_key: Optional[str] = None,
    timeout_sec: float = 45.0,
    model: Optional[str] = None,
    response_schema: Optional[Dict[str, Any]] = None,
    return_raw_text: bool = False,
) -> Any:
    """
    Executes an LLM call through Google Gemini API using strict round-robin rotation.
    Guarantees:
    1. Zero hammering: Requests pace with subtle random jitter and respect temp backoffs.
    2. Dynamic model resolution adhering to task minimum capability floors.
    3. Proper quota ledger accounting on HTTP 429 / 5xx / 403.
    4. Deterministic JSON repair on malformed responses.
    5. Fail-closed: Raises LLMUnavailableError if all retries fail.
    """
    pool = get_persistent_key_pool()
    model_mgr = get_model_manager()

    # Creative fiction / dramatic safety settings (BLOCK_NONE)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    payload: Dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
        "safetySettings": safety_settings,
    }
    if response_mime_type:
        payload["generationConfig"]["responseMimeType"] = response_mime_type
    if response_schema and response_mime_type == "application/json":
        payload["generationConfig"]["responseSchema"] = response_schema
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    data_bytes = json.dumps(payload).encode("utf-8")
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        # Subtle non-hammering pacing jitter between parallel threads (100ms - 350ms)
        time.sleep(random.uniform(0.10, 0.35))

        try:
            curr_key = explicit_key if (attempt == 0 and explicit_key) else pool.get_key(service=service)
        except Exception as e:
            logger.error(f"  [!] KeyPool key acquisition failure: {e}")
            raise LLMUnavailableError(f"No available Gemini API keys in pool: {e}") from e

        if not curr_key:
            curr_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        if not curr_key:
            raise LLMUnavailableError("KeyPool returned empty API key.")

        try:
            candidate_models = model_mgr.get_candidate_models_for_task(task_type)
        except Exception:
            candidate_models = []

        if model:
            if model in candidate_models:
                candidate_models = [model] + [m for m in candidate_models if m != model]
            else:
                candidate_models = [model] + candidate_models

        env_model = os.environ.get("GEMINI_TEXT_MODEL")
        if env_model:
            # If user specified a preferred model, prioritize it in candidate list
            # but NEVER hard-lock or prevent candidate cycling across retries
            if env_model in candidate_models:
                candidate_models = [env_model] + [m for m in candidate_models if m != env_model]
            else:
                candidate_models = [env_model] + candidate_models

        if not candidate_models:
            raise LLMUnavailableError(f"STRICT HALT: No valid models available for task {task_type}")

        if attempt > 0 and len(candidate_models) > 1:
            # Automatic candidate rotation on retries/errors (never hammer a single model)
            curr_model = candidate_models[attempt % len(candidate_models)]
        elif model:
            curr_model = model
        else:
            try:
                curr_model = model_mgr.resolve_active_model(task_type, api_key=curr_key)
            except Exception:
                curr_model = candidate_models[0]

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{curr_model}:generateContent?key={curr_key}"
        headers = get_stealth_sdk_headers(curr_key)
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode("utf-8"))
                pool.record_success(curr_key)

                resp_candidates = data.get("candidates", [])
                if not resp_candidates:
                    prompt_fb = data.get("promptFeedback", {})
                    raise GeminiPayloadError(f"Gemini API returned no candidates (blocked): {prompt_fb}")

                candidate = resp_candidates[0]
                if candidate.get("finishReason") == "MAX_TOKENS":
                    raise GeminiPayloadError("Gemini API output truncated: finishReason is MAX_TOKENS.")

                parts = candidate.get("content", {}).get("parts", [])
                if not parts:
                    continue

                raw_text = "".join(p.get("text", "") for p in parts if "text" in p).strip()

                if return_raw_text or response_mime_type != "application/json":
                    return raw_text

                if response_mime_type == "application/json":
                    try:
                        return json.loads(raw_text)
                    except json.JSONDecodeError:
                        return json_repair.loads(raw_text)
                return raw_text

        except GeminiPayloadError as gpe:
            # Deterministic payload problem: do NOT retry on identical payload
            last_error = gpe
            logger.warning(f"  [FAIL-FAST] {gpe}. Breaking model retry immediately.")
            raise gpe

        except urllib.error.HTTPError as e:
            last_error = e
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            finally:
                if hasattr(e, "close"):
                    e.close()

            error_type, wait_sec, msg = classify_gemini_error(e.code, err_body)
            preview = f"{curr_key[:6]}...{curr_key[-4:]}"
            logger.warning(
                f"  [!] LLM HTTP {e.code} ({error_type}) on key {preview} (attempt {attempt + 1}/{max_retries}): {msg}"
            )

            if error_type == "DAILY_QUOTA_EXHAUSTED":
                pool.mark_daily_quota_exhausted(curr_key, msg)
            elif error_type == "RPM_RATE_LIMIT":
                pool.mark_temporary_backoff(curr_key, wait_sec, msg)
            elif error_type == "INVALID_KEY":
                pool.mark_invalid(curr_key, msg)
            else:
                pool.mark_temporary_backoff(curr_key, 6.0, msg)

            # Jittered backoff before trying next round-robin key
            backoff_sleep = min(10.0, (1.5 * (attempt + 1)) + random.uniform(0.2, 0.8))
            time.sleep(backoff_sleep)
            continue

        except Exception as ex:
            last_error = ex
            logger.warning(f"  [!] LLM call failed on attempt {attempt + 1}/{max_retries}: {ex}")
            time.sleep(1.0 + random.uniform(0.1, 0.5))
            continue

    logger.error(f"  [!] STRICT HALT: All {max_retries} Gemini API retries exhausted across key pool.")
    raise LLMUnavailableError(
        f"STRICT HALT: Gemini LLM call failed for task '{task_type.value}' after {max_retries} retries: {last_error}"
    )
