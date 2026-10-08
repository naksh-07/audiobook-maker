# 💻 CLI Reference Manual

**Standard**: `v6.0-ENTERPRISE-DAG` & `v6.0-STUDIO-UI`  
**Package Namespace**: `audiobook_factory.cli` & `audiobook_factory.api`  
**Classification**: Command-Line Operations & IPC Bridge Reference  

---

## 1. Overview & Entrypoint Architecture

The Audiobook Studio command-line suite provides two tiers of operational control:
1. **Autonomous DAG Orchestration**: High-level execution of dynamic multi-room presets (`AUDIOBOOK_STUDIO`, `ENGLISH_AUDIOBOOK`, `MULTI_HOST_PODCAST`, `STANDALONE_TRANSLATION`).
2. **Standalone Room Subsystems**: Independent, surgical CLI entrypoints for Rooms 1 through 5.
3. **Studio Panel IPC Bridge**: Structured JSON-over-stdout CLI interface for the Antigravity Webview sidecar.

```bash
# Top-level autonomous DAG runner:
python -m audiobook_factory.cli.run --preset <PRESET> [OPTIONS]

# Standalone Room Subsystems:
python -m audiobook_factory.cli.ingest [OPTIONS]
python -m audiobook_factory.cli.translate [OPTIONS]
python -m audiobook_factory.cli.screenplay [OPTIONS]
python -m audiobook_factory.cli.synth [OPTIONS]
python -m audiobook_factory.cli.master [OPTIONS]
python -m audiobook_factory.cli.package [OPTIONS]

# Studio Panel Sidecar IPC Bridge:
python -m audiobook_factory.api.studio_bridge <COMMAND> [OPTIONS]
```

---

## 2. Master Autonomous DAG Runner (`cli.run`)

Executes dynamic end-to-end production pipelines, resolving dependency stages, checking SQLite ledger status, and invalidating dirty segments.

```bash
python -m audiobook_factory.cli.run --preset <PRESET> [OPTIONS]
```

### Options & Flags
| Flag | Type | Default | Description |
|:---|:---:|:---:|:---|
| `--preset` | Choice | `AUDIOBOOK_STUDIO` | Pipeline Preset: `AUDIOBOOK_STUDIO`, `ENGLISH_AUDIOBOOK`, `MULTI_HOST_PODCAST`, `STANDALONE_TRANSLATION`. |
| `--source` | Path | `None` | Path to source manuscript (`.epub`, `.pdf`, `.txt`, `.md`). |
| `--project-dir` | Path | Required | Path to output project working directory. |
| `--workers` | Integer | `3` | Number of concurrent Gemini Flash TTS workers. |
| `--voice` | String | `Aoede` | Default narrator voice persona. |
| `--target-lufs` | Float | `-19.0` | EBU R128 integrated loudness target (-19.0 for Audiobooks, -16.0 for Podcasts). |
| `--cover` | Path | `None` | Path to cover artwork image (JPEG/PNG). |
| `--reconcile-dirty`| Flag | `False` | Only re-run stages and takes that are marked dirty in SQLite ledger. |
| `--fidelity-tier` | Choice | `RAW_UNRATED` | Translation mode: `RAW_UNRATED` or `CLASSIC_REVERENT`. |

### Examples
```bash
# Full 5-Room Hindi Novel Audiobook:
python -m audiobook_factory.cli.run \
    --preset AUDIOBOOK_STUDIO \
    --source "books/Sword_of_Destiny.epub" \
    --project-dir "./projects/sword_of_destiny" \
    --workers 4

# English-Only Novel (Room 2 Bypassed):
python -m audiobook_factory.cli.run \
    --preset ENGLISH_AUDIOBOOK \
    --source "books/Dune.epub" \
    --project-dir "./projects/dune"

# Reconcile Dirty Stages After Manual Script / Translation Edits:
python -m audiobook_factory.cli.run \
    --reconcile-dirty \
    --project-dir "./projects/sword_of_destiny"
```

---

## 3. Standalone Room Subsystem CLIs

### 3.1 Room 1: Forensic Ingestion (`cli.ingest`)
Parses source manuscripts into character-accurate AST representations, harvests entities, and initializes project bibles.

```bash
python -m audiobook_factory.cli.ingest \
    --source "books/Sword_of_Destiny.epub" \
    --project-dir "./projects/sword_of_destiny" \
    --fidelity-tier RAW_UNRATED
```
- **Outputs**: `raw_book_manifest.json`, `book_bible.json`, `cast_lock.json`.

---

### 3.2 Room 2: Translation Collective (`cli.translate`)
Translates extracted chapters into literary dramatic Hindustani with surgical single-beat patching capability.

```bash
# Full chapter translation:
python -m audiobook_factory.cli.translate \
    --chapter 3 \
    --mode RAW_UNRATED \
    --project-dir "./projects/sword_of_destiny"

# Surgical single-beat patch:
python -m audiobook_factory.cli.translate \
    --chapter 3 \
    --patch-beat "ch03_beat012" \
    --text "विचर ने तलवार म्यान से खींची और धीमी आवाज़ में बोला।" \
    --project-dir "./projects/sword_of_destiny"
```
- **Outputs**: `chapter_XXX_translation.json`.

---

### 3.3 Room 3: Screenplay & Anti-Swap Dramaturgy (`cli.screenplay`)
Parses translated prose into screenplay dialogue turns, audits for 0% speaker swaps, and stages 4D acoustic formants.

```bash
# Build chapter screenplay:
python -m audiobook_factory.cli.screenplay \
    --chapter 3 \
    --project-dir "./projects/sword_of_destiny"

# Reconcile dirty segments while preserving user-locked lines:
python -m audiobook_factory.cli.screenplay \
    --chapter 3 \
    --reconcile-dirty \
    --project-dir "./projects/sword_of_destiny"
```
- **Outputs**: `chapter_XXX_screenplay.json`.

---

### 3.4 Room 4: Multi-Cast TTS & Dialogue Editorial (`cli.synth`)
Resolves existing audio takes from TakeBank (0 tokens) and synthesizes uncached segments via Gemini Flash TTS with DE-01-DE-07 editorial assembly.

```bash
python -m audiobook_factory.cli.synth \
    --chapter 3 \
    --workers 4 \
    --editorial-preset "natural" \
    --project-dir "./projects/sword_of_destiny"
```
- **Outputs**: `chapter_XXX_dialogue.wav`, `timeline_ledger.json`.

---

### 3.5 Room 5: Broadcast Vocal Mastering & Packaging (`cli.master` & `cli.package`)

```bash
# Master individual chapter to EBU R128 (-19.0 LUFS):
python -m audiobook_factory.cli.master \
    --chapter 3 \
    --target-lufs -19.0 \
    --project-dir "./projects/sword_of_destiny"

# Package complete novel into chaptered M4B container:
python -m audiobook_factory.cli.package \
    --cover "assets/cover.jpg" \
    --project-dir "./projects/sword_of_destiny"
```
- **Outputs**: `chapter_XXX_mastered.m4a`, `final_audiobook.m4b`.

---

## 4. Studio Panel IPC Bridge (`api.studio_bridge`)

The IPC Bridge provides structured JSON communication between the Node.js Sidecar (`main.mjs`) and the Python platform engine.

```bash
# 1. Health & KeyPool Status
python -m audiobook_factory.api.studio_bridge status

# 2. List All Active Projects
python -m audiobook_factory.api.studio_bridge list-projects

# 3. Get Chapter & Roster Details for Project
python -m audiobook_factory.api.studio_bridge project-detail --slug "sword_of_destiny"

# 4. Surgically Patch a Screenplay Segment & Invalidate Hash
python -m audiobook_factory.api.studio_bridge patch-segment \
    --slug "sword_of_destiny" \
    --chapter 3 \
    --segment-id "ch03_seg045" \
    --voice "Puck" \
    --pitch -0.06 \
    --text "विचर ने आगे बढ़कर जवाब दिया।"

# 5. Run Single-Sentence Scratch Audition (< 1.5s)
python -m audiobook_factory.api.studio_bridge audition \
    --voice "Charon" \
    --pitch -0.04 \
    --speed 0.95 \
    --text "सावधान रहो! वह कोई साधारण दानव नहीं है।"
```

---

## 5. Backward-Compatible CLI (`audiobook_cli.py`)

For legacy scripts and existing pipelines, `audiobook_cli.py` maps traditional subcommands directly to the underlying DAG architecture:

| Subcommand | Underlying Room / Engine | Description |
|---|---|---|
| `auto` | `dag.orchestrator` | 1-Click autonomous novel pipeline. |
| `extract` | `room1_ingest` | Document parsing and lore extraction. |
| `translate` | `room2_translate` | Literary Hindustani Translation Collective. |
| `script` | `room3_screenplay` | Screenplay building & anti-swap attribution. |
| `synthesize`| `room4_synth` | Multi-voice TTS & TakeBank caching. |
| `master` | `room5_master` | Two-pass EBU R128 linear loudness mastering. |
| `package` | `room5_master.packager` | Chaptered `.m4b` container assembly. |
| `audit` | `quality_gates` | Single-chapter gate verification. |
| `audit-book`| `quality_gates.macro` | Full-novel certification. |
