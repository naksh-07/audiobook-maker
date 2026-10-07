<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Pure Vocals-Only Studio Audiobook Production Engine

## Milestone: Universal Novel-Agnostic Engine & Audit Remediation
- **Status**: PRODUCTION CERTIFIED & 100% GREEN (813+ tests passing, 0 failures, 100% novel-agnostic).
- **Universal Novel-Agnostic Engine & DeepSearch Grounding**:
  - Purged all single-novel hardcoded titles, franchise signatures, character rosters, and branch shortcuts.
  - Fully enabled Antigravity Google Search Grounding (`NovelDeepSearchEngine`) for any novel dynamically.
  - 100% pass on `test_zero_hardcoding_contracts.py` across all factory modules.
- **Audible Flow Standard**:
  - Room 3: Narrator carries continuous narrative prose; character dialogue isolated without artificial quote-slicing or inverted turn swaps; zero synthetic foley/actions.
  - Room 4: Clean neural delivery without artificial asetrate pitch warping or telephone filters.
  - Room 5: Broadcast EBU R128 (-19.0 LUFS, -1.5 dBTP), organic TPDF room tone dither (~ -72 dBFS), syntax-aware pauses (180ms/380ms/600ms).
- **CLI Commands**:
  `audiobook_cli.py [extract|translate|script|synthesize|master|package|produce|auto|audit|audit-book]`
- **Active Sprint - Multi-Expert Audit Remediation [RESOLVED & VERIFIED]**:
  - **Zero-Hardcoding & Lore Purge**: Purged Witcher signs/monsters from `acoustic_bus_matrix.py` (added modern/sci-fi categories); generalized `voice_casting_catalog.json` archetypes; upgraded Gate 1 to dynamically query `VoiceCatalog`; unlocked full 215 English voice pool; dynamic gendered fallback in `dispatcher.py`.
  - **Creative Autonomy & LLM Integrity**: Preserved nuanced acting cues (`[ironic smirk]`, `[hesitates]`) into `speechMetadata.style`; constrained split-quote stitching to $\le 6$ words with explicit speech verbs, preserving authentic chronological narrative blocking; protected in-story bilingual/code-switching dialogue.
  - **Runtime Robustness & Audio Fixes**: Uniform 2-channel stereo mastering under `spatial_staging=True`, eradicating FFmpeg mono/stereo concat crashes; safe `{"gender": null}` parsing in `character_caster.py`; sliced `raw_pcm[:sample_count * 2]` in `struct.unpack`, eradicating odd-byte buffer crashes in `gemini.py`; cleaned dangling imports in `director.py`. 7 dedicated audit tests passing.
