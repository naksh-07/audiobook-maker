<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Maker Production Engine & Hollywood Directing Suite

## Milestone: Universal Hollywood-Grade Production Engine Upgrade (ALL 6 PHASES CERTIFIED)
- **Status**: COMPLETE & VERIFIED (53/53 Tests 100% Green).
- **Core Architecture Upgrades**:
  1. **Room 1 (Universal Book DNA & 4D Acoustic Formant Casting)**:
     - `BookDNAAgent`: Infers literary tradition (`CLASSIC_REVERENT`, `RAW_UNRATED`, etc.), dialect matrix, and honorific dynamics without hardcoding.
     - `compute_acoustic_formant_vector()`: Distinct 4D acoustic coordinates ($F_0$ pitch delta $\pm 4-12\%$, tempo, parametric EQ formant profiles) preventing character timbre convergence.
  2. **Room 2 (Source-Anchored Translation Collective)**:
     - Dual-Rule Invariant: Rule A (19-to-21 amplification for gritty unrated fiction) vs Rule B (Nothing Above Source reverence for dignified classic literature).
     - Visceral combat choreography & somatic intimacy without puritanical softening or clinical jargon.
  3. **Room 3 (Anti-Swap Screenplay Engine)**:
     - `DialogueAttributionAuditor`: Dedicated forensic QA LLM preventing speaker turn inversions ($A \leftrightarrow B$), resolving misattributions to Narrator/pronouns, and scrubbing leaked speech tags (`"उसने कहा"`).
  4. **Room 4 (Formant-Shifted Studio TTS & DSP Engine)**:
     - `TTSDispatcher` & `audio_slicer`: Unconditional chaining of $F_0$ `asetrate`, `aresample`, `atempo`, and 4D parametric EQ formant curves (`equalizer=f=...`).
     - Cache Hash Invalidation: `compute_canonical_segment_filename` incorporates `eq_formant_profile` into hash.
     - `TakeAuditionCritic`: Multi-take candidate audition deliberation selecting superior vocal strain and subtext.
     - Permanent `BLOCK_NONE` permissive fiction safety across all Gemini providers.
  5. **Room 5 (Living World Foley & Convolution IR Staging)**:
     - Expanded `ACOUSTIC_IR_PRESETS` with rural, modern, street, wooden cottage, and cathedral spaces + fuzzy fallback resolver.
     - `MicroFoleyAgent`: Zero Dead Voids density protection seeding organic micro-foley for gaps $> 8$ segments.
  6. **Room 6 (Pipeline Orchestration & Cache Governance)**:
     - Added `--force-rebuild` and `--stage-start` flags to CLI, pipeline runner, and `PipelineOrchestrator`.
- **Test Suite**: 53/53 targeted tests 100% GREEN (Zero hardcoded novel lore, 100% novel-agnostic).
- **Current State**: Ready for local commit and full audio production run.
