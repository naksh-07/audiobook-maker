# Active Context: Audiobook Maker Core Engine & Production

## Live Sprint State
- **Audio Drama Sync, Foley Staging & Soundscape Remediation (ADR-022):** COMPLETE & VERIFIED.
  - Eliminated cumulative timeline drift by synchronizing `pre_roll_breath_ms` across contracts, ledger, and director.
  - Eradicated 50% dead-center Foley trap with bilingual anchor mapping (`BILINGUAL_ANCHOR_MAP`) and transient placement.
  - Isolated domestic tableware (`DOMETabl`) & organic gore (`GOREAnat`) in UCS rules; prevented sword clashes on dinner plates.
  - Upgraded BGM to Scene-Bound Underscore with `until_segment` duration calculation and 20s cue floor.
  - Replaced 106-min flat monolithic ambience with dynamic multi-scene partitioning from `acoustic_env` shifts.
- **Zero-Voice-Drift Hardening & Speaker Attribution (ADR-021):** COMPLETE & VERIFIED.
- **Milestone v4.0.0-beta.1 (Latest Pre-Stable Beta):** TAGGED & RELEASED.
  - Final pre-stable beta consolidating ADR-001 through ADR-022.
  - 100% test pass rate across 243 tests (zero failures, zero errors).
- **Next Horizon:** Production stress test on full novel batch and subsequent v4.0.0 stable release.
