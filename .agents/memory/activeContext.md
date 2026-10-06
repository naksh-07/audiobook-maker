<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Pure Vocals-Only Studio Audiobook Production Engine

## Milestone: Vocals-Only Architecture Decoupling & Hardening (v4.0 Baseline)
- **Status**: PRODUCTION CERTIFIED & 100% GREEN (712 passed, 8 skipped, 0 failed in 98s).
- **Core Streamlined Pipeline**:
  `Source (PDF/EPUB/TXT) -> Extraction -> Translation (Hindustani) -> Screenplay & Cast Attribution -> Multi-Voice Gemini TTS -> Dialogue Editorial -> EBU R128 (-19 LUFS) Master -> M4B Packaging`.
- **Decoupled & Archived**:
  - Unlinked 2.2 GB sound bank junction and removed 354 MB SQLite FTS5 database.
  - Moved unstable BGM/SFX/5-track mix engines (`AgentDirector`, `manifest_renderer`, `sound_design`, `soundscape_engine`, `cinematic_mix`, `virtual_catalog`) and 35+ sound-related test files into `archive/cinematic_audio/` (git-ignored).
- **Key Vocal Intelligence Retained**:
  1. Character casting & voice registry (`Aoede`, `Kore`, `Charon`, `Fenrir`, `Puck`, `Zephyr`, `Leda`, `Orpheus`).
  2. Zero-voice-drift attribution & Stanislavski dramatic direction (`ADR-021`).
  3. Persistent round-robin SQLite Gemini key pool (123 active keys with token-bucket rate limiting).
  4. Workstation forced alignment (MMS CTC & honest acoustic energy fallback).
  5. Dialogue editorial layer, Hann micro-fades (12ms/18ms), and broadcast EBU R128 (-19.0 LUFS, -1.5 dBTP) vocal mastering.
  6. Chaptered M4B packaging with cover art and chapter metadata.
- **CLI Commands**:
  `audiobook_cli.py [extract|translate|script|synthesize|master|package|produce|auto|audit|audit-book]`
