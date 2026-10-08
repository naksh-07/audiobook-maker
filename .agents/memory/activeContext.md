<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-studio -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Studio Antigravity Plugin & Studio Engine (v6.0)

## Milestone: Phase 1, 2 & 3 — Core Platform & Standalone Rooms (v6.0-ENTERPRISE-DAG)
- **Status**: 100% IMPLEMENTED & VERIFIED (32/32 Core/Room tests + 142 regression tests green = 174/174 tests).
- **Standalone 5-Room Architecture (`audiobook_factory/rooms/`)**:
  - `room1_ingest`: Forensic source parsing (EPUB/PDF/TXT), AST monotonicity & Gate 0.1 audit.
  - `room2_translate`: 4-Agent translation collective, surgical beat patching & Gate 1.0 audit.
  - `room3_screenplay`: 4D acoustic formants, 0% Anti-Swap inversion & Gate 2.0 audit.
  - `room4_synth`: TakeBank SHA-256 caching, DE-01 - DE-07 DSP stem assembly & Gate 4.0 audit.
  - `room5_master`: Two-Pass Linear Loudnorm (-19.0 LUFS, -1.5 dBTP), Gate 5.0 audit & M4B packager.
- **Contracts & Ledger**: Pydantic v2 schemas (`schema_version: "2.0"`) & SQLite WAL `pipeline_ledger.db`.

## Production Milestone: Chapter 3 Mastered (`Sword of Destiny`)
- **Status**: 100% MASTERED & VERIFIED (-19.1 LUFS, -4.0 dBFS True Peak, 5.8 LU LRA, 129 chunks).

## Antigravity Studio Plugin & UI Extension
- **Live Extension**: Registered at `~/.gemini/config/plugins/audiobook-studio/` (`@audiobook-director`, `audiobook-studio` skill, Stitch-grade sidecar panel).
