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
  - Re-rendered discrete stems (`chapter_002_stem_DX/MX/FX/AMB/ME.wav`), premaster, and broadcast master.
  - Gate 5 (EBU R128): **PASS** (-19.0 LUFS, -1.8 dBTP).
  - Gate 5.2 (Spectral Masking): **PASS** (DMR +5.8 dB, Formant separation +4.8 dB, Music formant energy -35.4 LUFS).
  - Gate 5.3 (Stereo Phase Coherence): **PASS** (Mean phase correlation: 0.696, safe margin above 0.20).
  - Audio Reality Auditor: **PASS** (12 passed, 4 remediated, 6 rejected).
  - Mix Judge: **PASS** (Score: 1.0, 12/12 categories green).
  - Master Deliverable: `audiobooks/projects/sword_of_destiny/mastered/chapter_002_hi_cinematic.m4a` (23.4 MB, AAC 256k 48kHz).
- **Witcher 3 Sound Bank Remediation & Sonic Genome Enrichment**:
  - Reclassified 26,906 Witcher 3 assets from generic SFX into 10 categories (`AMB`: 3,143, `FOL`: 2,661, `MUS`: 622, `SFX`: 20,480).
  - 100% neural embeddings preserved (44,931). FTS5 search index rebuilt.
  - Enriched all 26,906 assets with `sonic_genome` v2.1 (transients, physical & emotional features) in 211s via 12 CPU workers (zero LLM cost).
  - Fixed transient blindness in `manifest_renderer.py` via `get_asset_in_point(cue.audio_path)` and dynamic `atrim`.
  - Added optional `duration_sec` control to `SoundSpotter` LLM schema. 20/20 regression tests passing.

