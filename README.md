# 🎙️ Audiobook Maker (Audiobook Factory v4.0)

> **Autonomous Studio-Grade Cinematic Audio Drama Production Engine with Multi-Cast Character Attribution, Dynamic BGM Scoring, SQLite FTS5 Foley & Native M4B Packaging.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-6.0%2B%20%7C%208.0-red.svg)](https://ffmpeg.org/)
[![TTS Engine](https://img.shields.io/badge/TTS-Google%20Gemini%203.1%20Flash%20API-green.svg)](https://ai.google.dev/)
[![Broadcast Standard](https://img.shields.io/badge/Broadcast-EBU%20R128%20(-19%20LUFS)-purple.svg)](docs/AUDIO_ENGINEERING.md)
[![Verification](https://img.shields.io/badge/Tests-232%20Passing%20(100%25)-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)

---

## 📖 Overview

**Audiobook Maker v4.0** is an enterprise-grade, autonomous audiobook production system modeled after the high-end multi-track standards of **Audible Drama** and **GraphicAudio ("A Movie in Your Mind")**.

It transforms raw literature (**EPUB, PDF, TXT, Markdown**) into broadcast-ready dramatized audiobooks featuring literary Hindustani translation, multi-voice character casting, surgical mood-matched musical scoring, tactile Foley sound effects, and native chapterized `.m4b` containers.

---

## 🏛️ The 4-Room Audio Drama Architecture

```mermaid
flowchart TD
    subgraph Room1["🚪 Room 1: Creative Production Room"]
        Book["Raw Book (PDF / EPUB / TXT)"] --> Extractor["Universal Extractor (Native PyPDF + Zero-Pip Fallback)"]
        Extractor --> Chapters["Structured Chapters (.txt / .md)"]
        Chapters --> Translator["Literary Hindustani Translator (Rolling Context & Glossary)"]
        Translator --> ScriptBuilder["Sliding-Window Screenplay Builder (Pydantic v2)"]
        ScriptBuilder --> Dispatcher["Token-Bucket Gemini 3.1 Flash TTS Dispatcher"]
        Dispatcher --> AudioChunks["Audio Segments (24kHz Mono 16-bit PCM)"]
    end

    subgraph Room2["🚪 Room 2: Agentic Directing Layer (Strict Agent Mandate)"]
        Bible["Sonic Bible & Leitmotifs (sound_bible.json)"] --> Director["Autonomous AgentDirector (No Script Overrides)"]
        AudioChunks --> Director
        Director --> SilenceCarve["Pass 1: Silence Carving (>= 60.0% Silence Mandate)"]
        SilenceCarve --> MusicDir["Pass 2: Dynamic FTS5 Music Director"]
        MusicDir --> FoleyMiner["Pass 3: Acoustic Foley Miner + Whisper Attenuation"]
        FoleyMiner --> Manifest["CreativeManifest v3.0 / CinemaAudioManifest"]
    end

    subgraph Room3["🚪 Room 3: Acoustic Compositor & DSP Mastering"]
        Manifest --> Renderer["Manifest Soundscape Renderer"]
        SoundBank["SQLite FTS5 CC0 Sound Bank"] --> Renderer
        Renderer --> Ducking["Whisper-Safe Sidechain Ducking (0.018 Threshold)"]
        Renderer --> Reverb["Dynamic Room Reverb Presets (Cathedral, Bedroom, Open Road)"]
        Renderer --> VocalDSP["5-Stage Vocal DSP Chain (SOXR 48kHz + EBU R128)"]
    end

    subgraph Room4["🚪 Room 4: Cinema Discrete Multi-Stem Engine"]
        VocalDSP --> CinemaEngine["Cinema Multi-Stem Engine (Music-Only 2.2kHz Notch)"]
        CinemaEngine --> Stems["5 Discrete Stems (DX, MX, FX, AMB, ME)"]
        CinemaEngine --> Master["Cinema Master (-19 LUFS, -1.5 dBTP)"]
        CinemaEngine --> Ledger["chapter_XXX_stem_ledger.json"]
    end

    Room4 --> Packager["FFMETADATA1 Chapter Generator & AAC Packager"]
    Packager --> M4B["Deliverable Audiobook (.m4b with FastStart Artwork)"]
```

---

## ✨ Key Technical Highlights

### 1. Cloud Speech Synthesis & Quota Isolation
- **Primary Engine:** **Google Gemini 3.1 Flash Cloud TTS API** (`gemini-3.1-flash-tts-preview`). Expressive personas tailored for multilingual cadence:
  - `Aoede`: Polished, melodic feminine narration (top choice for Hindi / Hinglish).
  - `Charon`: Deep, authoritative, resonant masculine cadence (ideal for fantasy / dark mystery).
  - `Orus` / `Fenrir` / `Puck` / `Zephyr`: Distinct character dialogue casting.
- **Quota Intelligence & Isolation:** Dedicated `service="text"` vs `service="tts"` key pool routing prevents auxiliary text prompts from depleting scarce 10 RPD Gemini TTS quotas. Multi-key persistent rotation pool with automatic date rollover, stealth cadence pacing, and automated `.env` quote stripping.

### 2. Multi-Gate Independent Verification Suite (Gates 0 - 6D)
Quality is mathematically audited at every stage of the pipeline:
- **Gate 0:** Source Text & Translation Coverage Parity
- **Gate 1:** Character Voice Casting & Collision Elimination
- **Gate 2:** Screenplay Scripting Schema & Prosody (Pydantic v2)
- **Gate 3 / 3.5:** Dynamic Manifest Feasibility Guard ($\ge 60\%$ acoustic silence mandate; accepts `CreativeManifest` & director-managed workflows)
- **Gate 5 / 5.2 / 5.3:** EBU R128 Master (standardized $\pm 1.0\text{ LU}$ tolerance), Dialogue-to-Music Ratio ($\text{DMR} \ge +12\text{ dB}$), and Stereo Phase ($r \ge 0.85$)
- **Gate 6A / 6B / 6C / 6D:** Cross-Chapter Voice Continuity, Inter-Chapter Loudness Consistency ($\le 1.0\text{ LU}$), TOC Monotonicity, and M4B Container Certification

### 3. Hollywood-Grade Acoustic DSP Mastering
- **Strict Agent Creative Mandate:** All creative acoustic choices (scoring, leitmotifs, Foley placement, pacing) belong strictly to autonomous agents (`AgentDirector`). Lower engine layers (`CinemaAudioEngine`, `ManifestRenderer`, DSP) are 100% deterministic execution runtimes with zero script overrides.
- **Music-Only 2.2kHz Spectral Notch EQ:** Parametric notch filter ($-5.5\text{ dB}$ at $2,200\text{ Hz}$, $Q=1.5$) is isolated strictly to the Music Bus `[0:a]`, preserving crisp Foley transients and expansive Ambience beds.
- **Whisper Collision Attenuation:** Foley cues triggered during quiet or whispered dialogue segments receive automatic $-6\text{ dBFS}$ attenuation via `attenuate_foley_whisper_collisions`.
- **Whisper-Safe Sidechain Ducking:** Detector calibrated to `0.018` linear (-34.9 dBFS) with $15\text{ ms}$ attack and $350\text{ ms}$ release, smoothly ducking music even during intimate whispers.
- **Dialogue Spatial Soundstage:** Constant-power stereo azimuth panning anchors Narrator dead-center ($pan = 0.0$) while subtly positioning cast characters across the stereo stage, maintaining 100% mono phase compatibility ($r \ge 0.85$).
- **Dynamic Headroom Calibration:** Explosive scenes tighten the limiter to `0.82` with True Peak ceiling `-2.0 dBTP`. Soft whisper scenes calibrate dynamic Loudness Range (`LRA = 6.0 LU`).
- **Auto-Janitor Safety Shield:** Raw WAV chunks are strictly preserved if master rendering or quality verification fails, protecting your API quota.

### 4. Container Reliability & Robust Orchestration
- **M4B AAC Packaging Safety:** Replaced brittle container copy with strict AAC validation (`is_all_aac`). Uncompressed WAV stems (`pcm_s16le`) or non-AAC assets are automatically transcoded to AAC (`-c:a aac -b:a 192k`) with `+faststart` MP4 metadata atom positioning.
- **Dynamic Vocal Track Inference:** Removed hardcoded paths; dynamically discovers vocal stems (`.wav` and `.m4a`) across project directory hierarchies.
- **Regex Chapter Parsing:** Script and audio chunk extraction utilizes robust regex `chapter_(\d+)` patterns, preventing chapter renumbering during partial runs.
- **Fast Zero-Quota PDF Extraction:** Integrated `pypdf>=5.0` for instantaneous local digital PDF parsing, bypassing the 8,192 token window before falling back to multimodal vision.

### 5. Adult Literary Fidelity & HBO/Manto Intimacy Framework (ADR-016 & ADR-019)
- **Unapologetic Raw Hindustani Street Grit & Period Profanity:** Eliminates prudish television euphemisms and sanitized bowdlerization (no more replacing 'bastard' with 'दुष्ट' or 'whore' with 'बुरी स्त्री'). Incorporates authentic, earthy Hindustani curses and dark tavern vitriol (`'गांड'`, `'भोसड़ीके'`, `'लंड'`, `'रांड'`, `'मादरचोद'`, `'बकचोदी'`, `'सूअर का पेशाब'`). Governed by the **19-to-21 Amplification Rule**, elevating mild source prose to visceral Desi impact for gut-punch delivery.
- **The 70/30 Anti-Parody Invariant:** Preserves a sacred **70% Canon Lore / 30% Sensory Desi Amplification** balance. European dark-fantasy mythos, monster classifications (specters, strigas, cursed beasts), and geographic realms remain untampered and un-corrupted; the 30% sensory layer is localized through organic tavern grit, Chambal/UP street idioms, and dynamic honorific power shifts (`तू` $\leftrightarrow$ `माई-बाप / सरकार`) without devolving into comic tapori spoofs.
- **Rule 8 Somatic Intimacy, Dirty Banter & Raw Erotica:** Mandates visceral erotic vocabulary, somatic friction, and bedroom dirty talk (`'लंड'`, `'चूत'`, `'गांड'`, `'चोदना'`, `'मसलना'`, `'तपती कमर'`, `'भीगी प्यास'`, `'बेकाबू सांसें'`) during passionate encounters.
- **The "Nothing Above Source" & "Anti-Cringe" Invariants:** Respects narrative truth—never fabricates explicit sexual acts out of thin air if characters are merely conversing. But when the source contains sexual tension, nudity, or passion, it renders with full Desi heat. Clinical biology-textbook words (`'योनि'`, `'लिंग'`) that sound like hospital autopsy reports remain permanently banned.
- **Permanent Gemini Flash TTS Safety Unlock:** Explicitly passes `safetySettings: [BLOCK_NONE]` across all 4 categories (`HARM_CATEGORY_HARASSMENT`, `HARM_CATEGORY_HATE_SPEECH`, `HARM_CATEGORY_SEXUALLY_EXPLICIT`, `HARM_CATEGORY_DANGEROUS_CONTENT`) in [`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py), eliminating false-positive censorship blocks while maintaining 100% synthesis success.
- **ASMR Proximity Audio & "The Erotic Silence":** Intimate dialogue lines are staged with dedicated ASMR acoustic parameters: `spatial.proximity: "intimate_close"`, dead-center azimuth `spatial.pan: 0.0`, dynamic intensity `low`, `200-250ms` organic breath pre-roll, and music sidechain attenuation carved down to `-22.0 dB`.
- **Cynical Protagonist Grunt Engine & Duraangi Zubaan:** Encodes weary, cynical protagonist idiolects using signature neural grunts (`[growl] हूँ...`, `[sighs] हम्म...`) paired with `1000-1400ms` pregnant pauses. Models internal vs. external dissonance (*Duraangi Zubaan* inner monologues) via `[whispers] (मन में: ...)` rendered in `binaural_whisper` acoustic environments.
- **Configuration & Backward Compatibility:** Controlled via the `adult_literary_mode: bool = Field(default=True)` configuration flag in [`ProjectConfig`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/contracts.py) and [`PipelineOrchestrator.run_autonomous_pipeline`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py), preserving 100% backward compatibility for standard literature projects.

### 6. Hollywood & AAA-Game Combat Sound Design & Action Acoustics (ADR-017)
- **The 3-Layer Combat Sandwich:** Crafts heart-stopping kinetic strikes across 3 distinct frequency bands:
  - *Layer 1 (Transient Bite):* 2.0 kHz – 7.5 kHz razor-sharp blade clangs, arrow releases, and armor parries.
  - *Layer 2 (Anatomical Body):* 180 Hz – 1.4 kHz visceral flesh lacerations, bone crunches, and heavy body thuds.
  - *Layer 3 (LFE Sub-Thump):* 45 Hz – 85 Hz tuned 52Hz sub-bass solar plexus shockwave.
- **Action-Beat Splitting (Temporal Isolation):** Major kinetic strikes never collide with spoken dialogue. The screenplay builder automatically isolates combat choreography into dedicated 800ms – 1500ms speech-free intervals (`speaker: "Foley"`, `text: "[ACTION]"`).
- **Dual-Perspective Spatial Staging:** Attacker strikes/vocals pan Left ($-0.6$), Defender parries/reactions pan Right ($+0.6$), and Fatal Clashes land Dead Center ($0.0$).
- **Strict Mono Sub-Bass Anchor (< 90Hz):** All LFE drops, warhammer thumps, and blast waves are centered at pan $0.0$ and summed to mono, guaranteeing mean phase correlation $r \ge 0.85$ and zero phase cancellation on mono speakers.
- **Dynamic Ducking & Tinnitus Shockwave:** `PROFILE_COMBAT_SHOCK` ($-24\text{ dB}$ attenuation, $4000\text{ ms}$ release) and `PROFILE_COMBAT` ($-22\text{ dB}$, $250\text{ ms}$ release) in `acoustic_bus_matrix.py`. "The Smother Cut" applies 150–250ms of hard digital silence right before fatal impacts.
- **Staccato Combat Prose & Neural Tags:** Narrative sentences fracture into rapid 2–4 word staccato beats ('कदम पीछे। तलवार का पैंतरा। वार। चूक गया!'), paired with validated neural tags: `[bellowing battlecry]`, `[combat strain]`, `[diaphragm strain]`, `[guttural grunt on blade deflect]`, `[spits blood]`, `[choked gasp]`, `[ragged heaving pant]`, `[slow motion]`.

### 7. Harry Potter / Pottermore Grade 4-Stem Decoupled Scene Acoustics (ADR-018)
- **4-Stem Decoupled Scene Acoustics:** Replaces flat single-loop ambience with 4 distinct stems per scene managed via [`SceneSoundscapeManifest`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/scene_acoustics.py):
  - *Stem 1 (Base Room Tone):* Architectural cavity resonance ($-34$ to $-36\text{ LUFS}$, stereo width 1.35).
  - *Stem 2 (Weather & Macro World):* Exterior storm, gale, blizzard, or rain ($-30$ to $-32\text{ LUFS}$, stereo width 1.40).
  - *Stem 3 (Crowd & Life Wallah):* Taverns, castle halls, cutlery, murmurs ($-28$ to $-30\text{ LUFS}$, stereo width 1.30).
  - *Stem 4 (Stochastic Spot Transients):* Subtle micro-events ($-22$ to $-26\text{ dBFS}$) triggered in dialogue pauses.
- **Acoustic Barrier Occlusion (< 18kHz):** Dynamic low-pass barrier filter ($1200\text{ Hz} - 1500\text{ Hz}$) naturally muffles exterior weather stems when characters are indoors, sweeping cleanly to $18\text{ kHz}$ upon door open action beats.
- **Zero-Token Local Stochastic Transient Generator:** Procedurally discovers $\ge 600\text{ ms}$ speech pauses from `TimelineLedger`, scattering non-repetitive micro-events (distant owls, candle sparks, floor creaks, ticking clocks) without consuming LLM tokens.
- **Voice Limiter & Priority Stealing:** `filter_concurrency_window` ($200\text{ ms}$ window, max 3 concurrent Foley cues) eliminates transient clutter, collisions, and acoustic mud.
- **Dialogue-to-Masking Ratio (DMR $\ge +10.0$ dB) Validation:** Automated proxy verification in `CinemaAudioEngine` and `StemLedger` guarantees dialogue clarity over the composite background bed.
- **Offline Foley & Magic Composite Asset Baker:** [`scripts/bake_foley_composites.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/scripts/bake_foley_composites.py) pre-renders multi-phase magic spells (`magic_lumos_light.wav`, `magic_expelliarmus_kinetic.wav`) and tactile props (`tactile_parchment_quill_scratch.wav`), indexing them permanently in SQLite FTS5 for zero-latency retrieval with zero runtime FFmpeg graph bloat.

### 8. Forensic Audit Remediation & Comprehensive Engine Hardening (ADR-020)
Post-integration forensic testing revealed 13 critical edge cases across production pipelines, all mathematically remediated and verified:
- **Contract Deserialization Rehydration:** Added `@model_validator(mode="after")` to [`CreativeManifest`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/contracts.py) ensuring nested `scene_acoustics` automatically reinstantiates as a [`SceneSoundscapeManifest`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/scene_acoustics.py) instance upon JSON deserialization.
- **Screenplay Dict Unpacking:** CLI commands and orchestrators unpack dictionary-wrapped scripts (`{"script_version": "2.0", "segments": [...]}`) safely without attribute errors.
- **Defensive TTS Safety & FinishReason Parsing:** Guarded [`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py) against empty candidate arrays and explicit finish reasons (`SAFETY`, `RECITATION`, `BLOCKLIST`), raising informative `ValueError` with `promptFeedback` context instead of unhandled `IndexError`.
- **Atomic Audio Generation & Verification:** Gemini TTS writes to `.tmp.wav`, validates Signal-to-Noise Ratio (SNR), clipping distortion, and silent DC corruptions, automatically unlinking corrupted files and promoting verified audio atomically via `.replace()`.
- **Text Service Backoff Cooldown:** Extends temporary quota cooldown handling in [`PersistentKeyPool`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/key_manager.py) to all service routes (`service="text"` and `service="tts"`), eliminating false daily exhaustion exceptions.
- **Dynamic Filter Complex Scripting (>6000 Chars):** Multi-layered ambient scene graphs exceeding 6,000 characters automatically pipe to `-filter_complex_script`, bypassing Windows 8,191-character shell command limit crashes in [`cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py).
- **Gate 3.5 & 4.5 Robustness:** Gate 3.5 seamlessly falls back to Sound Bank FTS5 queries when cue asset paths contain file extensions. Gate 4.5 sets a 44-byte WAV header floor for `[ACTION]` and `Foley` pacing segments, preventing zero-audio beats from failing audits.
- **Sanitizer Bracketed Tag Shield:** Strips bracketed tags before evaluating Latin word counts, allowing heavily-tagged combat battlecries (`[bellowing battlecry] [guttural grunt on blade deflect] वार!`) to pass without being discarded as English leakage.
- **Multi-Layer Stochastic Spacing:** Enforces minimum 250ms spacing between Layer 4 ambient spot transients in [`scene_acoustics.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/scene_acoustics.py).
- **FFMETADATA1 Special Character Escaping:** Special characters (`=`, `;`, `#`, `\`) in book titles and chapter markers are escaped cleanly via `_escape_ffmetadata()` in [`packager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py).
- **CLI Segment Take Deduplication:** Prevents multiple takes per segment index from being concatenated into final chapter masters in `audiobook_cli.py`.

---

## 📚 Complete Documentation Hub

| Document | Description |
|---|---|
| **[🏛️ Architecture Blueprint](docs/ARCHITECTURE.md)** | In-depth breakdown of the 4 rooms, 5 stems, 8 metadata bridges, Adult Literary Mode pipeline integration, and strict agent creative mandate. |
| **[🎬 Cinematic Sound Design & Adult Fidelity](docs/CINEMATIC_SOUND_DESIGN_AND_ADULT_FIDELITY.md)** | Authoritative guide to Hollywood 3-layer combat design (ADR-017), Pottermore 4-stem decoupled scene acoustics (ADR-018), and unfiltered adult intimacy (ADR-019). |
| **[🎓 End-to-End Tutorial & Cookbook](docs/TUTORIAL_E2E.md)** | Step-by-step recipes: 1-click runs, English audio drama, manual directing, quota resume, and DAW stems. |
| **[💻 CLI Reference](docs/CLI_REFERENCE.md)** | Full command reference for all 17 autonomous and modular production commands. |
| **[📚 API Reference](docs/API_REFERENCE.md)** | Pydantic v2 data models, public engine classes, Adult Literary contracts, and method signatures across 29 modules. |
| **[🎛️ Audio Engineering & DSP](docs/AUDIO_ENGINEERING.md)** | EBU R128 mastering, music-only 2.2kHz notch, whisper ducking, barrier occlusion, dynamic filter scripts, and reverb. |
| **[🛡️ Quality Gates Manual](docs/QUALITY_GATES.md)** | Complete specification of Gates 0 through 6D, thresholds, and CLI audit syntax. |
| **[🛡️ Audit Remediation & Hardening](docs/AUDIT_REMEDIATION_AND_HARDENING.md)** | Comprehensive engineering report on P0-P3 fixes and all 13 ADR-020 forensic audit remediations. |
| **[🎹 Sound Bank & Asset Catalog](docs/SOUND_BANK.md)** | SQLite FTS5 database schema, Sonic Genome indexing, UCS categories, and cloud CC0 seeding. |
| **[🤖 AI Agent & MCP Integration](docs/MCP_AGENT_INTEGRATION.md)** | Autonomous agent workflows, Agent Skills (`novel-audiobook-factory`, `audio-engineer-ffmpeg`), and MCP tools. |
| **[🛠️ Developer Guide](docs/DEVELOPER_GUIDE.md)** | Development environment setup, testing standards, and contribution guide. |

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- FFmpeg 6.0+ (compiled with `libsoxr` and `aac` support)
- `pypdf>=5.0` (bundled dependency for fast, zero-quota digital PDF extraction)

### 2. Installation
```bash
git clone https://github.com/naksh-07/audiobook-maker.git
cd audiobook-maker
pip install -e .
```

### 3. Configuration
Copy the configuration template:
```bash
cp .env.example .env
```
Edit `.env` to provide your Gemini API key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
TTS_PRIMARY_BACKEND=gemini_tts
GEMINI_TTS_MODEL=gemini-3.1-flash-tts-preview
GEMINI_DEFAULT_VOICE=Aoede
```

---

## 🛠️ Basic Usage

### 🚀 Autonomous 1-Click Production
Transform any EPUB or PDF novel into a fully dramatized, mastered `.m4b` audiobook:
```bash
python audiobook_cli.py auto books/my_novel.epub \
  --hindi \
  --dramatized \
  --voice Charon \
  --cover covers/cover.jpg \
  --workers 3
```

### 🛡️ Quality Audit Any Project
```bash
# Verify all quality gates across an entire book project
python audiobook_cli.py audit-book audiobooks/projects/my_novel

# Audit a specific chapter
python audiobook_cli.py audit my_novel --chapter 1
```

### 🎹 Manage the SQLite Sound Bank
```bash
# Ingest local audio assets into Sound Bank
python audiobook_cli.py bank ingest path/to/sound_assets/ --workers 4

# Search sound catalog
python audiobook_cli.py bank search "battle drums tension" --limit 5

# Check database statistics
python audiobook_cli.py bank stats
```

---

## 🧪 Verification & Test Suite

The codebase maintains **232 passing unit tests** across all modules with a zero-regression invariant (100% OK, 0 failures, 0 errors):

```powershell
# Run full regression suite (232 tests)
python -m unittest discover tests -p "test_*.py"

# Run dedicated forensic audit remediation suite (ADR-020)
python -m unittest tests/test_forensic_audit_remediation.py
```

---

## 🤝 Contributing

We welcome contributions! Please review our [Contributing Guidelines](CONTRIBUTING.md) and [Developer Guide](docs/DEVELOPER_GUIDE.md) for details on engineering standards and pull requests.

---

## 📜 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

Developed with ❤️ by **[Suraj (naksh-07)](https://github.com/naksh-07)**.
