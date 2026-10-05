<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Maker Production Engine & Hollywood Directing Suite

## Milestone: Stage 4.5 Halt & Batch Download-on-Demand Staging Gate (COMPLETE)
- **Status**: COMPLETE & VERIFIED (20/20 tests passing, 100% green).
- **Architectural Deliverables**:
  1. **Strict Semantic-First Retrieval** (`search.py`): Eliminated `is_downloaded DESC` bias; FTS5 BM25 match quality strictly dominates. Mismatched local files (e.g. handsaws for footsteps) completely eradicated.
  2. **Stage 4.5 Pre-Mix Staging Gate** (`resolver.py` & `downloader.py`): Halts pipeline before audio mix if virtual assets are spotted, downloads in parallel (4 workers) with real-time terminal progress, verifies via `AudioVerificationGate`, and enforces strict fail-closed protection.
  3. **SonicIntelligenceBridge Integration** (`multi_agent_director.py`): Wired Devanagari/Hindi taxonomy normalizer and query expansion into all foley and music cue resolution.
  4. **Catalog Taxonomy Grounding** (`micro_foley_agent.py`, `music_supervisor_agent.py`): Injected verified action verbs, materials, and music timbres into agent system prompts to eliminate hallucinated words.
  5. **Orchestrator & CLI Upgrades** (`orchestrator.py`, `audiobook_cli.py`): Auto-staged before FFmpeg in Step 5; added standalone `stage-sounds` CLI command.
  6. **Test Certification**: `tests/test_download_on_demand_and_staging.py` 7/7 PASSED; full regression suite 20/20 PASSED. Zero remote push maintained.
