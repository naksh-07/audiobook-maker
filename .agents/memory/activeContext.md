# Active Context: Audiobook Factory & TTS Suite

## Live Sprint State
- **Project Goal:** Studio-grade Audiobook Production with Literary Hindi Translation, Multi-Voice Synthesis, Dynamic BGM Scoring & M4B Packaging.
- **Current Phase:** Generated & Mastered 2m02s Hindi Cinematic Draft for *The Witcher: The Last Wish* (Scene 1).
- **CLI Runner:** [audiobook_cli.py](file:///root/tts_testing/audiobook_cli.py) + Global `audiobook-factory`.

## Active Invariants & Preferences
- **Piloting Philosophy:** Antigravity directly pilots each production stage interactively with naksh-07 (no blind script execution).
- **TTS Engines:** Primary: Google Gemini Flash TTS API (`Aoede`/`Charon`); Fallback: PC Kokoro/Goonj (emergency only).
- **Soundscape:** Dynamic sidechain ducking (-16dB during dialogue), mood detection, and ambient score (Procedural / MusicGen).
- **Mobile Guardrail:** Pure Python standard library + FFmpeg 8.0 on mobile ARM64; zero heavy pip packages.

## Recent Milestones
- [x] Switched primary TTS backend across project to Gemini API (`Aoede` top Hindi pick).
- [x] Built Pillar 3.5 Soundscape (`audiobook_factory/soundscape.py`) with mood detection & sidechain ducking.
- [x] Ingested `(Witcher 1)The Last Wish (1).pdf` from Termux input folder.
- [x] Translated Scene 1 (Wyzim arrival & The Fox tavern) into literary Hindi.
- [x] Synthesized multi-voice draft (Aoede for Narration, Charon for Geralt, Orus for Innkeeper).
- [x] Mastered with dark fantasy ambient score & exported MP3/M4A to `/storage/emulated/0/Documents/Termux/Audio/`.
