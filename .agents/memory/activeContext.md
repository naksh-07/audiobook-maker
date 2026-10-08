<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-studio -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Studio Antigravity Plugin & Studio Engine (v6.0)

## Milestone: Phase 1 — Contracts & Persistence Layer (v6.0-ENTERPRISE-DAG)
- **Status**: 100% IMPLEMENTED & VERIFIED (18/18 Phase 1 tests + 142 regression tests green).
- **Boundary Contracts**: Strongly-typed Pydantic v2 schemas (`schema_version: "2.0"`) with deterministic SHA-256 canonical hashing across all 5 rooms:
  - `ingestion.py` (RawBookManifest, RawChapterRecord, RawSentenceRecord)
  - `lore.py` (CharacterDossier, BookBible, CastLock)
  - `translation.py` (TranslatedSentenceRecord, TranslationBeatRecord, TranslationManifest)
  - `screenplay.py` (SegmentProvenance, ScreenplaySegment, ScreenplayScript)
  - `editorial.py` (SegmentTakeMetadata, TimelineCueRecord, TimelineLedger, ChapterDialogueManifest)
  - `mastering.py` (LoudnessComplianceReport, MasterArtifact, ChapterMarker, ContainerM4BManifest)
  - `ledger.py` (ProjectMetadataRecord, ChapterStageRecord, StageArtifactRecord, SegmentTakeCacheRecord, GateAuditRecord)
- **Persistence Layer**: `audiobook_factory/core/cache/ledger.py` with SQLite WAL mode (`pipeline_ledger.db`), cascading foreign keys, performance indexes, and full CRUD for project metadata, stage status, artifact registry, TakeBank cache, and gate audits.

## Production Milestone: Chapter 3 Mastered (`Sword of Destiny`)
- **Status**: 100% MASTERED & VERIFIED (-19.1 LUFS, -4.0 dBFS True Peak, 5.8 LU LRA, 129 chunks).

## Antigravity Studio Plugin & UI Extension
- **Live Extension**: Registered at `~/.gemini/config/plugins/audiobook-studio/` (`@audiobook-director`, `audiobook-studio` skill, Stitch-grade sidecar panel).
