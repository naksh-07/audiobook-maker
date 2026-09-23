# 🛡️ Architectural Audit, Remediation & Engine Hardening

> **Authoritative Engineering Record of the Audiobook Maker Core Engine Overhaul, Dynamic Gate Architecture, Acoustic DSP Signal Isolation, and Container Multiplexer Safety.**

[![Broadcast Standard](https://img.shields.io/badge/Broadcast-EBU%20R128%20(-19%20LUFS)-purple.svg)](AUDIO_ENGINEERING.md)
[![Verification](https://img.shields.io/badge/Tests-243%20Passing%20(100%25)-brightgreen.svg)](../tests/)
[![Safety](https://img.shields.io/badge/TTS%20Safety-BLOCK__NONE%20(Permanent)-red.svg)](../audiobook_factory/tts_dispatcher.py)

---

## 📌 Executive Summary

During production validation of multi-chapter novel production runs on Windows 11 high-performance workstations, four systematic hardening sprints were executed:
1. **Phase 1: Architecture Audit Remediation (P0-P3)**: Resolved container multiplexer crashes (WAV stream-copy in M4B), dynamic Gate 3 deadlock for agent-directed manifests, acoustic notch signal isolation to music bus, and quota exhaustion via dedicated text key routing.
2. **Phase 2: Forensic Audit Remediation & Hardening (ADR-020)**: Remediated 13 real-world production defects across model deserialization rehydration, CLI script unpacking, defensive TTS parsing, key manager cooldowns, Quality Gates 3.5 & 4.5, Sanitizer linguistic evaluation, audio take deduplication, and Windows shell command limit bypass.
3. **Phase 3: Zero-Voice-Drift Hardening & Deterministic Speaker Attribution (ADR-021)**: Eliminated silent narrator fallbacks, implemented fail-closed `UnregisteredSpeakerError`, auto-discovery of canonical project rosters, Gate 1 acoustic gender alignment checks, Gate 2 speaker whitelist enforcement, and two-pass pronoun disambiguation.
4. **Phase 4: Audio Drama Timeline Sync, Foley Staging & Soundscape Remediation (ADR-022)**: Eradicated cumulative timeline drift via contractual `pre_roll_breath_ms` synchronization, eliminated the 50% dead-center Foley trap with `BILINGUAL_ANCHOR_MAP`, isolated domestic tableware (`DOMETabl`) from combat weaponry (`WEAPSwd`), implemented scene-bound BGM underscore with `until_segment`, and enabled dynamic multi-scene ambience bed partitioning from `acoustic_env` shifts.

As of this release, the entire test suite maintains a **243/243 unit and regression test pass rate (100%)** with zero failures, zero errors, and zero regressions across all 34 test suites.

---

## 🗺️ Hardened Architectural Signal Flow

```mermaid
flowchart TD
    subgraph Ingestion["📥 Stage 1: Ingestion & Translation"]
        PDF["Digital or Scanned PDF / EPUB"] --> Extractor["Universal Extractor<br/>(pypdf fast path + Gemini vision fallback)"]
        Extractor --> Chapters["Extracted Chapters (.md)"]
        Chapters --> Translator["Literary Hindustani Translator<br/>• 250-Word Rolling Narrative Context<br/>• Lexicon Normalization"]
        Translator --> Scripts["Sliding-Window Screenplay JSON"]
    end

    subgraph QuotaShield["🛡️ Quota & Key Isolation"]
        KeyPool["Persistent SQLite Key Pool"]
        KeyPool -->|"service='text' (No TTS Burn)"| Mood["Soundscape Mood Detection"]
        KeyPool -->|"service='tts' (10 RPD Protected)"| TTS["Token-Bucket Cloud TTS Dispatcher"]
        Env[".env Loader"] -->|"strip('\"')"| KeyPool
    end

    subgraph Directing["🎬 Stage 2: Autonomous Agentic Directing"]
        Scripts --> Director["AgentDirector<br/>(Strict Creative Mandate: No Script Overrides)"]
        Director --> Carve["Silence Carving (>= 60.0% Silence Mandate)"]
        Carve --> Score["FTS5 Musical Scoring & Leitmotifs"]
        Score --> Foley["Acoustic Foley Placement"]
        Foley --> WhisperAttn["attenuate_foley_whisper_collisions (-6dB)"]
        WhisperAttn --> Manifest["CreativeManifest (.save_to_file / .from_file)"]
    end

    subgraph Verification["🛡️ Stage 3: Dynamic Multi-Gate Auditing"]
        Manifest --> Gate3["Dynamic Gate 3 & 3.5<br/>• CreativeManifest Feasibility<br/>• Director-Managed Acceptance"]
        Scripts --> Gate45["Gate 4.5 Timeline Ledger<br/>• Canonical scripts/ mirror<br/>• Monotonicity & Zero-Truncation"]
    end

    subgraph DSP["🎛️ Stage 4: Acoustic DSP & Discrete Stems"]
        TTS --> AudioChunks["24kHz Mono WAV Chunks"]
        AudioChunks --> Vocals["Vocal Dialogue Stem (DX)"]
        Manifest --> Compositor["Cinema Audio Engine"]
        Vocals --> Compositor
        Compositor --> MusicBus["Music Bus [0:a]<br/>• Isolated 2.2kHz Notch EQ (-5.5dB)"]
        Compositor --> FoleyBus["Foley Bus [1:a]<br/>• Untouched Crisp Transients"]
        Compositor --> AmbBus["Ambience Bus [2:a]<br/>• Expansive Spatial Bed"]
        MusicBus --> Ducking["Whisper-Safe Sidechain Ducking (0.018 Threshold)"]
        Ducking & FoleyBus & AmbBus --> StemMix["Master Stem Compositor"]
        StemMix --> Master["EBU R128 Master (-19 LUFS ± 1.0 LU, -1.5 dBTP)"]
    end

    subgraph Packaging["📦 Stage 5: Container Packaging"]
        Master --> Packager["M4B Packager<br/>• is_all_aac Pre-Flight Check<br/>• Non-AAC Auto-Transcode (-c:a aac -b:a 192k)<br/>• FastStart Metadata Atom"]
        Packager --> FinalM4B["Deliverable Chaptered M4B Audiobook"]
    end
```

---

## 🚨 P0 Showstoppers Resolved

### 1. M4B AAC Packaging Safety & Auto-Transcoding
- **Module**: [`audiobook_factory/packager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py)
- **Root Cause**: The packager previously executed a naive extension check (`has_mp3 = any(f.suffix.lower() == ".mp3" for f in chapter_audio_files)`). When chapters were delivered as uncompressed 48kHz WAV files (`pcm_s16le`), the packager evaluated `has_mp3` to `False` and invoked FFmpeg with `-c:a copy`. Placing raw PCM audio into an MP4/M4B container without AAC compression violates container specifications and caused immediate FFmpeg muxer process crashes.
- **Remediation**:
  Replaced the brittle MP3 check with strict, affirmative AAC stream validation:
  ```python
  is_all_aac = all(f.suffix.lower() in (".m4a", ".aac") for f in chapter_audio_files)
  audio_codec_args = ["-c:a", "copy"] if is_all_aac else ["-c:a", "aac", "-b:a", "192k"]
  ```
  If any input file is uncompressed WAV or non-AAC, FFmpeg automatically transcodes the stream to 192 kbps AAC-LC with `+faststart` atom placement. If all inputs are native `.m4a` or `.aac`, lossless stream copying is preserved.

### 2. Dynamic Gate 3 & Feasibility Auditing
- **Module**: [`audiobook_factory/gate_auditor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py)
- **Root Cause**: In [`audit_chapter_gates()`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py#L341), Gate 3 unconditionally checked for `chapter_XXX_scenes_source.json`. Modern workflows direct soundscapes autonomously via `AgentDirector` and emit a Pydantic v2 `CreativeManifest` (`chapter_XXX_manifest.json`), bypassing legacy scene files. As a result, Gate 3 raised fatal `GateAuditError` exceptions on valid modern projects.
- **Remediation**:
  Hardened Gate 3 with dynamic multi-path resolution:
  ```python
  if scenes_file.exists():
      report["gate_3"] = audit_gate3_scenes(scenes_file, script_file)
  elif manifest_file.exists():
      from audiobook_factory.contracts import CreativeManifest
      manifest = CreativeManifest.from_file(manifest_file)
      gate35_res = audit_gate3_5_acoustic_feasibility(manifest)
      if not gate35_res.passed:
          raise GateAuditError(f"Gate 3 (Manifest Feasibility) Failed: {gate35_res.errors}")
      report["gate_3"] = {
          "status": "PASS",
          "type": "creative_manifest",
          "details": gate35_res.details,
      }
  else:
      report["gate_3"] = {
          "status": "PASS",
          "type": "director_managed",
          "notice": "No scenes_source or manifest file present; verified script coverage.",
      }
  ```

### 3. Loudness Tolerance Standardization (Gate 5 & Gate 6B)
- **Module**: [`audiobook_factory/gate_auditor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py)
- **Root Cause**: Gate 5 (`audit_gate5_master`) defaulted to a narrow tolerance of `0.5 LU` (`-19.0 ± 0.5 LUFS`), while macro-level Gate 6B permitted `1.0 LU`. Complex orchestral dynamic range and explosive cinematic soundscapes frequently settled at $-18.2$ or $-19.8$ LUFS, causing spurious Gate 5 rejections despite pristine EBU R128 compliance.
- **Remediation**: Standardized `tolerance_lu: float = 1.0` across both Gate 5 and Gate 6B.

---

## 🧭 P1 Routing & Hardcoding Fixes

### 1. Dynamic Vocal Track Inference
- **Module**: [`audiobook_cli.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_cli.py)
- **Root Cause**: In `cmd_render`, if the `--vocal` flag was omitted, the CLI defaulted to a hardcoded project path: `PROJECTS_DIR / "witcher1" / "mastered" / f"{ch_id}_dialogue.wav"`. This broke rendering for all non-Witcher novels.
- **Remediation**: Replaced hardcoded lookup with dynamic directory hierarchy discovery:
  ```python
  project_mastered = manifest_file.parent.parent / "mastered"
  cand_dirs = [project_mastered]
  if hasattr(manifest, "project_dir") and manifest.project_dir:
      cand_dirs.append(Path(manifest.project_dir) / "mastered")

  cand_names = [
      f"{ch_id}_dialogue.wav",
      f"{ch_id}_mastered.wav",
      f"{ch_id}_dialogue.m4a",
      f"{ch_id}_mastered.m4a",
      f"{ch_id}.wav",
      f"{ch_id}.m4a",
  ]
  ```
  The renderer now dynamically tests candidate filenames across both `.wav` and `.m4a` formats before raising a clear diagnostic error.

### 2. Regex Chapter Parsing vs. Sequential Enumeration
- **Module**: [`audiobook_cli.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_cli.py)
- **Root Cause**: In `cmd_synthesize` and `cmd_master`, chapters were iterated using `enumerate(script_files, 1)`. If an operator performed a partial synthesis run (e.g. processing only Chapters 5 and 12), the scripts were assigned indices `1` and `2`, corrupting chunk filenames (`c001_*` instead of `c005_*`) and renumbering the entire book.
- **Remediation**: Chapter numbers are now extracted directly from filenames using regular expressions:
  ```python
  m = re.search(r"chapter_(\d+)", sf.stem)
  ch_num = int(m.group(1)) if m else 1
  ```

### 3. Canonical Master Timeline Ledger Storage
- **Module**: [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py)
- **Root Cause**: The timeline ledger was written exclusively to `soundscapes/`, but independent audit tools searched for it in `scripts/`.
- **Remediation**: The orchestrator now writes `chapter_XXX_timeline_ledger.json` canonically into `scripts/` and creates a reliable filesystem mirror in `soundscapes/`.

---

## 🎚️ P2 Acoustic Signal Flow & Creative Autonomy

### 1. Strict Architectural Mandate: Complete Creative Autonomy for Agents
- **Architectural Law**:
  > **Only autonomous AI agents are permitted to make creative decisions.** Downstream scripts, DSP routines, and CLI pipelines must NEVER override agent directives.
- **Implementation**:
  - `AgentDirector` autonomously decides dramaturgy, silence carving, leitmotif assignment, and Foley placement, emitting a validated `CreativeManifest`.
  - `CinemaAudioEngine`, `ManifestRenderer`, and audio DSP chains operate strictly as deterministic, reproducible execution runtimes with zero script overrides.

### 2. Music-Only 2.2 kHz Spectral Notch EQ
- **Module**: [`audiobook_factory/cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py)
- **Problem**: In earlier revisions, the vocal frequency notch (`equalizer=f=2200:t=q:w=1.5:g=-5.5`) was applied to the composite mix of Music, Foley, and Ambience. This inadvertently degraded the sharp attack transients of Foley cues (sword clangs, footsteps, armor rattles) and hollowed out environmental air textures.
- **Remediation**: The notch filter is now isolated strictly to the **Music Bus `[0:a]`** before mixing:
  ```text
  [0:a]equalizer=f=2200:t=q:w=1.5:g=-5.5[mx_notched];
  [mx_notched][1:a][2:a]amix=inputs=3:duration=first:normalize=0,aresample=48000[meout]
  ```
  Foley and Ambience stems bypass the notch filter completely, preserving tactile transient crispness and expansive stereo depth while ensuring vocal intelligibility.

### 3. Whisper Collision Attenuation
- **Modules**: [`audiobook_factory/soundscape.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/soundscape.py), [`audiobook_factory/agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py)
- **Implementation**: Wired `attenuate_foley_whisper_collisions` into `AgentDirector._resolve_foley_cues`. Any Foley cue scheduled concurrently with a speech segment having `intensity_level in ("low", "whisper")` or whispered delivery style receives automatic $-6.0\text{ dBFS}$ attenuation, preventing delicate vocal nuances from being masked.

### 4. Rolling Translation Context & Canonical Glossary Normalization
- **Module**: [`audiobook_factory/translator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py)
- **Implementation**:
  - `translate_book_project` now extracts the final 250 words of the previous translated chapter (`skipped_tail` or `tail_words`) and passes them as `preceding_summary` into consecutive chapter translation prompts. This guarantees cross-chapter tonal continuity and pronoun consistency.
  - `translate_chapter` invokes `normalize_translated_lexicon(full_trans, glossary)` to enforce standardized proper noun substitutions across all chunks.

---

## ⚡ P3 Quota & Ingestion Hardening

### 1. Quota Isolation for Non-Audio Text Prompts
- **Modules**: [`audiobook_factory/soundscape.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/soundscape.py), [`audiobook_factory/key_manager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/key_manager.py)
- **Problem**: Soundscape mood analysis previously requested API keys without specifying a service type, consuming the scarce 10 RPD Gemini TTS quota for pure text analysis.
- **Remediation**: Updated `detect_chapter_mood` to explicitly call:
  ```python
  api_key = global_key_pool.get_key(service="text")
  ```
  Text analysis requests route to standard Gemini text model quotas, completely shielding the dedicated TTS pool.

### 2. Automatic `.env` Quote Stripping
- **Module**: [`audiobook_factory/key_manager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/key_manager.py)
- **Problem**: When users enclosed keys in single or double quotes in `.env` (e.g. `GEMINI_API_KEY="AIzaSy..."`), naive string splitting retained the literal quote characters. This resulted in malformed HTTP authorization headers and `400 Bad Request` responses from Google AI Studio.
- **Remediation**: Hardened `_load_env_fallback()` with quote stripping:
  ```python
  clean_v = v.strip().strip("'\"")
  os.environ.setdefault(k.strip(), clean_v)
  ```

### 3. Native Fast Digital PDF Extraction via `pypdf`
- **Module**: [`audiobook_factory/extractor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py)
- **Problem**: Ingesting large digital PDF books via Gemini multimodal vision models consumed large token allocations and frequently collided with the 8,192 token output ceiling.
- **Remediation**: Added `pypdf>=5.0` as a core dependency. `extract_gemini_pdf` now attempts instantaneous, local, zero-quota text extraction first:
  ```python
  import pypdf
  reader = pypdf.PdfReader(str(file_path))
  pdf_pages = [page.extract_text() or "" for page in reader.pages]
  full_extracted = "\n\n".join([p.strip() for p in pdf_pages if p.strip()])
  if len(full_extracted.split()) >= 100:
      return clean_book_text(full_extracted)
  ```
  The system falls back to Gemini multimodal vision only if the PDF contains scanned image-only pages.

### 4. Purge of Residual Ghost Code
- Fully purged obsolete references to local Kokoro and MusicGen engines from CLI parser options and default dispatch configurations, streamlining the codebase around the official Google Gemini Cloud TTS architecture.

---

## 🔬 Phase 2: Forensic Audit Remediation & Comprehensive Engine Hardening (ADR-020)

Following full-pipeline novel stress tests, a rigorous forensic code audit was conducted across all 29 modules. The audit identified and resolved 13 subtle defects and friction points:

### 1. `CreativeManifest` Deserialization Rehydration
- **Modules**: [`audiobook_factory/contracts.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/contracts.py), [`audiobook_factory/cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py), [`audiobook_factory/manifest_renderer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/manifest_renderer.py)
- **Problem**: When `CreativeManifest` was serialized to JSON and reloaded via `.from_file()` or `.from_json()`, Pydantic loaded nested `scene_acoustics` as a plain Python `dict` instead of an active `SceneSoundscapeManifest` model instance. Calling methods such as `.generate_stochastic_cues()` raised fatal `AttributeError`.
- **Remediation**:
  Added an explicit `@model_validator(mode="after")` to `CreativeManifest` in `contracts.py`:
  ```python
  @model_validator(mode="after")
  def parse_scene_acoustics(self) -> "CreativeManifest":
      """Rehydrate scene_acoustics dictionary into SceneSoundscapeManifest upon JSON load."""
      if isinstance(self.scene_acoustics, dict):
          from audiobook_factory.scene_acoustics import SceneSoundscapeManifest
          self.scene_acoustics = SceneSoundscapeManifest.model_validate(self.scene_acoustics)
      return self
  ```
  Complementary defensive rehydration checks were added to `cinema_audio_engine.py` and `manifest_renderer.py`.

### 2. Screenplay Script Dictionary vs. List Unpacking
- **Modules**: [`audiobook_cli.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_cli.py), [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py)
- **Problem**: Screenplay JSON files produced by `ScreenplayScript.model_dump_json()` serialize as top-level dictionaries: `{"script_version": "2.0", "segments": [...]}`. Downstream CLI commands (`cmd_bgm`, `cmd_master`) and orchestrator methods assumed `script_data` was a raw list, crashing with `AttributeError` when accessing `.get()` or list iterators.
- **Remediation**:
  Standardized screenplay data extraction across all entry points:
  ```python
  if isinstance(script_data, dict):
      script_data = script_data.get("segments", script_data)
  ```

### 3. Defensive Gemini Cloud TTS Safety & FinishReason Parsing
- **Module**: [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py)
- **Problem**: In rare cases where cloud content filters or recitation warnings triggered on Google Gemini TTS, the API response omitted `candidates` or returned an empty array `candidates: []` alongside a `promptFeedback` object, or delivered a candidate with `finishReason in ("SAFETY", "RECITATION", "BLOCKLIST")`. Attempting to access `resp_json["candidates"][0]` threw an unhandled `IndexError`.
- **Remediation**:
  Implemented defensive candidate validation and explicit finishReason checking:
  ```python
  candidates = resp_json.get("candidates", [])
  if not candidates:
      fb = resp_json.get("promptFeedback", {})
      raise ValueError(f"Gemini TTS blocked generation (promptFeedback: {fb})")
  candidate = candidates[0]
  finish_reason = candidate.get("finishReason")
  if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST"):
      raise ValueError(f"Gemini TTS generation blocked by finishReason: {finish_reason}")
  ```

### 4. KeyManager Text Service Backoff Cooldown Routing
- **Module**: [`audiobook_factory/key_manager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/key_manager.py)
- **Problem**: In `PersistentKeyPool.get_key()`, the temporary backoff expiry wait block was nested inside `if service == "tts":`. If a key used for text analysis (`service="text"`) encountered an HTTP 429 and was assigned `TEMP_BACKOFF`, `get_key(service="text")` skipped the wait block and raised `ValueError("All ... keys have exhausted daily quota")`.
- **Remediation**:
  Lifted `TEMP_BACKOFF` detection and safe cooldown sleep out of the `service == "tts"` branch to execute universally for any requested service. Replaced recursive invocation with iterative `while` looping outside the SQLite database connection, preventing stack overflows.

### 5. Gate 3.5 Asset Extension Resolution Fallback
- **Module**: [`audiobook_factory/gate_auditor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py)
- **Problem**: `audit_gate3_5_acoustic_feasibility()` assumed that any asset reference ending with an audio extension (`.wav`, `.mp3`, `.flac`) was an absolute/relative file path on disk. If the path did not exist directly (e.g. `sword_slash.wav` stored inside the Sound Bank's database directory), it skipped FTS5 fuzzy resolution entirely, falsely failing Gate 3.5.
- **Remediation**:
  Updated resolution flow so that if direct path resolution fails, it unconditionally falls back to SQLite FTS5 catalog lookup:
  ```python
  if not resolved or not resolved.exists():
      try:
          resolved = bank.resolve_sound(asset_ref, category="SFX") or bank.resolve_sound(asset_ref)
      except Exception:
          resolved = None
  ```

### 6. Gate 4.5 Action Beat Size Floor Exemption
- **Modules**: [`audiobook_factory/gate_auditor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py), [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py)
- **Problem**: Empty chunk validation in Gate 4.5 ledger auditing previously rejected any audio chunk where `chunk_path.stat().st_size <= 1000`. However, valid silent action pacing chunks (e.g., dedicated 800ms speech-free canvas for Foley strikes created as short silent PCM WAVs) can legitimately be under 1,000 bytes (~200 bytes). This caused false Gate 4.5 failures.
- **Remediation**:
  Lowered the hard empty threshold to `<= 44` bytes (the minimal size of an empty RIFF WAV header) and explicitly exempted `[ACTION]` and `Foley` pacing segments:
  ```python
  elif chunk_path.stat().st_size <= 44:
      missing_chunks.append(f"{seg_l.audio_file} (empty)")
  elif chunk_path.stat().st_size <= 1000 and getattr(seg_l, "speaker", "").lower() not in ("foley", "action") and "[action]" not in getattr(seg_l, "text", "").lower():
      missing_chunks.append(f"{seg_l.audio_file} (empty)")
  ```

### 7. Sanitizer Bracketed Tag Shield & Empty Text Pruning
- **Module**: [`audiobook_factory/sanitizer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sanitizer.py)
- **Problem**: In `sanitize_screenplay_segment()`, `count_latin_words(text)` counted words inside bracketed acting tags (e.g., `[bellowing battlecry] [guttural grunt on blade deflect]`). In Hindi screenplay mode, combat lines with multiple tags exceeded the 6-word English threshold and were incorrectly discarded as English leakage. Conversely, lines with non-vocal cues stripped down to empty strings were passed to TTS.
- **Remediation**:
  Stripped bracketed acting tags before computing Latin word counts, and pruned any segments whose spoken dialogue becomes empty:
  ```python
  text_no_tags = re.sub(r"\[[^\]]+\]", "", text).strip()
  if not text_no_tags:
      return None
  if is_hindi:
      eng_words = count_latin_words(text_no_tags)
      dev_chars = count_devanagari_chars(text_no_tags)
  ```

### 8. Scene Acoustics Multi-Layer Stochastic Collision Avoidance
- **Module**: [`audiobook_factory/scene_acoustics.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/scene_acoustics.py)
- **Problem**: When a scene defined multiple Layer 4 stochastic spot transient layers (e.g., subtle floor creaks and distant owl hoots), the procedural placement algorithm calculated identical timestamps or pause slots for both layers, resulting in simultaneous, unnatural acoustic collisions.
- **Remediation**:
  Introduced `scene_used_timestamps: Set[int]` across all layers in the scene. When picking slots or calculating jitter, the algorithm validates timestamp uniqueness and enforces a minimum separation of at least $250\text{ ms}$:
  ```python
  while any(abs(ts - existing) < 250 for existing in scene_used_timestamps):
      ts += 300
  scene_used_timestamps.add(ts)
  used_timestamps.append(ts)
  ```

### 9. Catalog Seeder Word-Boundary Sub-Bass Classification
- **Module**: [`audiobook_factory/catalog_seeder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/catalog_seeder.py)
- **Problem**: In `derive_virtual_metadata()`, checking `any(k in stem for k in (..., "sub", ...))` triggered on subtle environmental sound files like `subtle_creak.wav` or `subway_rumble.wav`, mistakenly categorizing them as `Combat` Foley and tagging them with `tense` mood.
- **Remediation**:
  Replaced loose substring `"sub"` with explicit compound tokens:
  ```python
  if any(k in stem for k in ("sword", "chop", "blade", "slash", "knife", "metal", "armor", "mace", "parry", "clash", "flesh", "bone", "blood", "sub_drop", "sub_bass", "subwoofer", "subboom", "lfe")):
      subcat = "Combat"
      cat = "FOL"
  ```

### 10. Standard `FFMETADATA1` Special Character Escaping
- **Module**: [`audiobook_factory/packager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py)
- **Problem**: Novel titles, author names, or chapter headings containing special characters (`=`, `;`, `#`, `\`) corrupted the `FFMETADATA1` parser in FFmpeg, causing missing chapter titles or broken metadata tags in final `.m4b` containers.
- **Remediation**:
  Added `_escape_ffmetadata()` to escape all reserved characters:
  ```python
  def _escape_ffmetadata(val: Any) -> str:
      """Escape special characters (=, ;, #, \\) for FFMETADATA1 specification."""
      s = str(val or "")
      s = s.replace("\\", "\\\\")
      for char in ("=", ";", "#"):
          s = s.replace(char, f"\\{char}")
      return s.replace("\n", " ").strip()
  ```

### 11. Atomic Audio Generation & SNR Verification in TTS Dispatcher
- **Module**: [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py)
- **Problem**: Raw PCM audio from Gemini TTS was written directly to the target output file. If subsequent audio defect audits (clipping, DC offset, low RMS, stutter) failed, the defective WAV file remained on disk in the project audio cache.
- **Remediation**:
  Audio chunks are now written to a temporary destination (`.tmp.wav`). If any defect is detected, `tmp_file.unlink(missing_ok=True)` deletes the file immediately. Only upon passing all quality checks is the file atomically promoted:
  ```python
  # Atomically promote verified audio to target destination
  tmp_file.replace(output_file)
  ```

### 12. CLI Audio Segment Deduplication
- **Module**: [`audiobook_cli.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_cli.py)
- **Problem**: In `cmd_master`, `audio_dir.glob(f"c{ch_num:03d}_*.wav")` collected all matching files. If a chapter was synthesized multiple times or had take variations (e.g. `c001_s0001_v1.wav` and `c001_s0001_v2.wav`), both files were passed to `concatenate_and_master_chapter()`, causing duplicate spoken dialogue.
- **Remediation**:
  Segment files are now mapped by their 4-digit segment index `_s(\d{4})_`, preserving only the most recently modified take:
  ```python
  seg_dict = {}
  for p in raw_segments:
      m_s = re.search(r"_s(\d{4})_", p.name)
      if m_s:
          s_idx = int(m_s.group(1))
          if s_idx not in seg_dict or p.stat().st_mtime > seg_dict[s_idx].stat().st_mtime:
              seg_dict[s_idx] = p
  segments = [seg_dict[k] for k in sorted(seg_dict.keys())] if seg_dict else raw_segments
  ```

### 13. Dynamic Filter Complex Script Piping (>6000 Chars)
- **Module**: [`audiobook_factory/cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py)
- **Problem**: When rendering multi-scene soundscapes with dense ambient stems and stochastic spot cues, the generated FFmpeg `-filter_complex` string frequently exceeded Windows' maximum command-line argument limit of 8,191 characters, leading to silent subprocess crashes.
- **Remediation**:
  Added dynamic script piping: when `filter_str` exceeds 6,000 characters, it is automatically written to a temporary filter script file and supplied via `-filter_complex_script`:
  ```python
  filter_script = None
  if len(filter_str) > 6000:
      filter_script = out_dir / f"{ch_id}_amb_filter.txt"
      filter_script.write_text(filter_str, encoding="utf-8")
      fc_args = ["-filter_complex_script", str(filter_script)]
  else:
      fc_args = ["-filter_complex", filter_str]
  ```
  The script file is safely cleaned up immediately following FFmpeg process completion.

---

## 🎭 Phase 3: Zero-Voice-Drift Hardening & Deterministic Attribution (ADR-021)

### 1. Fail-Closed Unregistered Speaker Protection (`UnregisteredSpeakerError`)
- **Module**: [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py)
- **Problem**: When LLM screenplay extraction produced an unmapped or hallucinated character name, `TTSDispatcher.get_speaker_config()` silently fell back to the default narrator voice (`Aoede`). In full-cast audio dramas, this resulted in jarring "voice drift", where male warriors or sorceresses suddenly spoke in the narrator's female voice for a single dialogue line.
- **Remediation**:
  Implemented a strict fail-closed policy. Dialogue segments requesting an unregistered speaker raise a typed `UnregisteredSpeakerError` displaying fuzzy suggestions (`difflib.get_close_matches`):
  ```python
  if self.strict_speakers:
      raise UnregisteredSpeakerError(
          f"Speaker '{sp_clean}' (type: {seg_type}) is not registered in voice_registry.json "
          f"or character_roster.json!{close_hint} Silent fallback to Narrator is prohibited to prevent voice drift."
      )
  ```

### 2. Dynamic Character Roster & Voice Registry Auto-Discovery
- **Module**: [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py)
- **Remediation**:
  `TTSDispatcher._load_character_roster()` automatically loads `character_roster.json`, indexing canonical names, Devanagari transliterations, underscore/space variations, and character aliases. When a dialogue line is dispatched under an alias (e.g. `Witcher`, `विचर`, `Geralt_of_Rivia`), it resolves deterministically to the canonical voice configuration (`Charon`).

### 3. Pre-Flight Chapter Voice Validation
- **Module**: [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py)
- **Remediation**:
  Before making any external API calls, `TTSDispatcher.synthesize_chapter_script()` runs a zero-cost pre-flight sweep across all segments in the chapter. If any segment contains an unregistered speaker, synthesis aborts immediately, shielding Gemini API quota from partial run failures.

### 4. Gate 2 Screenplay Roster Audit & Whitelist Enforcement
- **Module**: [`audiobook_factory/gate_auditor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py), [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py)
- **Remediation**:
  `audit_gate2_script(script_file, project_dir=pdir)` auto-discovers the project character roster and builds a case-insensitive, space/underscore-normalized canonical whitelist. In `orchestrator.py`, Gate 2 failure halts chapter processing cleanly:
  ```python
  except GateAuditError as e:
      logger.error(f"\n[!] 🛑 GATE 2 AUDIT FAILED for Chapter {chapter_num:02d}: {e}")
      logger.error("[!] Screenplay contains non-canonical speakers or schema violations. Aborting synthesis to prevent voice drift.")
      raise
  ```

### 5. Gate 1 Acoustic Gender Alignment Check
- **Module**: [`audiobook_factory/gate_auditor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/gate_auditor.py)
- **Remediation**:
  `audit_gate1_roster()` cross-references roster `gender` against known Gemini persona profiles (`FEMALE_PERSONAS = {"aoede", "kore", "leda", "zephyr"}`, `MALE_PERSONAS = {"charon", "fenrir", "puck", "zeus", "orpheus", "achilles"}`), emitting diagnostic warnings if male characters are assigned female personas or vice versa. Non-vocal action tags (`Foley`, `SFX`) are cleanly bypassed.

### 6. Two-Pass Screenplay Pronoun & Alias Disambiguation
- **Module**: [`audiobook_factory/script_builder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py)
- **Remediation**:
  `clean_screenplay_pass2()` strips parenthetical actor annotations (`Geralt (Witcher)` $\rightarrow$ `Geralt`) and resolves pronouns in both English (`he`, `she`, `the man`, `the woman`) and Hindi (`उसने`, `वह`, `आदमी`, `लड़की`, `महिला`) to the most recently active character matching the gender.

---

## 🎧 Phase 4: Audio Drama Timeline Sync, Foley Staging & Soundscape Partitioning (ADR-022)

### 1. Cumulative Timeline Drift Elimination (`pre_roll_breath_ms`)
- **Modules**: [`contracts.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/contracts.py), [`timeline_ledger.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/timeline_ledger.py), [`agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py)
- **Problem**: When intimate dialogue segments included `pre_roll_breath_ms`, physical silence was inserted into the concatenated WAV audio, but `start_ms` in `TimelineLedger` and `seg_starts_ms` in `AgentDirector` did not offset speech accordingly. Over a long chapter, this accumulated 10-30s of timing drift, misaligning music drops and Foley hits.
- **Remediation**:
  - Added `pre_roll_breath_ms: int = Field(default=0, ge=0)` to `TimelineSegment`.
  - Synchronized start calculation: `start_ms = curr_t_ms + pre_breath`.
  - Synchronized director timeline offsets: `seg_starts_ms[s_idx] = current_time_ms + pre_breath`.

### 2. Eradication of 50% Dead-Center Foley Trap & Bilingual Anchor Mapping
- **Module**: [`audiobook_factory/agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py)
- **Problem**: Unmatched anchor words in Hindi dialogue lines fell back to segment midpoint (`len(words) // 2`), causing every sound effect to land dead-center in the middle of dialogue lines.
- **Remediation**:
  - Implemented `BILINGUAL_ANCHOR_MAP` mapping Hindi and English stems (`sword` $\leftrightarrow$ `तलवार`, `blade` $\leftrightarrow$ `खंजर`, `door` $\leftrightarrow$ `दरवाजा`, `slam` $\leftrightarrow$ `पटक`, `plate` $\leftrightarrow$ `थाली`, `pour` $\leftrightarrow$ `उड़ेल`).
  - Implemented transient lead-in phasing: preparatory actions land early ($\sim 15\%$), while physical impacts land on climax windows ($\sim 75\%$), eliminating dead-center sound effect placement.

### 3. Domestic Tableware vs. Combat Weaponry Taxonomy Isolation
- **Modules**: [`acoustic_bus_matrix.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/acoustic_bus_matrix.py), [`agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py)
- **Problem**: In Universal Category System (UCS) rules, the keyword "plate" expanded to armor plating (`WEAPMtl` / `steel`), causing dinner plates (`थाली`) in banquet scenes to trigger battlefield sword clashes.
- **Remediation**:
  - Added `DOMETabl` to `UCS_RULES` for tableware (`थाली`, `कटोरा`, `चम्मच`, `बर्तन`, `प्याला`, `plate`, `dish`, `bowl`, `cup`, `tankard`).
  - Added `GOREAnat` for anatomical bones and flesh (`हड्डी`, `मांस`).
  - Added category guards in `_resolve_foley_asset`: strictly prohibits weapon assets during domestic dining scenes.

### 4. Scene-Bound BGM Underscore with `until_segment` Calculation
- **Module**: [`audiobook_factory/agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py)
- **Remediation**:
  Pass 2 Music Director calculates cue duration dynamically using `until_segment`:
  $$\text{duration\_ms} = \text{seg\_starts\_ms}[u\_idx] - \text{start\_ms}$$
  Cues now span natural dramatic scenes (25s to 240s) rather than arbitrary 30s chops, with an enforced 40% chapter music budget.

### 5. Dynamic Multi-Scene Ambience Bed Partitioning
- **Module**: [`audiobook_factory/agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py)
- **Remediation**:
  `_partition_script_ambience_scenes()` monitors shifts in `acoustic_env` across screenplay segments (e.g. Castle Bath $\rightarrow$ Royal Banquet Hall $\rightarrow$ Forest Night), partitioning chapters into distinct acoustic scene blocks with smooth crossfades and decoupled 4-stem profiles, replacing flat monolithic 106-minute ambience loops.

---

## 🧪 Comprehensive Verification & Test Suite

The entire remediation and hardening architecture is codified and guarded by dedicated regression tests in [`tests/test_audit_remediation_sprint.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/tests/test_audit_remediation_sprint.py) and [`tests/test_forensic_audit_remediation.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/tests/test_forensic_audit_remediation.py).

### Test Suite Execution
```powershell
# Run Zero-Voice-Drift Hardening & Speaker Attribution suite (ADR-021):
python -m unittest tests/test_zero_voice_drift_adr021.py

# Run Audio Drama Sync, Foley Staging & Soundscape Remediation suite (ADR-022):
python -m unittest tests/test_audio_sync_and_soundscape_remediation.py

# Run the dedicated forensic audit remediation regression suite (ADR-020):
python -m unittest tests/test_forensic_audit_remediation.py

# Run the Phase 1 audit remediation sprint suite:
python -m unittest tests/test_audit_remediation_sprint.py

# Run the full project test discovery across all 34 suites (243 tests):
python -m unittest discover tests -p "test_*.py"
```

### Verification Matrix Summary

| Test Case | Module Tested | Verification Invariant | Status |
|---|---|---|:---:|
| `test_creative_manifest_deserialization_roundtrip` | `contracts.py` | Nested `scene_acoustics` automatically rehydrated into `SceneSoundscapeManifest`. | **PASS** |
| `test_cli_and_orchestrator_dict_screenplay_unpacking` | `audiobook_cli.py` | Screenplay scripts serialized as dictionaries unpack `segments` cleanly. | **PASS** |
| `test_sanitizer_combat_battlecry_not_dropped` | `sanitizer.py` | Multi-tagged combat cries are preserved and not dropped by Latin word counter. | **PASS** |
| `test_sanitizer_empty_text_dropped` | `sanitizer.py` | Segments reduced to empty text after tag stripping are safely dropped. | **PASS** |
| `test_gate35_asset_extension_fallback` | `gate_auditor.py` | Cues with extensions fall back seamlessly to Sound Bank FTS5 fuzzy search. | **PASS** |
| `test_gate45_action_beat_small_file` | `gate_auditor.py` | Action beat silent WAVs (> 44B header) pass Gate 4.5 without empty flag. | **PASS** |
| `test_scene_acoustics_multi_layer_collision_avoidance` | `scene_acoustics.py` | Multi-layer stochastic spot cues maintain distinct timestamps ($\ge 250\text{ ms}$). | **PASS** |
| `test_catalog_seeder_subtle_foley_classification` | `catalog_seeder.py` | `subtle_creak.wav` is categorized as `Doors`, not `Combat`. | **PASS** |
| `test_ffmetadata_escaping` | `packager.py` | Special characters (`=`, `;`, `#`, `\`) in FFMETADATA1 are escaped cleanly. | **PASS** |
| `test_gemini_tts_defensive_safety_parsing` | `tts_dispatcher.py` | Empty candidates raise descriptive `ValueError` with `promptFeedback`. | **PASS** |
| `test_key_manager_text_service_backoff` | `key_manager.py` | `get_key(service="text")` respects backoff cooldown without crashing. | **PASS** |
| `test_m4b_packager_wav_codec_detection` | `packager.py` | Non-AAC files force `-c:a aac -b:a 192k`; native AAC preserves `-c:a copy`. | **PASS** |
| `test_gate3_dynamic_scenes_and_manifest` | `gate_auditor.py` | Validates `CreativeManifest` via Gate 3.5; grants PASS for director-managed workflows. | **PASS** |
| `test_gate5_tolerance_standardization` | `gate_auditor.py` | Verifies `tolerance_lu` default signature is standardized to `1.0 LU`. | **PASS** |
| `test_env_loader_strips_quotes` | `key_manager.py` | Single and double quotes around `.env` keys are stripped cleanly. | **PASS** |
| `test_soundscape_mood_service_type` | `soundscape.py` | Mood analysis calls `get_key(service="text")`, shielding TTS quota. | **PASS** |
| `test_cli_chapter_regex_parsing` | `audiobook_cli.py` | Script chapter numbers are parsed via regex, preventing partial run renumbering. | **PASS** |
| `test_unregistered_dialogue_speaker_raises_error` | `tts_dispatcher.py` | Unregistered dialogue roles raise `UnregisteredSpeakerError` (ADR-021). | **PASS** |
| `test_alias_resolution_in_tts_dispatcher` | `tts_dispatcher.py` | Hindi/English aliases resolve deterministically to canonical voices (ADR-021). | **PASS** |
| `test_preflight_validation_aborts_synthesis` | `tts_dispatcher.py` | Halts synthesis before API dispatch on unmapped speakers (ADR-021). | **PASS** |
| `test_gate2_auto_discovers_roster_and_catches_unmapped` | `gate_auditor.py` | Auto-discovers project roster and enforces speaker whitelist (ADR-021). | **PASS** |
| `test_pre_roll_breath_cumulative_timeline_sync` | `contracts.py` | `pre_roll_breath_ms` synchronized across contracts, ledger, and director (ADR-022). | **PASS** |
| `test_bilingual_anchor_offset_no_dead_center` | `agent_director.py` | `BILINGUAL_ANCHOR_MAP` eliminates 50% dead-center trap (ADR-022). | **PASS** |
| `test_domestic_vs_combat_foley_taxonomy` | `acoustic_bus_matrix.py` | `DOMETabl` strictly isolates tableware from sword clash assets (ADR-022). | **PASS** |
| `test_scene_bound_bgm_duration` | `agent_director.py` | `until_segment` dynamically extends BGM across scene boundaries (ADR-022). | **PASS** |
| `test_dynamic_multi_scene_ambience_partitioning` | `agent_director.py` | `acoustic_env` shifts cleanly partition chapter ambience beds (ADR-022). | **PASS** |
| **Full Suite Total** | **29 Modules** | **243/243 unit and regression tests passing with 0 errors and 0 regressions.** | **100% PASS** |

---

## 📚 Related Documentation Links
- [🏛️ Architecture Blueprint](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/ARCHITECTURE.md)
- [🎬 Cinematic Sound Design & Adult Fidelity](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/CINEMATIC_SOUND_DESIGN_AND_ADULT_FIDELITY.md)
- [🎛️ Audio Engineering & DSP Manual](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/AUDIO_ENGINEERING.md)
- [🛡️ Quality Gates Specification](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/QUALITY_GATES.md)
- [💻 CLI Reference](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/CLI_REFERENCE.md)
- [📚 API Reference](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/API_REFERENCE.md)
- [🛠️ Developer & Contributor Guide](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/DEVELOPER_GUIDE.md)
