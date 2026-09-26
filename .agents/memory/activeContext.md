<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Sonic Intelligence Catalog & Virtual JIT Sound Bank (Certified)

## Live Sprint State: Sonic Intelligence Catalog & JIT Sound Bank (100% Green)
- **Status**: Completed full studio upgrade of Sound Bank into Virtual JIT Catalog.
- **Verification**: 45/45 regression & catalog tests passing (including 12/12 new virtual catalog tests & 4/4 AST zero-hardcoding contracts).
- **Core Pillars Delivered**:
  - **Zero Disk Bloat**: Cataloged 18,133 open-source tracks (Incompetech, BBC SFX, Sonniss GDC, Kenney CC0) as metadata-only entries with JIT remote streaming; ~200 GB raw audio replaced by ~45 MB SQLite index.
  - **Sonic Genome v2.0**: Unified 9-dimensional schema separating measured DSP, inferred semantics, and curated sound bible metadata (`PhysicalGenome`, `TemporalWaveGenome`, `SpatialGenome`, `EnvironmentalGenome`, `DramaticGenome`, `MixCompatibilityGenome`, `MusicIntelligence`, `FoleyIntelligence`, `RemoteAssetMetadata`).
  - **Bounded LRU Cache**: 1.5 GB default local cache with `protect_active_render` context manager, atomic eviction (`is_downloaded=0`, `filepath=NULL`), and metadata preservation.
  - **Multi-Source Virtual Adapters**: Incompetech, BBC Sound Effects, Sonniss GDC, Kenney CC0 / OpenGameArt adapters with atomic batch upserts and gzip seed hydration (`virtual_catalog_seed.json.gz`).
  - **Explainable Hybrid Search & Sound Cards**: `search_virtual_catalog` with multi-attribute filtering & `why_matched` explanations; LLM-ready Agent Sound Cards for zero-listening acoustic reasoning.
  - **JIT Remote Audio Streaming**: Atomic thread-safe downloads with `.part` rename, mirror fallback, retry backoff, and corrupted/HTML payload rejection.
  - **SoundAssetRetriever & CLI**: JIT resolution in `SoundAssetRetriever` and CLI commands (`bank virtual-status`, `search`, `inspect`, `prune-cache`, `prefetch`, `ingest-source`).
- **Boundaries Preserved**: Master renderer, FFmpeg mix graph, and existing audio pipelines remain 100% intact.
