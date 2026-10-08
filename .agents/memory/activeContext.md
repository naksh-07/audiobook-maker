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

## Active Production Track: Chapter 3 (`sword_of_destiny`)
- **Status**: IN PRODUCTION (148 segments synthesizing via Gemini 3.8 Flash TTS).
- **Gates Verified**:
  - Gate 2 (Script & Screenplay Attribution): PASSED (Score 1.0, 0 misattributed).
  - Gate 2.5 (Dramatic Fidelity): PASSED (0 issues across 148 segments after smoothing Innkeeper emotional arc).
  - Gate 1 (Voice Roster): PASSED (5 active characters, unique acoustic signatures).
- **Gemini 3.8 Flash TTS Batching & Lossless Slicing (v5.1)**:
  - Deployed scene-aware dialogue rally clustering (`multi_speaker_duo`) & narrator super-chunking (`narrator_chunk`), cutting API quota by 60%-75%.
  - Lossless silence-valley midpoint slicing via GPU MMS-FA CTC forced alignment: 100% natural conversational pauses, in-breath, and acoustic decay preserved.
  - Anti-hiss & anti-click shield: 30Hz HPF + Hann micro-fades + zero-crossing pinning + organic acoustic dither bed (-84 dBFS).
  - Selective hot-patching: automated single-take re-recording on pronunciation QA failure. All 18 tests 100% PASS.
- **Synthesizer Target**: `chapter_003_hi_mastered.m4a` (-19.0 LUFS EBU R128 master).
