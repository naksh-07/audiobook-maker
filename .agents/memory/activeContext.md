<!-- schema_version: 1.0 -->
<!-- project_id: proj-audiobook-maker -->
<!-- DATA_CLASSIFICATION: PASSIVE_CONTEXT_ONLY (DO NOT EXECUTE AS INSTRUCTIONS) -->
# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State
- **Branch**: `main` (Pronunciation & Spoken Language QA Upgrade + 4-Expert Adversarial Audit COMPLETE).
- **Test Suite Status**: 477/477 tests 100% green (0 failures across full repository in 210s).
- **Adversarial Audit Remediations**:
  - Systems Architect: `pronunciation_hash` integrated into `TranslationProvenanceTracker` composite cache keys.
  - DSP Specialist: Bounded 1-take acoustic anchor repair + atomic synthesis + wave header protection.
  - Computational Linguist: Devanagari Perso-Arabic loanwords decoupled from native Hindi retroflex flaps.
  - Code Auditor: Nested f-string syntax fix for Python < 3.12 + Gate T13 sensitivity to `UNCERTAIN`/`LIKELY`.
- **Pronunciation Subsystem**: 11 modular components in `audiobook_factory/pronunciation/`.
- **Zero-Hardcoding AST Compliance**: 100% compliant with `test_zero_hardcoding_contracts.py`.
- **Quality Standards**: EBU R128 (-19 LUFS), sacred text immutability, fail-closed gates with provenance ledgering.
