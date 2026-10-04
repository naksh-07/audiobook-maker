<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Maker Production Engine & Hollywood Directing Suite

## Milestone: Hollywood End-to-End Multi-Agent Architecture (Rooms 1-5 Certified)
- **Status**: PRODUCTION CERTIFIED ACROSS ALL 5 SPECIALIZED MULTI-AGENT ROOMS (41/41 Tests 100% Green).
- **Architecture Highlights**:
  1. **Room 1 (Pre-Production World & Lore Studio)**: `audiobook_factory/preproduction/`
     - `DramatisPersonaeAgent`: Full-novel character profiling without text slicing.
     - `SonicWorldArchitect`: Authoritative `sonic_bible.json` (convolution IR reverbs, foley palettes).
     - `PhoneticLexiconDramaturge`: Lore terminology & locations in `book_bible.json`.
     - `PreProductionSupervisor`: One-time master locking per novel with zero voice drift.
  2. **Room 2 (Literary Hindi Translation Collective)**: `audiobook_factory/translation/agents/`
     - `LiteraryDraftTranslator` -> `HindustaniCadenceSpecialist` -> `SubtextAndIdiomDramaturge` -> `TranslationQualityCritic`.
     - 4-pass pipeline enforcing 70/30 canon sacredness, spoken breath rhythm, 19-to-21 amplification of raw dialogue, and reflection repair.
  3. **Room 3 (Screenplay Dramaturgy & Spatial Staging)**: `audiobook_factory/script/agents/`
     - `DialogueTurnIsolator` -> `StanislavskiSubtextDirector` -> `PhysicalBlockingDirector` -> `DramaturgyConsistencyJudge`.
     - Actor physical blocking linked directly to stereo azimuth panning (`-0.8` to `+0.8`) and proximity zones.
  4. **Room 4 (Voice Performance & Audition)**: `audiobook_factory/performance/take_critic.py`
     - `TakeAuditionCritic`: Judicial auditioning comparing candidate takes on climactic scenes.
  5. **Room 5 (Living World Sound Design & Directing)**: `audiobook_factory/director/agents/`
     - Implicit scene physics decoupled from literal nouns; beat-timing placement (`pre_speech`, `mid_speech_pause`, `post_speech`, `under_speech`).
- **Test Suite**: 41/41 unit & integration tests 100% GREEN.
