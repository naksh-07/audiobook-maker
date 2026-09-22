# Active Context: Audiobook Maker Core Engine Overhaul

## Live Sprint State
- **Audit Remediation Sprint:** COMPLETE & VERIFIED (203/203 tests passing).
  - P0: M4B packager AAC encoding on WAV/non-AAC inputs; dynamic Gate 3 scenes / CreativeManifest feasibility.
  - P1: CLI dynamic vocal track inference (witcher1 unhardcoded), chapter regex parsing, WAV/M4A discovery.
  - P2/DSP: Music-only 2.2kHz notch EQ, whisper collision attenuation in AgentDirector, rolling translation context.
  - P3/Engine: .env quote stripping, text LLM quota isolation, pypdf digital PDF extraction, ghost Kokoro/MusicGen purged.
- **Verification Baseline:** 203/203 unit & integration tests passing (`tests/test_audit_remediation_sprint.py`).
- **Next Horizon:** Ready for novel batch production run or user next command.
