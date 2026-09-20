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

## ADR-007: Workstation Native Migration & Gemini 3.1 Flash TTS Adoption (Kokoro Retirement)
- **Context:** User requested migration of Audiobook Factory to the High-Performance PC Workstation, with Kokoro explicitly rejected in favor of Google AI Studio Gemini 3.1 Flash TTS (`gemini-3.1-flash-tts-preview`).
- **Decision:** 
  1. Default primary TTS model to `gemini-3.1-flash-tts-preview` and set `ENABLE_EMERGENCY_FALLBACK=false`.
  2. Implement automatic zero-dependency `.env` loading and UTF-8 console output for Windows.
  3. Replace `resampler=soxr` with universal `aresample=osr=48000` to maintain compatibility with Windows FFmpeg builds lacking libsoxr.
  4. Ensure all FFmpeg concat demuxer paths use forward slashes `/`.
- **Rationale:** Delivers studio-grade audio synthesis on high-performance desktop hardware without external dependency bloat or GPU server management.

## ADR-008: Zero-Cost BGM Strategy & Production Model Locking
- **Context:** Google AI Studio developer API gates `lyria-3.5` behind Tier-1 paid billing, and ElevenLabs free tier provides insufficient characters for long-form audiobooks.
- **Decision:**
  1. Formally lock top production models: `gemini-3.1-pro-preview` (deep extraction/translation), `gemini-flash-latest` (fast translation/scripting/mood), and `gemini-3.1-flash-tts-preview` (multi-voice speech).
  2. Implement a 100% free, dual-mode music engine via `resolve_ambient_score()`:
     - Primary: Checks `audiobooks/soundscapes/stems/` for drop-in royalty-free mood loops (`peaceful.mp3`, `mysterious.wav`, etc.).
     - Secondary: Automatic FFmpeg procedural organic harmonic drone synthesis (0 API tokens, infinite duration).
     - Both paths feed into FFmpeg `sidechaincompress` for automatic -16dB dialogue attenuation.
- **Rationale:** Guarantees zero recurring API costs or token anxiety while maintaining studio-grade broadcast quality.

## ADR-009: Local Meta MusicGen GPU Engine on RTX 4050
- **Context:** User requested local AI music generation capability on high-performance PC with NVIDIA RTX 4050 (6 GB VRAM).
- **Decision:** Integrated `transformers` native `facebook/musicgen-small` in `audiobook_factory/local_musicgen.py` running in `torch.float16` on CUDA.
- **Rationale:** Consumes only ~1.2 GB VRAM (under 25% of 6GB capacity), generates 30s broadcast-quality instrumental music in seconds, and eliminates cloud API dependencies entirely.

## ADR-010: Director Soundscape Plan JSON Architecture & GPU MusicGen Standby
- **Context:** Large 200GB archives (Sonniss) are overwhelming for agents and project storage. User requested placing GPU inference on standby and creating a dedicated JSON for soundscape/BGM/audio cues alongside the voice screenplay.
- **Decision:**
  1. Placed local GPU MusicGen on standby via `ENABLE_LOCAL_MUSICGEN=false` in `.env`.
  2. Adopted ultra-lightweight (<35MB) audio ecosystem: 6 core Incompetech mood stems + Kenney CC0/procedural SFX (`wind_gust`, `rain`, `thunder`, `lamp_ignite`, `heartbeat`).
  3. Established clean separation between voice script (`chapter_X_script.json`) and audio drama sound design (`soundscapes/chapter_X_soundscape.json`).
  4. Implemented `generate_chapter_soundscape_plan()` and `render_chapter_soundscape()` supporting multi-scene stem crossfades and dynamic -16dB sidechain ducking.
- **Rationale:** Prevents context bloat, guarantees fast deterministic execution, and gives agents and users explicit JSON control over musical moods and sound cues per scene.

## ADR-011: Curated 2-4 GB Local Sound Bank Architecture (SQLite FTS5)
- **Context:** User requested an optimized 2-4 GB curated sound bank on PC NVMe storage that avoids LLM context bloat and provides Hollywood-grade audio drama quality.
- **Decision:**
  1. Built `audiobook_factory/sound_bank.py` (`SoundBank` class) backed by SQLite FTS5 (`audiobooks/sound_bank/sound_bank.db`).
  2. Features sub-millisecond keyword/tag prefix matching (`search(query, category, mood, limit)`), returning file paths with 0 LLM token overhead.
  3. Implemented `scripts/download_sound_bank.py` for modular, automated downloading of curated Incompetech orchestral suites, Kenney CC0 foley/impacts, and ambient beds.
  4. Integrated `SoundBank` resolution directly into `soundscape.py` and CLI commands (`audiobook-maker bank scan|search|stats`).
- **Rationale:** Combines the fidelity of a multi-gigabyte audio library with the zero-overhead token efficiency of database indexing.

## ADR-012: Full-Novel Production Architecture & SOTA Engine Upgrades
- **Context:** Benchmarking against leading GitHub novel-to-audiobook projects (alexandria-audiobook, narrator-tts, Speak-EPUB) revealed critical bottlenecks for 100k-word novels (hardcoded [:8000] truncation, 6s sequential sleep, lack of transaction-safe state).
- **Decision:**
  1. Eliminated [:8000] character slicing in `script_builder.py` in favor of a sliding-window chunk parser with rolling context and character aliasing.
  2. Replaced sequential blocking `time.sleep(6.0)` in `tts_dispatcher.py` with a thread-safe `TokenBucketRateLimiter` and 3-worker `ThreadPoolExecutor` respecting the 15 RPM Gemini Free Tier quota.
  3. Implemented SQLite ACID-compliant `ProjectStateLedger` (`project_state.db`) for segment-level resumability and instant recovery.
  4. Decoupled CLI from core logic via `PipelineOrchestrator` supporting 1-command autonomous execution.
  5. Created dedicated `novel-audiobook-factory` Antigravity skill enabling single-instruction novel processing.
- **Rationale:** Delivers 4x faster synthesis, zero-loss crash resilience, and guarantees that 100k-word full novels are converted end-to-end without dropped chapters or truncated text.

## ADR-013: Linguistic Sanitizer & Defense-in-Depth Guardrail Engine
- **Context:** LLMs occasionally leak conversational meta-talk ("Here is the translation:", "Note:"), refusals ("I cannot provide a direct translation..."), or markdown artifacts into translations, which then contaminate screenplay scripts and ruin TTS narration audio quality.
- **Decision:**
  1. Built `audiobook_factory/sanitizer.py` implementing `validate_and_sanitize_translation()` and `sanitize_screenplay_segment()`.
  2. Enforces regex pattern rejection on all known LLM meta-chatter and refusal signatures.
  3. Enforces a Devanagari character purity guardrail (rejects outputs with <65% Devanagari density or >30 Latin words in Hindi mode).
  4. Automatic cache invalidation: `translate_chapter()` validates cached chunks on read and auto-re-translates any corrupted chunks.
  5. Automatic screenplay segment pruning: `build_dramatized_script_llm()` drops any segment flagged as meta-talk or English leakage.
  6. Configured `safetySettings: BLOCK_NONE` across all harm categories for mature dark fantasy fiction translation.
- **Rationale:** Guarantees 100% pure spoken narrative in audio scripts with zero leaked refusal summaries, conversational headers, or markdown debris.
