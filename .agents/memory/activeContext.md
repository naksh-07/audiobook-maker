<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State
- **Branch**: `main` (PR #1 `book_extractor` + PR #2 & PR #3 `translator` MERGED TO `main`, commit `2ff94a6`).
- **Forensic Ingestion Engine (Pillar 1, PR #1)**:
  - Canonical `CanonicalBook` AST (`canonical/book.json`), structural EPUB/PDF parsers, Meso-tier 12k splitting, fail-closed quality gates.
- **Literary Translation Intelligence Engine (Pillar 2, PR #3)**:
  - Canonical `BookBible` store with legacy `glossary.json` projection & decoupled `terminology_variants`.
  - Contextual Hindustani register ("Aate mein Namak jitni Urdu") & soft $\pm 0.75$ heuristic intensity model ("Nothing Above Source").
  - Narrative transition-driven Scene Segmentation, rolling `NarrativeContinuityState`, & Persistent Source Semantic Map.
  - Multi-Pass Independent Evaluators (Gates T0–T11) with deterministic pre-validation & Tiered Self-Healing Repair.
  - Chapter 9 Benchmark Standard (`audiobooks/standards/`).
- **Repo Hygiene & Novel-Agnostic Hardening**:
  - Independent audit remediated (UNCONDITIONAL PASS); multi-script Devanagari/Latin zero-hardcoding contract (`tests/test_zero_hardcoding_contracts.py`).
  - `audiobooks/projects/` and `projects/` gitignored; 37 one-off `witcher1` scripts purged; 319/319 tests passing.
- **Quality Standards**: EBU R128 (-19 LUFS), zero hardcoding, fail-closed gates with provenance ledgering.
