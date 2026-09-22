# 💻 CLI Reference: Complete Command & Workflow Guide

## Overview

The Audiobook Maker Command-Line Interface ([`audiobook_cli.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_cli.py)) provides complete operational control over the entire cinematic production pipeline. You can run an autonomous end-to-end novel production run with a single command or execute granular subcommands stage-by-stage.

```bash
# Entrypoint via Python script:
python audiobook_cli.py [COMMAND] [OPTIONS]

# Or via installed console scripts (pip install -e .):
audiobook-maker [COMMAND] [OPTIONS]
audiobook-factory [COMMAND] [OPTIONS]
```

---

## 🧭 Command Matrix

| Subcommand | Scope | Description |
|---|---|---|
| **[`auto`](#1-autonomous-production-auto)** | Full Book | 1-Click autonomous pipeline (Extract $\rightarrow$ Translate $\rightarrow$ Script $\rightarrow$ Synth $\rightarrow$ Master $\rightarrow$ Package). |
| **[`produce`](#2-chapter-production-produce)** | Chapter / All | Produces high-fidelity cinematic chapters with 5-track hierarchy and timeline ledger. |
| **[`extract`](#3-universal-document-extraction-extract)** | Ingestion | Ingests EPUB, PDF, TXT, or MD documents into clean Markdown chapters. |
| **[`translate`](#4-literary-translation-translate)** | Translation | Translates extracted chapters into literary dramatic Hindustani with project glossary. |
| **[`script`](#5-screenplay-scripting-script)** | Screenplay | Parses prose into standardized screenplay JSON with speaker attribution and acting tags. |
| **[`synthesize`](#6-speech-synthesis-synthesize)** | Audio (TTS) | Synthesizes dialogue chunks using Google Gemini 3.1 Flash Cloud TTS. |
| **[`timeline`](#7-master-timeline-ledger-timeline)** | Timeline | Builds and verifies the sample-accurate Gate 4.5 Audio Transcript & Timeline Ledger. |
| **[`direct`](#8-agentic-dramaturgy-direct)** | Directing | Directs chapter dramaturgy via `AgentDirector`, producing a `CreativeManifest`. |
| **[`render`](#9-deterministic-manifest-rendering-render)** | Compositing | Compiles and renders a `CreativeManifest` into master audio using FFmpeg filter graphs. |
| **[`master`](#10-vocal-dsp-mastering-master)** | Mastering | Concatenates vocal chunks with 5-stage DSP chain and EBU R128 loudness normalization. |
| **[`bgm`](#11-soundscape--ducking-bgm)** | Mixing | Generates ambient score and applies whisper-safe dynamic sidechain ducking. |
| **[`stems`](#12-discrete-stem-inspection-stems)** | Stems | Inspects and verifies exported 5-track discrete DME stems and stem ledger. |
| **[`audit`](#13-chapter-quality-audit-audit)** | QA (Chapter) | Runs Multi-Gate Independent Verification (Gates 0, 1, 2, 3, 4.5) on a specific chapter. |
| **[`audit-book`](#14-full-book-macro-audit-audit-book)** | QA (Macro) | Runs Macro-Tier Gate 6 certification (Voice Continuity, Loudness, TOC Monotonicity). |
| **[`package`](#15-m4b-container-packaging-package)** | Delivery | Packages all mastered chapters into a chapterized `.m4b` container with cover art. |
| **[`bank`](#16-sound-bank-management-bank--soundbank)** | Assets | Manages, seeds, ingests, and searches the local SQLite FTS5 Sound Bank catalog. |

---

## 1. Autonomous Production (`auto`)

Executes the entire 6-stage production pipeline autonomously in a single command.

```bash
python audiobook_cli.py auto <FILE> [OPTIONS]
```

### Positional Arguments
- `FILE`: Path to input book file (`.epub`, `.pdf`, `.txt`, `.md`).

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--hindi` | Flag | `False` | Translate English source text to literary Hindustani. |
| `--backend` | Choice | `gemini_tts` | Speech synthesis backend (`gemini_tts`). |
| `--voice` | String | `Aoede` | Lead voice persona (`Aoede`, `Charon`, `Puck`, `Fenrir`, `Zephyr`). |
| `--dramatized` | Flag | `False` | Multi-voice character casting vs single narrator reading. |
| `--cover` | Path | `None` | Path to cover artwork image (JPEG/PNG, min $1400 \times 1400$ px). |
| `--workers` | Integer | `3` | Number of concurrent TTS synthesis worker threads. |

### Example
```bash
python audiobook_cli.py auto books/the_witcher.epub \
  --hindi \
  --dramatized \
  --voice Charon \
  --cover covers/witcher.jpg \
  --workers 4
```

---

## 2. Chapter Production (`produce`)

Executes cinematic chapter production incorporating the 5-track standard, token-bucket speech synthesis, timeline ledger assembly, and sidechain ducking.

```bash
python audiobook_cli.py produce <BOOK_SLUG> [OPTIONS]
```

### Positional Arguments
- `BOOK_SLUG`: Name of the project directory inside `audiobooks/projects/`.

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--chapter` | Integer | `None` | Specific chapter number to produce (e.g. `--chapter 1`). |
| `--all` | Flag | `False` | Produce all chapters sequentially. |
| `--voice` | String | `Aoede` | Lead narrator voice persona. |
| `--workers` | Integer | `3` | TTS synthesis worker threads. |
| `--duck-db` | Float | `-16.0` | Sidechain ducking attenuation depth in dB. |

### Example
```bash
# Produce Chapter 3 only:
python audiobook_cli.py produce witcher1 --chapter 3 --voice Charon --workers 3

# Produce all chapters across the project:
python audiobook_cli.py produce witcher1 --all --duck-db -16.0
```

---

## 3. Universal Document Extraction (`extract`)

Ingests raw book files and segments them into structured, clean Markdown chapters.

```bash
python audiobook_cli.py extract <FILE>
```

### Positional Arguments
- `FILE`: Input file path (`.epub`, `.pdf`, `.txt`, `.md`).

### Output Artifacts
- Creates project folder: `audiobooks/projects/<BOOK_SLUG>/`
- Clean chapter files: `audiobooks/projects/<BOOK_SLUG>/extracted/chapter_XXX.md`
- Metadata state: `audiobooks/projects/<BOOK_SLUG>/project_state.json`

### Example
```bash
python audiobook_cli.py extract books/dune.epub
```

---

## 4. Literary Translation (`translate`)

Performs two-pass dramatic Hindustani translation with persistent project glossary.

```bash
python audiobook_cli.py translate <BOOK_SLUG> [OPTIONS]
```

### Positional Arguments
- `BOOK_SLUG`: Project directory name.

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--model` | String | `gemini-flash-latest` | Gemini LLM model identifier for translation. |

### Output Artifacts
- Translated chapters: `audiobooks/projects/<BOOK_SLUG>/translated_hi/chapter_XXX_hi.md`
- Project glossary: `audiobooks/projects/<BOOK_SLUG>/glossary.json`

---

## 5. Screenplay Scripting (`script`)

Parses chapter prose into standardized screenplay JSON with speaker attribution, dynamic emotion tags, spatial panning, and acting directives.

```bash
python audiobook_cli.py script <BOOK_SLUG> [OPTIONS]
```

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--hindi` | Flag | `False` | Source text from `translated_hi/` instead of `extracted/`. |
| `--dramatized` | Flag | `False` | Multi-voice character attribution (sliding-window memory bank). |

### Output Artifacts
- Screenplay scripts: `audiobooks/projects/<BOOK_SLUG>/scripts/chapter_XXX_script.json`
- Character casting roster: `audiobooks/projects/<BOOK_SLUG>/character_roster.json`
- Voice registry: `audiobooks/projects/<BOOK_SLUG>/voice_registry.json`

---

## 6. Speech Synthesis (`synthesize`)

Synthesizes audio segments from screenplay JSON using Google Gemini 3.1 Flash Cloud TTS API with Token Bucket concurrency. Chapter indices are extracted dynamically via regex `chapter_(\d+)`, ensuring partial or non-sequential runs never corrupt chapter numbers.

```bash
python audiobook_cli.py synthesize <BOOK_SLUG> [OPTIONS]
```

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--backend` | Choice | `gemini_tts` | Speech engine backend (`gemini_tts`). |
| `--voice` | String | `Aoede` | Default fallback voice persona. |

### Output Artifacts
- Segment audio files: `audiobooks/projects/<BOOK_SLUG>/audio_chunks/cXXX_sYYYY_voice.wav`
- 24kHz mono 16-bit uncompressed PCM speech segments.

---

## 7. Master Timeline Ledger (`timeline`)

Generates the sample-accurate Gate 4.5 Master Timeline & Audio Transcript Ledger and optionally stitches the continuous vocal master track.

```bash
python audiobook_cli.py timeline <BOOK_SLUG> --chapter <NUM> [OPTIONS]
```

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--chapter` | Integer | *(Required)* | Chapter number to index. |
| `--stitch` | Flag | `False` | Also stitch sample-accurate vocal master track (`chapter_XXX_dialogue.wav`). |

### Example
```bash
python audiobook_cli.py timeline witcher1 --chapter 1 --stitch
```

---

## 8. Agentic Dramaturgy (`direct`)

Invokes `AgentDirector` to run the 3-pass dramaturgy workflow (silence carving, FTS5 music selection, acoustic foley mining) and generate a `CreativeManifest`.

```bash
python audiobook_cli.py direct <BOOK_SLUG> --chapter <NUM> [OPTIONS]
```

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--chapter` | Integer | *(Required)* | Chapter number to direct. |
| `-o`, `--output` | Path | `None` | Custom output manifest JSON path. Defaults to `manifests/chapter_XXX_manifest.json`. |

### Example
```bash
python audiobook_cli.py direct witcher1 --chapter 1
```

---

## 9. Deterministic Manifest Rendering (`render`)

Compiles and renders a `CreativeManifest` into a master audio file using the Deterministic Engine.

```bash
python audiobook_cli.py render --manifest <PATH> [OPTIONS]
```

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--manifest` | Path | *(Required)* | Path to `creative_manifest.json`. |
| `--vocal` | Path | `None` | Optional vocal dialogue track. Dynamically inferred from manifest parent directories if omitted. |
| `--output` | Path | `None` | Optional output audio master destination path. Defaults to `mastered/<chapter_id>_cinematic_v2.m4a`. |
| `--skip-gate3-5` | Flag | `False` | Bypass Gate 3.5 Pre-Flight Feasibility Guard check. |

> [!NOTE]
> **Dynamic Vocal Track Inference**: If `--vocal` is not provided, the CLI dynamically checks `<project>/mastered/` for `<chapter_id>_dialogue.wav`, `<chapter_id>_mastered.wav`, `<chapter_id>_dialogue.m4a`, `<chapter_id>_mastered.m4a`, or simple `.wav` / `.m4a` stems. Hardcoded book paths have been completely eliminated.

### Example
```bash
# Automated vocal stem inference:
python audiobook_cli.py render \
  --manifest audiobooks/projects/witcher1/manifests/chapter_001_manifest.json

# Explicit vocal stem override:
python audiobook_cli.py render \
  --manifest audiobooks/projects/witcher1/manifests/chapter_001_manifest.json \
  --vocal audiobooks/projects/witcher1/mastered/chapter_001_dialogue.wav
```

---

## 10. Vocal DSP Mastering (`master`)

Concatenates speech WAV chunks with 5-stage DSP chain (SOXR 48kHz, rumble cut, de-esser, lowpass) and normalizes to EBU R128 (-19 LUFS). Segments are matched dynamically via regex `chapter_(\d+)` against `c{ch_num:03d}_*.wav` files, preventing chapter renumbering during partial runs.

```bash
python audiobook_cli.py master <BOOK_SLUG>
```

---

## 11. Soundscape & Ducking (`bgm`)

Generates ambient score and applies whisper-safe dynamic sidechain ducking. Automatically discovers dialogue stems across both uncompressed `.wav` and `.m4a` formats (`chapter_*_dialogue.wav`, `chapter_*_mastered.wav`, `chapter_*_dialogue.m4a`, `chapter_*_mastered.m4a`).

```bash
python audiobook_cli.py bgm <BOOK_SLUG> [OPTIONS]
```

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--engine` | Choice | `ambient_bed` | Scoring engine (`ambient_bed`). |
| `--duck-db` | Float | `-16.0` | Sidechain ducking attenuation depth in dB. |

---

## 12. Discrete Stem Inspection (`stems`)

Inspects and verifies exported 5-track discrete DME stems (`stem_DX`, `stem_MX`, `stem_FX`, `stem_AMB`, `stem_ME`) and the chapter stem ledger.

```bash
python audiobook_cli.py stems <BOOK_SLUG> --chapter <NUM>
```

---

## 13. Chapter Quality Audit (`audit`)

Executes Multi-Gate Independent Verification on a single chapter, checking Gate 0, Gate 1, Gate 2, Gate 3, Gate 4.5, and Gate 5.

```bash
python audiobook_cli.py audit <BOOK_SLUG> --chapter <NUM>
```

### Example
```bash
python audiobook_cli.py audit witcher1 --chapter 1
```

---

## 14. Full-Book Macro Audit (`audit-book`)

Executes Macro-Tier Gate 6 certification across the entire novel project.

```bash
python audiobook_cli.py audit-book <PROJECT_DIR_OR_SLUG>
```

### Audit Invariants Verified:
- **Gate 6A**: Cross-chapter character voice continuity.
- **Gate 6B**: Inter-chapter loudness variance $\le 1.0\text{ LU}$.
- **Gate 6C**: TOC timestamp monotonicity and non-overlapping chapters.
- **Gate 6D**: Packaging container specs and cover resolution $\ge 1400 \times 1400$.

---

## 15. M4B Container Packaging (`package`)

Assembles all mastered chapters into a single chapterized `.m4b` container with embedded cover art and `FFMETADATA1` markers.

> [!IMPORTANT]
> **AAC Packaging Safety Guard**: `package` performs pre-flight codec validation (`is_all_aac`). Uncompressed WAV stems (`pcm_s16le`) or non-AAC assets are automatically transcoded to AAC (`-c:a aac -b:a 192k`) with `+faststart` MP4 metadata flags. If all inputs are already AAC (`.m4a` / `.aac`), stream copying (`-c:a copy`) is used for maximum speed.

```bash
python audiobook_cli.py package <BOOK_SLUG> [OPTIONS]
```

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--cover` | Path | `None` | Path to square cover art image. |
| `--enforce-gate6` | Flag | `False` | Abort packaging if any Gate 6 verification check fails. |

---

## 16. Sound Bank Management (`bank` / `soundbank`)

Manages, indexes, seeds, and searches the local SQLite FTS5 Sound Bank catalog.

```bash
python audiobook_cli.py bank <ACTION> [OPTIONS]
# Alias:
python audiobook_cli.py soundbank <ACTION> [OPTIONS]
```

### Sub-Actions:

#### `scan`
Scans and indexes audio assets located in `audiobooks/sound_bank/`:
```bash
python audiobook_cli.py bank scan
```

#### `stats`
Displays statistics including total track count, audio hours, categories, and formats:
```bash
python audiobook_cli.py bank stats
```

#### `seed`
Seeds virtual sound catalog entries from verified CC0 cloud repositories (Freesound, Internet Archive):
```bash
python audiobook_cli.py bank seed
```

#### `search <QUERY>`
Executes Full-Text Search against the sound database:
```bash
python audiobook_cli.py bank search "dark fantasy tension cello" --limit 10
```

#### `ingest <DIR>`
Performs high-performance multi-threaded batch ingestion of an audio folder via `UniversalSoundBankIngester`:
```bash
python audiobook_cli.py bank ingest /path/to/raw_sounds/ --workers 4
```

---

## ⚙️ Environment Variables Reference

Configure these in your [`.env`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/.env) file or shell:

| Variable | Default | Description |
|---|:---:|---|
| `GEMINI_API_KEY` | *(Required)* | Google Gemini API key for TTS and LLM translation/dramaturgy. |
| `TTS_PRIMARY_BACKEND` | `gemini_tts` | Primary speech engine (`gemini_tts`). |
| `GEMINI_TTS_MODEL` | `gemini-3.1-flash-tts-preview` | Gemini TTS model endpoint identifier. |
| `GEMINI_DEFAULT_VOICE` | `Aoede` | Default narration voice persona. |
| `AUDIOBOOK_RETAIN_CHUNKS` | `0` | If set to `1`, auto-janitor preserves all raw WAV chunks for debugging. |
| `AUDIOBOOK_PROJECTS_DIR` | `audiobooks/projects` | Directory where projects and stems are saved. |
| `AUDIOBOOK_SOUND_BANK_DIR` | `audiobooks/sound_bank` | SQLite Sound Bank catalog directory. |
| `AUDIOBOOK_STRICT_AUDIT` | `0` | If set to `1`, forces Gate 6B probe checks to fail-closed. |
| `DEBUG` | `0` | If set to `1`, prints full Python tracebacks on exceptions. |

> [!TIP]
> **Key Sanitization & Quota Isolation**:
> - **Quote Stripping**: The `.env` fallback loader automatically strips surrounding quotes (`'` or `"`) from API keys, preventing header corruption and HTTP 400 errors.
> - **Quota Routing**: Soundscape mood analysis and auxiliary dramaturgy route explicitly to `service="text"`, ensuring text requests never consume scarce 10 RPD Gemini TTS quota allocations.

---

## 🛑 Exit Codes & Error Handling

| Exit Code | Meaning | Recovery Action |
|:---:|---|---|
| `0` | Success | Operation completed successfully. |
| `1` | General Pipeline Error | Review terminal error output; check API keys or missing input files. |
| `130` | User Aborted (`Ctrl+C`) | Checkpoint safely saved on disk. Rerun the command to resume. |
