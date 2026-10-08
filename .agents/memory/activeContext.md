<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-studio -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Studio Antigravity Plugin & Studio Engine (v6.0)

## Milestone: Phase 1 - 5 — Core Platform, Rooms, CLI & DAG Engine (v6.0-ENTERPRISE-DAG)
- **Status**: 100% IMPLEMENTED & VERIFIED (37/37 Core/Room/CLI/DAG tests + 142 regression tests green = 179/179 tests).
- **DAG Orchestrator & Diff Engine (`audiobook_factory/dag/`)**:
  - `diff_reconciler.py`: Incremental SHA-256 contract diffing across rooms, zero-cost clean stage skipping.
  - `orchestrator.py`: Multi-room automated scheduler (Room 1 -> 2 -> 3 -> 4 -> 5 -> Package) with SQLite WAL checkpoints.
- **Modular CLI Suite (`audiobook_factory/cli/`)**: Standalone `ingest`, `translate`, `screenplay`, `synth`, `master`, `package`, `doctor`.
- **Contracts & Ledger**: Pydantic v2 schemas (`schema_version: "2.0"`) & SQLite WAL `pipeline_ledger.db`.

## Production Milestone: Chapter 3 Mastered (`Sword of Destiny`)
- **Status**: 100% MASTERED & VERIFIED (-19.1 LUFS, -4.0 dBFS True Peak, 5.8 LU LRA, 129 chunks).

## Antigravity Studio Plugin & UI Extension
- **Live Extension**: Registered at `~/.gemini/config/plugins/audiobook-studio/` (`@audiobook-director`, `audiobook-studio` skill, Stitch-grade sidecar panel).
