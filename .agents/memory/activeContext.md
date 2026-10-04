<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Audiobook Maker Production Engine & Cinematic Sound Refinement

## Milestone: Hollywood-Grade SFX & BGM Cinematic Mixing Refinement (v2.0)
- **Status**: PRODUCTION CERTIFIED & GOLDEN VERIFIED (100% Green across all gates).
- **Architecture Refinements**:
  1. `foley_director.py` & `manifest_renderer.py`: Replaced flat 3.5s limit with UCS category duration ceilings (`IMPT`: 2.5s, `WEAP`: 3.0s, `DOOR`: 6.5s, `POUR`: 6.0s, `CLOTH`: 5.0s, `FIRE`: 4.5s) and >15s ambient isolation.
  2. `audio_reality_auditor.py`: Integrated category-aware duration validation in Check D, anti-repetition cooldown (180s), and rogue asset quarantine.
  3. `acoustic_bus_matrix.py` & `manifest.py`: Enhanced `DuckingProfile` with dynamic `ratio` (3.2) and `knee` (2.8) tuned per scene type.
  4. `cinema_audio_engine.py`: Added ambience HF air smoothing (`highshelf=6.5kHz:-3.5dB`), phase-safe stereo widening (`slev=1.15`), and dynamic speech-active windowed EQ pocketing.
  5. `gates/acoustics.py`: Upgraded Gate 5.2 to multi-factor vocal clarity with 1.8-3.2 kHz formant band collision evaluation; probe timeouts increased to 120s for long chapters.
- **Chapter 2 Live Validation**:
  - Re-rendered discrete stems (`chapter_002_stem_DX/MX/FX/AMB/ME.wav`), premaster, and broadcast master (-19.0 LUFS, -1.8 dBTP).
  - Master Deliverable: `audiobooks/projects/sword_of_destiny/mastered/chapter_002_hi_cinematic.m4a` (23.4 MB).
- **Chapter 3 Live Production & Verification**:
  - Screenplay & Attribution: 119 segments, Stanislavski subtext, cast lock (`Aoede`, `Algieba`, `Enceladus`, `Rasalgethi`, `Kore`).
  - Gates Passed: Gate 2, Gate 2.5, Gate 2.8 (with cached-take evaluation fix), Gate 3.5, Gate 5.0 (-19.2 LUFS, -1.9 dBTP), Gate 5.2 (DMR 24.4 dB), Gate 5.3 (phase r: 0.647), Mix Judge (Score 1.0).
  - Audio Reality Auditor: 22/22 cues passed sanity checks (zero loop fatigue or misclassified assets).
  - Master Deliverable: `audiobooks/projects/sword_of_destiny/mastered/chapter_003_hi_cinematic.m4a` (29.9 MB, 20.78 min, AAC 256k 48kHz).
- **Witcher 3 Sound Bank Remediation & Sonic Genome Enrichment**:
  - Reclassified 26,906 Witcher 3 assets into 10 categories (`AMB`: 3,143, `FOL`: 2,661, `MUS`: 622, `SFX`: 20,480).
  - Enriched with `sonic_genome` v2.1 in 211s via 12 CPU workers. Transient in-points & category-aware Foley limits active.

