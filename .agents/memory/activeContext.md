<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State: Commercial Studio Quality Upgrade (Waves 1-6 Complete)
- **Status**: ALL 6 Waves (Phases 1-25) COMPLETE & 100% green. 521/521 tests passing (0 regressions).
- **Wave 1 (Casting)**: `CharacterCastingProfile`, `VoiceCandidateEngine` (12 voices, 10 dimensions), `VoiceAuditionEngine` (10 modes), `CastingEvaluator`, `CastLockManager` (`cast_lock.json` + `TTSDispatcher` integration + recast audio invalidation).
- **Wave 2 (Voice Identity)**: `VoiceDNA` (4-layer: Identity, Behavior, Emotional, Forbidden), `ReferenceVoiceBank` (acoustic signature extraction: F0 median, centroid, flatness), `VoiceIdentityAnalyzer` (calibrated pitch drift defense).
- **Wave 3 (Acting Intelligence)**: `SceneEmotionalStateTracker` (6D vector trajectory smoothing), `PerformanceConstraintResolver` (clean prioritized directives, zero adjective bloat), `GenerationRiskEngine` ($R \in [0.0, 1.0] \to$ dynamic takes).
- **Wave 4 (Generation Quality)**: `GenerationStrategyResolver`, `TakeBank` (adaptive variants: `more_restrained`, `more_vulnerable`, `slower_heavier`, `colder`, `more_urgent`), `PerformanceEvaluator 2.0` (4 pillars: Acoustic, Performance, Voice Identity, Relational), `IntelligentTakeSelector` (context-aware weighting, drift penalty).
- **Wave 5 (Ensemble & Continuity)**: `ConversationalChemistry.evaluate_dialogue_chemistry` (pause fidelity, interruption snapping, energy dynamics), `PerformanceContinuityTracker` (`character_continuity.json` persistence, inter-chapter transition audit).
- **Wave 6 (Hardening & Documentation)**: `GoldenAudioRegressionSuite` (18 dramatic cases, synthetic offline WAVs), Human Casting Console CLI (`scripts/casting_console.py`), Gate 1 & 6A cast lock enforcement, full architecture guides (`docs/TTS_CASTING_ARCHITECTURE.md`, `docs/TTS_GENERATION_ARCHITECTURE.md`).
- **Zero-Hardcoding Compliance**: 100% verified by `test_zero_hardcoding_contracts.py`.
- **Independent Audit Verdict**: CERTIFIED / PASS WITH ADVISORY (Architect: 9.5/10, QA: 9.8/10, Forensic Detective: 9.5/10, Security: 10/10).
- **Integration & Remediation Pass Complete**: "Better wiring, not more machinery" completed. Wires `VoiceDNA` + `ReferenceVoiceBank` to `IntelligentTakeSelector`, dynamic take count control via `GenerationRiskEngine` + `GenerationStrategyResolver`, `SceneEmotionalStateTracker` + `VoiceDNA` in `PerformanceDirector`, dynamic acoustic scoring in `VoiceAuditionEngine`.
- **Test Integrity**: Dedicated 10-point test matrix (`tests/test_tts_integration_remediation.py`) 100% green; full test suite 531/531 tests passing (0 regressions); AST zero-hardcoding 100% compliant.
