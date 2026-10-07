<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Pure Vocals-Only Studio Audiobook Production Engine

## Milestone: Universal Multi-Model Guard, Shield & 120-Key Safety Architecture
- **Status**: PRODUCTION CERTIFIED & 100% GREEN (All regression suites + new 9/9 universal tests passing).
- **Universal Multi-Model Architecture**:
  - Two-tier SQLite ledger (`key_quota_ledger` + `model_quota_ledger`) in `key_manager.py` with in-flight concurrency tracking (`lease_key`), multi-provider key discovery, and timezone-aware rollover.
  - Universal `guard_shield.py`: `ModelQuotaProfile` (RPM/RPD/TPM), universal HTTP error classifier (`Retry-After`, `x-ratelimit-*`), 3-state `CircuitBreaker`, and `HardwareVRAMGuard` (RTX 4050 4.8GB cap).
  - Multi-dimensional `rate_limiter.py`: Per-model RPM/TPM token buckets with lock release during sleep and granular key/model pauses with organic jitter.
  - Universal client in `llm_client.py`: `call_model()` for Gemini + OpenAI-compatible endpoints with circuit breakers.
- **120-Key Anti-Ban Defense Stack**:
  - Authentic Google GenAI SDK headers (`x-goog-api-client`) eliminate bot fingerprints.
  - Sequential IP dispatch (`max_workers=1`) in `TTSDispatcher` prevents network clustering flags.
  - Least-loaded scheduling (`in_flight_requests ASC, requests_today ASC, last_used ASC`) prevents single-key dogpiling.
  - Per-model quota isolation prevents cross-model quota burning (Pro exhaustion leaves Flash/TTS alive).
- **Core Engine & Production Flow**:
  - Pure Vocals-Only: BGM/SFX decoupled; 0% speaker swap attribution; Hann micro-fades (12ms/18ms); EBU R128 (-19.0 LUFS, -1.5 dBTP).
  - CLI Commands: `audiobook_cli.py [extract|translate|script|synthesize|master|package|produce|auto|audit|audit-book]`

## Milestone: Fresh Novel End-to-End Production & Audit Verification (Chapter 2)
- **Status**: PRODUCTION VERIFIED & 100% AUDIT PASS.
- **Novel Tested**: *Sword of Destiny* (Chapter 2: "The Bounds of Reason", 1,497 words source).
- **Execution Lifecycle**:
  - Room 1 (Extraction): 51 chapters, 114k words (Gate 0.1 PASS).
  - Room 2 (Translation): 4-Agent Collective -> `chapter_002_hi.md` (8,491 chars Hindustani literature).
  - Room 3 (Screenplay): 72 segments, Stanislavski subtext, 0% speaker swap inversions.
  - Room 4 & 5 (TTS & Master): Gemini 3.8 Flash TTS multi-voice synthesis, -18.9 LUFS, -1.8 dBTP peak.
  - Packaging: Chaptered `Sword_of_Destiny.m4b` (14.32 MB, 10.32 mins, 48kHz AAC 192 kbps).
  - Independent Quality Gates: Gates 0, 1, 2, 3, 5 all 100% PASSED. All regression suites green.
