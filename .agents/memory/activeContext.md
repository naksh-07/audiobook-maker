<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Sound Design Subsystem Upgrade (Cinematic 20 Capabilities)

## Live Sprint State: Complete & Verified (703/703 Tests Passing, 100% Green)
- **Status**: Completed all 20 Sound Design Capabilities across Phases A - G.
- **Verification**: 703/703 tests passing (0 failures, 100% green in 257.05s).
- **Subsystem Architecture (`audiobook_factory/sound_design/`)**:
  - `contracts.py`: Authoritative Pydantic v2 sound design schemas.
  - `scene_understanding.py`: Scene audio understanding reusing screenplay tags & dramaturgy.
  - `blueprint.py`: SceneAudioBlueprint director instruction sheet.
  - `environment_profiles.py`: 12 canonical environments extending WorldAcousticProfile.
  - `asset_retriever.py`: Semantic FTS5 retriever, SHA-256 provenance, DSP sanity check.
  - `ambience_engine.py`: 5-tier decoupled ambience with cross-scene stateful evolution.
  - `walla_engine.py`: Contextual crowd activity, dialogue subordination & solitary restraint.
  - `silence_engine.py`: First-class negative sound design & adaptive density budgets.
  - `foley_engine.py`: Relevance scoring formula & conscious low-value verb rejection.
  - `foley_character_material.py`: Character physics, surface matrix, tableware isolation.
  - `narrative_sfx.py`: Action hard SFX impacts & multi-tier creature sound design.
  - `magical_sound.py`: Canonical spell stages (charge, release, impact) & families.
  - `music_motif_director.py`: Persistent leitmotifs, 6 variation modes & cue direction.
  - `spatial_acoustics.py`: Abstract room propagation & soundstage spatial continuity.
  - `sound_director.py`: Master orchestrator assembling chronological SoundTimeline.
  - `qc.py`: Multi-signal QC auditor evaluating 9 forensic sound design signals.
  - `adapter.py`: Clean adapter boundary for AgentDirector & CreativeManifest.
  - `golden_benchmarks.py`: 15 commercial cinematic audio drama scenarios.
- **Architectural Invariants Strictly Enforced**:
  - Adaptive scene density (no rigid universal 60% rule).
  - Sound design outputs intent/priority/spatial metadata only (Track 11 owns mixing).
  - Zero hardcoding contract compliant (`test_zero_hardcoding_contracts.py` passed).
