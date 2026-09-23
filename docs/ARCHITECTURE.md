# 🏛️ Architecture: The 4-Room Cinematic Audio Drama Engine

## Executive Overview

**Audiobook Maker (Audiobook Factory v4.0)** is an autonomous, studio-grade audiobook production system modeled after the high-end multi-track standards of **Audible Drama** and **GraphicAudio ("A Movie in Your Mind")**.

Unlike legacy audiobook generators that simply pipe unformatted text into a Text-to-Speech (TTS) engine and append speech files together, Audiobook Maker implements a **modular 4-Room Architecture** with **6 Quality Verification Gates**, **5 Discrete Audio Stems**, and an **Autonomous Agentic Director**.

---

## 🏗️ High-Level 4-Room Blueprint

```mermaid
flowchart TB
    subgraph Room1["🚪 Room 1: Creative Production Room"]
        direction TB
        RawBook["Raw Book File<br/>(EPUB / PDF / TXT / Markdown)"] --> Extractor["Universal Extractor<br/>(audiobook_factory/extractor.py)<br/>• Native PyPDF + Vision Fallback"]
        Extractor --> Chapters["Structured Chapter Files (.txt / .md)"]
        Chapters --> Translator["Literary Hindustani Translator<br/>(audiobook_factory/translator.py)<br/>• Adult Literary Fidelity & 70/30 Invariant"]
        Translator --> Sanitizer["Linguistic Sanitizer & Guardrail<br/>(audiobook_factory/sanitizer.py)<br/>• Profanity Preserved + Expanded Vocal Tags"]
        Sanitizer --> Screenplay["Sliding-Window Screenplay Builder<br/>(audiobook_factory/script_builder.py)<br/>• Grunt Engine, ASMR Intimacy & Sociolects"]
        Screenplay --> Scripts["Standardized Screenplay Script JSON<br/>(Speaker, Emotion, Spatial Pan, Intensity, Breath)"]
        Scripts --> Dispatcher["Token-Bucket TTS Dispatcher<br/>(audiobook_factory/tts_dispatcher.py)<br/>• Quota Isolation (service='text')"]
        Dispatcher --> Chunks["Speech Chunks (24kHz Mono PCM)"]
    end

    subgraph Room2["🚪 Room 2: Agentic Directing Layer (Strict Agent Mandate)"]
        direction TB
        Bible["Global Lore & Sonic Bible<br/>(sound_bible.json)"] --> Director["AgentDirector 3-Pass Workflow<br/>(audiobook_factory/agent_director.py)<br/>• No Script Overrides"]
        Scripts --> Director
        Chunks --> Director
        Director --> Pass1["Pass 1: Dramaturgy & Silence Carving<br/>(>= 60.0% Silence Mandate)"]
        Pass1 --> Pass2["Pass 2: Music Director<br/>(FTS5 Search & Character Leitmotifs)"]
        Pass2 --> Pass3["Pass 3: Acoustic Foley Miner<br/>(Word Alignment & -6dB Whisper Attenuation)"]
        Pass3 --> Manifest["CreativeManifest v3.0 / CinemaAudioManifest"]
    end

    subgraph Room3["🚪 Room 3: Acoustic Compositor & DSP Mastering"]
        direction TB
        Manifest --> Renderer["Manifest Soundscape Renderer<br/>(audiobook_factory/manifest_renderer.py)"]
        SoundBank["SQLite FTS5 Sound Bank<br/>(audiobooks/sound_bank/)"] --> Renderer
        Renderer --> Ducking["Whisper-Safe Sidechain Ducking<br/>(Threshold 0.018 linear / -34.9 dBFS)"]
        Renderer --> Reverb["Dynamic Room Reverb Presets<br/>(Cathedral, Bedroom, Open Road, Stone Hall)"]
        Renderer --> DSPMaster["5-Stage DSP Mastering Chain<br/>(audiobook_factory/mastering.py)"]
    end

    subgraph Room4["🚪 Room 4: Cinema Discrete Multi-Stem Engine"]
        direction TB
        Manifest --> CinemaEngine["Cinema Audio Engine<br/>(audiobook_factory/cinema_audio_engine.py)<br/>• Music-Only 2.2kHz Notch EQ"]
        DSPMaster --> CinemaEngine
        CinemaEngine --> Stems["Discrete 5-Track DME Stems:<br/>- stem_DX.wav (Dialogue)<br/>- stem_MX.wav (Music)<br/>- stem_FX.wav (Foley/SFX)<br/>- stem_AMB.wav (Ambience)<br/>- stem_ME.wav (Music & FX)"]
        CinemaEngine --> FullMaster["Cinema Broadcast Master<br/>(EBU R128: -19 LUFS, -1.5 dBTP)"]
        CinemaEngine --> StemLedger["chapter_XXX_stem_ledger.json"]
    end

    Room1 --> Room2
    Room2 --> Room3
    Room2 --> Room4
    Room3 --> Room4
    Room4 --> Packager["M4B Container Packager<br/>(audiobook_factory/packager.py)<br/>• AAC Safety Auto-Transcode"]
    Packager --> Deliverable["Final M4B Audiobook<br/>(Chapter Navigation + FastStart Artwork)"]
```

---

## 🚪 Deep-Dive: The Four Production Rooms

### 1. Room 1: Creative Production Room
*Purpose: Convert unstructured literature into structured, attributed dramatic screenplay assets.*

- **Universal Document Extractor ([`audiobook_factory/extractor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py))**:
  - Ingests EPUB, PDF, TXT, or Markdown.
  - **Native PyPDF Extraction**: Directly parses digital PDFs using `pypdf>=5.0` for instantaneous, zero-quota text extraction, bypassing the 8,192 token ceiling of vision models.
  - Falls back to Gemini multimodal document API only when encountering scanned image-only PDFs.
  - Detects semantic chapter breaks, table of contents, and scene dividers.
  - Automatically splits chapters $> 45,000$ characters on semantic boundaries to avoid LLM context overflow.
- **Literary Hindi Translator ([`audiobook_factory/translator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py))**:
  - Two-pass dramatic Hindustani translation with **Adult Literary Mode prompt switching** governed by `ADULT_LITERARY_MODE` (default `True`):
    - **Anti-Bowdlerization Mandate:** Strictly prohibits censorship, softening, or prudish television euphemisms for visceral combat, coarse tavern banter, or sensual bedroom intimacy.
    - **The 70/30 Anti-Parody Invariant:** Mandates that 70% of canon dark-fantasy lore, proper nouns, monster classifications (specters, strigas, cursed beasts), and geographic realms remain sacred; 30% sensory layer is localized through organic Hindustani grit without slipping into tapori spoofs.
    - **Period Tavern Grit & Raw Profanity:** Direct, unapologetic translation of gritty curses and tavern insults (`'गांड'`, `'भोसड़ीके'`, `'लंड'`, `'रांड'`, `'मादरचोद'`, `'बकचोदी'`, `'सूअर का पेशाब'`) replacing sanitized substitutions (e.g. never converting 'bastard' to 'दुष्ट').
    - **19-to-21 Amplification Rule & Dynamic Power Shifts:** Elevates mild source dialogue to authentic Desi punch, with dynamic honorific shifts (`तू / अबे` collapsing into groveling `माई-बाप / सरकार` under physical intimidation).
    - **Somatic Erotica & HBO Intimacy Standard:** Depicts passionate intimacy through somatic touch, heat, skin friction, breath physics, and garment mechanics (`'तपती कमर'`, `'पसलियों की लचक'`, `'कांपती उंगलियां'`). Clinical autopsy terms (`'योनि'`, `'लिंग'`, `'स्तन'`, `'संभोग'`) and roadside smut are strictly banned.
    - **Urdu ka Tarka:** Calibrates 10–15% atmospheric noir vocabulary (`'जिस्म'`, `'हवस'`, `'क़यामत'`, `'ख़ौफ़'`, `'ज़ख़्म'`) for existential dark-fantasy weight.
  - **Rolling Narrative Context**: Seamlessly threads a 250-word rolling context tail across chapter boundaries, ensuring narrative continuity and pronoun consistency across chapters.
  - **Lexicon Normalization**: Enforces strict post-translation canonical terminology via `normalize_translated_lexicon`.
- **Linguistic Sanitizer & Defense Guardrail ([`audiobook_factory/sanitizer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sanitizer.py))**:
  - **Raw Profanity & Intimacy Preservation:** Zero-loss preservation of earthy Hindustani vocabulary, slang, and somatic erotic textures—never misclassifying raw literary realism as harmful content.
  - **Expanded Neural Vocal Tags:** Validates and preserves expressive inline tags recognized natively by Gemini 3.1 Flash TTS: `[whispers]`, `[shouting]`, `[cold menace]`, `[intimate, breathy]`, `[trembling voice]`, `[sighs]`, `[gasp]`, `[growl]`, `[groan]`, `[spits]`, `[bellowing rage]`, `[breathless exhaustion]`, and `[mocking chuckle]`.
  - **Defense-in-Depth Stripping:** Recursively removes LLM meta-commentary, conversational refusals, Devanagari non-vocal stage directions, markdown fences, and conversational preambles/postambles.
- **Sliding-Window Screenplay Builder ([`audiobook_factory/script_builder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py))**:
  - Dissects prose into discrete `ScreenplaySegment` records with Hollywood Dramaturgy Director prompts.
  - **Sociolect Traits Integration:** Binds character profiles to distinct sociolect idiolects (`sociolect_trait` in `CharacterProfile`, e.g. `'COLD_CYNIC'`, `'CAUSTIC_ARISTOCRAT'`, `'THARKI_BARD'`).
  - **Cynical Protagonist Grunt Engine:** Automatically tags weary, cynical protagonist reactions with signature neural grunts (`[growl] हूँ...`, `[sighs] हम्म...`) and enforces `pause_after_ms` of 1000–1400ms for dramatic pregnant pause prosody.
  - **Duraangi Zubaan (Inner Monologues):** Encodes unspoken internal thoughts contrasting outward speech as `[whispers] (मन में: ...)`, paired with `spatial.proximity: 'intimate_close'` and `acoustic_env: 'binaural_whisper'`.
  - **ASMR Intimacy Staging:** Automatically assigns `spatial.proximity: "intimate_close"`, dead-center `spatial.pan: 0.0`, dynamic intensity `low`, `pre_roll_breath_ms: 200-250`, and music sidechain attenuation of `-22.0 dB` ("The Erotic Silence").
  - Employs a sliding-window character memory bank to eliminate narrator fallback and preserve character continuity across multi-chapter novels.
- **Precision Speech Synthesizer ([`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py))**:
  - Primary: Google Gemini 3.1 Flash Cloud TTS API (`gemini-2.5-flash-preview-tts` / `gemini-3.1-flash-tts-preview`).
  - Personas: `Aoede` (melodic narration), `Charon` (dark authoritative male), `Puck`, `Fenrir`, `Orus`, `Zephyr`.
  - Token-Bucket concurrency pool with exponential backoff on HTTP 429 quota exhaustion.
  - Multi-key rotation pool with persistent state tracking, automated date-rollover, and stealth cadence pacing.
  - **Quota Isolation**: Dedicated `service="text"` key pool routing for auxiliary LLM prompts (mood analysis, dramaturgy) isolates text requests from depleting scarce 10 RPD Gemini TTS quotas.
  - Automatic `.env` key sanitization (`strip("'\"")`) prevents malformed header HTTP 400 errors.

---

### 2. Room 2: Agentic Directing Layer
*Purpose: Autonomous soundscape dramaturgy, silence carving, and musical thematic scoring.*

> [!IMPORTANT]
> **STRICT ARCHITECTURAL MANDATE: Complete Creative Autonomy for Agents**
> Only autonomous AI agents are permitted to make creative decisions. Downstream scripts, DSP routines, and CLI pipelines must NOT override agent directives. `AgentDirector` creates the `CreativeManifest` autonomously; `CinemaAudioEngine`, `ManifestRenderer`, and audio DSP chains operate strictly as deterministic, reproducible execution runtimes.

- **Sonic Bible ([`audiobook_factory/sonic_bible.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sonic_bible.py))**:
  - Maintains a persistent `sound_bible.json` per project.
  - Registers character leitmotifs (associated track, instrument timbre, canonical tempo BPM, dramatic intent, track offset).
  - Specifies spatial acoustic profiles (`WorldAcousticProfile`) defining reverberation and room physics.
- **Autonomous Agent Director ([`audiobook_factory/agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py))**:
  - **Pass 1 (Dramaturgy & Silence Carving)**: Enforces the **broadcast audio drama standard of at least 60.0% acoustic silence**. Music is carved surgically around dramatic peaks; non-stop wall-to-wall music is strictly banned.
  - **Pass 2 (Music Director)**: Dynamically formulates FTS5 queries against the sound catalog for valence, arousal, tempo, and timbre. Injects character leitmotifs bound to the Sonic Bible. Gracefully falls back to pure silence if no asset matches (zero hardcoded tracks).
  - **Pass 3 (Acoustic Foley & Whisper Collision Attenuation)**: Analyzes dialogue verbs and objects for footsteps, weapon draws, doors, and weather transitions. Calls `attenuate_foley_whisper_collisions` to apply $-6\text{ dBFS}$ attenuation to any Foley cue that coincides with whispered or intimate dialogue lines.
  - Emits the validated **[`CreativeManifest`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/contracts.py)** (supporting direct `.save_to_file()` and `.from_file()` serialization).

---

### 3. Room 3: Acoustic Compositor & DSP Mastering
*Purpose: Surgical multitrack assembly, sidechain ducking, acoustic impulse response, and EBU R128 mastering.*

- **SQLite FTS5 Sound Bank ([`audiobook_factory/sound_bank.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank.py))**:
  - 100% free CC0/royalty-free local audio asset warehouse indexed with SQLite Full-Text Search (FTS5).
  - Categorizes tracks into `BGM`, `AMB`, and `SFX` with metadata: BPM, valence, arousal, dominant instruments, and duration.
- **Manifest Soundscape Renderer ([`audiobook_factory/manifest_renderer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/manifest_renderer.py))**:
  - Constructs complex dynamic FFmpeg `filter_complex` graphs.
  - **Whisper-Safe Sidechain Ducking**: Detector threshold set to `0.018` linear (-34.9 dBFS) with 15ms attack and 350ms release. Seamlessly accommodates **-22.0 dB "Erotic Silence"** ASMR cues and whispered dialogue without false gating or music pumping.
  - **Music-Only 2.2kHz Spectral Notch Carving**: Carves a -5.5 dB notch (`equalizer=f=2200:t=q:w=1.5:g=-5.5`) strictly into the music stem `[0:a]`, preserving the high-frequency snap of Foley cues and the spatial depth of Ambience beds without vocal masking.
  - **Dynamic Impulse Response Reverb**: Adapts wet send volume and delay reflections to scene presets (`cathedral`, `bedroom`, `open_road`, `stone_hall`, `binaural_whisper`).
- **DSP Vocal Mastering ([`audiobook_factory/mastering.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/mastering.py))**:
  - 5-stage DSP chain:
    1. SOXR 48kHz sinc resampling
    2. Highpass subsonic filter (60Hz cut)
    3. Neural vocoder broadband denoiser (`afftdn`)
    4. De-esser filter (6.7kHz sibilance control)
    5. Lowpass ultrasonic filter (14kHz air ceiling)
  - **Adult Literary Mode DSP Calibration**:
    - **Organic Breath Preservation:** Intimate pre-roll breaths (`pre_roll_breath_ms: 200-250`) and Grunt Engine pause buffers (`pause_after_ms: 1000-1400ms`) pass transparently through the mastering chain without noise-gate truncation or clipping.
    - **Dynamic Headroom Calibration:** Explosive combat cries trigger `limiter=0.82`, `attack=2ms`, `TP=-2.0 dBTP`. Soft whisper/erotic scenes calibrate `effective_lra = 6.0` to preserve close-mic nuance.
    - **Dialogue Spatial Staging & ASMR Centering:** Constant-power stereo azimuth panning anchors Narrator and intimate ASMR lines dead-center ($pan = 0.0$, `intimate_close`) while subtly staging cast members across the stereo panorama ($r \ge 0.85$).
- **Master Timeline Ledger ([`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py))**:
  - Standardized Gate 4.5 ledger written canonically to `scripts/chapter_XXX_timeline_ledger.json` and mirrored to `soundscapes/chapter_XXX_timeline_ledger.json` for reliable downstream validation.

---

### 4. Room 4: Cinema Discrete Multi-Stem Engine
*Purpose: Professional film/broadcast stem separation and delivery package certification.*

- **Cinema Audio Engine ([`audiobook_factory/cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py))**:
  - Renders and preserves **5 discrete stems** standardized to 48,000 Hz 16-bit stereo PCM:
    1. **`stem_DX.wav`**: Dialogue & Voice Acting (preserving full dynamic range for grunts, whispers, and visceral shouts)
    2. **`stem_MX.wav`**: Musical Score & Cues (with isolated 2.2kHz notch)
    3. **`stem_FX.wav`**: Physical Foley & SFX (tactile tavern and combat impacts)
    4. **`stem_AMB.wav`**: Environmental Background Ambience
    5. **`stem_ME.wav`**: Combined Music & Effects
  - Generates the unified **`chapter_XXX_stem_ledger.json`** recording duration, integrated LUFS, and true peak across every stem.
- **M4B Container Packager ([`audiobook_factory/packager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py))**:
  - Assembles all mastered chapters into a single chapterized `.m4b` container with embedded cover artwork and `FFMETADATA1` chapter markers.
  - **AAC Packaging Safety**: Inspects all input chapters with `is_all_aac`. Non-AAC or uncompressed WAV (`pcm_s16le`) chapters are automatically transcoded to high-fidelity AAC (`-c:a aac -b:a 192k`), preventing FFmpeg container multiplexer crashes.
  - Guarantees strict timeline monotonicity and clean seekability (`+faststart`) in Audible, Apple Books, and Smart AudioBook Player.

---

## 🌉 The 7 Metadata Bridges (Silo Elimination Matrix)

The system bridges all 7 critical producer-consumer metadata silos:

| Silo # | Metadata Produced | Upstream Producer | Downstream Consumer | How It Is Bridged in v4.0 |
|:---:|---|---|---|---|
| **S1** | `pause_after_ms`<br>`pre_roll_breath_ms` | `script_builder.py` | `mastering.py` | Passed to `concatenate_and_master_chapter`, generating micro-silence, 1000–1400ms Grunt Engine pauses, & 200–250ms ASMR breath intake pre-rolls. |
| **S2** | `intensity_level`<br>(`low`, `medium`, `explosive`) | `script_builder.py` | `mastering.py` | Explosive combat lines trigger True Peak ceiling -2.0 dBTP and limiter 0.82; whisper/erotic lines (`low`) tighten LRA to 6.0 LU. |
| **S3** | `spatial.pan`<br>`spatial.proximity` | `script_builder.py` | `mastering.py` | `spatial_staging=True` renders constant-power stereo panning (Narrator & `intimate_close` ASMR dead-center 0.0, cast dynamically panned). |
| **S4** | `acoustic_env`<br>IR Presets | `script_builder.py` | `manifest_renderer.py` | Dynamic reverb presets (`cathedral`, `bedroom`, `open_road`) adapt decay and wet mix. |
| **S5** | `SceneSoundscapeManifest` (4 Layers) | `scene_acoustics.py` | `cinema_audio_engine.py` | Multi-scene sequential compositor layers environmental beds across chapter timelines. |
| **S6** | Character Leitmotifs | `sonic_bible.py` | `agent_director.py` | Loaded via `project_dir / "sound_bible.json"` and bound to Pass 2 music cues. |
| **S7** | Quality Gate Suite | `gate_auditor.py` | `orchestrator.py` | Wired inline across pipeline stages (Gates 0, 1, 6A, 6C) and chapter production (Gates 2, 3.5, 5, 5.2, 5.3). |
