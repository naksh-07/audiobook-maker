<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Sonic Intelligence Library Harvesting Subsystem

## Live Sprint State: Library Harvester Architecture & Verification (100% Green)
- **Status**: Completed production-grade Sonic Intelligence Library Harvesting Subsystem for the ~200GB sound library.
- **Key Deliverables**:
  - `AudioMetadataExtractor`: Non-destructive extraction of ID3v1/v2, BWF/BEXT, RIFF INFO, Vorbis comments, UCS naming syntax, folder taxonomy tokens, and companion variation groupings (`raw_metadata` 100% preserved).
  - `SonicLibraryHarvester`: 11-stage pipeline with rapid fingerprinting (`size + mtime + SHA-256 header`), idempotent skip/resume, stage selectivity (`all`, `metadata_dsp`, `ai_only`), error isolation for corrupt audio, and periodic GPU VRAM eviction.
  - Multi-scale DSP & AI: 3-window composite sampling for long tracks ($> 60\text{s}$), energy-weighted CLAP pooling ($> 15\text{s}$), active-region centering with Hann micro-fades for micro-SFX ($< 1.0\text{s}$).
  - Unified Schema: Consolidated into existing primary `sound_catalog`, `sound_embeddings`, `sound_classifier_tags`, `sound_temporal_events`, and `sound_analysis_runs`.
  - Epistemic Invariant: Zero invented metadata. All 7 creative dimensions strictly default to `UNASSIGNED`/`UNASSESSED`.
  - CLI & API: `bank harvest`, `bank harvest-status`, `bank rebuild-index` with full batch reporting.
- **Verification**: 10/10 harvester tests passing in 53s, 30/30 core regression tests passing in 4.6s. Golden library fixtures verified.
- **Current Milestone**: HARD GATE reached. Awaiting explicit user authorization before launching harvest on the 200GB library.
