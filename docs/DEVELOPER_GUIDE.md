# 🛠️ Developer & Contributor Guide

## Development Environment Setup

### 1. System Prerequisites
- **Python**: Python 3.10+ (tested on 3.10, 3.11, 3.12, 3.13).
- **Node.js**: Version 18+ (for Antigravity Studio Panel Webview sidecar).
- **FFmpeg**: Version 6.0+ (compiled with `soxr`, `libmp3lame`, and `aac` support).
  - Verify on Windows: `ffmpeg -version`
  - Verify SOXR support: `ffmpeg -filters | findstr soxr` (or `grep soxr` on Linux/macOS).
- **pypdf**: Bundled dependency (`pypdf>=5.0`) for fast zero-quota digital PDF extraction.
- **Poppler Utilities**: `pdftotext` (optional fallback for non-standard formats).

### 2. Virtual Environment & Dependencies
```bash
# Clone the repository
git clone https://github.com/naksh-07/audiobook-studio.git
cd audiobook-studio

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
GEMINI_TTS_MODEL=gemini-3.8-flash
GEMINI_DEFAULT_VOICE=Aoede
```

### 4. Running & Debugging the Antigravity Studio Sidecar
To test the embedded Webview panel locally outside Antigravity:
```bash
cd sidecars/studio-panel
node main.mjs
```
The sidecar server starts on `http://127.0.0.1:4000` (or assigned port), bridging live IPC requests to `audiobook_factory.api.studio_bridge`.

To test the Python bridge directly:
```bash
python -m audiobook_factory.api.studio_bridge status
python -m audiobook_factory.api.studio_bridge list-projects
```

---

## 🧪 Testing Suite & Verification

The codebase maintains **758 passed unit and integration tests (100% green, 0 regressions)** across all active test suites:

```powershell
# Run Full Test Suite (100% Green - 758 passing)
uv run pytest

# 4D Voice Formants & DSP Formant Chaining
uv run pytest tests/test_4d_voice_formant_matrix.py tests/test_formant_shifted_tts_dsp.py tests/test_character_caster.py -v

# Screenplay & Anti-Swap Dialogue Attribution Auditor
uv run pytest tests/test_dialogue_attribution_auditor.py tests/test_multi_agent_screenplay.py -v

# 4-Agent Dramatic Translation Collective & Dual-Rule Invariant
uv run pytest tests/test_multi_agent_translation.py tests/test_translation_collective_dual_rule.py -v

# Pre-Production Intelligence & Universal Novel DeepSearch Grounding
uv run pytest tests/test_universal_deepsearch_grounding.py tests/test_book_dna_agent.py tests/test_multi_agent_preproduction.py tests/test_multi_agent_voice_audition.py -v

# Model Manager Quota Shield & Strict Halt
uv run pytest tests/test_model_manager_and_strict_halt.py -v

# Pillar 1 Forensic Ingestion, Layout-Aware PDF & EPUB
uv run pytest tests/test_pdf_engine.py tests/test_epub_parser.py tests/test_document_extractor_upgraded.py tests/test_forensic_analyzer.py -v

# Dialogue Editorial Layer (DE-01 - DE-07)
uv run pytest tests/test_dialogue_editorial_layer.py tests/test_dialogue_editing_integration.py -v

# EBU R128 Broadcast Vocal Mastering
uv run pytest tests/test_mastering_contracts.py tests/test_mastering_engine.py tests/test_mastering_certification.py -v

# Universal Zero-Hardcoding Contracts
uv run pytest tests/test_zero_hardcoding_contracts.py -v

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

### Sonic Intelligence Engine & Sound Bank Layout
```text
audiobook_factory/
├── deterministic_audio_analyzer.py # Phase 1: Sonic Genome v2.1 & 14 measured DSP metrics
├── audio_classifier_adapters.py   # Phase 2: AST AudioSet 527 taxonomy classifier
├── clap_semantic_adapter.py       # Phase 2: LAION-CLAP 512-d semantic embedding adapter
├── sonic_model_manager.py         # Phase 2: Dual model lifecycle & CUDA VRAM manager
├── sonic_query_planner.py         # Phase 3: Hinglish normalization & 15 intent types
├── query_embedding_cache.py       # Phase 3: Thread-safe RLock LRU + SQLite cache
├── sonic_candidate_generators.py  # Phase 3: 5 candidate generators & pool aggregator
├── sonic_hybrid_reranker.py       # Phase 3: Deterministic linear scoring & diversity filter
├── agent_sound_card.py            # Phase 3: Epistemically honest Agent Sound Cards v3.0
├── sonic_intelligence_engine.py   # Phase 3: Unified facade & execution telemetry
└── sound_bank.py                  # Room 3: SQLite FTS5 catalog & JIT streaming

tests/
├── test_deterministic_audio_analyzer.py # Phase 1 DSP test suite
├── test_sonic_enrichment_phase2.py     # Phase 2 AST & CLAP test suite
├── test_sonic_intelligence_phase3.py   # Phase 3 hybrid retrieval test suite
└── test_sonic_intelligence_phase3_audit.py # Phase 3 adversarial audit suite (11 tests)
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
8. **Epistemic Honesty & Provenance Transparency (ADR-038 & ADR-039)**:
   All sound metadata presented to AI agents or human directors must declare its exact evidentiary origin. Never present inferred or predicted attributes as physical ground truth. Use explicit epistemic prefixes: `[MEASURED DSP]` for deterministic physical measurements, `[CLASSIFIER INFERENCE]` for AudioSet predictions, `[CLAP SEMANTIC]` for vector cosine distances, and `[CANONICAL METADATA]` for catalog-curated taxonomy.

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

### Sonic Intelligence 4-Phase Ingestion & Enrichment Pipeline
For high-density audio understanding, raw audio passes through the Sonic Intelligence Engine (see [`docs/SOUND_BANK.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/docs/SOUND_BANK.md)):
1. **Phase 1 (Deterministic DSP)**: Computes 14 physical ground-truth metrics (EBU R128 LUFS, True Peak, spectral centroid, brightness, dynamic range) via `DeterministicAudioAnalyzer`.
2. **Phase 2 (AI Enrichment)**: Classifies sound with AudioSet 527 taxonomy via `ASTClassifierAdapter` and encodes 512-dimensional semantic vectors via `CLAPSemanticAdapter`.
3. **Phase 3 (Hybrid Intelligence Retrieval)**: Natural language query planning with Hinglish normalization, 5-generator candidate pooling, linear scoring, and epistemic `AgentSoundCard` v3.0 generation:
   ```bash
   python audiobook_cli.py bank search-intelligence "heavy wooden door creak" --limit 5 --card
   ```

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
| `QueryEmbeddingCache deadlocks during get_or_compute` | Non-reentrant lock acquired during nested cache store calls. | Remediated in ADR-039 by adopting re-entrant `threading.RLock()` across all cache operations. |
| `CUDA Out of Memory during AST/CLAP batch analysis` | Transformers models retaining PyTorch computation graph across batches. | Use `SonicModelManager.unload_models()` to explicitly flush CUDA VRAM or run inference under `torch.inference_mode()`. |
| `RuntimeError: FFmpeg mastering failed: ... filter 'soxr' not found` | FFmpeg was compiled without libsoxr. | Reinstall FFmpeg with `libsoxr` enabled (e.g. `choco install ffmpeg-full` on Windows or `apt install ffmpeg` on Ubuntu). |
| `AllKeysExhaustedTodayError: ... 429 quota reached` | Daily API request or token limits exceeded on Gemini API keys. | The system automatically checkpoints progress to disk. Production can be resumed after daily midnight PT quota reset or by adding additional keys to `.env`. |
| `GateAuditError: Gate 1 Failed: Voice collision detected` | Two characters are assigned the exact same voice and pitch. | Edit `voice_registry.json` or character roster so each active character has a distinct voice persona or pitch offset. |
| `GateAuditError: Gate 3 Failed: Scenes source file missing` | Project uses modern `CreativeManifest` rather than legacy scenes. | Gate 3 has been dynamically hardened in `gate_auditor.py` to audit `CreativeManifest` directly or grant PASS for director-managed workflows. Ensure latest `gate_auditor.py` is in place. |
| `FFmpeg packaging failed: Invalid audio stream copy` | Uncompressed WAV (`pcm_s16le`) was passed to M4B packager with `-c:a copy`. | The packager now automatically validates `is_all_aac` and transcodes non-AAC/WAV stems to AAC 192k with `+faststart`. |
| `HTTP 400 Bad Request on Gemini API Key` | Key in `.env` was enclosed in quotes (e.g. `GEMINI_API_KEY="AIza..."`). | Fixed automatically in `key_manager.py` by `.strip("'\"")`. Remove surrounding quotes if overriding via external environment variables. |

---

## 🧹 Git & Workspace Hygiene Protocol

To maintain repository cleanliness, avoid storage bloat, and protect against committing copyrighted audio literature or intermediate media:
1. **Zero Media in Git**: Never commit audio binary files (`*.wav`, `*.mp3`, `*.m4a`, `*.m4b`, `*.aac`, `*.flac`, `*.ogg`), ebooks (`*.epub`, `*.pdf`, `*.mobi`), or database journal files (`*.db-journal`, `*.db-wal`, `*.db-shm`).
2. **Audiobooks Production Outputs Ignored**: `audiobooks/output/`, `audiobooks/outputs/`, `audiobooks/projects/`, `audiobooks/real_audio_golden/`, `audiobooks/inputs/`, and `audiobooks/cache/` are strictly ignored by `.gitignore`.
3. **Temporary Directories Scrubbed**: `temp_audio/`, `tmp/`, `tmp_test/`, `dummy.wav`, and `standalone_workspace/` are temporary directories and must never be tracked.
4. **Test Fixtures Isolation**: Synthetic test books and audio fixtures belong strictly in `tests/fixtures/` (e.g. `tests/fixtures/dastan_e_hastinapur.txt`). Production test runners fall back transparently to fixtures if user input files are not present.

| `TTS Quota rapidly depleted by background tasks` | Text prompts (mood detection, dramaturgy) were sharing the TTS key pool. | Quota isolation now explicitly routes text prompts through `global_key_pool.get_key(service="text")`, shielding the scarce 10 RPD Gemini TTS quota. |
| `Gemini Flash TTS censorship false-positives on mature literature` | Harm categories triggered safety block. | Fixed permanently in `tts_dispatcher.py` by setting explicit `safetySettings: [BLOCK_NONE]` across all 4 categories (`HARASSMENT`, `HATE_SPEECH`, `SEXUALLY_EXPLICIT`, `DANGEROUS_CONTENT`). |
| `StemLedger reports dmr_compliant: false` | Background stems ($ME$) within 10dB of vocal dialogue ($DX$). | Check `chapter_XXX_manifest.json` ducking parameters or decrease background bed gain to guarantee $DMR \ge 10.0$ dB. |
| `AttributeError: 'dict' object has no attribute 'generate_stochastic_cues'` | Pydantic JSON deserialization parsed `scene_acoustics` as raw dict. | Fixed in `contracts.py` with `@model_validator(mode="after")` on `CreativeManifest` to rehydrate into `SceneSoundscapeManifest`. |
| `GateAuditError: Gate 3.5 Failed: Asset not found for asset with .wav extension` | Cue path had extension but was stored in Sound Bank without full path. | Fixed in `gate_auditor.py` to fall back unconditionally to SQLite FTS5 `bank.resolve_sound()`. |
| `GateAuditError: Gate 4.5 Failed: Missing or empty audio chunks (size <= 1000)` | Silent action beat chunks (<1000B) failed legacy size threshold. | Lowered floor to 44B (WAV header) and exempted `[ACTION]` / `Foley` segments in `gate_auditor.py`. |
| `FFmpeg process crash: Command line too long (Windows 8191 limit)` | Ambient soundscape filter complex exceeded maximum command argument length. | Fixed in `cinema_audio_engine.py` by automatically piping filters > 6000 chars into `-filter_complex_script`. |
| `Multiple take concatenation in chapter audio master` | Segments with multiple takes were all globbed into chapter master. | Fixed in `audiobook_cli.py` (`cmd_master`) by deduplicating segments using regex `_s(\d{4})_` and latest `st_mtime`. |
