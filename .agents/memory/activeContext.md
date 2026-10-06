<!-- schema_version: 2.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
<!-- LINE_BUDGET_HARD_CAP: 50 LINES -->
# Active Context: Pure Vocals-Only Studio Audiobook Production Engine

## Milestone: Vocals-Only Architecture Decoupling & Hardening (v4.0 Baseline)
- **Status**: PRODUCTION CERTIFIED & 100% GREEN. Ported Phase 1-3 from main.
- **Core Streamlined Pipeline**:
  `Source (PDF/EPUB/TXT) -> Extraction -> Pre-Production (DeepSearch/BookDNA) -> Translation Collective -> Screenplay & Anti-Swap Attribution -> 4D Formant Multi-Voice TTS -> Dialogue Editorial -> EBU R128 (-19 LUFS) Master -> M4B Packaging`.
- **Decoupled & Pure Vocals-Only**:
  - Excluded unstable BGM/SFX 5-track mix engines, Archive.org sound bank downloader, and noisy stems.
- **Ported Vocal & Pre-Production Upgrades from Main**:
  1. **Quota Shield & Model Fallbacks**: Excluded quota-trap models (`omni`, `gemma`, `pro`), 12s probe timeout.
  2. **Room 1 Pre-Production Intelligence**: `NovelDeepSearchEngine`, `BookDNAAgent`, `DramatisPersonaeAgent`, `PhoneticLexiconDramaturge`.
  3. **Room 2 Translation Collective**: 4-Agent Collective + Dual-Rule Invariant + Pass 1 Bounded 2-Attempt Retry.
  4. **Room 3 Screenplay & Staging**: `DialogueAttributionAuditor` (anti-swap QA), physical blocking spatial coordinates.
  5. **Room 4 4D Vocal Timbre**: `CharacterCaster` 4D acoustic vector ($F_0$ pitch delta, tempo, parametric EQ formants), `TakeAuditionCritic`.
  6. **Runtime Hardening & WinError 32 Shield**: Centralized `_atomic_replace` backoff retry across all modules, explicit FFmpeg timeouts on 100% of subprocess calls, NaN float audio sanitization.
  7. **Docs & Guardrails Synchronization**: `AGENTS.md`, `README.md`, skills, and docs aligned to Pure Vocals-Only standards (`ADR-051`).
- **Test Suite Status**: 764 passed, 8 skipped, 0 failed (100% green).
- **Literary Translation Intelligence (Restored & Hardened)**:
  - Universal World-Anchor (Rule 8) eliminates cartoonish village proverbs (*लंबरदार/पंच जी*) on foreign fantasy while preserving Premchand Awadhi/Bhojpuri.
  - `BLOCK_NONE` safety framing + multi-model safety rotation in `llm_client.py` and `repair_engine.py`.
  - Chapter 2 (*The Bounds of Reason*) translated with publication-grade Devanagari prose.
- **CLI Commands**:
  `audiobook_cli.py [extract|translate|script|synthesize|master|package|produce|auto|audit|audit-book]`
