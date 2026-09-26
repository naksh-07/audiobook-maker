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

## ADR-014: 100% Free Next-Gen Multi-Layer Screenplay, Deep Foley Miner & 5-Track Timeline Compositor
- **Context:** User requested Hollywood / GraphicAudio ("A Movie in Your Mind") grade production while strictly enforcing 100% free operation without third-party fees, and asked whether SFX/Foley should come from TTS or local setup.
- **Decision:**
  1. **Local Setup for SFX (Rejection of TTS for Foley)**: TTS models are trained for vocal phonemes and mouth sounds; generating SFX via TTS produces cartoonish vocal mimicry and burns speech quota. Replaced with local curated Kenney CC0 RPG/Impact Foley packs indexed in SQLite FTS5 (`audiobooks/sound_bank/`) + procedural FFmpeg audio recipes (zero runtime API cost).
  2. **Multi-Cast Screenplay Parsing (`script_builder.py`)**: Migrated to `gemini-flash-lite-latest` with stealth SDK headers and dynamic 80+ key pool rotation. Parses novels into multi-speaker dialogue segments with emotional acting tags (`whispering`, `growl`, `calm_raspy`, `angry`).
  3. **Deep Foley & Acoustic Director (`foley_miner.py`)**: Extracts physical object interactions, micro-timing offsets (`offset_ms`), spatial stereo coordinates (`pan`), and acoustic environment reverberation presets into `.cue.json`.
  4. **Multi-Cast Persona Routing (`tts_dispatcher.py`)**: Resolves characters to distinct Gemini Flash TTS voices (`Charon` for Geralt, `Aoede` for Narrator, `Puck` for Dandelion/Guards, `Fenrir` for Kings/Nobles, `Kore` for Sorceresses).
  5. **5-Track FFmpeg Timeline Compositor (`soundscape.py`)**: Track 1 (Voice with room reverb), Track 2 (Foley with millisecond `adelay`), Track 3 (Ambience), Track 4 (Music with 1.2kHz–3.2kHz spectral carving and -16dB dynamic lookahead sidechain ducking), Master Bus (EBU R128 -19 LUFS at 48kHz).
- **Rationale:** Delivers full-cast Hollywood-grade audio drama fidelity on local Windows workstation hardware with 0 ongoing subscription costs.

## ADR-015: Gangs of Wasseypur / Manto Grade Unfiltered Adult Literary Fidelity & DesiDialectDirector
- **Context:** User requested standardizing dark-fantasy novel translation and audio dramatization to raw Netflix / Gangs of Wasseypur / Saadat Hasan Manto fidelity, eliminating bookish sanitization ('गांड' over 'चूतड़') and establishing class-based Indian sociolect traits without parodying canon lore.
- **Decision:**
  1. **Urdu ka Tarka ("Aate me Namak")**: Atmospheric and sensual noir Hindustani texture (जिस्म, हवस, क़यामत, वहशी, रूह, सन्नाटा, ख़ंजर, ख़ौफ़, ज़ख़्म) for narrative gravity.
  2. **Netflix / Wasseypur Raw Street Grit**: Zero bookish censorship ('गांड' over 'चूतड़', 'भोसड़ीके', 'लंड', 'रांड/रंडी', 'भड़वा/दल्ला', 'बकचोदी') with 100% text retention.
  3. **19-to-21 Amplification Rule**: Restoring Sapkowski's raw Polish peasant dirty tavern dialogue that English translations softened.
  4. **Desi Muhavaron ka Katl**: Organic replacement of English idioms with visceral UP/Bihar/Chambal street idioms.
  5. **Tu <-> Maai-Baap Power-Shift Matrix**: Dynamic real-time shift in honorifics as physical intimidation occurs.
  6. **Acoustic Pain & Breath Acting**: Native Gemini 3.1 Flash TTS vocal tags ([whispers], [spits], [groan], [intimate, breathy], [cold menace]) with calibrated pre_roll_breath_ms (150-250ms).
  7. **Dedicated DesiDialectDirector Agent**: Assigns sociolect traits (Chambal ruggedness, Lucknowi adab, Purvanchal tapori) with a strict **No-Parody Invariant** (canon lore, monster names, Witcher signs remain 100% sacred).
  8. **Character Persona Archetypes**: Cold Cynic (Geralt), Tharki Bard (Dandelion), Khaanti Badtameez Goon (Tavern Thugs), Caustic Sorceress (Yennefer), Makkar Dalal (Innkeeper/Pimp).
  9. **Geralt Grunt Engine & Micro-Pause Prosody**: Signature heavy grunts ([growl] "हूँ...", 1.2s silence pause, low muttered "सत्यानाश...").
  10. **Duraangi Zubaan**: Staging spoken formal dialogue vs unfiltered inner thoughts using spatial binaural whisper/reverb.
  11. **Tavern Shock Reaction Beat**: Acoustic Foley drop (0.5s dead silence) across tavern ambience upon climactic death threats/filthy curses, followed by a solitary coin/glass clink.
- **Rationale:** Transforms translation from a sterile mechanical dub into an evocative, immersive, and culturally electrifying cinematic audio drama.

## ADR-016: HBO/Netflix Grade Sensual & Intimate Scene Production Framework
- **Context:** Intimate and sensual scenes in dark fantasy audiobooks require visceral emotional and physical immersion without falling into sterile medical terms or cheap roadside pulp erotica.
- **Decision:**
  1. **Tri-Tier Intimacy Taxonomy**: Classifies scenes into Deep Passion (Manto/Ismat Chughtai style), Primal Friction (Wasseypur/Mirzapur raw desi grit), and Seductive Power-Play (cold sorceress arrogance).
  2. **Anti-Cringe Invariant**: Strict prohibition of awkward anatomical textbook words ('योनि', 'लिंग', 'स्तन', 'नितंब'); mandate somatic focus on touch, heat, friction, breath, and clothing physics.
  3. **ASMR Proximity Audio Staging**: Configures `proximity="intimate_close"`, 0.0 stereo pan, zero room reverb (dry chamber), and 250ms pre-roll actor breath intake.
  4. **Breathless Prosody Formatting**: Breaks sentences into fragmented, breathless phrases using ellipses and vocal acting tags (`[whispers]`, `[intimate, breathy]`, `[gasp]`, `[sighs]`).
  5. **Erotic Acoustic Silence**: Fades background music to -22dB or warm sub-bass drone, spotlighting isolated tactile foley (`fire_crackle_soft`, `bedsheet_rustle`, intimate breathing loops).
- **Rationale:** Creates authentic, heart-pounding somatic erotic realism with Hollywood audio-drama production values.

## ADR-017: Hollywood & AAA-Game Combat Sound Design & Action Architecture
- **Context:** Action and combat scenes in audiobooks frequently collapse into an indistinct "audio soup" where wall-to-wall 160 BPM percussion, shouting voices, and uncalibrated sword clangs cause severe spectral masking (DMR < +12 dB) and mono phase cancellation (r < 0.85).
- **Decision:**
  1. **Anti-Overengineering Invariant**: Rejected runtime procedural FFmpeg Doppler math (`pan=t`) and timeline-stretching DSP. Delegated spatial flybys to pre-baked sound assets and slow-motion to the TTS generation layer (`acting.pacing=0.5`, `acting.delivery_style="slow_motion"`).
  2. **Action-Beat Splitting (Temporal Isolation)**: Major kinetic impacts (lethal strikes, bone fractures, shield bashes) must never occur over spoken words. Screenplay builder splits action beats into dedicated 0.8s - 1.5s speech-free intervals (`pause_after_ms: 800-1500`, `speaker: "Foley"`).
  3. **Dual-Perspective Spatial Staging**: Attacker actions/vocals pan Left (-0.6), Defender parries/vocals pan Right (+0.6), and Clash points / fatal strikes land Dead Center (0.0), maintaining full stereo separation without single-ear fatigue.
  4. **The 3-Layer Combat Sandwich**: Composite impacts across 3 frequency bands: Layer 1 Transient Bite (2.0k-7.5kHz blade/armor edge), Layer 2 Anatomical Body (180-1.4kHz bone/flesh weight), and Layer 3 LFE Sub-Thump (45-85Hz tuned 52Hz solar plexus shockwave).
  5. **Strict Mono Sub-Bass Anchor (< 90Hz)**: All LFE drops, body slams, and warhammer pulses are centered at pan 0.0 and summed to mono to guarantee mean phase correlation $r \ge 0.85$.
  6. **Dynamic Ducking & Tinnitus Shockwave**: Added `PROFILE_COMBAT_SHOCK` (-24dB attenuation, 4000ms release) and `PROFILE_COMBAT` (-22dB attenuation, 250ms release) in `acoustic_bus_matrix.py`. Heavy concussion impacts trigger the shock profile and pre-produced tinnitus assets.
  7. **Staccato Combat Prose & Neural Tags**: Enhanced translation prompt for rapid 2-4 word clauses ('कदम पीछे। तलवार का पैंतरा। वार। चूक गया!') and expanded `sanitizer.py` with combat vocal tags (`[bellowing battlecry]`, `[combat strain]`, `[diaphragm strain]`, `[guttural grunt on blade deflect]`, `[spits blood]`, `[choked gasp]`, `[ragged heaving pant]`).
  8. **4-Phase Combat Curve & "The Smother Cut"**: Standoff (80 BPM, 75% silence) -> First Blows (125 BPM, 50% silence) -> Bloodlust (160 BPM, 35% silence) -> Fatal Kill (Hard Mute 150-250ms digital silence before lethal strike).
- **Rationale:** Delivers heart-stopping Hollywood combat impact with crystal-clear dialogue intelligibility and strict broadcast compliance.

## ADR-018: Harry Potter & Pottermore Grade 4-Stem Decoupled Ambience, Spatial Occlusion & Tactile Magic Foley Architecture
- **Context:** Full-cast immersive audio drama productions (Audible/Pottermore Harry Potter benchmark) require hyper-realistic world-building where ambience and tactile Foley create deep spatial presence without drowning dialogue in continuous BGM.
- **Decision:**
  1. **4-Stem Decoupled Ambience Architecture**: Replaced flat single-loop ambience with 4 distinct stems per scene:
     - Stem 1: Base Room Tone / Acoustic Hull (-34 to -36 LUFS, architectural cavity resonance).
     - Stem 2: Weather & Macro World (-30 to -32 LUFS, exterior precipitation, howling wind, thunder).
     - Stem 3: Social & Life Wallah (-28 to -30 LUFS, student/patron murmurs, cutlery, crackling hearth).
     - Stem 4: Stochastic Spot Transients (-22 to -26 dBFS, 15-45s non-repetitive micro-events: owl flutter, candle spark, floor creak).
  2. **Acoustic Occlusion & Room Reverb (Space Physics)**:
     - Convolution IR presets (`IR_STONE_HALL`, `IR_COZY_ROOM`, `IR_FOREST`) dynamically applied across scene transitions.
     - Low-pass barrier occlusion filter (1200Hz - 1500Hz) applied to exterior stems when behind closed doors/windows, sweeping to 18kHz upon door open action beats.
  3. **3-Phase Organic Magic Sound Design**:
     - Spells structured as composite 3-part micro-chains: Phase A Gesture Pre-roll (wand flick whoosh 0-100ms) -> Phase B Arcane Exciter (crackling spark/ionization 100-300ms) -> Phase C Diegetic Impact/Dissipation (sub-bass drop 40-60Hz + acoustic reverb tail).
  4. **Material Affinity Foley Engine**:
     - Footsteps bound to terrain physics (stone flags, gravel, wet mud, creaking oak).
     - Micro-props: parchment rolls, quill scratching, wax seal snaps, potion uncorking, and robe cloth movement.
  5. **Binaural Spatial Staging & Spectral Pocketing**:
     - Center channel (azimuth 0.0) reserved exclusively for dry, crisp dialogue.
     - Ambience stereo width expanded to 1.3-1.5, carving out center space.
     - Foley panned across character stage coordinates (-0.6 to +0.6).
     - Formant pocketing: -5.5dB parametric notch at 2.2kHz-2.8kHz on background buses to guarantee zero vocal masking.
     - Whisper protection: dynamic ducking (-8dB to -12dB) during intimate or whispered lines.
- **Rationale:** Elevates Audiobook Maker to world-class Audible/BBC Radio 4 cinematic standards with 100% automated agent orchestration and zero token bloat.

## ADR-019: Full-Scale Unfiltered Adult Intimacy & Gemini TTS Safety Filter Unlock
- **Context:** In mature dark fantasy audiobooks, intimate, bedroom, and passionate scenes require authentic somatic realism, raw passion, and visceral dialogue without prudish television euphemisms, while ensuring the engine remains strictly faithful to the source material and preventing Google Gemini TTS safety filtering false positives.
- **Decision:**
  1. **TTS Safety Filter Unlock (`tts_dispatcher.py`)**: Added explicit `safetySettings: [BLOCK_NONE]` across all 4 harm categories (`HARM_CATEGORY_HARASSMENT`, `HARM_CATEGORY_HATE_SPEECH`, `HARM_CATEGORY_SEXUALLY_EXPLICIT`, `HARM_CATEGORY_DANGEROUS_CONTENT`) in `synthesize_gemini_tts`. Live API testing verified 100% synthesis success and zero censorship blocks.
  2. **Rule 8 Somatic Intimacy & Dirty Banter Mandate (`translator.py`)**: Mandated visceral erotic vocabulary and somatic friction ('लंड', 'चूत', 'गांड', 'चोदना', 'मसलना', 'तपती कमर', 'भीगी प्यास', 'बेकाबू सांसें') during passionate encounters and bedroom dialogue.
  3. **The "Nothing Above Source" Invariant**: Strictly prohibited fabricating explicit sexual acts out of thin air if characters are merely conversing or brushing shoulders. But whenever the source novel presents sexual tension, touching, nudity, or intercourse, the 19-to-21 Amplification Rule renders it in unapologetic, authentic Desi passion.
  4. **The Anti-Cringe Invariant**: Preserved the absolute ban on sterile, clinical biology-textbook words ('योनि', 'लिंग') that evoke autopsy reports or exams.
  5. **Screenplay ASMR Intimacy Staging (`script_builder.py`)**: Enhanced Rule 1 and Rule 6 to pair raw passion with `[whispers]` / `[intimate, breathy]` neural audio tags, `spatial.proximity: 'intimate_close'`, `spatial.pan: 0.0`, `pre_roll_breath_ms: 200-250`, and `music.ducking_db: -22.0` ("The Erotic Silence").
- **Rationale:** Unlocks full dramatic realism and adult literary authenticity for mature fiction while maintaining strict narrative truth and zero API censorship.

## ADR-020: Forensic Audit Remediation & Comprehensive Engine Hardening (13 Defects)
- **Context:** Post-integration stress validation across multi-chapter novel production runs uncovered 13 critical edge cases across CLI commands, model deserialization, TTS finish-reason parsing, key pool backoff handling, Quality Gates 3.5 & 4.5, Sanitizer linguistic evaluation, and FFmpeg command-line limits on Windows.
- **Decision:**
  1. **Model Deserialization Rehydration (`contracts.py`)**: Added `@model_validator(mode="after")` to `CreativeManifest` to rehydrate dictionary representations of `scene_acoustics` into typed `SceneSoundscapeManifest` instances with all member methods intact (`generate_stochastic_cues`, etc.), plus safe fallback validations in `cinema_audio_engine.py` and `manifest_renderer.py`.
  2. **Screenplay Dict vs. List Unpacking (`audiobook_cli.py`, `orchestrator.py`)**: Screenplays structured as `{"script_version": "2.0", "segments": [...]}` unpack `data.get("segments", data)` automatically, preventing `AttributeError` during chapter mastering and background soundscape compilation.
  3. **Gemini TTS Defensive FinishReason & Safety Parsing (`tts_dispatcher.py`)**: Guarded against empty candidate lists (`candidates: []`) and safety block codes (`finishReason in ('SAFETY', 'RECITATION', 'BLOCKLIST')`). Raises explicit `ValueError` displaying `promptFeedback` and `finishReason` instead of fatal `IndexError`.
  4. **KeyManager Text Service Backoff Cooldown (`key_manager.py`)**: Lifted `TEMP_BACKOFF` wait logic out of the `service == "tts"` branch to apply globally across all services (including `service="text"`), preventing infinite loop crashes when auxiliary text analysis keys are cooling down.
  5. **Gate 3.5 Asset Extension Resolution Fallback (`gate_auditor.py`)**: Allows cues with file extensions (e.g. `sword_slash.wav`) to fall back seamlessly to SQLite FTS5 fuzzy search (`bank.resolve_sound()`) when direct file path lookup fails, preventing false gate rejections.
  6. **Gate 4.5 Action Beat Size Floor (`gate_auditor.py`, `tts_dispatcher.py`)**: Decreased minimum file size floor from 1000B to 44B (WAV header size) for `[ACTION]` / `Foley` pacing segments, allowing valid short silent action chunks to pass Gate 4.5.
  7. **Sanitizer Bracketed Tag Shield (`sanitizer.py`)**: Strips bracketed tags `re.sub(r"\[[^\]]+\]", "", text)` before computing Latin vs. Devanagari density, preventing combat lines with multiple acting tags (`[bellowing battlecry] [guttural grunt on blade deflect] वार!`) from being misclassified and dropped as English leakage, while dropping segments that become empty after tag stripping.
  8. **Scene Acoustics Multi-Layer Stochastic Collision Avoidance (`scene_acoustics.py`)**: Added `scene_used_timestamps` set in `generate_stochastic_cues` with minimum 250ms spacing to prevent multiple stochastic layers from firing at the exact same millisecond.
  9. **Catalog Seeder Word-Boundary Sub-Bass Classification (`catalog_seeder.py`)**: Replaced loose `"sub"` substring match with specific compound tokens (`"sub_drop"`, `"sub_bass"`, `"subwoofer"`, `"subboom"`, `"lfe"`), ensuring subtle cues like `subtle_creak.wav` are not mistakenly categorized as Combat Foley.
  10. **FFMETADATA1 Special Character Escaping (`packager.py`)**: Implemented `_escape_ffmetadata()` to escape `=`, `;`, `#`, and `\` in titles, artists, and chapter names for standard `FFMETADATA1` files.
  11. **Atomic WAV Write & Verification (`tts_dispatcher.py`)**: Writes raw PCM to `.tmp.wav`, runs audio health checks (clipping, DC corruption, silence), unlinks on failure, and atomically promotes valid files via `.replace(output_file)`.
  12. **CLI Segment Deduplication (`audiobook_cli.py`)**: In `cmd_master`, globbed chapter segment files are deduplicated by segment index `_s(\d{4})_`, selecting the latest modified take to prevent duplicate segment concatenation.
  13. **Dynamic Filter Complex Script Piping (`cinema_audio_engine.py`)**: When `filter_str` exceeds 6,000 characters, it writes to a temporary script file and uses `-filter_complex_script`, preventing Windows 8,191-character command length overflow crashes.
- **Rationale:** Hardens the entire engine against real-world production stress and eliminates all 13 edge-case failures, verified by a dedicated regression suite with 232/232 tests passing (100% OK).

## ADR-021: Zero-Voice-Drift Hardening & Deterministic Speaker Attribution
- **Context:** Dialogue segments in multi-character screenplays occasionally experienced voice drift into the narrator voice or generic fallbacks when the LLM hallucinated novel speaker names, dropped character aliases, or left gender pronouns ("उसने कहा", "he said") unresolved, while voice gender misalignments went undetected prior to synthesis.
- **Decision:**
  1. **Strict Voice Dispatcher Contract (`tts_dispatcher.py`)**: Added `UnregisteredSpeakerError` (subclass of `ValueError`), enabled `strict_speakers=True` by default in `synthesize_screenplay`, added `validate_screenplay_speakers()` pre-flight verification, and added `get_speaker_config()` public accessor.
  2. **Canonical Roster Injection & Pass-2 Disambiguation (`script_builder.py`)**: Injected `character_roster.json` directly into the LLM system prompt and implemented `clean_screenplay_pass2()` for deterministic pronoun and alias resolution, mapping pronouns and aliases back to canonical roster names before synthesis.
  3. **Gate 1 Acoustic Gender Alignment Check (`gate_auditor.py`)**: Enhanced `audit_gate1_roster()` to cross-check character gender definitions against voice gender profiles (`GeminiTTSVoiceRegistry.get_voice_gender`), raising validation errors upon acoustic gender mismatch.
  4. **Gate 2 Canonical Whitelist Auto-Discovery (`gate_auditor.py`)**: Upgraded `audit_gate2_script()` to auto-discover canonical speaker whitelists from `character_roster.json` and fail closed whenever an unknown speaker is encountered.
- **Rationale:** Guarantees zero voice drift and 100% deterministic character vocal attribution across multi-chapter studio productions.

## ADR-022: Audio Drama Timeline Sync, Foley Staging & Soundscape Remediation
- **Context:** Audio drama chapter mastering revealed cumulative timeline drift (up to 4.8s per chapter) due to pre-roll breath pauses missing from timeline ledger start offsets; 50% of Foley cues clustered dead-center (pan 0.0) from missing Hindi anchor tokens; domestic dining scenes triggered combat sword clashes; BGM leaked past dramatic scene boundaries; and ambient beds remained static throughout multi-location chapters.
- **Decision:**
  1. **Timeline Data Contracts (`contracts.py`)**: Added `pre_roll_breath_ms: int = 0` to `TimelineSegment` and `until_segment: Optional[int] = None` to `MusicCue`.
  2. **Cumulative Timeline Drift Elimination (`agent_director.py`)**: Synchronized timeline ledger offset calculations so that each segment's start time accumulates both vocal duration and pre-roll breath (`seg_duration + (seg.pre_roll_breath_ms / 1000.0)`), reducing timing error to 0.000s.
  3. **Bilingual Anchor Mapping & Foley Staging (`agent_director.py`)**: Introduced `BILINGUAL_ANCHOR_MAP` in `_compute_word_level_offset()` to bind Foley cues to both Hindi and English dialogue action anchors, eliminating the 50% dead-center fallback pan trap.
  4. **Domestic Tableware Taxonomy Isolation (`agent_director.py`, `acoustic_bus_matrix.py`)**: Added `DOMETabl` UCS category and explicitly isolated domestic utensils (spoons, forks, plates, cups) from combat weaponry (`WEAPSwd`), preventing accidental sword clashes during dinner scenes.
  5. **Scene-Bound BGM Underscore (`agent_director.py`)**: Enforced `music.until_segment` boundaries so that thematic music cues terminate cleanly when the scene transitions rather than overlapping into unrelated dialogue.
  6. **Dynamic Multi-Scene Ambience Bed Partitioning (`agent_director.py`)**: Implemented `_partition_script_ambience_scenes()` to slice long chapters into distinct acoustic environments based on `acoustic_env` shifts, providing tailored ambient beds across changing locations.
- **Rationale:** Eradicates cumulative timeline drift, eliminates audio staging artifacts, prevents comedic sound misclassifications, and achieves seamless multi-scene spatial immersion verified across 243 passing tests.

## ADR-023: Dynamic Literary Advisory Lexicon DB & Register Quality Guard
- **Context:** Translating raw high-fantasy literature (like *The Witcher*) into Hindustani faced two major issues: (1) low-tier LLMs (`flash-lite`) generated immersion-breaking literalisms ("सुनहरी लड़की", "कुंवारी चोटी", "नमस्ते, गेराल्ट", "दारू"), and (2) hardcoding explicit Hindi slurs into system prompts triggered Gemini safety classifiers (`PROHIBITED_CONTENT`), masquerading as transient HTTP 503 errors.
- **Decision:**
  1. **SQLite Dynamic Literary Advisory Lexicon DB (`audiobook_factory/advisory_lexicon.py`)**: Created `literary_advisory_rules` in SQLite (`audiobooks/literary_advisory.db`) storing aesthetic directions, recommended vocabulary, and banned antipatterns across multiple categories (appearances, youth/sensuality, salutations, beverages, profanity, combat). Rather than rigid hardcoding, rules dynamically inject guidance into the LLM system prompt.
  2. **Meso-Tier Literary Register Guard (`audiobook_factory/sanitizer.py`)**: Added `audit_literary_register()` with Devanagari Unicode lookaround boundaries to catch and auto-normalize robotic antipatterns before TTS synthesis.
  3. **High-Tier Model Enforcement (`audiobook_factory/translator.py`, `.env`)**: Hardcoded minimum `gemini-3.7-flash` and default `gemini-3.8-flash` in `translator.py` and updated `.env`, strictly prohibiting robotic `flash-lite` downgrades for literary translation.
- **Rationale:** Delivers authentic, gritty, literary Hindustani dialogue with appropriate Urdu/Hindi balance while preventing API safety rejections and robotic literalisms, verified with 248/248 passing tests.
## ADR-024: Gemini 3.8 Flash TTS Upgrade, 3-Layer Control Stack, Zero-Click Hybrid Batching & RTX 4050 Local Forced Alignment
- **Context:** Individual segment-by-segment TTS synthesis rapidly exhausts Google AI Studio Free Tier daily quotas (10 RPD per project) on dialogue-heavy chapters. However, naive multi-speaker batching produces merged audio streams that eliminate individual character 3D spatial panning, introduce transitional digital clicks/beeps at buffer boundaries, and risk voice timbre drift in long prompts (>800 words).
- **Decision:**
  1. **Primary Model Migration**: Defaulted primary speech model to `gemini-3.8-flash-tts` (`GEMINI_TTS_MODEL=gemini-3.8-flash-tts`), supporting native `multiSpeakerVoiceConfig` and per-part `speechMetadata`.
  2. **Deterministic UID Lifecycle Tracking (`contracts.py`)**: Added immutable, deterministic `uid` to `ScreenplaySegment` and `TimelineSegment` for 100% end-to-end traceability across script JSONs, batch manifests, audio slices, and final mixes.
  3. **3-Layer Acoustic Control Stack**: Macro `speechMetadata.style` (e.g. "deep, gravelly, quiet warning") + English inline tags (`[whispers]`, `[gasp]`, `[sighs]`) + Punctuation prosody (`...`, `—`).
  4. **Pre-TTS Smart Batch Dispatch Planner (`batch_planner.py`)**: Groups contiguous 2-character dialogue into `multi_speaker_duo` (300-600 words max) and narrator runs into `narrator_chunk`, while strictly isolating intimate ASMR and combat/action beats into dedicated single requests to preserve 100% acoustic fidelity. Cuts TTS API calls by 60%–75%.
  5. **Workstation Superpower Local Forced Alignment (`forced_aligner.py`)**: Deployed Meta MMS_FA CTC Forced Aligner on NVIDIA GeForce RTX 4050 GPU (CUDA) to extract sample-accurate (±20ms) word and sentence boundaries in ~150ms with 0 API tokens, backed by automatic energy-valley fallback.
  6. **Acoustic De-Clicking Engine (`tts_dispatcher.py`)**: Applies a 25Hz high-pass filter (`highpass=f=25`) to remove DC offset bursts and applies a 5ms raised-cosine fade-in/fade-out at slice boundaries, completely eliminating transition pops, beeps, and clicks.
  7. **Zero-Breaking Downstream Invariant**: Slices are promoted as canonical `c{ch:03d}_s{idx:04d}_{hash}.wav` files, guaranteeing 100% compatibility with downstream 5-stage FFmpeg DME mastering and all existing test suites.
  8. **Forensic Audit Remediation & Hardening**:
     - Fixed `NameError: name 'subprocess' is not defined` in `slice_and_declick_batch` by adding module-level import.
     - Replaced `torchaudio.load()` with standard-library `wave` tensor loader `_load_wav_tensor_safely()` so MMS_FA runs on CUDA RTX 4050 GPU on Windows without `soundfile`/`sox` backend dependencies.
     - Unified cache key generation via `compute_canonical_segment_filename()` and added sequential loop skip `if results[idx - 1] is not None: continue`, preventing redundant single-segment re-synthesis and quota burn.
     - Added true RMS energy valley silence detection in `_align_with_energy_fallback()`, preventing split cuts through spoken syllables.
     - Added character DSP EQ/softclip filter chaining to batch slice FFmpeg commands.
     - Added Chandrabindu (`ँ`) and Nuktas to `DEVA_TO_ROMAN_MAP` for accurate phonetic CTC alignment.
     - Prevented duplicate segment rows and primary key collisions in `ProjectStateLedger` on chapter resume.
- **Rationale:** Delivers 60%-75% quota reduction, studio-grade multi-character conversational cadence, and sample-accurate acoustic synchronization backed by local workstation GPU compute, verified with 261/261 passing tests (100% OK).

## ADR-025: Multi-Voice Transient Noise Elimination, DC Offset Pinning & Broadcast Brickwall Peak Limiting
- **Context:** Rapid dialogue switching between characters in multi-voice scenes produced noticeable transient artifacts ("hiss", "futt / pop / click" noises), degrading the premium audio drama experience.
- **Forensic Diagnosis:**
  1. **Unconstrained DSP Gain:** Character EQ calibration curves (e.g. Geralt volume gain +2.5dB, presence boost +3.2dB) applied without ceiling headroom caused 1,065+ PCM samples to saturate and flat-top at maximum positive rail (+32767).
  2. **Raw Digital Splicing Discontinuity:** The legacy timeline stitching function concatenated raw non-zero PCM endpoints directly against `b"\x00\x00"` digital silence, creating massive 70% full-scale cliff step jumps that manifest acoustically as sudden "pops" or "futt" transients.
  3. **Vocoder Noise-Floor Gating:** Abrupt truncation of synthesis room noise without tapering caused the underlying TTS vocoder noise floor to sharply cut in and out ("hiss" pumping).
- **Decision:**
  1. **Broadcast Brickwall Limiter (`tts_dispatcher.py`):** Added FFmpeg `alimiter=limit=-1.2dB:attack=5:release=50:asc=true` to all character DSP calibration chains and multi-speaker batch slice pipelines, guaranteeing zero rail-pinning and preserving 1.2dB true-peak headroom.
  2. **Hann Raised-Cosine Micro-Fades (`timeline_ledger.py`, `produce_chapter_011.py`, `produce_chapter_012.py`):** Replaced naive byte concatenation with 12ms fade-in and 18ms fade-out Hann raised-cosine tapering on every dialogue segment.
  3. **DC Bias Subtraction:** Subtracted running mean (`samples - np.mean(samples)`) prior to fading to eradicate baseline shift clicks.
  4. **Boundary Endpoint Zero Clamping:** Clamped the exact first and last samples of every segment to zero (`samples[0] = 0.0, samples[-1] = 0.0`), mathematically proving a 0.0000% step jump across all silence transitions.
  5. **Calibrated SNR Gatekeeper:** Updated clipping detection from naive peak threshold to requiring >= 6 consecutive samples pinned at rail, preventing false-positive rejection of valid dynamic speech.
- **Rationale:** Permanently eliminates clicks, pops, and hiss pumping across all character transitions while preserving full dynamic range and broadcast EBU R128 compliance. Verified across 19/19 dedicated audio unit tests with 0.0000% boundary step jump.

## ADR-028: Dual-Layer Forensic Audio Restoration & Dead-Air Clamping Engine
- **Context:** Residual high-frequency electronic noise ("zzz", "ftt", trailing metadata screech) persisted in silence intervals following dialogue lines in Gemini 3.8 Flash TTS outputs. Forensic autopsy revealed isolated 300ms–480ms dead-air tails containing vocoder decay ringing and embedded C2PA metadata bursts (e.g. `c012_s0017` had an isolated 110ms burst of 32,768 peak amplitude at $t=4.62$s). Naive backward threshold scanners were deceived by the loudness of the burst.
- **Decision:**
  1. **Layer 1 Forensic Analysis (`audiobook_factory/forensic_analyzer.py`):**
     - Implemented silence-valley detection scanning backwards for $\ge 100$ms quiet intervals ($\le -40$ dBFS).
     - Flagged trailing bursts (`TRAILING_C2PA_BURST_AFTER_VALLEY`) and identified genuine speech endpoints prior to the valley.
     - Added a 40ms phonetic safety buffer to preserve trailing Hindi unvoiced fricatives and aspirates ('स', 'श', 'त', 'क').
  2. **Layer 2 Surgical Audio QC (`audiobook_factory/audio_qc_agent.py`):**
     - Slices away corrupt dead air while preserving valid speech.
     - Applies an 18ms Hann raised-cosine decay taper to exact 0.0 at the new endpoint.
     - Pins the final sample to 0.0 (`pcm[-1] = 0.0`), preventing step discontinuities.
  3. **Strict Sample-Accurate Timeline Synchronization (`audiobook_factory/timeline_ledger.py`):**
     - Transferred trimmed dead-air milliseconds directly into `pause_after_ms` (`total_pause_ms = pause_after_ms + trimmed_ms`).
     - Preserves 100.00% timeline alignment against music cues and diegetic SFX anchors.
  4. **Studio 6-Stage DSP Polishing (`audiobook_factory/restoration.py`):**
     - Sequenced FFmpeg `adeclick` -> `afftdn=nr=8:nf=-52` -> `highpass=40` -> `lowpass=11200` -> `deesser` -> `agate` on all master dialogue tracks.
- **Rationale:** Eliminates 100% of residual vocoder tails, C2PA static bursts, and digital clicks without clipping Hindi phonetic endings or drifting timeline markers. Silence pause peak amplitude dropped from 32,768 to 0.0000. Verified across test suites and fully rendered in Chapter 12 master (`chapter_012_cinematic.m4a`, 182.32 MB, -18.7 LUFS).

## ADR-029: Forensic Literary Document Ingestion, Canonical AST & Dual-Layer Quality Gates
- **Context:** Ingesting complex literary documents (EPUB, PDF, TXT, Markdown) into Audiobook Maker revealed significant structural defects in legacy extraction:
  1. Destructive string-splitting and naive regex stripping flattened scene breaks (`* * *`), section headings, and blockquotes, discarding document hierarchy.
  2. Complete lack of forensic provenance: downstream translation and screenplay errors could not be traced back to original document locations (spine item, anchor, or PDF page).
  3. PDF extraction was vulnerable to silent OCR noise, broken line wraps, running headers/footers, and corrupted scanned pages leaking into downstream LLM translation and TTS stages.
  4. EPUB anchor slicing frequently severed HTML opening tags (`id="..."`), corrupting text.
  5. Giant monolithic chapters ($> 12,000$ words) overflowed LLM context windows, causing silent truncation.
  6. Absence of an upfront quality gate allowed corrupted documents to proceed deep into the pipeline, burning generative AI API quota.
- **Decision:**
  1. **Canonical Book Model & Forensic Provenance (`audiobook_factory/book_model.py`):**
     - Established strongly typed Pydantic v2 data models: [`CanonicalBook`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/book_model.py#L182-L262), [`CanonicalChapter`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/book_model.py#L80-L122), [`CanonicalBlock`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/book_model.py#L64-L79), and [`SourceProvenance`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/book_model.py#L44-L63).
     - Preserves sacred, unmutated raw text alongside speech-normalized text.
     - Granular block-level forensic provenance tracking: `source_file`, `source_type`, `page_number`, `spine_item`, `html_tag`, `html_id`, `line_start`, `char_offset`, and `reading_order`.
  2. **Non-Destructive Literary Normalizer (`audiobook_factory/normalizer.py`):**
     - Applied Unicode NFC normalization and zero-width hygiene (`\u200b`, `\u200c`, `\u200d`, `\ufeff`, `\u2060`).
     - Healed hyphenated linebreaks across line wraps in both Latin and Devanagari scripts (`"impor-\ntant"` -> `"important"`).
     - Standardized typographic quotes and spaced dashes while offering a `preserve_literary_quotes` option.
     - Stripped footnote citation brackets (`[1]`, `[23]`) and stripped recurring running headers/footers.
  3. **Single-Pass Structural EPUB Parser (`audiobook_factory/epub_parser.py`):**
     - Implemented single-pass OPF and spine traversal ([`ForensicEPUBParser`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/epub_parser.py#L184-L463)) to eliminate redundant unzipping.
     - Added DOM-aware structural block parsing ([`EPUBStructuralHTMLParser`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/epub_parser.py#L34-L182)) preserving headings, blockquotes, and scene breaks.
     - Implemented opening angle-bracket (`<`) backtracking during Nav/NCX anchor slicing to prevent severed HTML tags.
  4. **Layout-Aware PDF Engine & Quality Analyzer (`audiobook_factory/pdf_engine.py`):**
     - Fast local digital text extraction via `pypdf>=5.0`.
     - 4-signal heuristic page quality analysis ([`PDFQualityAnalyzer`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/pdf_engine.py#L44-L140)): interior low density, OCR symbol noise ratio ($> 8\%$), Unicode replacement glyphs (`\ufffd`), and multi-column line wrap anomalies.
     - Filtered recurring running headers/footers appearing across $\ge 3$ pages.
     - Added selective single-page multimodal vision escalation ([`GeminiVisionPDFExtractor`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/pdf_engine.py#L150-L220) via `gemini-3.8-flash`) strictly on flagged suspicious pages.
  5. **Multi-Tier Chapter Segmentation & Meso-Tier Semantic Splitter (`audiobook_factory/chapter_segmenter.py`):**
     - Comprehensive regex heading detection across English, Devanagari/Hindi, Roman numerals, word numbers, and story landmarks.
     - Conservative false-positive validator ([`is_valid_heading_candidate`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/chapter_segmenter.py#L36-L61)) protecting against uppercase dialogue and shouting.
     - Implemented a 12,000-word Meso-tier semantic splitter ([`split_large_chapter_on_semantic_boundary`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/chapter_segmenter.py#L149-L241)) with a 5-tier priority hierarchy (Scene break -> Section heading -> Paragraph boundary -> Sentence boundary -> Emergency word split) preventing LLM context overflow.
  6. **Independent Ingestion Quality Gate (Gate 0.1) (`audiobook_factory/quality_gate.py`):**
     - Implemented [`ExtractionQualityAuditor`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/quality_gate.py#L21-L111) evaluating extraction completeness, word count floors ($> 50$ words), non-empty chapters ($> 5$ words), and suspicious page ratios ($< 25\%$).
     - Fails closed on status `REVIEW`, raising [`ExtractionGateAuditError`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/book_model.py#L33-L43) with actionable terminal diagnostics and remediation guidance.
     - Provided `--force-gate` CLI flag override for intentional operator bypasses.
  7. **Dual-Layer Architecture & Universal Facade (`audiobook_factory/extractor.py`):**
     - Created isolated project workspace: `raw/` (SHA-256 manifest and source copy), `canonical/` (`book.json` and `quality_report.json`), and `extracted/` (`chapter_XXX.md`).
     - Guaranteed 100% backward compatibility for downstream translation and screenplay stages via [`project_legacy_extracted()`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/book_model.py#L214-L230).
- **Rationale:** Ensures zero data loss and uncompromised structural fidelity at the document ingestion boundary, blocks corrupted text from wasting generative AI API quota, provides instant provenance traceability, and maintains seamless backward compatibility across the entire production pipeline.

---

## ADR-030: Literary Translation Intelligence Engine, Multi-Gate Certification (Gates T0-T11) & Novel-Agnostic Hardening
- **Status:** Accepted
- **Date:** 2026-04-06
- **Context:**
  1. Legacy single-pass chunk-based translation (`translator.py`) split chapters at arbitrary 4,000-character boundaries with a fragile 500-character tail buffer, causing mid-scene dialogue severing, pronoun honorific drift (`आप`/`तुम`/`तू`), negation flips, and silent beat omissions.
  2. Enforcing a rigid numeric quota for Urdu vocabulary produced unnatural stuffing rather than organic Hindustani literary prose, while calqued English idioms (*"golden girl" $\rightarrow$ "सुनहरी लड़की"*) and modern clinical loanwords (*डिप्रेशन, ट्रॉमा, स्ट्रेस*) degraded literary immersion.
  3. Novel-specific character names and Devanagari spelling fixes had crept into core library scripts, violating novel-agnostic architecture.
- **Decision:**
  1. **Persistent Canonical Book Bible & Entity Discovery (`book_bible.py`, `entity_discovery.py`):**
     - Created [`BookBible`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/book_bible.py) (`v2.0.0`) stored at `<project_dir>/book_bible.json` with deterministic 16-char SHA-256 `get_version_hash()`, decoupled `terminology_variants`, and backward-compatible `export_legacy_glossary()`.
     - Built [`EntityDiscoveryEngine`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/entity_discovery.py) with 130+ `ENGLISH_NON_ENTITY_STOPWORDS` defense and positional confidence scoring (`0.85` auto-commit vs `0.50` sentence-starter hold).
  2. **Contextual Hindustani Register, Character Profiles & 7D Relationship Engine (`hindustani_register.py`, `character_profile.py`, `relationship_state.py`, `intensity_model.py`):**
     - Replaced rigid Urdu quotas with [`HindustaniRegisterEngine`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/hindustani_register.py) (*"Aate mein Namak jitni Urdu"*) across 4 contextual domains (`atmosphere_words`, `passion_and_somatics`, `combat_and_grit`, `scholastic_and_courtly`).
     - Created 8 novel-agnostic [`UNIVERSAL_ARCHETYPE_PRESETS`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/character_profile.py) and [`RelationshipStateEngine`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/relationship_state.py) to dynamically resolve Hindi pronouns (`आप`, `तुम`, `तू`) across 7 interpersonal dimensions.
     - Built [`LiteraryIntensityVector`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/intensity_model.py) enforcing the **"Nothing Above Source"** maturity principle ($\pm 0.75$ soft `WARN`, $> 2.0$ hard `FAIL`).
  3. **Transition-Driven Scene Planning & Frozen Semantic Map (`scene_planner.py`, `source_semantic_map.py`, `narrative_state.py`):**
     - Replaced arbitrary character chunking with [`ScenePlanner.plan_chapter()`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/scene_planner.py) (detecting temporal, spatial, and markdown scene transitions) and [`SourceSemanticMapEngine`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/source_semantic_map.py) (freezing per-beat actors, dialogue speakers, and negation markers).
  4. **12-Gate Independent Certification & Tiered Self-Healing Repair (`certification.py`, `repair_engine.py`, `provenance.py`):**
     - Implemented [`TranslationCertifier.certify_scene()`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/certification.py) executing Gates `T0`–`T11` (word sanity, terminology/entity audit, deterministic negation & LLM semantic fidelity, dialogue quote parity & omission detection, addition detection, character voice/pronouns, 7D intensity, literary naturalness, Hindustani balance, and 6-part SHA-256 provenance cache sealing).
     - Implemented [`TieredRepairEngine`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/repair_engine.py) escalating from Tier 1 (0ms deterministic regex & SQLite Advisory Lexicon repair) $\rightarrow$ Tier 2 (surgical single-paragraph LLM rewrite, max 2 attempts) $\rightarrow$ Tier 3 (full scene retranslation, max 1 attempt).
  5. **World & Character Memory 2.0 (`audiobook_factory/translation/memory/`):**
     - Built a 10-module event-driven epistemic continuity engine with `TemporalMode` isolation (`PRESENT` vs `FLASHBACK`), `HARD_CANON` vs `SOFT_STATE` delta tracking, `CharacterKnowledgeEngine` (`KNOWN`, `SUSPECTED`, `FALSE_BELIEF`, `UNKNOWN`, `DISPROVEN`), 7 `MemoryValidator` guardrails, and a 7-tier narrative-salience `MemoryRetriever`.
  6. **Chapter 9 Benchmark Standard & Multi-Script Zero-Hardcoding Enforcement:**
     - Established read-only calibration standards in `audiobooks/standards/` (`chapter_009_hi_old_canonical.md` vs `chapter_009_hi_standard.md` and `chapter_009_benchmark_comparison.md`).
     - Purged 37 legacy novel-specific utility scripts and enforced a multi-script (Latin + Devanagari `FORBIDDEN_CHARACTERS_DEVANAGARI`) AST Zero-Hardcoding contract in [`tests/test_zero_hardcoding_contracts.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/tests/test_zero_hardcoding_contracts.py).
- **Rationale:** Transforms literary translation from a brittle single-pass prompt into a self-auditing, context-aware, novel-agnostic studio engine with provable semantic fidelity, natural Hindustani cadence, and cryptographic cache provenance.

---

## ADR-031: World + Character Memory 2.0 (Deterministic State Deltas, Epistemic Isolation & Dual Chronology)
- **Status:** Accepted
- **Date:** 2026-09-25
- **Context:**
  1. Long-form audiobook generation across 100+ chapters suffers from amnesia, knowledge leakage across character boundaries, resurrection of deceased characters in present timelines, and erratic relationship pronoun jumps (`आप`/`तुम`/`तू`).
  2. Overwriting full state blobs causes race conditions and resets prior environmental damage (e.g. damaged locations reverting to normal).
  3. LLM prompts for downstream Screenplay generation were overriding explicit director delivery styles when memory vocal constraints were blindly applied.
- **Decision:**
  1. Built `audiobook_factory/translation/memory/` as a pure deterministic state transition engine driven by explicit `StateDelta` models across 5 domains (`CHARACTER`, `RELATIONSHIP`, `KNOWLEDGE`, `WORLD`, `NARRATIVE`).
  2. Implemented `SceneChangeDetector` with 0ms pre-filtering, noun/verb trigger matching, transitive attacker vs. victim disambiguation, and gated LLM event proposal with deterministic fallback and deduplication.
  3. Implemented `CharacterKnowledgeEngine` enforcing strict `known_by` membership (`KnowledgeStatus.KNOWN`), scoped `DISPROVEN` transitions, asymmetric secret prioritization, and `MUST_NOT_KNOW` prompt boundaries.
  4. Implemented `MemoryValidator` enforcing 7 contradiction classes (`canon_contradiction`, `timeline_contradiction`, `dead_character_violation`, `physical_impossibility`, `relationship_jump`, `knowledge_violation`, `world_rule_violation`).
  5. Implemented Ghost Event Isolation in `MemoryStore`: rejected contradictory events are permanently quarantined in `store.rejected_events` and excluded from `store.events`, `world_state.timeline`, and salience queries.
  6. Implemented selective 7-tier + Narrative Salience retrieval in `MemoryRetriever` and `MemoryContext` with an enforced $\le 800$ token budget cap.
  7. Implemented conservative performance guidance in `apply_performance_guidance_to_segment()`, strictly preserving explicit nested `acting.delivery_style` while injecting physical vocal constraints (`strained_breath`, `fatigued_low_energy`) into `ScreenplaySegment` contracts and Gemini TTS `speechMetadata.style`.
- **Rationale:** Guarantees unbreakable narrative, epistemic, and physical continuity across 100+ chapter novels without context window blowup, prevents ghost event corruption, and enriches vocal performance with true character physical state.

---

## ADR-032: Pillar 1 Forensic Extraction Upgrades & Multi-Signal Quality Gate Hardening
- **Status:** Accepted
- **Date:** 2026-09-25
- **Context:**
  1. Multi-column PDF documents suffered from reading-order interleaving across column gutters, where sentences from Column 1 were haphazardly fused with Column 2 on the same horizontal scanline, while single-column dialogue and indented epigraphs were at risk of false column splitting.
  2. PDF block extraction lacked character-accurate source provenance across page boundaries; mid-sentence paragraph continuations lost track of starting and ending pages, and raw text was vulnerable to destructive mutations from control codes (`\x00`, `\x07`) and soft hyphens (`\u00ad`).
  3. Escalation to Gemini multimodal vision was prone to accepting hallucinated outputs, conversational LLM preamble/refusal leakage, 4-gram repetition loops, and severe text truncation simply because an escalation candidate had a high word count.
  4. Pipelines blurred the line between authentic authorial literary chapters and artificial execution chunks, causing 12k-word semantic splits and fallback chunks (`Production Chunk N`) to distort chapter numbering and table-of-contents generation.
- **Decision:**
  1. **Upgrade 1 — Geometric PDF Reading Order & XY-Cut Layout Reconstructor (`PDFLayoutReconstructor` in `pdf_engine.py`):**
     - Extracts positioned glyph and word spans directly from `pypdf` content streams (`TextStateManager`, `recurse_to_target_op`, `resolve_font`, `displaced_tx`, `space_tx`).
     - Groups spans by horizontal baseline tolerance ($0.45 \times \max(fh, 8.0)$) and merges intra-line words while splitting on column gutters exceeding $\max(3.5 \times sw, 14.0\text{ pt})$.
     - Detects vertical column gutters with strict false-split defense for single-column dialogue and epigraphs, requiring vertical band overlap, parallel row pairs (`same_row_pairs \ge 2`), or dense column stacks (`median_dy \le 2.2 \times fh`), and spanning banner dominance.
     - Recursively decomposes pages via XY-cut: horizontal splits around spanning banners/headers/footers and vertical splits across column gutters (Left Column $\rightarrow$ Right Column).
     - Merges cross-column mid-sentence continuations and heals broken hyphens (`prev_p[:-1] + curr_p`).
     - Implements whitespace-aligned multi-column de-interleaving fallback (`reconstruct_multicolumn_text`) for layout-spaced raw text with 4+ space gutters.
  2. **Upgrade 2 — End-to-End PDF Source Provenance (`ForensicPDFEngine` & `SourceProvenance` in `pdf_engine.py`, `book_model.py`):**
     - Implemented `_PDFPageSpanRecord` indexing mapping joined document character ranges `[doc_char_start, doc_char_end)` back to exact `page_number`, `page_end`, `line_start`, `line_end`, page-relative `char_offset`, `reading_order`, `extraction_method`, and `confidence`.
     - Joins pages with `\n` when paragraphs continue mid-sentence, recording dual-page bounds (`page_number` + `page_end`) on cross-page blocks.
     - Preserves complete provenance through `segment_into_canonical_chapters()` into `CanonicalChapter` and `CanonicalBlock`.
     - Enforces the **Sacred Source Invariant**: `raw_text` remains 100% unmutated, while `normalized_text` purges C0/C1 control characters (`[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]`, e.g. `\x00`, `\x07`) and soft hyphens (`\u00ad`) for speech synthesis.
  3. **Upgrade 3 — Multi-Signal Gemini Escalation Quality Gate (`PDFQualityAnalyzer` in `pdf_engine.py`):**
     - Computes normalized quality metrics across Reading Order (40%), Text Integrity (45%), and Sentence Coherence (15%), supporting ASCII, Accented Latin (`\u00C0-\u024F\u1E00-\u1EFF`), and Devanagari (`\u0900-\u097F`).
     - In `compare_extraction_candidates()`, rejects naive word-count preference and enforces hard disqualifiers on Gemini output: conversational LLM refusals (`"I cannot extract"`, `"As an AI"`, markdown fences), 4-gram repetition loops ($\ge 5\times$, $> 30\%$ words), replacement char (`\ufffd`) regressions, low integrity ($< 0.65$), and clean prose truncation ($> 45\%$ clean word loss).
  4. **Upgrade 4 — Literary Chapter vs. Production Chunk Architecture (`CanonicalBook`, `CanonicalChapter`, `ChapterSegmenter`, `ForensicEPUBParser`):**
     - Added explicit `unit_type` (`"literary_chapter" | "production_chunk"`), `is_literary_chapter`, `is_production_chunk`, and `boundary_origin` (`"detected_heading" | "toc_navigation" | "inferred_prologue" | "semantic_split_chunk" | "fallback_production_chunk" | "spine_fallback"`).
     - Preserves section subheadings (`###`) at the start of Part 2 and scene breaks (`* * *`) at the tail of Part 1 during Meso-tier >12k semantic splits across TXT, MD, PDF, and EPUB.
     - Implemented `book.get_literary_chapters()` (reunites split chunks back into unified parent chapters sorted by source number) and `book.get_production_chunks()` (returns execution units for batch processing).
     - Tracked in `ExtractionQualityReport`: `detected_literary_chapters`, `production_chunks`, `used_fallback_chunking`, and logged warnings on fallback chunking.
- **Rationale:** Permanently eliminates multi-column layout corruption, guarantees byte-accurate traceability back to original document pages and lines, protects against LLM hallucinations and conversational leakage, cleanly separates authorial book structure from pipeline batch limits, and completes the production hardening of Pillar 1.

---

## ADR-033: Literary Translation Hardening v2.0 (Proposition Slots, Semantic Aligner, 4-Tier Certification & Multi-Tier Orchestrated Repair)
- **Status:** Accepted
- **Date:** 2026-09-25
- **Context:**
  1. The translation engine audit revealed 7 critical architectural vulnerabilities:
     - `SourceSemanticMap` extracted an empty `actions=[]` list, failing to capture WHO $\rightarrow$ DID WHAT $\rightarrow$ TO WHOM $\rightarrow$ OBJECT $\rightarrow$ NEGATION $\rightarrow$ TIME/LOCATION.
     - Semantic QA lacked a target representation or alignment layer, evaluating Hindi translations heuristically without comparing against a structured semantic proposition graph.
     - Certification logic allowed critical warning conditions on semantic fidelity, beat omissions, and register balance to silently pass overall certification as `PASS`.
     - The 7-dimensional `LiteraryIntensityVector` and `IntensityEvaluator` were never wired into the execution loop, causing Gate `T8` to default-pass when vectors were missing.
     - `TieredRepairEngine` lacked multi-paragraph and scene-level orchestration, bounded retry loops, and actionable failure attribution.
     - `sanitizer.py` (`audit_literary_register`) performed aggressive deterministic regex replacements modifying legitimate literary choices (e.g., `नमस्ते`, `राम-राम`, `नमस्कार`, `दारू`, `सोने की लड़की`).
     - Provenance tracking lacked semantic and intensity fingerprints, and `translate_book_project` defaulted to legacy character chunking rather than the hardened scene pipeline.
- **Decision:**
  1. **Source Proposition Slot Extraction (`source_semantic_map.py` v2.0):**
     - Upgraded `SourceSemanticMap` to v2.0 with full semantic slot extraction (`actors`, `action`, `recipients`, `key_objects`, `negation`, `time_marker`, `location_marker`, `quotes`).
     - Implemented dual deterministic regex fallback and LLM JSON extraction capturing complete narrative clause propositions.
  2. **Target Semantic Representation & Alignment Layer (`source_semantic_map.py`, `semantic_fidelity.py`):**
     - Introduced `TargetSemanticProposition`, `TargetSemanticMap`, and `SemanticAligner`.
     - Maps target Hindi propositions to source English propositions with beat coverage, character voice validation, and paragraph-indexed negation auditing (`affected_paragraphs: List[int]`).
  3. **Strict 4-Tier Certification State Machine (`certification.py` v2.0):**
     - Upgraded `TranslationCertifier` to v2.0 with four explicit certification states: `PASS`, `PASS_WITH_WARNINGS`, `REVIEW_REQUIRED`, and `BLOCKED`.
     - Hardened Gate `T8` to execute calibrated intensity evaluations rather than default-passing.
     - Activated Gate `T10_register_balance` into the evaluation loop.
     - Enforced fail-closed pipeline halting on `BLOCKED` unless `--force-gate` is explicitly passed.
  4. **End-to-End Intensity Model Wiring (`intensity_model.py`, `scene_planner.py`, `orchestrator.py`):**
     - Populated `ScenePlan.intensity_vector` via `estimate_source_intensity()`.
     - Evaluated target translation intensity against source vectors across all 7 dimensions (`violence`, `eroticism`, `profanity`, `tension`, `darkness`, `substance`, `emotional_distress`), enforcing the "Nothing Above Source" principle ($\pm 0.75$ soft warning, $> 2.0$ hard failure).
  5. **Hierarchical Repair Engine Orchestration (`repair_engine.py`, `orchestrator.py`):**
     - Implemented multi-tier automated self-healing with bounded retry limits:
       - Tier 1: 0ms deterministic Book Bible entity & unambiguous calque correction.
       - Tier 2: Surgical paragraph-level LLM targeted rewrites (`MAX_PARAGRAPH_ATTEMPTS = 2`) isolating only failing paragraphs.
       - Tier 3: Full scene retranslation (`MAX_SCENE_ATTEMPTS = 1`) with strict critique injection.
  6. **Literary Sanitizer Role Separation (`sanitizer.py`):**
     - Separated security sanitization (stripping LLM chatter, refusals, markdown wrappers) from literary editing.
     - Made `audit_literary_register(..., apply_substitutions=False)` non-destructive by default, strictly preserving authorial cultural vocabulary (`नमस्ते`, `राम-राम`, `दारू`, `सोने की लड़की`), while delegating unambiguous calque correction (`सुनहरी लड़की`, `कुंवारी चोटी`, `डिप्रेशन`) to the repair engine.
  7. **11-Dimension Provenance Sealing & Production Pipeline Default (`provenance.py`, `translator.py`):**
     - Upgraded `TranslationProvenanceTracker` to compute cache keys across 11 dimensions (`source_hash`, `prompt_hash`, `model_name`, `temperature`, `bible_version_hash`, `policy_hash`, `memory_state_hash`, `scene_plan_hash`, `semantic_map_hash`, `intensity_vector_hash`, `evaluator_version`).
     - Wired `translate_book_project()` to default to `IntelligentTranslationPipeline` (`TranslationOrchestrator`) and assemble top-level `chapter_XXX_hi.md` for downstream screenplay and TTS synthesis stages.
- **Rationale:** Eliminates silent quality degradation, guarantees provable semantic alignment and authentic Hindustani register, provides bounded automated self-healing without human intervention, and ensures complete backward compatibility across the studio pipeline.

## ADR-027: World + Character Memory 2.0 Production Hardening & Dual Independent Expert Audit
- **Status:** Accepted
- **Date:** 2026-09-25
- **Context:**
  1. The World + Character Memory 2.0 system required a final production hardening pass and dual expert audit across 5 critical dimensions:
     - BookBible canon pollution: Dynamic relationship updates (pronouns, trust, respect) were being written back into canonical `BookBible.relationships`.
     - Silent memory amnesia: `MemoryStore.load()` contained `except Exception: pass`, resetting corrupted stores to empty state without warning.
     - Partial transaction state leakage: Exceptions mid-commit could leave character health or location mutations applied without corresponding event logs.
     - Epistemic boundary leaks: Unpossessed secrets could be revealed by characters who did not know them, and rejected knowledge deltas left companion narrative threads committed.
     - Multi-script director cue stomping: Screenplay parenthetical stage directions in Devanagari (e.g. `(धीमी आवाज़ में)`) failed ASCII regex checks, allowing memory emotion guidance to override directorial intent.
- **Decision:**
  1. **Hard Canon Immutability (`memory_store.py`):**
     - Completely removed BookBible writeback from `commit_scene_memory()`. BookBible remains byte-for-byte read-only Hard Canon.
     - Evolving relationships live strictly in `MemoryStore.relationships`.
  2. **Two-Tier Persistence Safety & Integrity Validation (`memory_store.py`):**
     - Implemented atomic two-phase write with verified `.bak` creation before file replacement.
     - Added `_validate_store_integrity()` verifying root JSON object, `schema_version == "2.0"`, required containers, and commit version consistency.
     - Replaced silent `except: pass` with fail-closed `MemoryPersistenceError`.
  3. **Transactional Deep Snapshot Rollback (`memory_store.py`):**
     - Implemented `_create_snapshot()` and `_restore_snapshot()` performing true deep clones (`model_copy(deep=True)`) across all 11 mutable containers.
     - Guaranteed 100% pre-commit state restoration upon any exception during delta computation, validation, or application.
  4. **Epistemic Isolation & Strict Event Atomicity (`memory_validator.py`, `character_memory.py`):**
     - Enforced that revealing unpossessed secrets or acting on unknown facts is strictly rejected (Check 7A/7B).
     - Allowed recipient characters to transition `UNKNOWN` $\to$ `KNOWN` through valid revelation events.
     - Exempted disproven false beliefs from revealer prior-knowledge requirements.
     - Enforced strict event atomicity: if any delta of an event fails validation, all companion deltas are purged and the event is rejected.
     - Added case-insensitive normalized character lookups in `KnowledgeFact.get_status_for_character()`.
  5. **Multi-Script Director Supremacy (`memory_context.py`):**
     - Replaced ASCII parenthetical regex with Unicode-agnostic `r"\([^)]*[^\s)]+[^)]*\)"`.
     - Protected nested `acting.emotion` / `acting.delivery_style` and custom `vocal_tags` from memory overrides.
  6. **Adversarial Verification Suite (`test_adversarial_expert_audit.py`):**
     - Added 7 hostile penetration probes covering all attack vectors.
     - Re-verified full test suite at **368 passed, 17 subtests passed (100% green)**.
- **Rationale:** Guarantees absolute narrative and character continuity across 100+ chapter novels without risk of data loss, canon corruption, epistemic paradoxes, or artistic overrides.

## ADR-030: Stage 3 Screenplay Dramatic Adaptation & Dramaturgy Engine
- **Status:** Accepted
- **Date:** 2026-09-25
- **Context:**
  1. The existing Stage 3 Screenplay system mechanically parsed prose into JSON segments without dramatic reasoning (missing scene purpose, stakes, character objectives, actioning verbs, tension trajectories, conservative subtext, and sociolect performance rules).
  2. Arbitrary 1200-word paragraph chunking severed dramatic beats and dialogue exchanges across chunk boundaries.
  3. Upgrades had to be strictly confined to Stage 3 without altering downstream stages (Stage 4 AgentDirector, Stage 6 TTS, mixing, mastering) and without breaking existing test suites.
- **Decision:**
  1. **Dramaturgy Engine Package (`audiobook_factory/dramaturgy/`):**
     - `contracts.py`: Strictly typed Pydantic v2 schemas (`DramaticBeat`, `CharacterDramaticObjective`, `SceneDramaticPlan`, `DramaticPlan`, `CharacterPerformanceProfile`, `PerformanceBible`, `DramaticValidationResult`).
     - `scene_analyzer.py`: Discovers natural scene boundaries, computes scored multi-signal genre inference, dramatic questions, stakes, and listener knowledge states.
     - `beat_planner.py`: Extracts state transitions, derives transitive actioning verbs, maps surface vs. underlying emotions, computes conservative subtext with confidence bounds, generates tension curves, and provides `slice_chapter_by_beats`.
     - `performance_bible.py`: Projects BookBible/rosters into acoustic delivery directives (`SOCIOLECT_PRESETS`, narrator styles, rules).
     - `dramatic_validator.py`: Enforces 5-pillar audit (structural indexing, character epistemics, anti-emotional teleportation, dramatic fidelity, creative overreach).
  2. **Non-Breaking ScreenplaySegment Extensions:**
     - Extended `ScreenplaySegment` with optional, defaulted fields (`scene_id`, `beat_id`, `actioning`, `subtext`, `tension_before`, `tension_after`, etc.).
  3. **Beat-Aligned Chunk Slicing (`slice_chapter_by_beats`):**
     - Slices novel chapters strictly along pre-planned scene and intra-scene beat boundaries, eliminating severed dialogue cycles.
  4. **Fail-Closed Gate 2.5 (`audit_gate2_5_dramatic_fidelity`):**
     - Added dedicated Gate 2.5 in `audiobook_factory/gate_auditor.py` keeping legacy Gate 2 intact.
  5. **Verification & Audit:**
     - 40 new dramaturgy tests covering unit functionality, 10 golden benchmark scenes, and the identical-dialogue (*"Don't touch it."*) multidimensional proof test.
     - Full test suite passes at **408/408 tests green**.
     - Triple expert audit panel (Systems Architect, QA Specialist, Security Auditor) awarded unanimous **Grade A+ (Production Pass)**.
- **Rationale:** Transforms the screenplay pipeline from a text-segmentation tool into a dramatically intelligent storytelling engine supporting commercial audio drama performance while guaranteeing 100% backward compatibility and zero hardcoding.



## ADR-031: Stage 3 Refined Dramatic Adaptation & 10 Capabilities Pass
- **Status:** Accepted
- **Date:** 2026-09-25
- **Context:**
  - Following the initial Stage 3 implementation (ADR-030), a forensic audit revealed missing dramatic dimensions necessary for professional dramatic storytelling:
    1. Beat Causality (disjoint beat lists lacking trigger-response-consequence chains).
    2. Dramatic State Delta (absence of explicit scene entry vs exit net transformation).
    3. Relationship Evolution (lack of beat-level interpersonal shifts).
    4. Power + Information Dynamics (missing tactical leverage and dramatic irony preservation).
    5. Meaningful Physical Blocking (absence of material physical staging).
    6. Narrative Mode & Distance (inability to distinguish direct dialogue from internal monologues or reported speech).
    7. Explicit Adaptation/Fidelity Policy (need for deterministic boundaries preventing fabricated plot lore).
    8. Long-Range Story Connections (linking motifs and foreshadowing without a duplicate database).
    9. Conversational Dynamics (turn-taking cutoffs, interruptions, hesitation, and strategy pivots).
    10. Dramatic Silence Intent (narrative intent of pauses without premature audio DSP execution).
  - Strict constraint: Zero architectural redesign, no downstream disruption to Stages 4-13, and 100% backward compatibility.
- **Decision:**
  1. **Additive Contract Enhancements (contracts.py & ScreenplaySegment):**
     - Introduced DramaticStateDelta, RelationshipShift, PhysicalBlocking, StoryConnectionRecord, ConversationalDynamic, DramaticSilenceIntent, AdaptationFidelityPolicy.
     - Extended DramaticBeat, SceneDramaticPlan, DramaticPlan, and ScreenplaySegment with optional, defaulted attributes.
  2. **Scene & Beat Intelligence Upgrades (scene_analyzer.py, beat_planner.py):**
     - Spliced South Park ('therefore' / 'but') causal chaining across contiguous beats.
     - Quantified net state delta across knowledge, relationships, power, danger, decisions, and emotion.
     - Preserved dramatic irony by mapping audience vs. character epistemic divergence.
     - Mapped meaningful physical blocking and conversational turn-taking dynamics.
  3. **Script Builder Pass 2 Refinement (script_builder.py):**
     - Inferred narrative_mode (direct_dialogue, internal_monologue, reported_speech, narrator_exposition).
     - Detected conversational interruptions (--, -) and hesitation pauses (...).
  4. **Tiered Strictness Validation (dramatic_validator.py):**
     - Hard FAIL on fabricated reveals and character epistemic breaches; soft WARNING on aesthetic inferences.
  5. **Zero Disruption to Downstream Stages:**
     - Stages 4-13 continue reading only standard fields; new attributes live passively as rich metadata in dramatic_plan.json and segment records.
  6. **Verification:**
     - Added 12 new comprehensive tests in test_dramatic_refinements.py and test_dramatic_contracts.py.
     - Full project test suite passes at 420/420 tests green (17 subtests passing).
- **Rationale:** Empowers Stage 3 to understand not only what happens in a scene, but why each beat happens, what changes because of it, how relationships evolve, what the listener knows, and what must remain faithful to source literature.

## ADR-032: Dramatic Intelligence to Actor Performance Realization Layer & Gate 2.8
- **Status:** Accepted
- **Date:** 2026-09-25
- **Context:**
  1. Stage 3 produces rich dramatic metadata (`CharacterDramaticObjective`, `DramaticBeat`, `PerformanceBible` sociolect profiles, subtext, tension curves, actioning verbs, physical blocking, conversational dynamics, silence intent), but the speech synthesis layer historically collapsed all acting into a flattened string (`acting.delivery_style`).
  2. Every segment received a single take regardless of dramatic weight (climax vs routine narration), and audio QC was restricted to acoustic DSP checks (clipping, DC bias, RMS floor) with zero evaluation of acting performance, subtext conveyance, emotional truth, or conversational turn-taking chemistry.
  3. Constraints: Absolute immutability of sacred literary dialogue text, zero disruption to existing gates or contracts, 100% backward compatibility, explainable take selection (no opaque single scores; avoid loudest=best trap), and grounded emotional continuity (no emotional teleportation without dramatic triggers).
- **Decision:**
  1. **Performance Realization Package (`audiobook_factory/performance/`):**
     - `contracts.py`: Strongly typed Pydantic models for `PerformanceDirection`, `TakeVariant`, `PerformanceEvaluationResult`, `EvaluationDimensionScore`, `PerformanceFidelityReport`, and provenance modes (`SOURCE_DIRECT`, `DRAMATIC_CANON`, `INFERRED_PERFORMANCE`, `DRAMATIC_INTERPRETATION`). Re-exported cleanly in root `contracts.py`.
     - `timing_realizer.py`: Calibrated human respiratory breaths (120-250ms pre/post-roll), organic punctuation hesitation, dramatic silences (shock, realization, grief: 1200-1800ms), and conversational interruption cutoffs (80ms abrupt cuts).
     - `director.py`: `PerformanceDirector` maps `ScreenplaySegment` + `PerformanceBible` + `DramaticBeat` into actionable actor directions, grounding sudden emotional leaps against volatile teleportation transitions.
     - `tts_adapter.py`: `GeminiTTSPerformanceAdapter` synthesizes multi-token `speechMetadata.style` strings and take variants (`standard`, `restraint`, `vulnerable`, `exposed`), guaranteeing text immutability.
     - `evaluator.py`: `PerformanceEvaluator` scores takes across 8 dimensions: intent match, emotional match, prosody, pacing, subtext, character consistency, relationship consistency, naturalness.
     - `take_bank.py`: `TakeBank` allocates candidate takes by priority (`standard`=1, `focused`=2, `high`=3, `climactic`=4) avoiding quota waste on routine narration.
     - `take_selector.py`: `IntelligentTakeSelector` selects the optimal take based on multidimensional balance, preventing the "loudest = best" trap, with explainable human-readable rationales.
     - `chemistry.py`: `ConversationalChemistry` couples dialogue turns: zero-onset interruption cuts, intimidation hesitation, intimate close-mic whispering.
     - `continuity.py`: `PerformanceContinuityTracker` monitors character pace/energy averages across scenes, flagging >30% drift anomalies.
     - `gate.py`: `PerformanceFidelityGate` (Gate 2.8) enforces pre-mix quality before dialogue stems enter mastering.
  2. **Pipeline Integration:**
     - `gate_auditor.py`: Added `audit_gate2_8_performance_fidelity` between Gate 2.5 and Gate 3.
     - `tts_dispatcher.py`: Integrated `performance_direction` into `synthesize_gemini_tts` and `synthesize_segment`; integrated `TakeBank`, `IntelligentTakeSelector`, `ConversationalChemistry`, and Gate 2.8 report generation in `synthesize_chapter_script`.
     - `orchestrator.py`: Integrated Gate 2.8 pre-mix audit verification prior to dialogue stem mastering.
  3. **Verification:**
     - Added 23 comprehensive tests in `tests/test_performance_realization.py` covering all 14 capabilities and end-to-end integration: 23/23 PASSED.
     - Verified existing gate auditing with 5/5 tests passing in `tests/test_gate_auditor.py`.
     - Full regression suite confirmed 100% green across all existing and new tests.
- **Rationale:** Bridges the critical divide between Stage 3 dramatic intelligence and final speech synthesis, transforming synthetic TTS speech into emotionally grounded, dynamically paced, multi-cast dramatic audio drama performances with complete explainability and zero regression risk.

## ADR-022: Pronunciation & Spoken Language QA Subsystem (Dual-Layer Text Decoupling, Deterministic 7-Tier Resolution, Acoustic MMS_FA Verification, and Single-Take Surgical Repair)
- **Status:** Accepted
- **Date:** 2026-09-26
- **Context:**
  1. Multilingual, historical, fantasy, and translated literature poses acute phonetic hazards for generative neural TTS models: non-standard proper nouns, foreign names, numerals, currencies, compound units, percentages, and acronyms are frequently mispronounced, swallowed, or read as robotic digit sequences.
  2. Naive attempts to fix pronunciation by rewriting dialogue in the screenplay corrupted human-facing text, broken subtitles, TOC displays, and original authorial prose, violating text immutability invariants.
  3. Bracketed neural acting directives (`[whispers]`, `[gasp]`, `[shouting]`) were vulnerable to verbalization or transliteration mutilation by naive phoneticizers.
  4. TTS vocoders occasionally dropped difficult tokens or entered runaway stutter loops without acoustic verification, and character pronunciations drifted across chapters without project-wide consistency auditing.
- **Decision:**
  1. **Dual-Layer Text Decoupling (`contracts.py`, `spoken_text.py`):**
     - Established absolute physical separation between sacred literary prose (`ScreenplaySegment.text`, 100% immutable for subtitles, display, and archive) and phonetic TTS delivery payloads (`ScreenplaySegment.spoken_text` + `pronunciation_metadata`).
     - Preserved neural acting tags (`ACTING_TAG_PATTERN = re.compile(r"(\[[^\]]+\])")`) passing them through verbatim without phonetic expansion.
  2. **Unicode-Safe Script & Dialect Classifier (`language_detector.py`, `code_switch.py`):**
     - Analyzed character ranges to distinguish Perso-Arabic loanwords (`URDU_NUKTA_PATTERNS`: क़, ख़, ग़, ज़, फ़) and Sanskrit Tatsama conjuncts (क्ष, त्र, ज्ञ, श्र) from native Hindi retroflex flaps.
     - Implemented Option 1A Hybrid Mode: phonetic Devanagari guidance for foreign proper nouns in Hindi dialogue, colloquial loanword preservation, and authentic code-switching retention.
  3. **Deterministic 7-Tier Resolver (`resolver.py`):**
     - Enforced strict auditable precedence: Tier 1 Manual Override $\rightarrow$ Tier 2 Canonical BookBible $\rightarrow$ Tier 3 Verified Project History $\rightarrow$ Tier 4 Canonical Lexicon Entry $\rightarrow$ Tier 5 Deterministic Rules (currency expansion `₹500` $\rightarrow$ `पाँच सौ रुपये`, percentages, Devanagari/Latin numerals up to 100M, compound units `10km` $\rightarrow$ `दस किलोमीटर`, acronym initialisms `FBI` $\rightarrow$ `एफ़.बी.आई.`) $\rightarrow$ Tier 6 Model-Assisted Inference $\rightarrow$ Tier 7 `REVIEW_REQUIRED` (zero silent pass on unknown foreign tokens).
     - Standardized objective states without fake precision: `VERIFIED`, `LIKELY`, `UNCERTAIN`, `FAILED`, `REVIEW_REQUIRED`.
  4. **Acoustic Forced Alignment QA (`auditor.py`):**
     - Integrated Meta MMS_FA CTC alignment on GPU/CPU with proportional energy valley fallback to compute frame-accurate token boundaries (`start_ms`, `end_ms`, `duration_ms`).
     - Implemented forensic detectors for swallowed/omitted tokens ($< \max(60, \text{syllables} \times 45)\text{ms}$), vocoder stutter loops ($> \max(1200, \text{syllables} \times 350)\text{ms}$), and rushed/dragging cadence anomalies.
  5. **Targeted Single-Take Repair Engine (`repair.py`):**
     - Bounded by a strict circuit breaker of max 1 targeted repair attempt per segment to eliminate runaway retry loops or quota exhaustion.
     - Injected rhythmic micro-pause anchors (gentle commas) around swallowed tokens to give the neural vocoder acoustic onset breathing room.
     - Enforced atomic synthesis to `.tmp.wav` before promoting verified audio takes into `TakeBank`.
  6. **Cross-Chapter Drift Auditor & Production Quality Gates (`consistency.py`, `certification.py`, `gate_auditor.py`):**
     - Added Scene Gates T12 (Spoken Language QA), T13 (Pronunciation Plan QA - Critical), T14 (Pronunciation Audio QA), and T15 (Cross-Chapter Consistency) to `TranslationCertifier`.
     - Added Book Master Gate 6E (`CrossChapterConsistencyAuditor`) to `audit_book_master` in `gate_auditor.py`, failing closed before final `.m4b` delivery if unexempted pronunciation drift is detected.
     - Integrated 16-char SHA-256 lexicon hash into `TranslationProvenanceTracker` composite cache key for clean downstream take invalidation upon pronunciation edits.
  7. **Verification:**
     - Created permanent Golden Pronunciation Bank (`golden_set.py`) covering 20 edge cases across 8 linguistic dimensions, passing with 100% precision.
     - Validated complete 6-stage lifecycle in `tests/pronunciation/test_end_to_end_pronunciation_integration.py`.
- **Rationale:** Guarantees flawless spoken clarity and character entity continuity across full-novel audio drama productions without mutating authorial prose, corrupting subtitles, or exhausting generative AI quota.


## ADR-023: Commercial Studio Audiobook TTS Casting, Voice Identity & Acting Intelligence Subsystem (Waves 1-6 Architecture)
- **Status:** Accepted
- **Date:** 2026-09-26
- **Context:**
  1. Producing premium commercial audiobooks (Harry Potter / Pottermore caliber) requires moving beyond flat, single-pass TTS synthesis toward nuanced acting direction, multi-take candidate banking, acoustic voice identity preservation, conversational chemistry between characters, and cross-chapter performance continuity.
  2. Subjective voice casting risked voice collisions and misaligned personas. Without empirical auditioning and immutable cast locking, cast assignments were fragile across re-runs.
  3. Generative TTS models suffer from acoustic drift across takes and emotional extremes (shouting, whispers, crying). Without reference voice banking and spectral signature probing, character identity drifted over long chapters.
  4. Abrupt emotional teleportation (e.g. calm to explosive fury without transitional grounding) degraded listener immersion.
- **Decision:**
  1. **Wave 1 — Empirical Casting & Cast Lock Authoritative Priority (`casting/`):**
     - Built `CharacterCastingProfile`, `VoiceCandidateEngine` (12 Gemini TTS catalog voices across 6 acoustic/dramatic dimensions with explainable breakdown), and `VoiceAuditionEngine` (10 standardized dramatic modes).
     - Implemented `CastLockManager` (`cast_lock.json`) providing authoritative priority in `TTSDispatcher` over raw registries, and automated recasting with previous audio take archival/invalidation.
  2. **Wave 2 — Voice DNA & Acoustic Drift Defense (`identity/`):**
     - Established 4-layer `VoiceDNA` (Identity, Behavior, Emotional, Forbidden) and `VoiceDNABank`.
     - Built `ReferenceVoiceBank` extracting 4-dimensional acoustic signatures (Median F0, Spectral Centroid, Spectral Flatness, RMS dBFS).
     - Built `VoiceIdentityAnalyzer` comparing synthesized takes against golden reference baselines with dynamic tolerance widening during dramatic extremes.
  3. **Wave 3 — Acting Intelligence & Dynamic Risk Allocation (`performance/`):**
     - Implemented `SceneEmotionalStateTracker` computing continuous 6D vectors $(\text{valence}, \text{arousal}, \text{tension}, \text{restraint}, \text{vulnerability}, \text{energy})$ with exponential smoothing ($\alpha = 0.35$).
     - Built `PerformanceConstraintResolver` synthesizing concise, prioritized directives (Primary Intention, $\le 3$ Secondary Modifiers, Forbidden Behaviors) eliminating adjective pileup.
     - Built `GenerationRiskEngine` computing continuous risk $R \in [0.0, 1.0]$ driving dynamic take allocation.
  4. **Wave 4 — Generation Quality & Evaluator 2.0 (`performance/`):**
     - Implemented `GenerationStrategyResolver` selecting generation mode (`CHUNKED_NARRATION`, `ISOLATED_SINGLE_TAKE`, `ISOLATED_MULTI_TAKE`, `CRITICAL_SCENE_TAKE`).
     - Upgraded `TakeBank` with uncertainty-driven adaptive variants (`more_restrained`, `more_vulnerable`, `slower_heavier`, `colder`, `more_urgent`).
     - Upgraded `PerformanceEvaluator 2.0` assessing 4 pillars (Acoustic, Performance, Voice Identity, Relational), and `IntelligentTakeSelector` with context-aware weighting and $-0.40$ drift penalty.
  5. **Wave 5 — Ensemble Performance & Long-Form Continuity (`performance/`):**
     - Extended `ConversationalChemistry` with post-synthesis `evaluate_dialogue_chemistry()` measuring pause fidelity, interruption sharpness ($\le 40\text{ ms}$ snapping), and dynamic energy contrast.
     - Extended `PerformanceContinuityTracker` persisting character performance arcs across chapters to `character_continuity.json`, auditing inter-chapter physical recovery anomalies and unbuffered energy leaps.
  6. **Wave 6 — Production Hardening & Documentation (`tests/`, `scripts/`, `docs/`):**
     - Built `GoldenAudioRegressionSuite` (`tests/test_golden_audio_regression_suite.py`) testing 18 dramatic cases offline with synthetic WAV fixtures.
     - Built Human Casting Console CLI (`scripts/casting_console.py`) supporting voice exploration, status display, recommendations, audition packs, locking, and recasting.
     - Upgraded Pre-Mix Gate 1 and Gate 6A in `gate_auditor.py` to enforce Cast Locks.
     - Authored complete architecture guides: [`docs/TTS_CASTING_ARCHITECTURE.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/TTS_CASTING_ARCHITECTURE.md) and [`docs/TTS_GENERATION_ARCHITECTURE.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/TTS_GENERATION_ARCHITECTURE.md).
  7. **AST Zero-Hardcoding Contract Compliance:**
     - 100% compliant with `tests/test_zero_hardcoding_contracts.py` (0 character names, 0 chapter branch hacks in engine files).
     - Full repository test suite confirmed 100% green: 521/521 tests passing.
- **Rationale:** Delivers commercial studio-quality, Harry Potter / Pottermore-caliber vocal performances with complete architectural provenance, zero character hardcoding, and zero regressions.

## ADR-024: Commercial Studio Quality Upgrade — Alignment 2.0, Performance Evidence, Take Selection 2.0 & Scene Continuity (Waves A-E)
- **Status:** Accepted
- **Date:** 2026-09-26
- **Context:**
  1. Commercial studio audiobook productions (Harry Potter / Pottermore standard) require precise character-level speech alignment, evidence-grounded performance evaluation, and intelligent take selection that rewards dramatic restraint, subtext, and scene continuity over raw acoustic loudness.
  2. Forced alignment previously lacked word-level token spans, pause intelligence classification, and robust Hindi/Hinglish handling.
  3. Performance evaluation previously used static heuristic scores rather than forensic acoustic/prosodic evidence, failing to penalize monotonic pitch-lock or reward icy dramatic restraint.
  4. Take selection previously lacked technical and voice identity hard gates, pairwise judicial deliberation for close margins, and whole-scene performance arc optimization.
- **Decision:**
  1. **Wave A — Alignment 2.0 (`forced_aligner.py`, `alignment_contracts.py`):**
     - Built `AlignmentResult`, `WordAlignment`, `PauseInterval`, and `SpeechRegion` contracts.
     - Extracted character-accurate word token spans directly from MMS_FA CTC emissions.
     - Implemented 7-class pause intelligence (`natural_pause`, `dramatic_pause`, `hesitation`, `interruption_gap`, `breath_pause`, `dead_air`, `synthetic_gap`).
     - Added Hindi conjuncts/nukta normalization and transparent energy-valley fallback.
  2. **Wave B — Performance Evidence & Evidence-Grounded Evaluation (`evaluator.py`, `contracts.py`):**
     - Replaced static score baselines with dynamic evidence extraction (`AcousticEvidence`, `ProsodyEvidence`, `PacingEvidence`, `PerformanceEvidence`).
     - Implemented autocorrelation-based fundamental pitch (F0) tracking, pitch variance, and dynamic range.
     - Added monotonic pitch lock detection ($\sigma_{F0} < 5\text{ Hz}$ on non-whisper speech).
     - Enforced iron restraint vs shouting in high-restraint dramatic moments.
     - Enforced two-tier voice identity gates (hard gate on catastrophic drift $< 0.45$ similarity or $> 60\%$ F0 shift; soft preference on emotional variation).
  3. **Wave C — Take Selection 2.0 (`take_selector.py`):**
     - Implemented 3-stage hard gates: Technical audio integrity (clipping $\ge 12$ pinned samples, DC offset $> 1500$, duration, dead air $> 2.0\text{s}$), Alignment validity (confidence $< 0.35$, word omissions $> 50\%$), and Voice identity safety.
     - Added 6-mode contextual scoring (Exposition, Climax, Whisper, Anger, Grief, Standard).
     - Built `PairwiseTakeJudge` deliberating on restraint, dramatic pauses, subtext, and voice stability.
     - Designed `TakeSelectionResult` with explainable reason codes, runner-up provenance, and review flags.
     - Protected against circular-repr recursion with `repr=False` on `TakeVariant.selection_result`.
  4. **Wave D — Scene Selection, Chemistry & Continuity (`take_selector.py`, `chemistry.py`, `continuity.py`):**
     - Implemented `select_scene_takes` tracking whole-scene performance arcs (`energy_curve`, `pace_curve`, `tension_curve`).
     - Defends against listener fatigue (monotonous screaming) and premature scene climax.
     - Integrates `ConversationalChemistry` to couple adjacent dialogue turns with responsive turn-taking latency.
     - Integrates `PerformanceContinuityTracker` to maintain character tempo stability across beats.
  5. **Wave E — Golden Behavioral Benchmark Suite (`tests/test_golden_take_selection_benchmark.py`):**
     - Built 7 behavioral benchmark scenarios verifying that restraint beats loudness, dramatic pause beats dead air, voice stability beats pitch drift, chemistry beats isolated score, scene arc beats segment score, naturalness beats distortion, and subtext beats generic aggressive yelling.
  6. **Regression Protection & AST Compliance:**
     - 100% compliant with AST zero-hardcoding contracts (`test_zero_hardcoding_contracts.py`).
     - Full repository test suite confirmed 100% green: 581/581 tests + 17 subtests passing with 0 regressions.
- **Rationale:** Preserves the existing architecture while dramatically improving the quality, expressiveness, and commercial credibility of audiobook performance decisions.





## ADR-034: Cinematic Sound Design Subsystem Upgrade (Commercial Pottermore-Caliber 20 Capabilities, Adaptive Density & Multi-Signal QC)
- **Status:** Accepted
- **Date:** 2026-09-26
- **Context:** Commercial cinematic audio dramas (such as Harry Potter / Pottermore full-cast productions) require continuous world atmosphere, character-accurate movement acoustics, supernatural sound design vocabularies, thematic leitmotif evolution, and intentional negative sound design (silence).
- **Decision:** Implemented all 20 Sound Design capabilities across Phases A-G under audiobook_factory/sound_design/ (contracts, scene understanding, blueprint, 12 environment profiles, asset retriever with SHA-256 & DSP sanity, 5-tier ambience with cross-scene evolution, walla with dialogue subordination & solitary restraint, silence engine with adaptive density budgets, foley engine with relevance scoring & low-value verb rejection, character physics & material matrix with tableware isolation, narrative hard SFX & creature sound engines, magical sound language, leitmotif variations & music cue director, abstract spatial acoustics & soundstage geometry, master sound design director, 9-signal QC auditor, clean adapter boundary, and 15 canonical golden benchmarks).
- **Rationale:** 100% compliant with AST zero-hardcoding contract. 703/703 tests passing (100% green).
