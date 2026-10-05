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


def _model_supports_thinking(model_name: str) -> bool:
    """Returns True if the given Gemini model is known to support thinkingConfig."""
    m = model_name.lower()
    return "thinking" in m or "2.5" in m or "3." in m or "flash" in m


def call_gemini(
    prompt: str,
    system_instruction: Optional[str] = None,
    task_type: TaskType = TaskType.UTILITY,
    response_mime_type: str = "application/json",
    temperature: Optional[float] = None,
    max_output_tokens: int = 8192,
    max_retries: int = 6,
    service: str = "text",
    explicit_key: Optional[str] = None,
    timeout_sec: float = 45.0,
    model: Optional[str] = None,
    response_schema: Optional[Dict[str, Any]] = None,
    return_raw_text: bool = False,
    thinking_budget: Optional[int] = None,
    json_mode: Optional[bool] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    **kwargs: Any,
) -> Any:
    """
    Executes an LLM call through Google Gemini API using strict round-robin rotation.
    Guarantees:
    1. Zero hammering: Requests pace with subtle random jitter and respect temp backoffs.
    2. Dynamic model resolution adhering to task minimum capability floors.
    3. Proper quota ledger accounting on HTTP 429 / 5xx / 403.
    4. Deterministic JSON repair on malformed responses.
    5. Fail-closed: Raises LLMUnavailableError if all retries fail.
    6. Task-adaptive temperature: Creative tasks default to 0.85, utility to 0.2.
    7. thinkingConfig injection: Separates reasoning tokens from output tokens.
    8. MAX_TOKENS truncation retry: Retries with halved thinking budget before failing.
    9. json_mode backward compatibility: Automatically maps json_mode to response_mime_type.
    """
    if json_mode is not None:
        response_mime_type = "application/json" if json_mode else "text/plain"
    # --- Task-Adaptive Temperature (Phase 2 Fix) ---
    # Creative / literary tasks need expressive range (0.80–0.92).
    # Analytical / utility tasks stay deterministic (0.20).
    # Callers may always override by passing an explicit temperature.
    _TASK_TEMPERATURE_MAP: Dict[TaskType, float] = {
        TaskType.TRANSLATION:  0.85,  # Literary — needs stylistic range & dialect variety
        TaskType.SCREENPLAY:   0.88,  # Dramatic — expressive dialogue construction
        TaskType.DRAMATURGY:   0.82,  # Narrative beat planning — moderate creativity
        TaskType.DIRECTING:    0.80,  # Sound design intent — grounded but expressive
        TaskType.SOUND_DESIGN: 0.72,  # Mostly structured JSON — slight creative latitude
        TaskType.AUDITING:     0.20,  # Evaluation — must be deterministic
        TaskType.EXTRACTION:   0.20,  # Parsing — deterministic
        TaskType.UTILITY:      0.20,  # Lightweight JSON — fully deterministic
    }
    resolved_temperature = temperature if temperature is not None else _TASK_TEMPERATURE_MAP.get(task_type, 0.20)

    # --- thinkingConfig: separate reasoning tokens from output tokens (Phase 2 Fix) ---
    # Creative reasoning tasks get a thinking budget so internal CoT tokens don't
    # cannibalize maxOutputTokens and cause premature MAX_TOKENS truncation.
    _THINKING_TASK_TYPES = {TaskType.TRANSLATION, TaskType.SCREENPLAY, TaskType.DRAMATURGY, TaskType.DIRECTING}
    _DEFAULT_THINKING_BUDGET = 1024  # balanced budget — leaves ample room for long multi-turn JSON responses

    pool = get_persistent_key_pool()
    model_mgr = get_model_manager()

    from audiobook_factory.safety import get_universal_safety_settings
    safety_settings = get_universal_safety_settings()

    def _build_payload(current_thinking_budget: Optional[int]) -> Dict[str, Any]:
        """Build the API payload, optionally injecting thinkingConfig."""
        p: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": resolved_temperature,
                "maxOutputTokens": max_output_tokens,
            },
            "safetySettings": safety_settings,
        }
        if response_mime_type:
            p["generationConfig"]["responseMimeType"] = response_mime_type
        if response_schema and response_mime_type == "application/json":
            p["generationConfig"]["responseSchema"] = response_schema
        if system_instruction:
            p["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        # Inject thinkingConfig only for creative reasoning tasks
        if current_thinking_budget and current_thinking_budget > 0:
            p["generationConfig"]["thinkingConfig"] = {
                "thinkingBudget": current_thinking_budget
            }
        if tools:
            p["tools"] = tools
        return p

    # Resolve effective thinking budget for this call
    effective_thinking_budget: Optional[int] = None
    if task_type in _THINKING_TASK_TYPES:
        effective_thinking_budget = thinking_budget if thinking_budget is not None else _DEFAULT_THINKING_BUDGET

    last_error: Optional[Exception] = None
    _max_tokens_retried = False  # guard: only retry once on MAX_TOKENS
    _thinking_disabled = False   # guard: disable thinkingConfig if model rejects it

    for attempt in range(max_retries):
        # Subtle non-hammering pacing jitter between parallel threads (100ms - 350ms)
        time.sleep(random.uniform(0.10, 0.35))

        try:
            curr_key = explicit_key if explicit_key else pool.get_key(service=service)
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

        env_model = os.environ.get("GEMINI_TEXT_MODEL")
        if env_model:
            if env_model in candidate_models:
                candidate_models = [env_model] + [m for m in candidate_models if m != env_model]
            else:
                candidate_models = [env_model] + candidate_models

        if model:
            if model in candidate_models:
                candidate_models = [model] + [m for m in candidate_models if m != model]
            else:
                candidate_models = [model] + candidate_models

        if not candidate_models:
            raise LLMUnavailableError(f"STRICT HALT: No valid models available for task {task_type}")

        if model:
            curr_model = model
        elif env_model:
            curr_model = env_model
        elif attempt > 0 and len(candidate_models) > 1:
            # Automatic candidate rotation on retries/errors (never hammer a single model)
            curr_model = candidate_models[attempt % len(candidate_models)]
        else:
            try:
                curr_model = model_mgr.resolve_active_model(task_type, api_key=curr_key)
            except Exception:
                curr_model = candidate_models[0]

        # Determine whether current candidate model supports thinkingConfig
        use_thinking = (
            effective_thinking_budget is not None
            and not _thinking_disabled
            and _model_supports_thinking(curr_model)
        )
        curr_budget = effective_thinking_budget if use_thinking else None
        attempt_payload = _build_payload(curr_budget)
        data_bytes = json.dumps(attempt_payload).encode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{curr_model}:generateContent?key={curr_key}"
        headers = get_stealth_sdk_headers(curr_key)
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        t_req_start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw_bytes = resp.read()
                latency_sec = time.perf_counter() - t_req_start
                data = json.loads(raw_bytes.decode("utf-8"))
                pool.record_success(curr_key)

                # Record Telemetry API Call
                usage_meta = data.get("usageMetadata", {})
                prompt_tok = usage_meta.get("promptTokenCount", 0)
                cand_tok = usage_meta.get("candidatesTokenCount", 0)
                cost_est = (prompt_tok * 0.075 + cand_tok * 0.30) / 1_000_000
                run_id = os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", "studio_run")
                try:
                    from audiobook_factory.telemetry import get_telemetry_ledger
                    get_telemetry_ledger().record_api_call(
                        run_id=run_id,
                        service="gemini_llm",
                        endpoint=curr_model,
                        status_code=200,
                        latency_sec=latency_sec,
                        is_rate_limit=False,
                        prompt_tokens=prompt_tok,
                        completion_tokens=cand_tok,
                        est_cost_usd=cost_est,
                    )
                except Exception as t_err:
                    logger.debug(f"[telemetry] Notice recording API call: {t_err}")

                resp_candidates = data.get("candidates", [])
                if not resp_candidates:
                    prompt_fb = data.get("promptFeedback", {})
                    raise GeminiPayloadError(f"Gemini API returned no candidates (blocked): {prompt_fb}")

                candidate = resp_candidates[0]
                if candidate.get("finishReason") == "MAX_TOKENS":
                    # --- MAX_TOKENS Truncation Retry (Phase 2/3 Fix) ---
                    # Thinking tokens eat into maxOutputTokens on Gemini 3+.
                    # On first MAX_TOKENS hit: retry with halved thinking budget.
                    # On second hit (or no thinking budget): fail-hard.
                    if (
                        effective_thinking_budget
                        and not _max_tokens_retried
                        and not _thinking_disabled
                        and _model_supports_thinking(curr_model)
                    ):
                        halved_budget = effective_thinking_budget // 2
                        logger.warning(
                            f"  [!] MAX_TOKENS on {curr_model} (thinking_budget={effective_thinking_budget}). "
                            f"Retrying with halved thinking budget ({halved_budget}) on next candidate..."
                        )
                        effective_thinking_budget = halved_budget
                        _max_tokens_retried = True
                        continue  # proceed to next retry iteration
                    raise GeminiPayloadError(
                        f"Gemini API output truncated: finishReason is MAX_TOKENS "
                        f"(model={curr_model}, thinking_budget={effective_thinking_budget}). "
                        "Consider reducing chunk size or disabling thinkingConfig for this task."
                    )

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
            run_id = os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", "studio_run")
            try:
                from audiobook_factory.telemetry import get_telemetry_ledger
                get_telemetry_ledger().record_incident(
                    run_id=run_id,
                    stage_name="LLM Generation",
                    incident_type="SAFETY_OR_PAYLOAD_BLOCK",
                    details={"model": curr_model, "error": str(gpe)},
                )
            except Exception:
                pass
            raise gpe

        except urllib.error.HTTPError as e:
            latency_sec = time.perf_counter() - t_req_start
            last_error = e
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else str(e)
            finally:
                if hasattr(e, "close"):
                    e.close()

            # Automatic fallback if thinkingConfig is rejected by the model (e.g. standard Gemini 1.5)
            if e.code == 400 and ("thinkingConfig" in err_body or "thinking_config" in err_body):
                logger.warning(
                    f"  [MODEL REJECTED thinkingConfig] {curr_model} does not support thinkingConfig. "
                    f"Disabling thinkingConfig and immediately retrying on same key..."
                )
                _thinking_disabled = True
                continue

            error_type, wait_sec, msg = classify_gemini_error(e.code, err_body)
            preview = f"{curr_key[:6]}...{curr_key[-4:]}"
            logger.warning(
                f"  [!] LLM HTTP {e.code} ({error_type}) on key {preview} (attempt {attempt + 1}/{max_retries}): {msg}"
            )

            run_id = os.environ.get("CURRENT_AUDIOBOOK_RUN_ID", "studio_run")
            try:
                from audiobook_factory.telemetry import get_telemetry_ledger
                t_led = get_telemetry_ledger()
                t_led.record_api_call(
                    run_id=run_id,
                    service="gemini_llm",
                    endpoint=curr_model,
                    status_code=e.code,
                    latency_sec=latency_sec,
                    is_rate_limit=(e.code == 429),
                    prompt_tokens=0,
                    completion_tokens=0,
                    est_cost_usd=0.0,
                )
                if e.code == 429:
                    t_led.record_incident(
                        run_id=run_id,
                        stage_name="LLM Generation",
                        incident_type="RATE_LIMIT_429",
                        details={"model": curr_model, "attempt": attempt + 1, "key": preview, "error": msg},
                    )
            except Exception as t_err:
                logger.debug(f"[telemetry] Notice recording error telemetry: {t_err}")

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
