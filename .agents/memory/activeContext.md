<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Dynamic Model Intelligence & Strict Production Halt Enforced

## Live Sprint State: Zero Hardcoded Models & Fail-Closed Halts
- **Status**: COMPLETE & VERIFIED (13/13 New Tests Passed, 4/4 Zero Hardcoding Contracts Passed).
- **Core Architecture (`ModelManager`)**:
  - Live Gemini API model discovery with semantic capability tiers (Tier 1 Flagship, Tier 2 Balanced, Tier 3 Utility).
  - Non-general model exclusion (`-tts`, `deep-research`, `robotics`, `lyria`, `computer-use`, etc.).
  - Concurrent 2-3 candidate health pings via `ThreadPoolExecutor` (latency & availability evaluated simultaneously).
  - Minimum quality floor gates (`TASK_MINIMUM_TIERS`) raising `ModelTierFloorBreachError`.
  - Fail-closed halts (`LLMUnavailableError`): zero silent script fallbacks in `script_builder`, `beat_planner`, `agent_director`, `soundscape`, `translator`.
- **Zero Hardcoding Invariant**:
  - AST verification confirms zero hardcoded model strings in `audiobook_factory/` (strictly exempting TTS dispatcher & pronunciation contracts).
- **Test Certification**:
  - `tests/test_model_manager_and_strict_halt.py`: 13/13 OK.
  - `tests/test_zero_hardcoding_contracts.py`: 4/4 OK.
