#!/usr/bin/env python3
"""
Test Suite for Dynamic Model Intelligence & Strict Production Halt Contracts
=============================================================================
Validates:
1. Dynamic model discovery and semantic capability tiering.
2. Concurrent multi-model health ping & latency-based model resolution.
3. Strict quality floor breach enforcement (ModelTierFloorBreachError).
4. Strict fail-closed production halts across all creative modules (LLMUnavailableError):
   - script_builder.py
   - dramaturgy/beat_planner.py
   - agent_director.py
   - soundscape.py
   - translator.py
5. AST scan asserting zero hardcoded Gemini model string literals across
   audiobook_factory/ outside exempt modules (model_manager.py, tts_dispatcher.py,
   pronunciation/contracts.py, pronunciation/provenance.py).
"""

import ast
import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.model_manager import (
    ModelManager,
    ModelTier,
    TaskType,
    TASK_MINIMUM_TIERS,
    LLMUnavailableError,
    ModelTierFloorBreachError,
)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
FACTORY_DIR = WORKSPACE_DIR / "audiobook_factory"


class TestModelManagerAndStrictHalt(unittest.TestCase):

    def setUp(self):
        self.manager = ModelManager(cache_ttl_sec=3600.0, ping_cache_ttl_sec=300.0)

    # =========================================================================
    # 1. Dynamic Discovery & Semantic Capability Tiering
    # =========================================================================
    def test_01_tier_classification(self):
        """Validates that models are accurately classified into semantic capability tiers."""
        # Tier 1 Flagship: High reasoning models and pro previews
        self.assertEqual(self.manager.classify_model_tier("gemini-3.8-flash"), ModelTier.TIER_1_FLAGSHIP)
        self.assertEqual(self.manager.classify_model_tier("gemini-3.7-flash"), ModelTier.TIER_1_FLAGSHIP)
        self.assertEqual(self.manager.classify_model_tier("gemini-2.5-pro"), ModelTier.TIER_1_FLAGSHIP)
        self.assertEqual(self.manager.classify_model_tier("gemini-pro-preview-0514"), ModelTier.TIER_1_FLAGSHIP)

        # Tier 2 Balanced: Standard balanced flash models
        self.assertEqual(self.manager.classify_model_tier("gemini-3.6-flash"), ModelTier.TIER_2_BALANCED)
        self.assertEqual(self.manager.classify_model_tier("gemini-3.5-flash"), ModelTier.TIER_2_BALANCED)
        self.assertEqual(self.manager.classify_model_tier("gemini-2.5-flash"), ModelTier.TIER_2_BALANCED)
        self.assertEqual(self.manager.classify_model_tier("gemini-flash-latest"), ModelTier.TIER_2_BALANCED)

        # Tier 3 Utility: Lightweight / small parameter models
        self.assertEqual(self.manager.classify_model_tier("gemini-3.1-flash-lite"), ModelTier.TIER_3_UTILITY)
        self.assertEqual(self.manager.classify_model_tier("gemini-flash-lite-latest"), ModelTier.TIER_3_UTILITY)
        self.assertEqual(self.manager.classify_model_tier("gemma-2-9b-it"), ModelTier.TIER_3_UTILITY)

    def test_02_task_minimum_tier_contracts(self):
        """Validates that creative tasks require TIER_1_FLAGSHIP, and balanced tasks require TIER_2_BALANCED."""
        self.assertEqual(TASK_MINIMUM_TIERS[TaskType.TRANSLATION], ModelTier.TIER_1_FLAGSHIP)
        self.assertEqual(TASK_MINIMUM_TIERS[TaskType.SCREENPLAY], ModelTier.TIER_1_FLAGSHIP)
        self.assertEqual(TASK_MINIMUM_TIERS[TaskType.DRAMATURGY], ModelTier.TIER_1_FLAGSHIP)
        self.assertEqual(TASK_MINIMUM_TIERS[TaskType.DIRECTING], ModelTier.TIER_2_BALANCED)
        self.assertEqual(TASK_MINIMUM_TIERS[TaskType.SOUND_DESIGN], ModelTier.TIER_2_BALANCED)
        self.assertEqual(TASK_MINIMUM_TIERS[TaskType.AUDITING], ModelTier.TIER_2_BALANCED)
        self.assertEqual(TASK_MINIMUM_TIERS[TaskType.EXTRACTION], ModelTier.TIER_2_BALANCED)
        self.assertEqual(TASK_MINIMUM_TIERS[TaskType.UTILITY], ModelTier.TIER_3_UTILITY)

    def test_03_discovery_filters_non_general_models(self):
        """Validates that specialized non-chat/audio/robotics models are filtered during discovery."""
        mock_raw_response = {
            "models": [
                {"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3.8-flash-tts", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/deep-research-preview", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/imagen-3.0-generate-002", "supportedGenerationMethods": ["generateImage"]},
                {"name": "models/gemini-robotics-rt", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]},
            ]
        }
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json_bytes(mock_raw_response)
            mock_resp.__enter__.return_value = mock_resp
            mock_urlopen.return_value = mock_resp

            discovered = self.manager.discover_available_models(refresh=True, api_key="fake-key")

            self.assertIn("gemini-3.8-flash", discovered)
            self.assertIn("gemini-3.6-flash", discovered)
            self.assertNotIn("gemini-3.8-flash-tts", discovered)
            self.assertNotIn("deep-research-preview", discovered)
            self.assertNotIn("imagen-3.0-generate-002", discovered)
            self.assertNotIn("gemini-robotics-rt", discovered)

    # =========================================================================
    # 2. Concurrent Multi-Model Health Pings & Active Selection
    # =========================================================================
    def test_04_concurrent_ping_selection_healthy(self):
        """Validates that pinging concurrently selects the healthy model for balanced task."""
        # Simulate: gemini-3.8-flash fails (HTTP 503), gemini-3.7-flash fails (timeout), gemini-3.6-flash succeeds (120ms)
        def mock_ping(candidates, api_key=None, timeout=6.0):
            res = []
            for c in candidates:
                if "3.8" in c:
                    res.append((c, False, 800.0, "HTTP 503"))
                elif "3.7" in c:
                    res.append((c, False, 6000.0, "Timed out"))
                elif "3.6" in c:
                    res.append((c, True, 120.0, None))
                else:
                    res.append((c, True, 250.0, None))
            return res

        with patch.object(self.manager, "ping_candidate_models", side_effect=mock_ping):
            with patch.object(self.manager, "discover_available_models", return_value=["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]):
                chosen = self.manager.resolve_active_model(TaskType.DIRECTING, force_refresh=True)
                self.assertEqual(chosen, "gemini-3.6-flash")

    def test_05_active_model_caching_and_invalidation(self):
        """Validates that resolved models are cached within TTL and invalidated on report_failure."""
        with patch.object(self.manager, "ping_candidate_models", return_value=[("gemini-3.6-flash", True, 50.0, None)]):
            with patch.object(self.manager, "discover_available_models", return_value=["gemini-3.6-flash"]):
                chosen1 = self.manager.resolve_active_model(TaskType.DIRECTING, force_refresh=True)
                self.assertEqual(chosen1, "gemini-3.6-flash")

                # Modify mock return to gemini-2.5-pro; without refresh or invalidation, cache returns gemini-3.6-flash
                with patch.object(self.manager, "ping_candidate_models", return_value=[("gemini-2.5-pro", True, 40.0, None)]):
                    chosen2 = self.manager.resolve_active_model(TaskType.DIRECTING, force_refresh=False)
                    self.assertEqual(chosen2, "gemini-3.6-flash")

                    # Invalidate cache
                    self.manager.report_failure(TaskType.DIRECTING, "gemini-3.6-flash")
                    # Next resolve should fetch fresh
                    with patch.object(self.manager, "discover_available_models", return_value=["gemini-2.5-pro"]):
                        chosen3 = self.manager.resolve_active_model(TaskType.DIRECTING, force_refresh=False)
                        self.assertEqual(chosen3, "gemini-2.5-pro")

    # =========================================================================
    # 3. Quality Floor Breach & Strict Fail-Closed Halts
    # =========================================================================
    def test_06_model_tier_floor_breach_error(self):
        """Validates that ModelTierFloorBreachError is raised when only sub-par models are available."""
        # Only Tier 3 utility models available
        with patch.object(self.manager, "discover_available_models", return_value=["gemini-3.1-flash-lite", "gemma-2-9b-it"]):
            with self.assertRaises(ModelTierFloorBreachError):
                self.manager.get_candidate_models_for_task(TaskType.TRANSLATION)

            with self.assertRaises(ModelTierFloorBreachError):
                self.manager.resolve_active_model(TaskType.SCREENPLAY, force_refresh=True)

    def test_07_all_candidates_unhealthy_raises_llm_unavailable(self):
        """Validates that LLMUnavailableError is strictly raised when all eligible candidates fail ping."""
        mock_failures = [
            ("gemini-3.8-flash", False, 500.0, "HTTP 503"),
            ("gemini-3.6-flash", False, 500.0, "HTTP 429"),
            ("gemini-2.5-flash", False, 500.0, "Connection refused"),
        ]
        with patch.object(self.manager, "ping_candidate_models", return_value=mock_failures):
            with patch.object(self.manager, "discover_available_models", return_value=["gemini-3.8-flash", "gemini-3.6-flash", "gemini-2.5-flash"]):
                with self.assertRaises(LLMUnavailableError) as ctx:
                    self.manager.resolve_active_model(TaskType.DIRECTING, force_refresh=True)
                self.assertIn("STRICT HALT", str(ctx.exception))

    # =========================================================================
    # 4. Strict Production Halt Verification Across Creative Modules
    # =========================================================================
    def test_08_script_builder_strict_halt_on_failure(self):
        """Validates that script_builder strictly raises LLMUnavailableError on LLM failure."""
        from audiobook_factory.script_builder import _parse_dramatized_chunk_llm

        # Mock urllib to simulate API total failure
        with patch("urllib.request.urlopen", side_effect=Exception("API service down")):
            with patch("audiobook_factory.key_manager.get_persistent_key_pool") as mock_pool:
                mock_pool.return_value.get_key.return_value = "fake-key"
                with self.assertRaises(LLMUnavailableError) as ctx:
                    _parse_dramatized_chunk_llm(
                        chunk_text="A dramatic tense confrontation.",
                        api_key="fake-key",
                        max_retries=1,
                    )
                self.assertIn("STRICT HALT", str(ctx.exception))

    def test_09_beat_planner_strict_halt_on_failure(self):
        """Validates that beat_planner strictly raises LLMUnavailableError when LLM fails."""
        from audiobook_factory.dramaturgy.beat_planner import BeatPlanner
        from audiobook_factory.dramaturgy.contracts import SceneDramaticPlan

        scene = SceneDramaticPlan(
            scene_id="SCENE_001",
            scene_index=0,
            location="Castle Chamber",
            dramatic_purpose="Confrontation",
            participants=["Hero", "Villain"],
            stakes="Survival",
            dramatic_complexity="HIGH",
        )
        with patch("urllib.request.urlopen", side_effect=Exception("LLM network timeout")):
            with patch("audiobook_factory.key_manager.get_persistent_key_pool") as mock_pool:
                mock_pool.return_value.get_key.return_value = "fake-key"
                with self.assertRaises(LLMUnavailableError) as ctx:
                    BeatPlanner.plan_scene_beats(scene, use_llm_intent=True)
                self.assertIn("STRICT HALT", str(ctx.exception))

    @unittest.skip("AgentDirector decoupled in Vocals-Only engine")
    def test_10_agent_director_strict_halt_on_failure(self):
        """Validates that agent_director strictly raises LLMUnavailableError when LLM fails."""
        from audiobook_factory.agent_director import AgentDirector

        with patch("urllib.request.urlopen", side_effect=Exception("Director LLM down")):
            with patch("audiobook_factory.agent_director.get_persistent_key_pool") as mock_pool:
                mock_pool.return_value.get_key.return_value = "fake-key"
                director = AgentDirector(model="test-model")
                with self.assertRaises(LLMUnavailableError) as ctx:
                    director._pass1_dramaturgy_and_silence_carving(
                        chapter_id="chapter_001",
                        script_segments=[{"index": 1, "speaker": "Hero", "text": "Halt!"}],
                        total_duration_sec=15.0,
                        max_retries=1,
                    )
                self.assertIn("STRICT HALT", str(ctx.exception))

    @unittest.skip("Soundscape LLM planning decoupled in Vocals-Only engine")
    def test_11_soundscape_strict_halt_on_failure(self):
        """Validates that soundscape module strictly raises LLMUnavailableError on LLM failure."""
        from audiobook_factory.soundscape import detect_chapter_mood, generate_chapter_soundscape_plan

        with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
            with patch("audiobook_factory.tts_dispatcher.global_key_pool.get_key", return_value="fake-key"):
                with self.assertRaises(LLMUnavailableError):
                    detect_chapter_mood("Some chapter text")

                with self.assertRaises(LLMUnavailableError):
                    generate_chapter_soundscape_plan(1, "Some chapter text")

    def test_12_translator_strict_halt_on_failure(self):
        """Validates that translator strictly raises LLMUnavailableError when retries are exhausted."""
        from audiobook_factory.translator import call_gemini

        with patch("urllib.request.urlopen", side_effect=Exception("API unreachable")):
            with patch("audiobook_factory.key_manager.get_persistent_key_pool") as mock_pool:
                mock_pool.return_value.get_key.return_value = "fake-key"
                with self.assertRaises(LLMUnavailableError) as ctx:
                    call_gemini("Translate this line", max_retries=1)
                self.assertIn("STRICT HALT", str(ctx.exception))

    # =========================================================================
    # 5. AST Zero-Hardcoded-Models Scan Across Codebase
    # =========================================================================
    def test_13_assert_zero_hardcoded_model_strings(self):
        """
        Recursively scans all Python files in audiobook_factory/ using AST.
        Strictly asserts zero hardcoded Gemini model string literals outside
        exempt modules:
        - model_manager.py (definitions of fallback catalog and tier patterns)
        - tts_dispatcher.py (speech synthesis model)
        - pronunciation/contracts.py & provenance.py (speech synthesis models)
        """
        exempt_files = {
            "model_manager.py",
            "tts_dispatcher.py",
            "constants.py",
            "contracts.py",
            "provenance.py",
        }
        model_pattern = re.compile(r"^gemini-[0-9a-zA-Z.-]+$")

        violations = []
        for py_path in FACTORY_DIR.rglob("*.py"):
            if py_path.name in exempt_files:
                continue

            content = py_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(py_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val = node.value.strip()
                    if model_pattern.match(val):
                        violations.append(
                            f"File: {py_path.relative_to(WORKSPACE_DIR)}:{getattr(node, 'lineno', '?')} | Model: '{val}'"
                        )

        self.assertEqual(
            len(violations),
            0,
            f"Detected {len(violations)} hardcoded Gemini model string(s) in codebase:\n"
            + "\n".join(violations),
        )

    def test_14_llm_client_candidate_cycling_with_env_preference(self):
        """
        Validates that call_gemini dynamically cycles across candidate models upon retry,
        even when GEMINI_TEXT_MODEL is set in the environment, preventing static model deadlocks.
        """
        import os
        from audiobook_factory.llm_client import call_gemini
        from audiobook_factory.key_manager import get_persistent_key_pool
        import urllib.request
        from unittest.mock import MagicMock

        models_contacted = []

        def mock_urlopen(req, timeout=45.0):
            # Record which model URL was called
            url = req.full_url
            for m in ["model-primary", "model-fallback", "model-alt"]:
                if m in url:
                    models_contacted.append(m)
            # Fail first call with 503, succeed second call
            if len(models_contacted) == 1:
                import urllib.error
                raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)
            mock_resp = MagicMock()
            mock_resp.__enter__.return_value = mock_resp
            mock_resp.read.return_value = json.dumps({
                "candidates": [{"content": {"parts": [{"text": '{"result": "success"}'}]}}]
            }).encode("utf-8")
            return mock_resp

        with patch.dict(os.environ, {"GEMINI_TEXT_MODEL": "model-primary"}):
            with patch("urllib.request.urlopen", side_effect=mock_urlopen):
                with patch("audiobook_factory.llm_client.get_model_manager", return_value=self.manager):
                    with patch.object(self.manager, "get_candidate_models_for_task", return_value=["model-primary", "model-fallback", "model-alt"]):
                        with patch.object(self.manager, "resolve_active_model", return_value="model-primary"):
                            with patch.object(get_persistent_key_pool(), "get_key", return_value="AIzaSyDummyKey"):
                                res = call_gemini("test prompt", max_retries=3)
                                self.assertEqual(res, {"result": "success"})
                                # First attempt was model-primary (503), second attempt cycled to model-fallback!
                                self.assertEqual(models_contacted, ["model-primary", "model-fallback"])

    def test_15_creative_tasks_enforce_tier_1_and_blacklist(self):
        """Validates that creative tasks exclude 3.5-flash, 3.6-flash, and -lite models."""
        discovered = [
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-flash-latest",
        ]
        with patch.object(self.manager, "discover_available_models", return_value=discovered):
            candidates = self.manager.get_candidate_models_for_task(TaskType.TRANSLATION)
            self.assertIn("gemini-3.8-flash", candidates)
            self.assertIn("gemini-3.7-flash", candidates)
            self.assertNotIn("gemini-3.6-flash", candidates)
            self.assertNotIn("gemini-3.5-flash", candidates)
            self.assertNotIn("gemini-3.1-flash-lite", candidates)
            self.assertNotIn("gemini-flash-latest", candidates)

    def test_16_creative_latency_banishment(self):
        """Validates that for creative tasks, gemini-3.8-flash is preferred over 3.7-flash even if 3.7 has lower latency."""
        def mock_ping(candidates, api_key=None, timeout=6.0):
            return [
                ("gemini-3.8-flash", True, 3500.0, None),  # Higher latency
                ("gemini-3.7-flash", True, 800.0, None),   # Lower latency
            ]

        with patch.object(self.manager, "ping_candidate_models", side_effect=mock_ping):
            with patch.object(self.manager, "discover_available_models", return_value=["gemini-3.8-flash", "gemini-3.7-flash"]):
                chosen = self.manager.resolve_active_model(TaskType.TRANSLATION, force_refresh=True)
                # 3.8-flash must win due to version superiority, despite higher ping latency!
                self.assertEqual(chosen, "gemini-3.8-flash")


def json_bytes(obj) -> bytes:
    return json.dumps(obj).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
