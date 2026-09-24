<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State
- **Forensic Document Ingestion Engine (Pillar 1 Upgrade):** COMPLETE & 100% GREEN (305 passed tests).
  - Strongly typed `CanonicalBook` AST (`canonical/book.json`) with block-level provenance (`SourceProvenance`).
  - Sacred raw source preservation (`raw/` archive with SHA256 checksums).
  - Single-pass structural EPUB parser (DOM preservation, TOC/Nav anchor precision, 2x faster).
  - Lightweight layout-aware PDF analyzer (density heuristics, multi-column, repeated header/footer stripping, selective escalation).
  - Non-destructive normalization & multi-tier chapter detection with 12k-word Meso-tier semantic splitting.
  - Independent Quality Gate (`PASS`/`WARN`/`REVIEW`) with fail-closed protection and `--force-gate` override.
  - 100% backward compatibility for downstream stages (`extracted/chapter_XXX.md`).
- **Production Pipelines (Witcher Ch 10-13):** COMPLETE & CERTIFIED.
  - Chapters 10-13 translated, screenplay-gated, CUDA forced-aligned, and mastered to EBU R128 (-19 LUFS).
- **Standalone Pipeline (Two-System Lean Runner):** COMPLETE & TESTED.
  - Offline screenplay parser + Gemini 3.8 Flash TTS integration with configurable director style.
- **Status:** All 305 tests passing, zero regressions, ready to merge `book_extractor`.
