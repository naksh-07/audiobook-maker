<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State
- **Branch**: `main` (Stage 3 Screenplay / Dramatic Adaptation Sprint COMPLETE).
- **Test Suite Status**: 408/408 tests 100% green (368 baseline + 40 Stage 3 dramaturgy tests).
- **Stage 3 Deliverables**:
  - Dramaturgy Engine (`audiobook_factory/dramaturgy/`): contracts, scene analyzer, beat planner, performance bible, dramatic validator.
  - ScreenplaySegment extensions with safe defaults & 100% backward compatibility.
  - Beat-aligned chunk slicing (`slice_chapter_by_beats`) eliminating 1200w arbitrary split bottleneck.
  - Dedicated Gate 2.5 (`audit_gate2_5_dramatic_fidelity`) fail-closed verification.
  - 10 golden benchmark scenes + *"Don't touch it."* identical-dialogue multidimensional delivery proof.
  - AST zero-hardcoding compliance: 100% verified.
- **Quality Standards**: EBU R128 (-19 LUFS), zero hardcoding, fail-closed gates with provenance ledgering.
