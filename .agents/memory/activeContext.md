<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Pure Vocals-Only Studio Audiobook Production Engine

## Milestone: Universal Novel-Agnostic Engine & Audible Flow Transformation
- **Status**: PRODUCTION CERTIFIED & 100% GREEN (775 tests passing, 0 failures, 100% novel-agnostic).
- **Universal Novel-Agnostic Engine & DeepSearch Grounding**:
  - Purged all single-novel hardcoded titles, franchise signatures, character rosters, and branch shortcuts from `project_classifier.py`, `novel_deepsearch.py`, `book_dna_agent.py`, `performance/golden_suite.py`, `performance/calibration.py`, and `gates/llm_judge.py`.
  - Fully enabled Antigravity Google Search Grounding (`NovelDeepSearchEngine`) for any novel dynamically.
  - Eliminated dishonest test exclusions (`exclude_dirs = {"performance", "pronunciation"}`) from `test_zero_hardcoding_contracts.py`; suite now passes 100% across all factory files.
- **Audible Flow Standard (Option A)**:
  - **Room 3 (Audible Flow Scripting)**: Narrator carries continuous narrative prose & dialogue tags (*"उसने कहा"*); character dialogue isolated without artificial quote-slicing or inverted turn swaps; zero synthetic foley/actions.
  - **Room 4 (Clean Neural DSP)**: Neutral natural Gemini voice delivery without artificial asetrate pitch shifting or harsh telephone low-pass filters.
  - **Room 5 (Studio Vocal Mastering)**: Broadcast EBU R128 (-19.0 LUFS, -1.5 dBTP), organic TPDF room tone dither (~ -72 dBFS), syntax-aware pauses (180ms/380ms/600ms), and Phantom Center default.
  - **Permissive Safety**: Verified `BLOCK_NONE` safety threshold configured across all generative LLM & TTS pipelines.
- **CLI Commands**:
  `audiobook_cli.py [extract|translate|script|synthesize|master|package|produce|auto|audit|audit-book]`
- **Active Sprint - Chapter 2 Pilot Remediation**:
  - **Issue 1 (Translation & Lexicon Hygiene) [RESOLVED & VERIFIED]**:
    - Purged seed lexicon contamination; 100% dynamic novel-agnostic lexicon.
    - Fixed BookBible category routing (locations, creatures, titles partitioned).
    - Shifted persona to Netflix/HBO Dialogue Adapter with 4-Tier Cognitive Semantic Register Ladder (zero hardcoded word replacements).
    - **Universal Idiomatic Transposition ('Pinch of Salt') Framework**: Category A (Universal Spoken Idioms) vs Category B (Banned Village Parody) implemented across `DraftTranslator`, `CadenceSpecialist`, `IdiomDramaturge`, and `AdvisoryLexiconDB`. Live verified on Gemini Flash (*"लिख के ले लो"*, *"मौत के मुँह में कूदना"*, *"टांग अड़ाना"*, *"खाल उधेड़ना"*). 16 unit tests passing.
  - **Issue 2 (Screenplay Attribution & Split Quotes) [RESOLVED & VERIFIED]**:
    - Purged destructive `speaker = last_active_character` theft in `screenplay_cleaner.py`.
    - Added bidirectional article-stripped alias resolution (`"the stranger"` <-> `"stranger"` -> canonical character).
    - Implemented deterministic `stitch_split_dialogue_turns`: unifies split thoughts around narrative tags (< 35 words), pre-positions narration with em-dash (`—`), eliminating mid-sentence audio stutter.
    - Updated `dialogue_parser.py` and `DialogueAttributionAuditor` with conversational turn polarity (question-answer interlocutor tracking) and speech tag scrubbing.
    - Chapter 2 screenplay verified: 81 choppy micro-clips collapsed to 68 unified beats with zero line theft. 24 unit tests passing.
  - **Issue 3 (Voice Convergence & 4D Acoustic Formants Restore)**: Next active target.

