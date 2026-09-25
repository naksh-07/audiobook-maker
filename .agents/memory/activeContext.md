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
- **World + Character Memory 2.0 (`audiobook_factory/translation/memory/`)**:
  - Event-driven state delta engine (`StoryEvent`, `TemporalMode`, `SceneChangeDetector`, `EventExtractor`, `StateDeltaEngine`) with transitive attacker/victim disambiguation, intra-scene movement tracking, and LLM vs. deterministic event deduplication.
  - Dynamic `CharacterState` + `CharacterArcState` & strict epistemic isolation (`KNOWN`, `SUSPECTED`, `FALSE_BELIEF`, `UNKNOWN`, `DISPROVEN`) with strict `known_by` membership, scoped `DISPROVEN`, and 100-chapter token budget scaling (`<= 800` tokens).
  - Evidence-backed `DynamicRelationshipState` with bounded contextual priors & Hindi register/pronoun evolution (`aap` $\rightarrow$ `tum` $\rightarrow$ `tu`).
  - Dynamic `WorldState`, 7-class `MemoryValidator` contradiction guardrails (rejected ghost events isolated in `rejected_events`), Selective 7-Tier + Narrative Salience `MemoryRetriever`, and versioned `MemoryStore`.
  - Wired end-to-end into `translation/orchestrator.py` (with `TranslationDecisionMemory`), `translator.py` (strict READ-before-translate / COMMIT-after-translate), `script_builder.py`, `contracts.py`, `tts_dispatcher.py`, `certification.py`, and `orchestrator.py` (nested `acting.delivery_style` & persisted script enrichment).
- **Repo Hygiene & Verification**:
  - Multi-script Devanagari/Latin zero-hardcoding contract (`tests/test_zero_hardcoding_contracts.py`); **340/340 tests passing** (incl. 10-chapter Golden Novel & 100-chapter 600-event audit stress tests).
- **Quality Standards**: EBU R128 (-19 LUFS), zero hardcoding, fail-closed gates with provenance ledgering.
