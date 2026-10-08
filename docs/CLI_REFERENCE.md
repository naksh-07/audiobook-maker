# 💻 CLI Reference: Audiobook Studio Engine

## Overview

The Audiobook Studio Command-Line Interface ([`audiobook_cli.py`](file:///c:/Users/Suraj/Documents/antigravity/optimistic-kepler/audiobook_cli.py)) provides operational control over the entire studio-grade vocal production pipeline. You can run an autonomous end-to-end novel production run with a single command or execute granular subcommands stage-by-stage.

```bash
# Entrypoint via installed CLI or Python:
audiobook-studio [COMMAND] [OPTIONS]
# or:
python audiobook_cli.py [COMMAND] [OPTIONS]
```

---

## 🧭 Active Production Command Matrix

| Subcommand | Scope | Description |
|---|---|---|
| **[`auto`](#1-autonomous-production-auto)** | Full Book | 1-Click autonomous pipeline (Extract $\rightarrow$ Translate $\rightarrow$ Script $\rightarrow$ Synth $\rightarrow$ Master $\rightarrow$ Package). |
| **[`produce`](#2-chapter-production-produce)** | Chapter / All | Produces high-fidelity vocal chapters with EBU R128 (-19 LUFS) and timeline ledger. |
| **[`extract`](#3-universal-document-extraction-extract)** | Ingestion | Ingests EPUB, PDF, TXT, or MD documents into clean Markdown chapters. |
| **[`translate`](#4-literary-translation-translate)** | Translation | Translates extracted chapters into literary dramatic Hindustani with Translation Collective. |
| **[`script`](#5-screenplay-scripting-script)** | Screenplay | Parses prose into standardized screenplay JSON with speaker attribution and acting tags. |
| **[`synthesize`](#6-speech-synthesis-synthesize)** | Audio (TTS) | Synthesizes dialogue chunks using Google Gemini Flash Cloud TTS and 4D acoustic formants. |
| **[`master`](#7-vocal-dsp-mastering-master)** | Mastering | Concatenates vocal chunks with 5-stage DSP chain and EBU R128 loudness normalization. |
| **[`package`](#8-m4b-container-packaging-package)** | Delivery | Packages all mastered chapters into a chapterized `.m4b` container with cover art. |
| **[`audit`](#9-chapter-quality-audit-audit)** | QA (Chapter) | Runs Multi-Gate Independent Verification (Gates 0, 1, 2, 2.5, 2.8) on a specific chapter. |
| **[`audit-book`](#10-full-book-macro-audit-audit-book)** | QA (Macro) | Runs Macro-Tier Gate 6 certification (Voice Continuity, Loudness, TOC Monotonicity). |

---

## 1. Autonomous Production (`auto`)

Executes the entire pure vocals-only pipeline autonomously in a single command.

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
| `--voice` | String | `Aoede` | Lead voice persona (`Aoede`, `Charon`, `Puck`, `Fenrir`, `Zephyr`, `Kore`, `Leda`, `Orpheus`). |
| `--dramatized` | Flag | `False` | Multi-voice character casting vs single narrator reading. |
| `--cover` | Path | `None` | Path to cover artwork image (JPEG/PNG, min $1400 \times 1400$ px). |
| `--workers` | Integer | `3` | Number of concurrent TTS synthesis worker threads. |
| `--force-gate` | Flag | `False` | Bypass Ingestion Quality Gate REVIEW warning and force production. |

### Example
```bash
python audiobook_cli.py auto "C:/path/to/novel.epub" --hindi --dramatized --voice Aoede --workers 3
```

---

## 2. Chapter Production (`produce`)

Produces mastered vocal chapters with EBU R128 (-19 LUFS) and timeline ledgers.

```bash
python audiobook_cli.py produce <BOOK_SLUG> [OPTIONS]
```

### Positional Arguments
- `BOOK_SLUG`: Project folder slug under `audiobooks/projects/`.

### Options
| Flag | Type | Default | Description |
|---|:---:|:---:|---|
| `--chapter` | Integer | `None` | Specific chapter number to produce (e.g. `--chapter 1`). |
| `--all` | Flag | `False` | Produce all chapters in sequence. |
| `--voice` | String | `Aoede` | Lead narrator voice persona. |
| `--workers` | Integer | `3` | Number of concurrent TTS synthesis worker threads. |

---

## 3. Universal Document Extraction (`extract`)

Ingests any digital book into clean, segmented Markdown chapters.

```bash
python audiobook_cli.py extract <FILE> [--force-gate]
```

---

## 4. Literary Translation (`translate`)

Translates extracted chapters into literary dramatic Hindustani using the 4-Agent Translation Collective.

```bash
python audiobook_cli.py translate <BOOK_SLUG> [--model <MODEL>]
```

---

## 5. Screenplay Scripting (`script`)

Parses chapter prose into standardized screenplay JSON with speaker attribution, 4D formant metadata, and Stanislavski acting cues.

```bash
python audiobook_cli.py script <BOOK_SLUG> [--hindi] [--dramatized]
```

---

## 6. Speech Synthesis (`synthesize`)

Synthesizes dialogue segments via Google Gemini Flash TTS with 4D acoustic formant modulation.

```bash
python audiobook_cli.py synthesize <BOOK_SLUG> [--voice <VOICE>] [--backend gemini_tts]
```

---

## 7. Vocal DSP Mastering (`master`)

Concatenates speech segments with Hann micro-fades and normalizes to EBU R128 (-19 LUFS) at 48kHz / 24-bit.

```bash
python audiobook_cli.py master <BOOK_SLUG>
```

---

## 8. M4B Container Packaging (`package`)

Assembles all mastered chapters into a final chapterized `.m4b` container with TOC navigation and embedded cover art.

```bash
python audiobook_cli.py package <BOOK_SLUG> [--cover <IMAGE_PATH>] [--enforce-gate6]
```

---

## 9. Chapter Quality Audit (`audit`)

Executes Multi-Gate Independent Verification on a single chapter.

```bash
python audiobook_cli.py audit <BOOK_SLUG> --chapter <NUM>
```

---

## 10. Full-Book Macro Audit (`audit-book`)

Executes Macro-Tier Gate 6 certification across the entire novel project.

```bash
python audiobook_cli.py audit-book <PROJECT_DIR_OR_SLUG>
```

---

## 📦 Archived Subsystems Notice

The legacy subcommands (`direct`, `render`, `bgm`, `stems`, `bank`) belong to the decoupled 5-track cinematic audio engine and are archived in `archive/cinematic_audio/`. They are not part of the active Vocals-Only pipeline.
