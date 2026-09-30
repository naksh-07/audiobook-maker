<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: 360° Re-Audit & Production Hardening Complete

## Live Sprint State: 360° Architectural Re-Audit & Surgical Production Fixes
- **Status**: PRODUCTION RE-AUDITED, SURGICALLY PATCHED & REGRESSION VERIFIED.
- **Auditors Convened**: Pipeline Architecture, DSP Acoustic, Security & Safety, Test Suite.
- **Surgical Remediations Implemented**:
  - **State DB Concurrency**: Removed unprompted `IN_PROGRESS` reset from `_init_db()`; added explicit `recover_orphaned_segments()` and `auto_recover=False` in `TTSDispatcher`.
  - **Audio Sync & Breath Alignment**: Prepended `pre_roll_breath_ms` silence in `stitch_dialogue_track_from_ledger()`; updated `resolve_timeline_start_offsets()` with dict support and pre-breath accumulation.
  - **DSP Headroom & Intersample Peak Defense**: Added lookahead peak limiting (`alimiter=limit=0.95`) to intermediate stems (`cmd_me`, `cmd_premaster`); reordered `MasteringEngine` chain to `aresample -> loudnorm -> alimiter`.
  - **Win32 Buffer Protection**: Offloaded `render_music_bus` filter complex to `-filter_complex_script` file, eliminating 8,191-char CLI overflows.
  - **CLAP Resilient Fallback**: Replaced random Gaussian noise on OOM with VRAM flush, CPU inference fallback, and zero-vector fallback.
  - **Security & Subprocess Hardening**: Enforced `shell=False` in `audio_master.py`, sanitized dynamic DDL column names in `sound_bank.py`, closed HTTP error sockets in `script_builder.py`, and added retry backoff to atomic file writers.
- **Verification**: Clean regression test pass across all modified audio, gate, and pipeline modules.
