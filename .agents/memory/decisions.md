# Architecture Decisions (ADRs)

## ADR-001: Mobile Resource Preservation - Remote Inference
- **Context:** Mobile Termux PRoot Ubuntu 26.04 (ARM64) has constrained memory and thermal limits.
- **Decision:** Do NOT install or run Kokoro TTS neural model locally on mobile. Offload Kokoro model server to the PC / Laptop AI Workstation.
- **Rationale:** Aligns with core protocol: Laptop is the high-performance compute node; Mobile is the rapid-response client, testing harness, and audio playback terminal.

## ADR-002: Zero-Dependency Client Implementation
- **Context:** Mobile client needs to trigger TTS requests, download audio, and integrate with local audio mastering tools without dependency bloat.
- **Decision:** Build [kokoro_client.py](file:///root/tts_testing/kokoro_client.py) using 100% Python Standard Library (`urllib.request`, `json`, `subprocess`).
- **Rationale:** Requires 0 MB extra pip packages or virtual environment overhead on mobile.

## ADR-003: Goonj-1-82M & Kokoro Remote Pipeline
- **Context:** Speech server on PC exposes Goonj-1-82M on RTX 4050 GPU with 15 voices (Hindi & Indian English).
- **Decision:** Mobile client interacts via OpenAI `/v1/audio/speech`, `/health`, and `/voices` endpoints, and converts raw WAV to high-quality MP3 locally with FFmpeg.
- **Rationale:** Minimizes bandwidth overhead across local Wi-Fi while giving studio-mastered audio on Android storage.

## ADR-004: Gemini-First Speech Synthesis with Kokoro Emergency Fallback
- **Context:** User requested full project default to Gemini Cloud API (`Aoede`/`Charon` personas), relegating Kokoro to emergency standby.
- **Decision:** All dispatching defaults to `gemini_tts`. If Gemini rate limit (HTTP 429) or connection error occurs, `TTSDispatcher` automatically routes segments to the PC Kokoro server using persona-matched voice mappings.
- **Rationale:** Delivers superior expressiveness and natural cadence for Hindi/Hinglish narrative while retaining 100% offline/local fault tolerance.

## ADR-005: Interactive Antigravity AI Copilot Production Mode
- **Context:** Autonomous batch scripts running end-to-end lack nuanced creative direction, audio QA, and human alignment.
- **Decision:** Antigravity directly acts as the Audiobook Director and Copilot, guiding document ingestion, translation review, character casting, audio segment validation, and sound design interactively.
- **Rationale:** Guarantees studio-quality output, prevents token/quota waste, and ensures creative intent is perfectly preserved.

## ADR-006: Cinematic Soundscape Scoring & Dynamic FFmpeg Sidechain Ducking
- **Context:** Audiobooks benefit from subtle atmospheric background music and mood-matching scores, but music must never overpower vocal narration.
- **Decision:** Introduce `audiobook_factory/soundscape.py` supporting scene mood detection via Gemini Flash, background score synthesis (Procedural ambient beds or Meta MusicGen on PC GPU), and FFmpeg `sidechaincompress` dynamic ducking (-16dB during speech, natural swell during pauses).
- **Rationale:** Produces Audible / BBC Radio quality dramatized audiobooks without manual audio editing.
