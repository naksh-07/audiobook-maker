# 🎙️ Audiobook Maker (Audiobook Factory v4.0)

> **Autonomous Studio-Grade Cinematic Audio Drama Production Engine with Multi-Cast Character Attribution, Dynamic BGM Scoring, SQLite FTS5 Foley & Native M4B Packaging.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-6.0%2B%20%7C%208.0-red.svg)](https://ffmpeg.org/)
[![TTS Engine](https://img.shields.io/badge/TTS-Google%20Gemini%203.1%20Flash%20API-green.svg)](https://ai.google.dev/)
[![Broadcast Standard](https://img.shields.io/badge/Broadcast-EBU%20R128%20(-19%20LUFS)-purple.svg)](docs/AUDIO_ENGINEERING.md)
[![Verification](https://img.shields.io/badge/Tests-197%20Passing%20(100%25)-brightgreen.svg)](tests/)
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
        Book["Raw Book (PDF / EPUB / TXT)"] --> Extractor["Universal Extractor (Zero Pip)"]
        Extractor --> Chapters["Structured Chapters (.txt / .md)"]
        Chapters --> Translator["Literary Hindustani Translator (Two-Pass)"]
        Translator --> ScriptBuilder["Sliding-Window Screenplay Builder (Pydantic v2)"]
        ScriptBuilder --> Dispatcher["Token-Bucket Gemini 3.1 Flash TTS Dispatcher"]
        Dispatcher --> AudioChunks["Audio Segments (24kHz Mono 16-bit PCM)"]
    end

    subgraph Room2["🚪 Room 2: Agentic Directing Layer"]
        Bible["Sonic Bible & Leitmotifs (sound_bible.json)"] --> Director["Autonomous AgentDirector"]
        AudioChunks --> Director
        Director --> SilenceCarve["Pass 1: Silence Carving (>= 60.0% Silence Mandate)"]
        SilenceCarve --> MusicDir["Pass 2: Dynamic FTS5 Music Director"]
        MusicDir --> FoleyMiner["Pass 3: Acoustic Foley Miner"]
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
        VocalDSP --> CinemaEngine["Cinema Multi-Stem Engine"]
        CinemaEngine --> Stems["5 Discrete Stems (DX, MX, FX, AMB, ME)"]
        CinemaEngine --> Master["Cinema Master (-19 LUFS, -1.5 dBTP)"]
        CinemaEngine --> Ledger["chapter_XXX_stem_ledger.json"]
    end

    Room4 --> Packager["FFMETADATA1 Chapter Generator & Packager"]
    Packager --> M4B["Deliverable Audiobook (.m4b with Artwork)"]
```

---

## ✨ Key Technical Highlights

### 1. Dual-Engine Speech Synthesis with Token-Bucket Concurrency
- **Primary:** **Google Gemini 3.1 Flash Cloud TTS API** (`gemini-3.1-flash-tts-preview`). Expressive personas tailored for multilingual cadence:
  - `Aoede`: Polished, melodic feminine narration (top choice for Hindi / Hinglish).
  - `Charon`: Deep, authoritative, resonant masculine cadence (ideal for fantasy / dark mystery).
  - `Orus` / `Fenrir` / `Puck` / `Zephyr`: Distinct character dialogue casting.
- **Emergency Standby:** Automatic persona-mapped fallback to local GPU **Kokoro & Goonj-1-82M** server if cloud quota drops.

### 2. The 6-Gate Independent Verification Suite
Quality is mathematically audited at every stage of the pipeline:
- **Gate 0:** Source Text & Translation Coverage Parity
- **Gate 1:** Character Voice Casting & Collision Elimination
- **Gate 2:** Screenplay Scripting Schema & Prosody (Pydantic v2)
- **Gate 3.5:** Acoustic Pre-Flight Feasibility Guard ($\ge 60\%$ acoustic silence mandate)
- **Gate 5 / 5.2 / 5.3:** EBU R128 Master, Dialogue-to-Music Ratio ($\text{DMR} \ge +12\text{ dB}$), and Stereo Phase ($r \ge 0.85$)
- **Gate 6A / 6B / 6C / 6D:** Cross-Chapter Voice Continuity, Loudness Consistency, and TOC Monotonicity

### 3. Hollywood-Grade Acoustic DSP Mastering
- **Whisper-Safe Sidechain Ducking**: Detector calibrated to `0.018` linear (-34.9 dBFS) with $15\text{ ms}$ attack and $350\text{ ms}$ release. Soft whispers trigger music ducking without audio clipping.
- **2.2kHz Spectral Notch Carving**: Attenuates music by $-5.5\text{ dB}$ at $2,200\text{ Hz}$ ($Q=1.5$) during speech to guarantee vocal intelligibility.
- **Dialogue Spatial Soundstage**: Constant-power stereo azimuth panning anchors Narrator dead-center ($pan = 0.0$) while subtly positioning cast characters across the stereo stage, maintaining 100% mono phase compatibility ($r \ge 0.85$).
- **Dynamic Headroom Calibration**: Explosive scenes tighten the limiter to `0.82` with True Peak ceiling `-2.0 dBTP`. Soft whisper scenes calibrate dynamic Loudness Range (`LRA = 6.0 LU`).
- **Auto-Janitor Safety Shield**: Raw WAV chunks are strictly preserved if master rendering or quality verification fails, protecting your API quota.

---

## 📚 Complete Documentation Hub

| Document | Description |
|---|---|
| **[🏛️ Architecture Blueprint](docs/ARCHITECTURE.md)** | In-depth breakdown of the 4 rooms, 5 stems, and the 7 metadata bridges. |
| **[🎓 End-to-End Tutorial & Cookbook](docs/TUTORIAL_E2E.md)** | Step-by-step recipes: 1-click runs, English audio drama, manual directing, quota resume, and DAW stems. |
| **[💻 CLI Reference](docs/CLI_REFERENCE.md)** | Full command reference for all 17 autonomous and modular production commands. |
| **[📚 API Reference](docs/API_REFERENCE.md)** | Pydantic v2 data models, public engine classes, and method signatures across 28 modules. |
| **[🎛️ Audio Engineering & DSP](docs/AUDIO_ENGINEERING.md)** | EBU R128 mastering, sidechain ducking, spectral carving, and reverb presets. |
| **[🛡️ Quality Gates Manual](docs/QUALITY_GATES.md)** | Complete specification of Gates 0 through 6D, thresholds, and CLI audit syntax. |
| **[🎹 Sound Bank & Asset Catalog](docs/SOUND_BANK.md)** | SQLite FTS5 database schema, Sonic Genome indexing, UCS categories, and cloud CC0 seeding. |
| **[🤖 AI Agent & MCP Integration](docs/MCP_AGENT_INTEGRATION.md)** | Autonomous agent workflows, Agent Skills (`novel-audiobook-factory`, `audio-engineer-ffmpeg`), and MCP tools. |
| **[🛠️ Developer Guide](docs/DEVELOPER_GUIDE.md)** | Development environment setup, testing standards, and contribution guide. |

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.10+
- FFmpeg 6.0+ (compiled with `libsoxr` and `aac` support)
- Poppler Utilities (`pdftotext` optional, for PDF extraction)

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

The codebase maintains **197 passing unit tests** across all modules with a zero-regression invariant:

```powershell
# Run full regression suite
python -m unittest discover tests -p "test_*.py"
```

---

## 🤝 Contributing

We welcome contributions! Please review our [Contributing Guidelines](CONTRIBUTING.md) and [Developer Guide](docs/DEVELOPER_GUIDE.md) for details on engineering standards and pull requests.

---

## 📜 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for details.

Developed with ❤️ by **[Suraj (naksh-07)](https://github.com/naksh-07)**.
