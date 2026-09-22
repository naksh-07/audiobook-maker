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

The codebase maintains **203 passing unit tests** across all modules with a zero-regression invariant.

### Running Dedicated Phase Test Suites
```powershell
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
