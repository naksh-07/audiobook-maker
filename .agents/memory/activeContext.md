<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Pure Vocals-Only Studio Audiobook Production Engine

## Milestone: Studio Audio & Performance Architecture Upgrade (v5.0)
- **Status**: 100% IMPLEMENTED & TEST VERIFIED.
- **Actor Overacting Elimination**:
  - Directing Phrasing: Stripped theatrical `"acting to..."` directives; injected physical vocal anchors and universal anti-theatrical anchor `"understated natural dialogue (never theatrical)"`.
  - Narrator Transparency Invariant: Narrator strictly locked to `"calm, steady, articulate, measured audiobook delivery"` (temp 0.32, zero melodrama).
  - Temperature Clamping: Clamped to `0.30 - 0.52` across `constraint_resolver.py`, `tts_adapter.py`, and `gemini.py` (preventing pitch instability, slurring, and theatrical screeching).
  - Judicial Critic Alignment: `TakeAuditionCritic` re-aligned to prioritize grounded human realism over histrionics.
- **Audio Post-Processing Overhaul**:
  - Eliminated WSOLA `atempo` in `dispatcher.py`: Neural audio maintains pristine vocal formants and phase coherence.
  - Eliminated Destructive De-Esser in `mastering.py`: Preserves crisp Hindi dental & aspirated consonants (स, श, छ, थ, ध).
  - Two-Pass Measured Linear Loudnorm in `concatenate_and_master_chapter`: Zero dynamic breathing or pause pumping.
- **Zero-Hardcoding Contract & Agnostic Invariant**:
  - Replaced franchise-specific tokens in prompt instructions (`dialogue_parser.py`, `translator.py`, `entity_discovery.py`, `draft_translator.py`) with universal generic fantasy exemplars (100% PASS across 98 regression tests).
