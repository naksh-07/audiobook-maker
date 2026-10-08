# 🎓 End-to-End Production Tutorial & Recipe Cookbook

**Standard**: `v6.0-ENTERPRISE-DAG` & `v6.0-STUDIO-UI`  
**System**: Studio Audio Production & Vocal Mastering Engine  
**Classification**: Developer Guide & Production Recipes  

---

## 📖 Introduction

This tutorial guides you through real-world production scenarios using the **v6.0-ENTERPRISE-DAG** decoupled architecture — from running autonomous multi-room novel pipelines to performing sub-15-second surgical dialogue patches and directing character acting in the Antigravity Webview Studio Panel.

---

## 📋 Prerequisites Checklist

Verify your workstation environment before starting:

```bash
# 1. Verify Python version (>= 3.10)
python --version

# 2. Verify Node.js version (>= 18 for Antigravity Sidecar Webview)
node --version

# 3. Verify FFmpeg SOXR support
ffmpeg -filters | findstr soxr   # Windows
# or
ffmpeg -filters | grep soxr      # Linux / macOS

# 4. Verify Google Gemini API credentials
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API Key OK' if os.environ.get('GEMINI_API_KEY') else 'Missing API Key')"
```

---

## 🍳 Recipe 1: Full 5-Room Hindi Novel Audiobook (`AUDIOBOOK_STUDIO`)

Transform an English fantasy novel into a fully cast, dramatized Hindustani audiobook with 4D formants and broadcast EBU R128 mastering.

```bash
python -m audiobook_factory.cli.run \
    --preset AUDIOBOOK_STUDIO \
    --source "books/Sword_of_Destiny.epub" \
    --project-dir "./projects/sword_of_destiny" \
    --workers 4 \
    --cover "covers/sword_of_destiny.jpg" \
    --target-lufs -19.0
```

### What Happens Under the Hood:
1. **Room 1 (Ingestion)**: Dissects the EPUB with XY-cut layout order, extracts character names into `book_bible.json`, and generates `cast_lock.json`.
2. **Room 2 (Translation Collective)**: 4-Agent Collective translates prose into dramatic Hindustani (`chapter_XXX_translation.json`), enforcing the Dual-Rule invariant.
3. **Room 3 (Screenplay & Anti-Swap)**: Attributes dialogue turns, audits for 0% speaker flips, and calculates 4D formant offsets (pitch, tempo, EQ curves).
4. **Room 4 (Multi-Cast TTS & Editorial)**: Checks TakeBank cache (0 tokens), synthesizes uncached lines via Gemini Flash TTS, and applies DE-01-DE-07 Hann micro-fades.
5. **Room 5 (Broadcast Mastering)**: Executes two-pass linear loudnorm (-19.0 LUFS / -1.5 dBTP) and packages `final_audiobook.m4b` with embedded cover art.

---

## 🍳 Recipe 2: English-Only Novel Audiobook (`ENGLISH_AUDIOBOOK`)

For native English literature where translation is not required, use the `ENGLISH_AUDIOBOOK` preset:

```bash
python -m audiobook_factory.cli.run \
    --preset ENGLISH_AUDIOBOOK \
    --source "books/Dune.epub" \
    --project-dir "./projects/dune" \
    --workers 4 \
    --cover "covers/dune.jpg"
```

- **Room 2 is completely bypassed**.
- Room 3 parses the English AST from Room 1 directly into multi-cast screenplay scenes.
- 4D formants, Stanislavski directing anchors, and EBU R128 mastering execute identically.

---

## 🍳 Recipe 3: Multi-Host Research-to-Podcast Engine (`MULTI_HOST_PODCAST`)

Convert a research paper, Markdown article, or topic brief into a dual-host conversational banter podcast mastered to podcast broadcast standard (-16.0 LUFS):

```bash
python -m audiobook_factory.cli.run \
    --preset MULTI_HOST_PODCAST \
    --source "papers/quantum_computing.pdf" \
    --project-dir "./projects/quantum_podcast" \
    --target-lufs -16.0
```

- Generates Host A vs Host B banter dialogue with dynamic conversational turn latencies (-150ms overlap).
- Synthesizes dialogue using distinct vocal timbres (`Puck` vs `Aoede`).
- Masters to standard podcast loudness (-16.0 LUFS, -1.0 dBTP).

---

## 🍳 Recipe 4: Surgical Single-Beat Patching & Zero-Cost TakeBank Re-renders

If you notice a typo in a single translated sentence or wish to tweak an actor's voice line:

### Step 1: Patch the Single Beat
```bash
python -m audiobook_factory.cli.translate \
    --chapter 3 \
    --patch-beat "ch03_beat012" \
    --text "विचर ने तलवार म्यान से खींची और धीमी आवाज़ में बोला।" \
    --project-dir "./projects/sword_of_destiny"
```

### Step 2: Reconcile Dirty Stages
```bash
python -m audiobook_factory.cli.run \
    --reconcile-dirty \
    --project-dir "./projects/sword_of_destiny"
```

### What Happens:
- The **Diff Reconciler** detects that only `ch03_beat012` changed.
- Out of 129 chapter segments, **128 segments hit the TakeBank cache** ($0\text{ms}$ delay, 0 API tokens).
- Only 1 segment is synthesized via TTS.
- Tier 2 Local Assembly stitches and masters the new chapter in $< 15$ seconds!

---

## 🍳 Recipe 5: Interactive Directing in Antigravity Webview Studio Panel

1. **Launch Studio Panel**: Open Antigravity IDE and click the **Audiobook Studio** icon in the Aux Pane.
2. **Inspect 5-Room Stepper**: Observe visual stage indicators (`PASS` in green, `DIRTY` in amber).
3. **Dual-Pane Translation Editing**: Click **Room 2** in the stepper to open parallel English $\leftrightarrow$ Hindi text. Edit any line directly.
4. **4D Formant Tuning**: Click **Room 3** to open the Cast Board. Adjust pitch slider to $-6\%$ or speed to $0.95\times$. Click `[🔒 Lock Segment]` to protect human casting.
5. **1-Click Audition**: Click `[🔊 Audition Line]` on any segment to generate and hear the speech take in $< 1.5$s inside the IDE.
6. **Sticky Audio Dock**: Click `[▶ Play]` in the bottom dock to listen to the continuous master track while observing the real-time EBU R128 (-19.0 LUFS) compliance badge.

---

## 🍳 Recipe 6: Independent Multi-Gate Verification

Run quality gates to certify broadcast and linguistic compliance:

```bash
# Audit Room 1 AST Ingestion Gate (Gate 0.1)
python -m audiobook_factory.cli.audit --gate GATE_0_1_INGEST --project-dir "./projects/sword_of_destiny"

# Audit Room 3 Anti-Swap Attribution Gate (Gate 2.0 - 0% Speaker Flips)
python -m audiobook_factory.cli.audit --gate GATE_2_0_SCREENPLAY --chapter 3 --project-dir "./projects/sword_of_destiny"

# Audit Room 5 EBU R128 Broadcast Mastering Gate (Gate 5.0 - -19 LUFS / -1.5 dBTP)
python -m audiobook_factory.cli.audit --gate GATE_5_0_MASTER --chapter 3 --project-dir "./projects/sword_of_destiny"
```
