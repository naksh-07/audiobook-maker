#!/usr/bin/env python3
"""
Audiobook Factory - Global Dynamic Model Intelligence Manager.
Discovers available Google Gemini models via API, manages capability tiering,
executes concurrent 2-3 model health pings (evaluating latency and availability),
and enforces strict minimum quality floor gates with fail-closed production halts.
"""

from __future__ import annotations
import os
import re
import time
import json
import threading
import urllib.request
import urllib.error
from enum import Enum, IntEnum
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from audiobook_factory.logger import logger
from audiobook_factory.key_manager import get_persistent_key_pool
from audiobook_factory.cadence import get_stealth_sdk_headers


class ModelTier(IntEnum):
    """
    Capability tier for LLM reasoning and literary comprehension.
    Lower integer value indicates higher capability / intelligence tier.
    """
    TIER_1_FLAGSHIP = 1    # Deep reasoning, complex dialects, high-subtext drama
    TIER_2_BALANCED = 2    # Standard production, balanced speed/nuance, scene acoustics
    TIER_3_UTILITY = 3     # Fast parsing, token normalization, lightweight JSON


class TaskType(str, Enum):
    """Production tasks with mandatory minimum capability floors."""
    TRANSLATION = "translation"        # Minimum Floor: TIER_2_BALANCED
    SCREENPLAY = "screenplay"          # Minimum Floor: TIER_2_BALANCED
    DRAMATURGY = "dramaturgy"          # Minimum Floor: TIER_2_BALANCED
    DIRECTING = "directing"            # Minimum Floor: TIER_2_BALANCED
    SOUND_DESIGN = "sound_design"      # Minimum Floor: TIER_2_BALANCED
    AUDITING = "auditing"              # Minimum Floor: TIER_2_BALANCED
    EXTRACTION = "extraction"          # Minimum Floor: TIER_2_BALANCED
    UTILITY = "utility"                # Minimum Floor: TIER_3_UTILITY


TASK_MINIMUM_TIERS: Dict[TaskType, ModelTier] = {
    TaskType.TRANSLATION: ModelTier.TIER_2_BALANCED,
    TaskType.SCREENPLAY: ModelTier.TIER_2_BALANCED,
    TaskType.DRAMATURGY: ModelTier.TIER_2_BALANCED,
    TaskType.DIRECTING: ModelTier.TIER_2_BALANCED,
    TaskType.SOUND_DESIGN: ModelTier.TIER_2_BALANCED,
    TaskType.AUDITING: ModelTier.TIER_2_BALANCED,
    TaskType.EXTRACTION: ModelTier.TIER_2_BALANCED,
    TaskType.UTILITY: ModelTier.TIER_3_UTILITY,
}


class LLMUnavailableError(RuntimeError):
    """Raised when an LLM service is unavailable, unauthenticated, or exhausted."""
    pass


class ModelTierFloorBreachError(RuntimeError):
    """Raised when available healthy models fall below the safe quality floor for a task."""
    pass


# Default catalog used as offline fallback if API discovery cannot connect
OFFLINE_CATALOG_FALLBACK: List[str] = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-flash-lite-latest",
]

# Patterns for specialized or non-text-generative models to exclude from LLM text tasks
EXCLUDED_PATTERNS = (
    "-tts",
    "-image",
    "-transcribe",
    "-2.5-",
    "gemini-2.5",
    "robotics",
    "lyria",
    "nano-banana",
    "deep-research",
    "antigravity-preview",
    "computer-use",
    "customtools",
    "omni",
    "gemma",
    "-pro",
    "gemini-pro",
)


class ModelManager:
    """
    Central Dynamic Model Intelligence Manager.
    Eliminates hardcoded model strings by discovering live Gemini models,
    classifying capability tiers, pinging top candidates concurrently,
    and enforcing strict fail-closed quality cutoffs.
    """

    def __init__(self, cache_ttl_sec: float = 3600.0, ping_cache_ttl_sec: float = 300.0):
        self.cache_ttl_sec = cache_ttl_sec
        self.ping_cache_ttl_sec = ping_cache_ttl_sec
        self._cached_models: Optional[List[str]] = None
        self._last_discovery_time: float = 0.0
        self._active_task_models: Dict[TaskType, Tuple[str, float]] = {}
        self._lock = threading.Lock()
        self.pool = get_persistent_key_pool()

    def discover_available_models(self, refresh: bool = False, api_key: Optional[str] = None) -> List[str]:
        """
        Dynamically queries Google Gemini v1beta/models API to discover all live models
        supporting general text/content generation.
        """
        now = time.time()
        with self._lock:
            if not refresh and self._cached_models and (now - self._last_discovery_time < self.cache_ttl_sec):
                return list(self._cached_models)

        key = api_key or self.pool.get_key(service="text")
        if not key:
            logger.warning("  [MODEL MANAGER] No text API key available. Using catalog fallback.")
            with self._lock:
                self._cached_models = OFFLINE_CATALOG_FALLBACK
                self._last_discovery_time = now
                return list(self._cached_models)

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        headers = get_stealth_sdk_headers(key)
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models_raw = data.get("models", [])
                discovered: List[str] = []
                for m in models_raw:
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" not in methods:
                        continue
                    m_name = m.get("name", "").replace("models/", "")
                    # Filter out non-general generation models
                    if any(x in m_name for x in EXCLUDED_PATTERNS):
                        continue
                    discovered.append(m_name)

                if discovered:
                    with self._lock:
                        self._cached_models = discovered
                        self._last_discovery_time = now
                    logger.info(f"[+] Model Manager: Discovered {len(discovered)} live general models from Gemini API.")
                    return list(discovered)
        except Exception as e:
            logger.warning(f"  [MODEL MANAGER] API discovery notice ({e}). Using offline catalog fallback.")

        with self._lock:
            self._cached_models = OFFLINE_CATALOG_FALLBACK
            self._last_discovery_time = now
            return list(self._cached_models)

    @staticmethod
    def classify_model_tier(model_name: str) -> ModelTier:
        """
        Classifies an arbitrary model string into its semantic capability tier.
        """
        m = model_name.lower()
        # Tier 3 Utility: explicitly lightweight models or gemma weights
        if any(x in m for x in ("lite", "flash-lite", "gemma")):
            return ModelTier.TIER_3_UTILITY

        # Tier 1 Flagship: High reasoning models and pro previews
        if any(x in m for x in ("3.8-flash", "3.7-flash", "-pro", "pro-preview", "gemini-pro")):
            return ModelTier.TIER_1_FLAGSHIP

        # Tier 2 Balanced: Standard balanced flash models
        return ModelTier.TIER_2_BALANCED

    def get_candidate_models_for_task(self, task: TaskType, refresh: bool = False) -> List[str]:
        """
        Returns all discovered models that satisfy the minimum quality floor for the task,
        sorted by capability tier (Tier 1 first, then Tier 2) and Gemini version descending.
        """
        discovered = self.discover_available_models(refresh=refresh)
        floor = TASK_MINIMUM_TIERS.get(task, ModelTier.TIER_2_BALANCED)

        eligible: List[Tuple[ModelTier, float, str]] = []
        for name in discovered:
            tier = self.classify_model_tier(name)
            if tier <= floor:  # Satisfies floor (remember: lower value = higher quality)
                # Extract numeric version for recency sorting on core gemini models
                match = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
                version = float(match.group(1)) if match else (2.0 if "gemini" in name else 1.0)
                eligible.append((tier, version, name))

        if not eligible:
            raise ModelTierFloorBreachError(
                f"STRICT HALT: No available models satisfy minimum quality floor {floor.name} "
                f"for task '{task.value}'. Refusing to compromise production quality."
            )

        # Sort: Primary by tier ascending (Tier 1 before Tier 2), Secondary by version descending (3.8 before 3.6), Tertiary by name
        eligible.sort(key=lambda x: (x[0].value, -x[1], x[2]))
        return [x[2] for x in eligible]

    def ping_candidate_models(
        self,
        candidates: List[str],
        api_key: Optional[str] = None,
        timeout: float = 12.0,
    ) -> List[Tuple[str, bool, float, Optional[str]]]:
        """
        Concurrently pings 2-3 candidate models with a minimal dry-run request.
        Returns a list of tuples: (model_name, is_ok, latency_ms, error_msg).
        """
        key = api_key or self.pool.get_key(service="text")
        if not key:
            raise LLMUnavailableError("STRICT HALT: No API key available to ping candidate models.")

        payload_bytes = json.dumps({
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 1, "temperature": 0.0},
        }).encode("utf-8")
        headers = get_stealth_sdk_headers(key)

        def _probe_single(model_name: str) -> Tuple[str, bool, float, Optional[str]]:
            t0 = time.time()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
            req = urllib.request.Request(url, data=payload_bytes, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    dur_ms = (time.time() - t0) * 1000.0
                    return (model_name, True, dur_ms, None)
            except urllib.error.HTTPError as e:
                dur_ms = (time.time() - t0) * 1000.0
                return (model_name, False, dur_ms, f"HTTP {e.code}")
            except Exception as e:
                dur_ms = (time.time() - t0) * 1000.0
                return (model_name, False, dur_ms, str(e))

        results: List[Tuple[str, bool, float, Optional[str]]] = []
        with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as executor:
            future_to_model = {executor.submit(_probe_single, m): m for m in candidates}
            for fut in as_completed(future_to_model):
                results.append(fut.result())

        # Sort results to preserve candidate preference order
        order_map = {m: i for i, m in enumerate(candidates)}
        results.sort(key=lambda r: order_map.get(r[0], 999))
        return results

    def resolve_active_model(
        self,
        task: TaskType,
        api_key: Optional[str] = None,
        force_refresh: bool = False,
    ) -> str:
        """
        Resolves the optimal active model for a task by:
        1. Checking the dynamic minimum quality floor.
        2. Selecting top favorable candidates in batches (up to 3 at a time).
        3. Concurrently pinging candidates to evaluate real-time health and latency.
        4. Selecting the healthiest, lowest-latency candidate meeting or exceeding the floor.
        5. If a batch fails, probing the next batch of eligible candidates.
        6. Strictly halting (raising LLMUnavailableError) if all eligible candidates fail.
        """
        now = time.time()
        # Check active cached model for this task
        with self._lock:
            if not force_refresh and task in self._active_task_models:
                cached_model, cached_time = self._active_task_models[task]
                if now - cached_time < self.ping_cache_ttl_sec:
                    return cached_model

        # 1. Get candidate models satisfying minimum quality floor
        candidates = self.get_candidate_models_for_task(task, refresh=force_refresh)
        env_pref = os.environ.get("GEMINI_TEXT_MODEL")
        if env_pref and env_pref in candidates:
            candidates = [env_pref] + [m for m in candidates if m != env_pref]

        floor = TASK_MINIMUM_TIERS.get(task, ModelTier.TIER_2_BALANCED)
        if not candidates:
            raise ModelTierFloorBreachError(
                f"STRICT HALT: No models meet quality floor {floor.name} for task '{task.value}'."
            )

        # 2. Probe candidates in batches of 3 until a healthy candidate is found
        batch_size = 3
        all_probed_results: List[Tuple[str, bool, float, Optional[str]]] = []

        for i in range(0, min(len(candidates), 6), batch_size):
            batch = candidates[i:i + batch_size]
            logger.info(f"[*] Model Manager: Concurrently pinging favorable candidates for {task.value}: {batch}")
            probe_results = self.ping_candidate_models(batch, api_key=api_key, timeout=12.0)
            all_probed_results.extend(probe_results)

            healthy = [r for r in probe_results if r[1] is True]
            for m_name, ok, lat, err in probe_results:
                status_str = f"HEALTHY ({lat:.0f}ms)" if ok else f"FAILED ({err}, {lat:.0f}ms)"
                logger.info(f"    - {m_name}: {status_str}")

            if healthy:
                # Pick preferred model first; then by tier and low latency
                def _score(item: Tuple[str, bool, float, Optional[str]]) -> Tuple[int, int, float]:
                    m_name, _, latency, _ = item
                    is_pref = 0 if (env_pref and m_name == env_pref) else 1
                    tier = self.classify_model_tier(m_name)
                    return (is_pref, tier.value, latency)

                healthy.sort(key=_score)
                chosen_model = healthy[0][0]
                chosen_latency = healthy[0][2]
                chosen_tier = self.classify_model_tier(chosen_model)

                if chosen_tier > floor:
                    raise ModelTierFloorBreachError(
                        f"STRICT HALT: Candidate '{chosen_model}' ({chosen_tier.name}) breaches minimum "
                        f"quality floor {floor.name} for '{task.value}'. Production halted."
                    )

                logger.info(f"[+] Model Manager: Selected active model '{chosen_model}' for {task.value} (Latency: {chosen_latency:.0f}ms).")
                with self._lock:
                    self._active_task_models[task] = (chosen_model, now)
                return chosen_model

        # All eligible candidates failed ping
        raise LLMUnavailableError(
            f"STRICT HALT: All candidate models satisfying quality floor {floor.name} for '{task.value}' "
            f"failed health pings: {[(r[0], r[3]) for r in all_probed_results]}. Production halted to prevent degraded output."
        )

    def report_failure(self, task: TaskType, model_name: str) -> None:
        """Invalidates task model cache when an in-flight error occurs."""
        with self._lock:
            entry = self._active_task_models.get(task)
            if entry and entry[0] == model_name:
                self._active_task_models.pop(task, None)


# Module-level singleton
_MODEL_MANAGER_INSTANCE: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Returns the process-wide ModelManager singleton."""
    global _MODEL_MANAGER_INSTANCE
    if _MODEL_MANAGER_INSTANCE is None:
        _MODEL_MANAGER_INSTANCE = ModelManager()
    return _MODEL_MANAGER_INSTANCE
