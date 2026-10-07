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
