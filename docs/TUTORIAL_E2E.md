# 🎓 End-to-End Production Tutorial & Recipe Cookbook

## 📖 Introduction

This tutorial walks you through every production scenario in **Audiobook Maker v4.0** — from running your first 1-click autonomous novel to surgically directing custom screenplay cues and exporting discrete multitrack stems for studio re-mixing.

---

## 📋 Prerequisites Checklist

Before beginning, ensure your workstation environment is verified:

```bash
# 1. Verify Python version (>= 3.10)
python --version

# 2. Verify FFmpeg SOXR support (Mandatory for 48kHz audio resampler)
ffmpeg -filters | findstr soxr   # Windows
# or
ffmpeg -filters | grep soxr      # Linux / macOS

# 3. Verify Gemini API key configuration
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API Key OK' if os.environ.get('GEMINI_API_KEY') else 'Missing API Key')"
```

---

## 🍳 Recipe 1: 1-Click Autonomous Cinematic Hindi Audio Drama

Transform an English fantasy novel into a full-cast, dramatized Hindustani audio drama complete with orchestral score, physical Foley, and `.m4b` delivery.

```bash
python audiobook_cli.py auto books/the_witcher.epub \
  --hindi \
  --dramatized \
  --voice Charon \
  --cover covers/witcher.jpg \
  --workers 4
```

### What Happens Under the Hood:
1. **Extraction**: The EPUB is dissected into clean Markdown chapters (`audiobooks/projects/the_witcher/extracted/`).
2. **Translation**: A two-pass dramatic Hindustani translation runs, generating a character glossary (`glossary.json`) and preserving archaic fantasy honorifics.
3. **Screenplay Scripting**: Dialogue is attributed to distinct characters using sliding-window attribution. Pacing pauses, spatial panning, and acting directives are embedded.
4. **Speech Synthesis**: Chunks are synthesized concurrently via Gemini 3.1 Flash TTS (`Charon`, `Aoede`, `Puck`, `Fenrir`) using a token-bucket rate limiter.
5. **Acoustic Directing**: `AgentDirector` carves acoustic silence ($\ge 60\%$), queries the SQLite Sound Bank for musical underscore, and places Foley cues.
6. **Mastering & Packaging**: FFmpeg normalizes audio to EBU R128 (-19 LUFS), embeds cover art and chapter seek points, and produces `audiobooks/output/the_witcher.m4b`.

---

## 🍳 Recipe 2: Original English Cinematic Audio Drama

If your book is already in English and you do not want translation, omit the `--hindi` flag:

```bash
python audiobook_cli.py auto books/dune.epub \
  --no-hindi \
  --dramatized \
  --voice Charon \
  --cover covers/dune.jpg \
  --workers 3
```

- In this mode, Stage 2 (Translation) is bypassed entirely.
- The Screenplay Builder parses English prose directly into dialogue and narration segments.
- Full multi-voice casting, dynamic BGM scoring, and sidechain ducking remain active.

---

## 🍳 Recipe 3: Traditional Single-Narrator Audiobook

For non-fiction, biographies, or classic single-narrator audiobooks without theatrical music or sound effects:

```bash
python audiobook_cli.py auto books/sapiens.epub \
  --no-hindi \
  --no-dramatized \
  --voice Aoede \
  --cover covers/sapiens.jpg
```

- Narrator reads all passages in a clean, consistent voice.
- Background music is subdued or bypassed.
- EBU R128 broadcast mastering ensures compliant -19 LUFS output.

---

## 🍳 Recipe 4: Chapter-by-Chapter Modular Production & Creative Direction

For high-profile projects where you want to audition characters, adjust delivery style, and fine-tune soundscapes before rendering:

### Step 1: Ingest and Extract
```bash
python audiobook_cli.py extract books/chapter_one_sample.epub
# Creates: audiobooks/projects/chapter_one_sample/
```

### Step 2: Generate Screenplay Scripts
```bash
python audiobook_cli.py script chapter_one_sample --dramatized
# Creates: audiobooks/projects/chapter_one_sample/scripts/chapter_001_script.json
```

### Step 3: Inspect & Customize Screenplay
Open `chapter_001_script.json` in your editor. You can fine-tune any segment:
```json
{
  "index": 14,
  "type": "dialogue",
  "speaker": "Geralt",
  "text": "People like to invent monsters and monstrosities.",
  "emotion": "melancholic_weary",
  "acting": {
    "delivery_style": "low_growl_cynical",
    "pacing": 0.95
  },
  "spatial": {
    "pan": -0.15,
    "proximity": "close_mic"
  },
  "acoustic_env": "stone_hall",
  "intensity_level": "medium"
}
```

### Step 4: Synthesize Audio
```bash
python audiobook_cli.py synthesize chapter_one_sample --voice Aoede --workers 3
```

### Step 5: Build Master Timeline Ledger
```bash
python audiobook_cli.py timeline chapter_one_sample --chapter 1 --stitch
# Assembles sample-accurate continuous dialogue: chapter_001_dialogue.wav
```

### Step 6: Direct Soundscape
```bash
python audiobook_cli.py direct chapter_one_sample --chapter 1
# Emits validated CreativeManifest: manifests/chapter_001_manifest.json
```

### Step 7: Render Master Audio
```bash
python audiobook_cli.py render \
  --manifest audiobooks/projects/chapter_one_sample/manifests/chapter_001_manifest.json \
  --vocal audiobooks/projects/chapter_one_sample/mastered/chapter_001_dialogue.wav
```

### Step 8: Package Final Container
```bash
python audiobook_cli.py package chapter_one_sample --cover covers/cover.jpg
```

---

## 🍳 Recipe 5: Handling Daily API Quotas & Resuming Interrupted Runs

If your Google AI Studio daily API token quota is reached during synthesis, production is never lost:

1. **State Preservation**: The [`ProjectStateLedger`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/state.py) automatically commits state to `project_state.json`. Every successfully generated `.wav` chunk remains safely on disk in `audio_chunks/`.
2. **Quota Reset**: After the quota resets (or after updating `.env` with a fresh API key), simply rerun the same command:
   ```bash
   python audiobook_cli.py produce witcher1 --all
   ```
3. **Smart Resume**: The TTS Dispatcher probes existing chunks on disk, skips all segments already synthesized, and resumes seamlessly from the exact unrendered segment.

---

## 🍳 Recipe 6: Exporting Discrete 5-Track DME Stems for Professional DAWs

If a sound engineer wishes to perform custom mastering or surround mixing in Pro Tools, Reaper, Logic Pro, or Audacity:

```bash
# Verify exported stems for Chapter 1
python audiobook_cli.py stems witcher1 --chapter 1
```

The stems reside at `audiobooks/projects/witcher1/mastered/stems/`:
- **`chapter_001_stem_DX.wav`**: Dry/Processed Voice Dialogue (Vocal Corridor Centered).
- **`chapter_001_stem_MX.wav`**: Musical Score & Cues (with 2.2kHz notch).
- **`chapter_001_stem_FX.wav`**: Tactile Foley & Dramatic SFX.
- **`chapter_001_stem_AMB.wav`**: Environmental Background Bed (-32 LUFS).
- **`chapter_001_stem_ME.wav`**: Combined Music & Effects (International Dubbing Stem).

Accompanying ledger: `chapter_001_stem_ledger.json` contains exact integrated LUFS and True Peak metrics for each stem.

---

## 🍳 Recipe 7: Quality Verification & Audit

Before distributing your audiobook to platforms, verify broadcast compliance:

```bash
# 1. Audit individual chapter (Gates 0 - 5.3)
python audiobook_cli.py audit witcher1 --chapter 1

# 2. Run full-book macro certification (Gates 6A - 6D)
python audiobook_cli.py audit-book witcher1
```

### Understanding Audit Output:
- `Gate 0 (Translation)`: Ratio of translated characters vs source characters.
- `Gate 1 (Voice Roster)`: Asserts zero voice persona collisions across active cast.
- `Gate 2 (Screenplay)`: Confirms Pydantic v2 schema compliance.
- `Gate 4.5 (Timeline)`: Confirms pause buffers and continuous dialogue alignment.
- `Gate 5 (Broadcast Master)`: Integrated loudness $-19.0 \pm 0.5$ LUFS, True Peak $\le -1.5$ dBTP.
- `Gate 6A-6D`: Continuity across chapters, TOC monotonicity, and container metadata.
