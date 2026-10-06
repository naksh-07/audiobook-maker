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
  3. **Room 2 Translation Collective**: 4-Agent Collective (`DraftTranslator`, `CadenceSpecialist`, `IdiomDramaturge`, `TranslationCritic`) + Dual-Rule Invariant.
  4. **Room 3 Screenplay & Staging**: `DialogueAttributionAuditor` (anti-swap QA), physical blocking spatial coordinates.
  5. **Room 4 4D Vocal Timbre**: `CharacterCaster` 4D acoustic vector ($F_0$ pitch delta, tempo, parametric EQ formants), `TakeAuditionCritic`.
  6. **Docs & Guardrails Synchronization**: `AGENTS.md`, `README.md`, skills, and docs aligned to Pure Vocals-Only standards (`ADR-051`).
- **CLI Commands**:
  `audiobook_cli.py [extract|translate|script|synthesize|master|package|produce|auto|audit|audit-book]`
