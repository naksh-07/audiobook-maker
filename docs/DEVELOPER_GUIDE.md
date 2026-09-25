# 🛠️ Developer & Contributor Guide

## Development Environment Setup

### 1. System Prerequisites
- **Python**: Python 3.10+ (tested on 3.10, 3.11, 3.12, 3.13).
- **FFmpeg**: Version 6.0+ (compiled with `soxr`, `libmp3lame`, and `aac` support).
  - Verify on Windows: `ffmpeg -version`
  - Verify SOXR support: `ffmpeg -filters | findstr soxr` (or `grep soxr` on Linux/macOS).
- **pypdf**: Bundled dependency (`pypdf>=5.0`) for fast zero-quota digital PDF extraction.
- **Poppler Utilities**: `pdftotext` (optional fallback for non-standard formats).

### 2. Virtual Environment & Dependencies
```bash
# Clone the repository
git clone https://github.com/naksh-07/audiobook-maker.git
cd audiobook-maker

# Create and activate virtual environment
python -m venv .venv

# Windows Powershell:
.\.venv\Scripts\Activate.ps1

# Linux / macOS / Termux:
source .venv/bin/activate

# Install development dependencies
pip install -e .
```

### 3. Environment Configuration
Copy the `.env.example` file and configure your API keys:
```bash
cp .env.example .env
```
Ensure `GEMINI_API_KEY` is provided (surrounding quotes are automatically stripped during load):
```env
GEMINI_API_KEY=AIzaSy...your_gemini_api_key...
TTS_PRIMARY_BACKEND=gemini_tts
GEMINI_TTS_MODEL=gemini-3.1-flash-tts-preview
GEMINI_DEFAULT_VOICE=Aoede
```

---

## 🧪 Testing Suite & Verification

The codebase maintains **521 passed unit tests (17 subtests passed)** across all test suites with a zero-regression and multi-script zero-hardcoding invariant (100% OK, 0 failures, 0 errors).

### Running Dedicated Phase Test Suites
```powershell
# Commercial Studio Voice Casting, Identity & Generation Suites (Waves 1-6, 77 tests)
pytest tests/test_wave1_casting.py tests/test_wave2_voice_identity.py tests/test_wave3_acting_intelligence.py tests/test_wave4_generation_quality.py tests/test_wave5_ensemble_performance.py -v

# Golden Audio Regression Suite (18 dramatic cases offline)
pytest tests/test_golden_audio_regression_suite.py -v

# AST Zero-Hardcoding Contracts Verification
pytest tests/test_zero_hardcoding_contracts.py -v

# Dramatic Performance Realization Layer & Gate 2.8 (ADR-032, 23 tests)
pytest tests/test_performance_realization.py -v

# Stage 3 Dramaturgy, Beat Planner & Golden Scenes (7 test suites)
pytest tests/dramaturgy/ -v

# World + Character Memory 2.0 Test Suite (7 test suites, 35+ tests)
python -m unittest discover tests/translation/memory -p "test_*.py"

# Forensic Audit Remediation Probes (100-chapter stress, victim ordering, ghost event isolation)
python -m unittest tests/translation/memory/test_audit_remediation.py

# Literary Translation Intelligence & Memory 2.0 Suites (Pillar 2 - ADR-030)
python -m unittest discover tests/translation -p "test_*.py"

# Multi-Script (Latin + Devanagari) Zero-Hardcoding AST Contract Suite (ADR-030)
python -m unittest tests/test_zero_hardcoding_contracts.py

# Forensic Document Ingestion & Canonical AST Suite (Pillar 1 - ADR-029)
python -m unittest tests/test_book_ingestion_pillar1.py

# Zero-Voice-Drift Hardening & Deterministic Speaker Attribution (ADR-021)
python -m unittest tests/test_zero_voice_drift_adr021.py

# Audio Drama Sync, Foley Staging & Soundscape Remediation (ADR-022)
python -m unittest tests/test_audio_sync_and_soundscape_remediation.py

# Forensic Audit Remediation & Hardening Suite (ADR-020 - 13 Defects)
python -m unittest tests/test_forensic_audit_remediation.py

# 4-Stem Decoupled Scene Acoustics, Stochastic Generator & Occlusion Suite (ADR-018)
python -m unittest tests/test_scene_acoustics_and_stochastic.py

# Hollywood & AAA Combat Audio Drama Suite (ADR-017)
python -m unittest tests/test_combat_audio_drama_fidelity.py

# Adult Literary Fidelity & HBO Intimacy Suite (ADR-016 & ADR-019)
python -m unittest tests/test_adult_literary_fidelity.py

# Audit Remediation & Hardening Sprint (P0-P3 showstoppers)
python -m unittest tests/test_audit_remediation_sprint.py

# Phase 1: Audio Timing & State Integrity
python -m unittest tests/test_phase1_remediation.py

# Phase 2: Metadata Pipeline & Data Silos Unification
python -m unittest tests/test_phase2_metadata_unification.py

# Phase 3: Spatial Audio Staging, Fail-Closed Gates & Checkpoint Safety
python -m unittest tests/test_phase3_spatial_and_failclosed_gates.py

# DSP Loudness & Sidechain Ducking
python -m unittest tests/test_audio_dsp_loudness.py tests/test_action_beats_and_musical_ducking.py
```

### Running Full Repository Regression Test Discovery
```powershell
python -m unittest discover tests -p "test_*.py"
```

### World + Character Memory 2.0 Repository Layout
```text
audiobook_factory/translation/memory/
├── __init__.py               # Package exports
├── state.py                  # Pure deterministic transition functions
├── events.py                 # StoryEvent, StoryEventType, TemporalMode, SceneChangeDetector, EventExtractor
├── character_memory.py       # CharacterState, CharacterArcMemory, CharacterKnowledgeEngine (MUST_NOT_KNOW)
├── world_memory.py           # WorldState, LocationState, ObjectState, NarrativeThreadState, TimelinePoint
├── memory_delta.py           # StateDelta, DeltaDomain, StateMutability, StateDeltaEngine
├── memory_validator.py       # MemoryValidator (7 contradiction classes), MemoryValidationReport
├── memory_store.py           # MemoryStore (versioned persistence, ghost event isolation)
├── memory_retriever.py       # MemoryRetriever (7-tier selective hierarchy + Narrative Salience)
└── memory_context.py         # MemoryContext (800-token budget cap, performance guidance adapter)

tests/translation/memory/
├── test_audit_remediation.py           # 5 independent audit probes & Pass 2 polish items
├── test_character_and_knowledge.py     # Epistemic isolation & CharacterKnowledgeEngine
├── test_events_and_deltas.py           # StoryEvent hashing, delta projection, location conditions
├── test_golden_novel_continuity.py     # 10-chapter Golden Novel end-to-end integration test
├── test_relationships_and_register.py  # 7D relationship mutations, pronoun/register resolution
├── test_retriever_and_store.py         # 7-tier retrieval, atomic persistence, version hashing
└── test_world_and_validator.py         # WorldState, timeline, 7 contradiction classes
```

---

## 📐 Core Engineering Standards & Invariants

1. **Zero-Placeholder Guarantee**:
   No `TODO`, `pass`, empty stubs, or mock implementations in production paths. Every component must be fully implemented, tested, and verified.
2. **Non-Destructive Invariant**:
   All new features and contract extensions must maintain backward compatibility. Defaults ensure legacy workflows continue to execute without exceptions.
3. **Fail-Closed Security & Quality Audits**:
   Quality gates must never fail-open. When audio probes or file inspections fail, the gate must report a hard failure (`status="FAIL"`) to prevent corrupted files from reaching listeners.
4. **Auto-Janitor Safety Shield**:
   Synthesized speech WAV chunks are valuable and consume API quota. Chunks must NEVER be purged unless the master audio file has been generated and validated with $> 1000$ bytes on disk.
5. **Clickable Links In Prose**:
   All file paths in development handoffs and internal documentation must use markdown file links (`[file.py](file:///path/to/file.py)`).
6. **Strict Agent Creative Mandate**:
   Creative decisions (character casting, emotion tags, dramaturgy, silence carving, leitmotif assignment, and Foley placement) belong exclusively to autonomous AI agents ([`AgentDirector`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py)). Downstream execution layers ([`CinemaAudioEngine`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py), [`ManifestRenderer`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/manifest_renderer.py), and DSP mastering) are 100% deterministic compilation and execution runtimes and must NEVER override agent creative intent.
7. **Multi-Script Novel-Agnostic Zero-Hardcoding Contract (ADR-030)**:
   Core engine modules inside `audiobook_factory/` must remain 100% novel-agnostic. Hardcoding book-specific character names, locations, project slugs, or Devanagari spelling variants (`FORBIDDEN_CHARACTERS_DEVANAGARI`) into Python source files is strictly forbidden and enforced by [`tests/test_zero_hardcoding_contracts.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/tests/test_zero_hardcoding_contracts.py). All book-specific lore belongs exclusively in `<project_dir>/book_bible.json`.

---

## 🎹 Adding Assets to the Sound Bank

Audiobook Maker relies on a 100% free, local CC0 sound catalog indexed with SQLite FTS5.

### Ingestion Workflow
Place new WAV, MP3, OGG, or FLAC files into an asset folder:
```bash
python audiobook_cli.py bank scan path/to/my_new_sfx/
```
The `UniversalSoundBankIngester` will:
1. Probe audio sample rate, channels, and duration.
2. Compute emotional valence and arousal heuristics.
3. Generate FTS5 full-text search indexes on tags and filenames.
4. Commit assets to `audiobooks/sound_bank/catalog.db`.

### Offline Foley & Magic Composite Asset Baking
To avoid runtime FFmpeg filter graph bloat for complex, multi-phase magic spells and tactile foley:
```bash
python scripts/bake_foley_composites.py
```
This renders composite assets (`magic_lumos_light.wav`, `magic_expelliarmus_kinetic.wav`, `tactile_parchment_quill_scratch.wav`) and indexes them directly into the SQLite FTS5 catalog.

---

## 🩺 Diagnostics & Troubleshooting

| Issue | Root Cause | Solution |
|---|---|---|
| `RuntimeError: FFmpeg mastering failed: ... filter 'soxr' not found` | FFmpeg was compiled without libsoxr. | Reinstall FFmpeg with `libsoxr` enabled (e.g. `choco install ffmpeg-full` on Windows or `apt install ffmpeg` on Ubuntu). |
| `AllKeysExhaustedTodayError: ... 429 quota reached` | Daily API request or token limits exceeded on Gemini API keys. | The system automatically checkpoints progress to disk. Production can be resumed after daily midnight PT quota reset or by adding additional keys to `.env`. |
| `GateAuditError: Gate 1 Failed: Voice collision detected` | Two characters are assigned the exact same voice and pitch. | Edit `voice_registry.json` or character roster so each active character has a distinct voice persona or pitch offset. |
| `GateAuditError: Gate 3 Failed: Scenes source file missing` | Project uses modern `CreativeManifest` rather than legacy scenes. | Gate 3 has been dynamically hardened in `gate_auditor.py` to audit `CreativeManifest` directly or grant PASS for director-managed workflows. Ensure latest `gate_auditor.py` is in place. |
| `FFmpeg packaging failed: Invalid audio stream copy` | Uncompressed WAV (`pcm_s16le`) was passed to M4B packager with `-c:a copy`. | The packager now automatically validates `is_all_aac` and transcodes non-AAC/WAV stems to AAC 192k with `+faststart`. |
| `HTTP 400 Bad Request on Gemini API Key` | Key in `.env` was enclosed in quotes (e.g. `GEMINI_API_KEY="AIza..."`). | Fixed automatically in `key_manager.py` by `.strip("'\"")`. Remove surrounding quotes if overriding via external environment variables. |
| `TTS Quota rapidly depleted by background tasks` | Text prompts (mood detection, dramaturgy) were sharing the TTS key pool. | Quota isolation now explicitly routes text prompts through `global_key_pool.get_key(service="text")`, shielding the scarce 10 RPD Gemini TTS quota. |
| `Gemini Flash TTS censorship false-positives on mature literature` | Harm categories triggered safety block. | Fixed permanently in `tts_dispatcher.py` by setting explicit `safetySettings: [BLOCK_NONE]` across all 4 categories (`HARASSMENT`, `HATE_SPEECH`, `SEXUALLY_EXPLICIT`, `DANGEROUS_CONTENT`). |
| `StemLedger reports dmr_compliant: false` | Background stems ($ME$) within 10dB of vocal dialogue ($DX$). | Check `chapter_XXX_manifest.json` ducking parameters or decrease background bed gain to guarantee $DMR \ge 10.0$ dB. |
| `AttributeError: 'dict' object has no attribute 'generate_stochastic_cues'` | Pydantic JSON deserialization parsed `scene_acoustics` as raw dict. | Fixed in `contracts.py` with `@model_validator(mode="after")` on `CreativeManifest` to rehydrate into `SceneSoundscapeManifest`. |
| `GateAuditError: Gate 3.5 Failed: Asset not found for asset with .wav extension` | Cue path had extension but was stored in Sound Bank without full path. | Fixed in `gate_auditor.py` to fall back unconditionally to SQLite FTS5 `bank.resolve_sound()`. |
| `GateAuditError: Gate 4.5 Failed: Missing or empty audio chunks (size <= 1000)` | Silent action beat chunks (<1000B) failed legacy size threshold. | Lowered floor to 44B (WAV header) and exempted `[ACTION]` / `Foley` segments in `gate_auditor.py`. |
| `FFmpeg process crash: Command line too long (Windows 8191 limit)` | Ambient soundscape filter complex exceeded maximum command argument length. | Fixed in `cinema_audio_engine.py` by automatically piping filters > 6000 chars into `-filter_complex_script`. |
| `Multiple take concatenation in chapter audio master` | Segments with multiple takes were all globbed into chapter master. | Fixed in `audiobook_cli.py` (`cmd_master`) by deduplicating segments using regex `_s(\d{4})_` and latest `st_mtime`. |
