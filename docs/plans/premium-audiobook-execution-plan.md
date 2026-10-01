# Premium Audiobook Execution Plan: Non-Destructive Remediation & Hardening

**Document Version**: 1.0  
**Target Repository**: `naksh-07/audiobook-maker` (`proj-audiobook-maker`)  
**Objective**: Harden, wire, and enforce fail-closed quality gates across the existing 18-stage production engine without rebuilding or replacing existing architectures.

---

## 1. Principles of Execution

1. **Zero Architectural Rewrites**: The existing architecture is sophisticated, modular, and DSP/Acoustically sound. Over 90% of the required system already exists in code.
2. **Non-Destructive Surgical Wiring**: Fix broken glue code, eliminate silent exceptions, and connect isolated components without altering their internal contracts.
3. **Fail-Closed by Default**: Production MUST halt on quality gate violations, missing audio assets, or failed take evaluations unless an explicit, authenticated override is provided.
4. **Cache Cryptographic Integrity**: Audio chunks must never be re-used purely by index; cache keys must include SHA-256 hashes of text, speaker, and performance parameters.

---

## 2. Systems That MUST NOT Be Rebuilt

The forensic audit confirms that the following systems are fully functional, verified on disk, or architecturally mature. **Do NOT rebuild or replace them**:

1. **`audiobook_factory/cinema_audio_engine.py` & `cinematic_mix/`**:
   - 5-track bus matrix (`DX`, `FX`, `MX`, `AMB`, `ME`).
   - Dynamic sidechain ducking (-16dB ducking, -5.5dB spectral carve @ 2.2kHz).
   - `MixJudge` perceptual and spectral verification.
2. **`audiobook_factory/mastering_engine.py` (`MasteringEngineV2`) & `mastering_analyzer.py`**:
   - Broadcast EBU R128 dual-pass linear loudnorm (`-19.4 LUFS`).
   - True-peak lookahead limiter (`-1.7 dBTP`).
   - Dialogue protection ratio & spectral tilt verification.
3. **`audiobook_factory/performance/take_bank.py`, `take_selector.py`, and `evaluator.py`**:
   - Multi-take evaluation, evidence fusion, pairwise arbitration, and SSIM/spectral scoring.
4. **`audiobook_factory/dialogue_editing/` (`DialogueEditor`, `EndpointEditor`, `BreathEditor`, `PauseEditor`)**:
   - Hann 12ms/18ms micro-fades, de-clicking, room-tone insertion, breath shaping.
5. **`audiobook_factory/sound_bank.py` & `sonic_intelligence_engine.py`**:
   - SQLite FTS5 semantic cue matching, CLAP vector similarity, multi-tier SFX caching.
6. **`audiobook_factory/translation/orchestrator.py` & `translation/memory/store.py`**:
   - 5-stage Hindustani literary translation pipeline, term glossary, persistent SQLite entity store.
7. **`audiobook_factory/pdf_engine.py`**:
   - Geometric XY-cut layout reconstructor, character-accurate bounding box extraction, Gate 0.1 analyzer.

---

## 3. Phased Implementation Roadmap

### Phase 1: Hardening & Fail-Closed Enforcement (P0 Defects)
**Goal**: Prevent degraded audio, broken takes, and silent failures from escaping into the vocal master.

- **Task 1.1: Enforce Fail-Closed Take Selection**:
  - File: [`audiobook_factory/performance/take_selector.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/take_selector.py) & [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py)
  - Action: Modify `take_selector.py` to raise `TakeSelectionFailedException` or set `is_selected=False` when all takes fail perceptual criteria. In `tts_dispatcher.py` (L1494), verify `winning_take.is_selected is True` before copying `audio_path` to production output.
- **Task 1.2: Enforce Gate 2.8 Pre-Mix Performance Fidelity Gate**:
  - File: [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py) (L362–L378)
  - Action: Convert Gate 2.8 from advisory warning to fail-closed gate. If `chapter_XXX_performance_report.json` indicates composite score $< 0.70$ or critical take failure, abort chapter compilation with a descriptive error.
- **Task 1.3: Connect Gate 2.5 Dramatic Intent Validator**:
  - File: [`audiobook_factory/script_builder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py) (L986) & [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py)
  - Action: Remove `except Exception: pass` swallowing in `script_builder.py`. Wire `audit_gate2_5_dramatic_fidelity` into `orchestrator.py:run_screenplay` to ensure dramatic beat alignment is validated prior to TTS dispatch.

---

### Phase 2: Performance Direction & Batching Resolution (P0 & P1 Defects)
**Goal**: Ensure all voiced dialogue and dramatic narrative pass through calibrated performance direction.

- **Task 2.1: Granular Batching Routing**:
  - File: [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py) (L1640)
  - Action: Update `DEFAULT_BATCHING_ENABLED` logic so that batching is strictly restricted to neutral narrator paragraphs. High-tension narration and all character dialogues MUST route through `PerformanceDirector`, `TakeBank`, and `TakeSelector`.
- **Task 2.2: Restore Calibrated Temperature & Pitch Controls**:
  - File: [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py) (L377)
  - Action: Stop overwriting `target_temp` with uniform random jitter `(0.685, 0.715)`. Use the calibrated temperature computed by `GeminiTTSPerformanceAdapter` based on emotion, subtext, and scene tension.
- **Task 2.3: Enforce Dialogue Editorial QC Threshold**:
  - File: [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py) (L394–L401)
  - Action: When `DialogueEditingQC` detects severe clipping or endpoint cutoff, halt and re-run editing with adjusted padding rather than silently falling back to unedited audio.

---

### Phase 3: Cache Invalidation & Lineage Integrity (P0 & P1 Defects)
**Goal**: Eliminate stale audio re-use and preserve forensic source-to-audio lineage.

- **Task 3.1: Cryptographic Chunk Caching**:
  - File: [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py) (L1750)
  - Action: Replace index-only glob matching with SHA-256 fingerprinting: `hash(text + voice_id + temperature + prompt_version + performance_params)`. Only reuse audio if the cache key matches the content hash.
- **Task 3.2: Preserve Source Provenance Across Extraction**:
  - File: [`audiobook_factory/extractor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py) & [`audiobook_factory/script_builder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py)
  - Action: Persist `_PDFPageSpanRecord` metadata alongside extracted markdown sections so that screenplay chunks retain character-accurate physical bounding boxes and page numbers.

---

### Phase 4: Cinematic Mix Automation & Legacy Isolation (P1 & P2 Defects)
**Goal**: Enable dynamic remixing loops and isolate legacy runner scripts.

- **Task 4.1: Enable Stage 11 Automated Remix Loop**:
  - File: [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py) & [`audiobook_factory/cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py)
  - Action: Pass `enable_remix=True` into `CinemaAudioEngine.mix_chapter()`. Allow `RemixController` to execute up to 3 iterative mix adjustments when `MixJudge` detects masking or dialogue clash.
- **Task 4.2: Deprecate `standalone_pipeline.py`**:
  - File: [`standalone_pipeline.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/standalone_pipeline.py)
  - Action: Add clear deprecation warnings and redirect production invocations to `ProductionOrchestrator.produce_chapter()`. Prevent accidental execution of the unmastered, bypassed runner.

---

## 4. Verification & Benchmarking Strategy

Every phase must be verified with concrete objective metrics and subjective golden-audio listening checks:

| Milestone | Verification Type | Target Standard / Metric | Command / Test Harness |
|---|---|---|---|
| **Gate 2.8 Hardening** | Unit & Contract | Ingestion of failing take report raises `QualityGateError` | `pytest tests/test_performance_gate.py` |
| **Cache Invalidation** | Integration | Text modification forces take re-generation; identical text hits cache | `pytest tests/test_cache_invalidation.py` |
| **Dialogue Editing** | Golden Audio | Hann fades (12ms/18ms) zero-crossing check; 0 DC offset | `pytest tests/test_dialogue_editing_qc.py` |
| **Mix & Ducking** | Perceptual & EBU R128 | Dialogue protection $\ge 14\text{ dB}$, sidechain ducking $\ge -14\text{ dB}$ | `pytest tests/test_cinema_mix_ducking.py` |
| **Mastering V2** | Broadcast Certification | Integrated Loudness: $-19.0 \pm 0.5\text{ LUFS}$, True Peak: $\le -1.5\text{ dBTP}$ | `pytest tests/test_mastering_v2_certification.py` |
| **End-to-End Chapter** | Full Production Smoke | Chapter 1 full run generating `.m4b` container with all 5 stems | `python -m audiobook_factory.cli produce --chapter 1 --dry-run` |

---

## 5. Implementation Sequence & Order of Execution

```
[Phase 1: Fail-Closed Gates]
   ├── 1.1: TakeSelector fail-closed enforcement
   ├── 1.2: Gate 2.8 Pre-mix performance gate halt
   └── 1.3: Gate 2.5 Dramatic validator wiring
        │
        ▼
[Phase 2: Performance Routing & Calibration]
   ├── 2.1: Restrict batching to neutral narration
   ├── 2.2: Restore calibrated TTS temperature
   └── 2.3: Dialogue editorial QC threshold enforcement
        │
        ▼
[Phase 3: Caching & Provenance Integrity]
   ├── 3.1: SHA-256 chunk cache keying
   └── 3.2: PDF page span record persistence
        │
        ▼
[Phase 4: Cinematic Mix & System Deprecation]
   ├── 4.1: Enable Stage 11 automated remix loop
   └── 4.2: Deprecate standalone_pipeline.py
        │
        ▼
[Phase 5: Golden Audio Chapter 1 Verification]
```
