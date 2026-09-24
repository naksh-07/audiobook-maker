<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State
- **Branch**: `translator` (Active Sprint: Literary Translation Intelligence Engine).
- **Core Pillars**:
  - Book Bible canonical store with legacy `glossary.json` projection.
  - Contextual Hindustani register ("Aate mein Namak jitni Urdu" - no arbitrary quota).
  - Narrative transition-driven Scene Segmentation & Structured Narrative State.
  - Stable Persistent Source Semantic Map per scene/chapter.
  - Multi-Pass Dedicated Independent Evaluators (Gates T0-T11) with deterministic pre-validation.
  - Soft ±0.75 intensity evaluation heuristic ("Nothing Above Source", no universal hard rejection).
  - Tiered Self-Healing Repair (max 2 paragraph rewrites -> 1 scene retranslation).
  - Non-destructive Witcher Chapter 9 Benchmark Milestone (`chapter_009_hi.new.md` vs canonical).
- **Sprint Status**:
  - Independent forensic audit completed; all 4 findings remediated (UNCONDITIONAL PASS).
  - Leaky entity stopwords hardened; Devanagari multi-script zero-hardcoding contract enforced.
  - Terminology variants decoupled into Book Bible; anachronisms synced.
  - Standards package in `audiobooks/standards/` fully verified; Gate T5 false-positive warnings reduced to 0.
  - `audiobooks/projects/` and `projects/` added to `.gitignore`; 37 one-off `witcher1` scripts purged; engine & tests 100% novel-agnostic.
- **Quality Standards**: EBU R128 (-19 LUFS), zero hardcoding, fail-closed gates with provenance ledgering.
