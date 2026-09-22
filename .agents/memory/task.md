# Task List: Agentic/MCP Refactor

- [x] **Phase 1: Architecture & Supervisor Setup**
  - [x] Implement Supervisor Agent script to replace linear `orchestrator.py`
  - [x] Add graceful halt/checkpointing for `AllKeysExhaustedTodayError`

- [x] **Phase 2: Data Healing & Prompt Refactor**
  - [x] Remove regex JSON parsing from `script_builder.py`
  - [x] Implement LLM-based truncation recovery loop

- [x] **Phase 3: FFmpeg MCP & Audio Engineer**
  - [x] Remove `ACOUSTIC_PRESETS` from `foley_miner.py` (Delegated to agent logic)
  - [x] Create `ffmpeg_agent.py` to handle dynamic FFmpeg graph generation & execution
  - [x] Plumb existing semantic metadata (environment, emotion) into the agent's context

- [x] **Phase 4: Semantic Extraction**
  - [x] Refactor `extractor.py` to use semantic chunking instead of arbitrary char limits

- [/] **Phase 5: Testing & Validation**
  - [ ] Test JSON recovery on simulated truncated data
  - [ ] Verify Audio Engineer generates valid FFmpeg syntax
  - [ ] Test key exhaustion halt mechanism
