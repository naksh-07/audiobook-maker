<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-studio -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Studio Antigravity Plugin & Studio Engine (v6.0)

## Milestone: Phase 1 & 2 — Core Platform & Persistence (v6.0-ENTERPRISE-DAG)
- **Status**: 100% IMPLEMENTED & VERIFIED (27/27 Core tests + 142 regression tests green).
- **Core Platform (`audio_platform_core`)**:
  - `core/key_manager.py`: 120+ KeyPool SQLite rotation, cool-down, token-bucket concurrency.
  - `core/model_manager.py`: Tier-1 Flagship routing with mandatory `BLOCK_NONE` safety filters.
  - `core/cache/take_bank.py`: Content-addressed SHA-256 audio cache with LRU disk pruning.
  - `core/dialogue_editorial/`: DE-01 - DE-07 DSP (Hann micro-fades 12ms/18ms, -52 dBFS trimming, 40Hz Butterworth highpass) & zero-cost timeline stem stitcher.
  - `core/mastering/`: Two-Pass Measured Linear Loudnorm (-19.0 LUFS ±0.5, -1.5 dBTP) & M4B packager with FFMETADATA1 chapter markers and embedded cover art.
- **Contracts & Ledger**: Pydantic v2 schemas (`schema_version: "2.0"`) & SQLite WAL `pipeline_ledger.db`.

## Production Milestone: Chapter 3 Mastered (`Sword of Destiny`)
- **Status**: 100% MASTERED & VERIFIED (-19.1 LUFS, -4.0 dBFS True Peak, 5.8 LU LRA, 129 chunks).

## Antigravity Studio Plugin & UI Extension
- **Live Extension**: Registered at `~/.gemini/config/plugins/audiobook-studio/` (`@audiobook-director`, `audiobook-studio` skill, Stitch-grade sidecar panel).
