<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Overloaded LLM Deconstruction & Anti-Fake Engine Certified

## Live Sprint State: Multi-Agent Decoupling & Anti-Hammering Key Pool Deployed
- **Status**: COMPLETE & VERIFIED (170+ targeted unit & regression tests passing 100%).
- **Key Architectures Delivered**:
  1. **Centralized Non-Hammering Client (`audiobook_factory/llm_client.py`)**:
     - Centralized `call_gemini` backed by `PersistentKeyPool.get_key(service="text")`.
     - 100+ rotating API keys with true round-robin scheduling (`ORDER BY last_used ASC NULLS FIRST`).
     - Pacing jitter (100–350ms) to prevent server hammering; categorized error classification (`503`, `429`, `400`).
     - Permissive `BLOCK_NONE` thresholds across all safety categories for unfiltered literary drama.
     - Fail-closed typed `LLMUnavailableError` with zero silent degraded fallbacks.
  2. **Two-Pass Decoupled Screenplay Parser (`script_builder.py`)**:
     - *Pass 1*: Pure dialogue isolation, canonical character roster attribution, clean text, neural vocal tags.
     - *Pass 2*: Stanislavski subtext, actioning verbs, dynamic headroom intensity, delivery styles, spatial panning.
  3. **Translation Pre-Production & Entity Discovery (`translator.py`, `entity_discovery.py`)**:
     - `generate_book_glossary` deconstructed into 3 parallel specialist agents (Character, Sociolect, Lore).
     - Context-Calibrated Scene Prompt Router (`COMBAT`, `INTIMATE`, `DIALOGUE`, `LORE`).
  4. **Dramaturgy & Sound Design Heuristic Purge (`beat_planner.py`, `agent_director.py`)**:
     - Purged canned Stanislavski templates (`underlying_desire`, `core_fear`, `strategy`); authentic LLM intent only.
     - Purged 4-word domestic Foley regex guessing (`door`, `gate`, `cup`, `tea`); cues strictly from `SoundSpotter`.
  5. **Adversarial Gate 1 Hardening (`gate_auditor.py`)**:
     - Deconstructed anti-censorship audit into 3 parallel specialist checkers (Profanity, Combat, Intimacy).
     - Fail-closed in production if audit is bypassed or fails.
- **Verification Highlights**:
  - `tests/dramaturgy/`: 52/52 PASS.
  - `tests/translation/`: 56/56 PASS.
  - `tests/test_model_manager_and_strict_halt.py`: 13/13 PASS (AST confirms 0 hardcoded models).
  - Screenplay, Gate Auditor, Sound Spotter, Caster suites: 100% green.
