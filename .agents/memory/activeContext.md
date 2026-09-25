<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State
- **Branch**: `main` (Performance Realization Layer & Gate 2.8 COMPLETE).
- **Test Suite Status**: 443/443 tests 100% green (23 dedicated performance tests, 5 gate auditor tests, zero regressions).
- **Performance Realization Deliverables**:
  - `audiobook_factory/performance/`: 11 modular components bridging Stage 3 dramaturgy with TTS synthesis.
  - Contracts & Models: `PerformanceDirection`, `TakeVariant`, `PerformanceEvaluationResult`, `PerformanceFidelityReport`.
  - Humanized Timing: Respiratory breaths (120-250ms), hesitation pauses, dramatic silence intent, 80ms interruption cuts.
  - Actor Direction: `PerformanceDirector` grounding sudden emotional leaps against teleportation.
  - Multi-Take Architecture: `TakeBank` (1-4 takes based on priority), `GeminiTTSPerformanceAdapter` (text immutable).
  - 8-Dimensional Evaluator: Intent, emotion, prosody, pacing, subtext, character, relationship, naturalness.
  - Intelligent Take Selection: Explanatory rationales, avoiding "loudest = best" trap.
  - Conversational Chemistry: Zero-onset interruption cuts, intimidation hesitation, intimate close-mic whisper.
  - Performance Continuity: Character pace/energy drift tracking (>30% anomaly alerts).
  - Quality Gate 2.8: `PerformanceFidelityGate` pre-mix validation before dialogue stems enter mastering.
- **Quality Standards**: EBU R128 (-19 LUFS), sacred text immutability, fail-closed gates with provenance ledgering.
