<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State
- **Branch**: `main` (Translation Hardening v2.0 & Dual Expert Audit COMPLETE, 355/355 tests passing).
- **Forensic Ingestion Engine (Pillar 1 Upgrades Complete & Verified)**:
  - Canonical `CanonicalBook` AST (`canonical/book.json`), non-destructive normalization (sacred `raw_text` vs. speech `normalized_text`), fail-closed Gate 0.1.
  - `PDFLayoutReconstructor` recursive XY-cut multi-column reading order; `_PDFPageSpanRecord` end-to-end page provenance.
  - Multi-signal `PDFQualityAnalyzer` Gemini escalation gate; explicit `literary_chapter` vs `production_chunk` distinction.
- **Literary Translation Hardening v2.0 (Pillar 2 Hardening Complete & Verified)**:
  - Fix 1: `SourceSemanticMap` v2.0 with slot extraction (WHO -> DID WHAT -> TO WHOM -> OBJECT -> NEGATION -> TIME/LOCATION).
  - Fix 2: Target Semantic Representation (`TargetSemanticProposition`, `TargetSemanticMap`) & `SemanticAligner` with paragraph-level negation auditing.
  - Fix 3: Strict 4-tier Certification (`PASS`, `PASS_WITH_WARNINGS`, `REVIEW_REQUIRED`, `BLOCKED`) with fail-closed gate halting.
  - Fix 4: Calibrated 7D `LiteraryIntensityVector` wired into pipeline & Gate `T8` ("Nothing Above Source").
  - Fix 5: Multi-tier `TieredRepairEngine` orchestration (Level 1 deterministic -> Level 2 paragraph LLM [max 2] -> Level 3 scene [max 1]).
  - Fix 6: Sanitizer separation: `sanitizer.py` non-destructive by default; calque fixing moved to repair engine.
  - Fix 7: 11-field `TranslationProvenanceTracker` sealing + `translate_book_project` defaulted to `IntelligentTranslationPipeline`.
- **World + Character Memory 2.0 Hardening & Dual Expert Audit (COMPLETE & VERIFIED)**:
  - Hard Canon separation (zero BookBible writebacks, evolving dynamic state strictly in MemoryStore).
  - Persistence safety (fail-closed MemoryPersistenceError, atomic write/rename, schema & integrity verified .bak recovery).
  - Deep snapshot rollback (`_create_snapshot` / `_restore_snapshot`) on scene commit failure.
  - Epistemic isolation & Strict Event Atomicity (conflicting event companion deltas purged, disproven beliefs exempted).
  - Multi-script Director Supremacy (Devanagari/Latin parentheticals, nested acting & vocal tags inviolate).
- **Repo Hygiene & Verification**:
  - Multi-script Devanagari/Latin contracts; **368/368 tests passing** (17 subtests passing).
- **Quality Standards**: EBU R128 (-19 LUFS), zero hardcoding, fail-closed gates with provenance ledgering.
