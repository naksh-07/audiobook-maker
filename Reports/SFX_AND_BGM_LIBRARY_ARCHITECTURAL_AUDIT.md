# Architectural Audit: SFX, Ambience & BGM Library
**Target:** `naksh-07/audiobook-maker`  
**Date:** 2026-09-22  
**Status:** FORENSIC AUDIT COMPLETE & ACTIONABLE BLUEPRINT READY  

This report outlines a comprehensive, forensic architectural audit of the sound design, library management, and rendering subsystems in the Audiobook Maker. It uncovers critical bugs, database schisms, acoustic timing flaws, and missing asset vulnerabilities, followed by an actionable modernization blueprint.

---

## 1. Physical Sound Bank & Database Schism

### 1.1 Table Disconnect & Lost DSP Metrics
There is a severe architectural schism between the ingestion pipeline and the runtime engine:
* **The Ingestor:** `UniversalSoundBankIngester` in [`sound_bank_ingest.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank_ingest.py#L135) correctly parses files and populates a rich table called `sound_assets`, packed with EBU R128 LUFS, True Peak, and Spectral Centroid data.
* **The Runtime:** The actual `SoundBank` in [`sound_bank.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank.py#L66) ignores this and queries a completely different, disjointed table called `sound_catalog`, entirely discarding the rich acoustic metrics derived during ingestion.
* **Dead Temp Paths in Database:** In `sound_assets`, all 40 registered rows point to deleted temporary directories (e.g. `C:/Users/Suraj/AppData/Local/Temp/tmpa23b5s7t/...`).

### 1.2 Ghost Entries & Silent Resolution Fallbacks
In `SoundBank.resolve_sound`, the engine relies on a strict `LIMIT` (e.g., `LIMIT 4`) when querying the catalog. However, the database contains 171 virtual/missing tracks. 
* **The Flaw:** If a query returns 4 virtual tracks and the JIT download fails (due to network timeout or dead temp paths), those ghost entries consume the entire result limit. The engine silently falls back to `None` without fetching the next batch of valid local assets, resulting in missing audio in the final mix.

---

## 2. BGM & OST Sectioning Flaws (The Smoking Gun)

### 2.1 The "Zero-Second" Slicing Bug
**Why are the epic Witcher 3 battle climaxes never heard?**
* **The Flaw:** In `render_music_bus` in [`manifest_renderer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/manifest_renderer.py#L224-L231), the `ffmpeg` command is assembled as follows:
  ```bash
  ffmpeg -y -i cue_path -t dur_sec ...
  ```
* **The Smoking Gun:** It **NEVER** seeks (`-ss`) into the track! Even if the agent correctly requests the `CLIMAX_DROP` section (which should start at, say, 2m30s), the renderer blindly slices the audio from `0.0s`. The listener always hears the first 30 seconds of the track (usually quiet ambient intros). The climactic battle drops, thunderous taiko drums, and choral swells are **physically unreachable** by the current renderer!

### 2.2 Hardcoded Budget Mismatch
* **The Flaw:** In [`agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py#L377), `max_music_budget_ms` is hardcoded to:
  ```python
  max_music_budget_ms = int(total_duration_ms * 0.35)
  ```
* **The Disconnect:** The silence carving pass was updated to enforce `0.40` (40% max music budget), creating an arbitrary 5% timeline divergence that randomly truncates valid music cues before the 2-Tier score can fully lay down its background bed.

### 2.3 Naive Sectioning & Duplicate FTS Rows
* **Naive Slicing:** [`sound_bank.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank.py#L160) assigns musical energy landmarks using naive percentages (`INTRO_BED 0-25%`, `RISING_TENSION 25-60%`, `CLIMAX_DROP 60-85%`, `AFTERMATH_FADE 85-100%`). Real musical dynamics do not adhere to exact linear percentage boundaries.
* **FTS Duplication:** `search_music_catalog` in [`sound_bank.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank.py#L767) uses a `LEFT JOIN sound_track_sections` against `sound_catalog_fts`. Because `sound_track_sections` contains multiple sections per track, this query artificially multiplies rows in the search results without making the section tags themselves FTS-searchable.

---

## 3. SFX & Foley Acoustic Timing Flaws

### 3.1 The Double Pre-Roll Subtraction Bug
Foley transients are consistently out of sync (pulled too early) because of a double subtraction bug:
* **Pass 3 Calculation:** [`agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py#L501) correctly calculates:
  $$\text{cue\_start\_ms} = \max(0, \text{seg\_start\_ms} + \text{anchor\_offset\_ms} - \text{pre\_roll\_ms})$$
  The transient lead-in is already subtracted.
* **Render Pass Calculation:** [`manifest_renderer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/manifest_renderer.py#L113) recalculates the delay:
  ```python
  cue_start_ms = max(0, int(cue.start_ms - getattr(cue, "pre_roll_ms", 0)))
  ```
* **Result:** The `pre_roll_ms` is subtracted **twice**, pulling the Foley transient 50ms to 100ms ahead of where the physical action actually happens!

### 3.2 Headroom & Format Jitter
* **Uncalibrated Gain:** Sound bank assets vary wildly in native loudness (-3 dBFS peak vs -40 LUFS). Without pre-normalization at ingestion, the `amix` filter can cause clipping or inaudible clicks during rendering.
* **MP3 Codec Latency:** Relying on MP3s for Foley introduces 12-24ms of priming sample delay (encoder padding), which ruins frame-accurate transient sync compared to uncompressed 48kHz PCM WAV.

---

## 4. Library Breadth & Coverage Gaps

* **Severe Asset Drought:** An audit of the actual assets on disk reveals a shocking lack of physical files:
  * **Ambience:** Only 7 files (Nature: 2, Weather: 3, Tavern: 1, General: 1). Completely lacking fantasy settings (crypts, castle halls, swamps, dungeons, snowy passes).
  * **SFX/Foley:** Only 1 pure SFX file on disk (Magic: 1). Zero monster roars (Striga, Ghoul, Bruxa) and zero Witcher signs (Aard, Igni, Quen, Axii, Yrden).
* **Dead Links:** The database contains 40 rows pointing to dead `C:/Users/Suraj/AppData/Local/Temp/...` paths and 171 un-downloaded virtual files.

---

## 5. Modernization & Perfection Blueprint

To achieve production-perfect, Hollywood-grade sound design without breaking backward compatibility (all 144 tests must pass), execute the following non-destructive blueprint:

### Phase 1: Database & Ingestion Unification
1. **Schema Harmonization:** Unify `sound_assets` and `sound_catalog`. Ensure runtime queries utilize the rich DSP metrics (`integrated_lufs`, `true_peak_db`, `spectral_centroid_hz`) without breaking existing callers.
2. **EBU R128 Pre-Normalization:** Update asset indexing to normalize Foley/SFX files to `-23 LUFS` (anchor) and `-1.5 dBTP` and convert them to `48kHz WAV` on disk to eliminate MP3 priming delay.
3. **Dead Link Purge & Virtual Asset Hydration:** Pre-download the 171 virtual files into permanent local storage and purge dead temp-path ghost entries.

### Phase 2: Renderer & Timing Fixes
1. **Fix the "Zero-Second" Slicing Bug:** Update [`manifest_renderer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/manifest_renderer.py#L224) to include `-ss` seeking:
   ```python
   # Seek directly into the requested track section
   start_offset_sec = getattr(cue, "section_start_sec", 0.0)
   cmd = [
       ffmpeg, "-y",
       "-ss", f"{start_offset_sec:.2f}",
       "-i", str(cue_path),
       "-t", f"{dur_sec:.2f}",
       ...
   ]
   ```
2. **Fix Double Pre-Roll Subtraction:** In [`manifest_renderer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/manifest_renderer.py#L113), remove `- getattr(cue, "pre_roll_ms", 0)`. Trust the `start_ms` already calculated by `AgentDirector`.
3. **Sync Music Budget:** Update [`agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py#L377) to:
   ```python
   max_music_budget_ms = int(total_duration_ms * 0.40)
   ```

### Phase 3: Acoustic Coverage Expansion
1. **Curated Expansion Pack:** Download and ingest a curated batch of 50-100 high-quality, royalty-free fantasy Foley and Ambience WAVs (Witcher signs, medieval weapons, monster vocals, deep dungeon reverbs).
2. **Semantic FTS5 Synonyms:** Expand FTS5 index triggers to automatically append semantic synonyms (e.g. mapping `igni` to `fire flame magic burst`, `striga` to `monster beast roar scream`, `quen` to `magic shield forcefield hum`) so the AI can successfully trigger them without exact filename matches.
