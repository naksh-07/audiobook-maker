# Active Context: Audiobook Factory & TTS Testing Suite

## Live Sprint State
- **Project Goal:** End-to-end production pipeline for Audiobook Ingestion, Literary Hindi Translation, TTS synthesis, and M4B packaging.
- **Current Phase:** Full 3-pillar Audiobook Factory built and verified with 1-command autonomous execution.
- **CLI Runner:** [audiobook_cli.py](file:///root/tts_testing/audiobook_cli.py) + Global CLI `audiobook-factory`.

## Active Blockers & Invariants
- **Architecture:** Zero external pip dependencies on mobile ARM64; pure Python standard library + FFmpeg 8.0.
- **Engines:** Gemini 2.5/3.5 Flash for Two-Pass Literary Translation & Glossary; Gemini 3.1 Flash TTS + PC RTX 4050 Kokoro/Goonj for speech.
- **Deliverables:** Embedded M4B audiobooks with chapters synced to `/storage/emulated/0/Documents/Termux/Audiobooks/output/`.

## Recent Milestones
- [x] Connected PC Kokoro & Goonj server (`http://10.236.21.128:8880`).
- [x] Pillar 1 Extractor: EPUB/TXT/PDF parsing with regex chapter detection and de-hyphenation.
- [x] Pillar 2 Translator: Two-Pass Literary Translation with persistent Character & Honorifics Glossary.
- [x] Pillar 3.1 Script Builder: Screenplay JSON converter with dialogue/narration segmentation.
- [x] Pillar 3.2 TTS Dispatcher: Dual-engine routing, voice continuity, and resume checkpointing.
- [x] Pillar 3.3 Mastering: 48kHz SOXR polyphase sinc resampler + EBU R128 loudness normalization.
- [x] Pillar 3.4 Packager: Chapter markers (`FFMETADATA1`) and native M4B containerization.
- [x] Verified full 1-command pipeline (`audiobook-factory auto sample_story.txt --hindi --backend kokoro`).
