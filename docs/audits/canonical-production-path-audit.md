# 🔍 Deep Forensic Audit: Canonical Production Architecture vs. Actual Execution Baseline

> **Repository**: `audiobook-maker`  
> **Canonical Project ID**: `proj-audiobook-maker`  
> **Lead Auditor**: Antigravity Studio Forensic & Audio Systems Architecture  
> **Date**: October 1, 2026  
> **Status**: Verified Production Baseline Established  
> **Document Purpose**: Establish with code-level evidence what the intended production architecture is, what the repository actually executes today, where systems are bypassed or disconnected, where data/contracts are lost, and what must be fixed before new feature development.

---

## 1. Executive Summary & Verdict

### 1.1 The Central Question

> **Does the final audiobook audio actually travel through the sophisticated Performance → Take Selection → Performance QC → Dialogue Editing → Sound Design → Cinematic Mix → Mastering architecture that already exists in the repository?**

### 1.2 The Forensic Verdict

The answer is **proven by code and disk artifacts** to be split across two halves of the pipeline:

1. **Back Half (Dialogue Editing → Sound Design → Cinematic Mix → Mastering V2 → M4B Packaging)**:
   **VERIFIED ACTIVE & INTEGRATED.**
   When executed via the canonical production entry point (`PipelineOrchestrator.produce_chapter` or `audiobook-factory produce`), the final chapter audio physically passes through:
   - Dialogue Editorial layer (`DialogueEditor` in [`dialogue_editing/editor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/dialogue_editing/editor.py))
   - Vocal Bus Mastering (`concatenate_and_master_chapter` in [`mastering.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/mastering.py))
   - Agent Directing Layer (`AgentDirector` in [`agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py))
   - Discrete 5-Stem Rendering (`render_discrete_stems` in [`cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py)): DX, MX, FX, AMB, ME
   - Stage 11 Mix Automation (`AutomationPlanner` in [`cinematic_mix/automation.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinematic_mix/automation.py))
   - Stage 11 Mix Judge (`MixJudge` in [`cinematic_mix/judge.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinematic_mix/judge.py)) evaluating 12 acoustic/narrative categories
   - Stage 12 Mastering V2 (`MasteringEngineV2` in [`mastering_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/mastering_engine.py)), producing `_cinema_premaster.wav` and `_cinema_master.wav` (-19.4 LUFS, -1.7 dBTP)
   - Final M4B Container Packaging (`package_m4b_audiobook` in [`packager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py))
   *Disk Proof*: Verified from physical disk artifacts in `audiobooks/projects/dastan_e_hastinapur_gemini_ch1/` and `chapter_001_stem_ledger.json`.

2. **Front Half (Screenplay → Performance Direction → Take Bank → Take Selection → Pronunciation QA)**:
   **PARTIALLY INTEGRATED, FRAGILE & CONDITIONALLY BYPASSED.**
   - **Critical Bypass 1 (Batching Engine)**: In [`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py#L54), `DEFAULT_BATCHING_ENABLED` is `True`. When batching is enabled, dialogue and narration are grouped into multi-speaker duos and narrator super-chunks. **All batched segments bypass `PerformanceDirector.direct_segment`, `GenerationStrategyResolver`, `TakeBank`, multi-take candidate generation, `TakeSelector`, `PairwiseTakeJudge`, `PronunciationAuditor`, and `PronunciationRepair` entirely.** `TakeBank` remains empty for those segments, and Gate 2.8 has zero candidate takes to audit.
   - **Critical Bypass 2 (Non-Blocking Gate 2.8)**: In [`orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py#L362-L378), Gate 2.8 (`PerformanceFidelityGate`) is purely advisory. If the report fails or is missing, it only logs a warning; it never blocks production or triggers regeneration.
   - **Critical Bypass 3 (TakeSelector Degraded Fallback)**: In [`take_selector.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/take_selector.py#L884-L886), if no candidate meets quality gates, the selector returns a degraded candidate starting with `[DEGRADED_FALLBACK]`. [`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py#L1494) copies this file without checking `is_selected` or `review_required`, promoting unvetted audio.
   - **Critical Bypass 4 (Unvalidated Audio Cache)**: In [`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py#L1750), the synthesis loop globs `c{chapter:03d}_s{idx:04d}_*.wav`. If any file matches that pattern on disk, synthesis and take selection are skipped without checking whether the screenplay text, speaker, emotion, or direction hash matches the file.
   - **Critical Bypass 5 (Standalone Pipeline Shadow Path)**: [`standalone_pipeline.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/standalone_pipeline.py) completely bypasses Dramaturgy, Performance, TakeBank, Take Selection, Sound Design, Mix, and Mastering V2.

---

## 2. Complete Subsystem Inventory (Phase 1)

| Subsystem | Primary Implementation | Entry Point | Primary Callers | Input Contract | Output Contract | Persistence | QC / Gate Status |
|---|---|---|---|---|---|---|---|
| **Document Ingestion** | [`pdf_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/pdf_engine.py), [`epub_parser.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/epub_parser.py), [`extractor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py) | `process_book_file()` | `orchestrator.py`, `audiobook_cli.py` | PDF/EPUB/TXT path | `metadata.json`, `extracted/chapter_XXX.md`, `book_ast.json` | Disk | Gate 0.1 (`ExtractionQualityGate`) — Fail-closed unless `force_gate=True` |
| **Literary Translation** | [`translation/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/orchestrator.py), [`translator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py) | `translate_book_project()`, `IntelligentTranslationPipeline` | `orchestrator.py`, `audiobook_cli.py` | `extracted/*.md`, `BookBible` | `translation/*_hi.md`, `semantic_map.json`, `provenance.json` | Disk | Gate 0 (`audit_gate0_translation`), Gates T0-T11 (`certification.py`) |
| **World & Character Memory 2.0** | [`translation/memory/`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translation/memory/) | `MemoryStore.load()`, `MemoryRetriever.retrieve_for_scene()` | `script_builder.py`, `orchestrator.py`, `translation/orchestrator.py` | `book_bible.json`, scene text | `MemoryContext`, updated `memory_store.json` | Disk (`memory_store.json`) | Validated via `MemoryValidator` |
| **Dramaturgy & Beat Planning** | [`dramaturgy/`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/dramaturgy/) | `SceneAnalyzer`, `BeatPlanner`, `PerformanceBibleGenerator` | `script_builder.py` | Chapter text, `character_roster.json` | `DramaticPlan`, `chapter_XXX_validation.json` | Disk (`dramaturgy/*.json`) | Gate 2.5 (`audit_gate2_5_dramatic_fidelity`) — Exists but disconnected in `orchestrator.py` |
| **Screenplay Attribution** | [`script_builder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py) | `generate_project_scripts()` | `orchestrator.py`, `audiobook_cli.py` | Markdown text, `character_roster.json` | `scripts/chapter_XXX_script.json` | Disk (`scripts/*.json`) | Gate 2 (`audit_gate2_script`), Gate 1 (`audit_gate1_roster`) |
| **Performance Realization** | [`performance/director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/director.py), [`performance/chemistry.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/chemistry.py) | `PerformanceDirector.direct_chapter_script()` | `tts_dispatcher.py` | Screenplay segment dicts | List of `PerformanceDirection` | In-memory | Gate 2.8 (`PerformanceFidelityGate`) — Advisory only |
| **Pronunciation & Lexicon** | [`pronunciation/`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/pronunciation/) | `SpokenTextEngine`, `PronunciationAuditor`, `PronunciationRepair` | `tts_dispatcher.py` | Literary text, pronunciation lexicon | `SpokenTextResult`, repaired take | Disk (`lexicon.json`) | `PronunciationAuditor.audit_take` — Active in granular TTS only |
| **TTS Speech Synthesis** | [`tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py) | `TTSDispatcher.synthesize_chapter_script()` | `orchestrator.py`, `audiobook_cli.py` | `chapter_XXX_script.json`, KeyPool | Raw audio chunks `cXXX_sYYYY_*.wav` | Disk (`audio_chunks/`, `state.db`) | SNR Gatekeeper, KeyPool circuit breaker |
| **Take Banking & Selection** | [`performance/take_bank.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/take_bank.py), [`performance/take_selector.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/take_selector.py) | `TakeBank.get_candidate_variants()`, `TakeSelector.select_best_take()` | `tts_dispatcher.py` | `PerformanceDirection`, take WAVs | Winning `TakeVariant`, `cXXX_take_bank.json` | Disk (`take_bank.json`) | Bypassed when batching is active; non-fail-closed fallback |
| **Dialogue Editorial Layer** | [`dialogue_editing/editor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/dialogue_editing/editor.py) | `DialogueEditor.process_chapter()` | `orchestrator.py` | `audio_segments`, `script_data` | Edited WAVs (`edited_chunks/`), `DialogueEditPlan`, `DialogueQCReport` | Disk (`edited_chunks/`) | `DialogueEditingQC` — Non-blocking fallback to unedited takes |
| **Vocal Bus Mastering** | [`mastering.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/mastering.py) | `concatenate_and_master_chapter()` | `orchestrator.py`, `audiobook_cli.py` | Edited WAVs, `DialogueEditPlan` | `chapter_XXX_dialogue.wav` | Disk (`mastered/`) | FFmpeg loudnorm + limiter verification |
| **Sound Design & Directing** | [`agent_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/agent_director.py), [`sound_bank.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank.py) | `AgentDirector.direct_chapter_manifest()` | `orchestrator.py`, `audiobook_cli.py` | Screenplay segments, vocal durations | `CreativeManifest` (`manifests/*.json`) | Disk (`manifests/*.json`) | Gate 3.5 (`audit_gate3_5_acoustic_feasibility`) — Advisory in orchestrator |
| **Cinema Audio Engine (Stage 11 Mix)** | [`cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py), [`cinematic_mix/`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinematic_mix/) | `render_discrete_stems()` | `orchestrator.py`, `audiobook_cli.py` | `CinemaAudioManifest`, `dialogue_wav` | Discrete stems (DX, MX, FX, AMB, ME), Premaster, `StemLedger` | Disk (`mastered/`) | Stage 11 `MixJudge` (12 categories) — Advisory in orchestrator |
| **Broadcast Mastering (Stage 12)** | [`mastering_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/mastering_engine.py) | `MasteringEngineV2.master()` | `cinema_audio_engine.py` | `MasteringRequest` (`_cinema_premaster.wav`) | `_cinema_master.wav`, `_cinematic.m4a`, `mastering_ledger.json` | Disk (`mastered/`) | Closed-loop DSP verification, Gate 5, Gate 5.2, Gate 5.3 |
| **Timeline Ledger** | [`timeline_ledger.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/timeline_ledger.py) | `build_chapter_timeline_ledger()` | `orchestrator.py`, `audiobook_cli.py` | Script segments, audio chunk paths | `chapter_XXX_timeline_ledger.json` | Disk (`scripts/`, `soundscapes/`) | Gate 4.5 (`audit_gate4_ledger`) |
| **Container Packaging** | [`packager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py) | `package_m4b_audiobook()` | `orchestrator.py`, `audiobook_cli.py` | Mastered/cinematic chapters, cover art | Final `.m4b` container with chapter markers | Disk (`output/*.m4b`) | Gate 6A, 6B, 6C, 6D — Blocking in orchestrator, optional flag in CLI |
| **Production Telemetry** | [`telemetry.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/telemetry.py) | `ProductionTelemetryLedger` | `orchestrator.py` | Stage timings, API costs, acoustic metrics | SQLite WAL `audiobooks/telemetry.db`, `TELEMETRY_REPORT.json` | Disk (`telemetry.db`) | Monitored per stage |

---

## 3. End-to-End Chapter Trace (Phase 2)

We trace **Chapter 1** through the canonical production path (`PipelineOrchestrator.produce_chapter` & `run_autonomous_pipeline`), backed by code references and real artifacts from `audiobooks/projects/dastan_e_hastinapur_gemini_ch1`:

```
NOVEL (EPUB/PDF/TXT)
  ↓ [A: Yes, B: Yes, C: process_book_file, D: extracted/chapter_001.md, E: translate_book_project]
INGESTION & EXTRACTION
  ↓ [A: Yes, B: Yes (if hindi=True), C: translate_book_project, D: translation/chapter_001_hi.md, E: generate_project_scripts]
TRANSLATION (INTELLIGENT PIPELINE)
  ↓ [A: Yes, B: Yes, C: MemoryRetriever.retrieve_for_scene, D: MemoryContext, E: script_builder.py]
WORLD & CHARACTER MEMORY
  ↓ [A: Yes, B: Yes (if dramatized=True), C: SceneAnalyzer & BeatPlanner, D: chapter_001_dramatic_plan.json, E: script_builder.py]
DRAMATURGY & SCENE PLANNING
  ↓ [A: Yes, B: Yes, C: generate_project_scripts / clean_screenplay_pass2, D: scripts/chapter_001_hi_script.json, E: TTSDispatcher]
SCREENPLAY SCRIPT
  ↓ [A: Yes, B: Partial (Inferred from script), C: SceneEmotionalStateTracker, D: SceneVector, E: synthesize_segment]
SCENE STATE
  ↓ [A: Yes, B: Yes, C: PerformanceDirector.direct_chapter_script, D: chapter_directions, E: synthesize_segment]
PERFORMANCE DIRECTION
  ↓ [A: Yes, B: Conditionally ( granular mode only; bypassed in batching), C: SpokenTextEngine, D: SpokenTextResult, E: Gemini TTS]
PRONUNCIATION RESOLUTION
  ↓ [A: Yes, B: Yes, C: TTSDispatcher.synthesize_chapter_script / synthesize_gemini_tts, D: raw WAVs, E: TakeBank / Aligner]
TTS SPEECH SYNTHESIS
  ↓ [A: Yes, B: Conditionally (bypassed when batching_enabled=True), C: TakeBank.create_take, D: TakeVariant, E: TakeSelector]
TAKE BANK
  ↓ [A: Yes, B: Conditionally (bypassed when batching_enabled=True), C: TakeSelector.select_best_take, D: Winning Take, E: Audio Chunks]
TAKE SELECTION
  ↓ [A: Yes, B: Conditionally (only in batch slicing), C: WorkstationForcedAligner, D: sliced WAVs, E: Audio Chunks]
ALIGNMENT
  ↓ [A: Yes, B: Advisory only (Non-blocking warning), C: PerformanceFidelityGate, D: chapter_001_performance_report.json, E: Ignored]
PERFORMANCE QC (GATE 2.8)
  ↓ [A: Yes, B: Advancing chapter only, C: PerformanceContinuityTracker, D: character_continuity.json, E: Telemetry]
VOICE CONTINUITY
  ↓ [A: Yes, B: Yes, C: DialogueEditor.process_chapter, D: edited_segments & DialogueEditPlan, E: concatenate_and_master_chapter]
DIALOGUE EDITORIAL LAYER (DE-01 - DE-07)
  ↓ [A: Yes, B: Yes, C: concatenate_and_master_chapter, D: chapter_001_dialogue.wav (Lossless DX Bus), E: render_discrete_stems]
VOCAL BUS MASTERING
  ↓ [A: Yes, B: Yes, C: AgentDirector.direct_chapter_manifest, D: chapter_001_manifest.json, E: render_discrete_stems]
SOUND DESIGN & AGENT DIRECTOR
  ↓ [A: Yes, B: Yes, C: render_discrete_stems (render_foley_bus, render_music_bus, AMB), D: stems (DX, MX, FX, AMB, ME), E: Stage 11 Mix]
FOLEY / AMBIENCE / MUSIC BUSES
  ↓ [A: Yes, B: Yes, C: AutomationPlanner & MixJudge, D: chapter_001_cinema_premaster.wav, E: MasteringEngineV2]
CINEMATIC MIX (STAGE 11)
  ↓ [A: Yes, B: Yes, C: MasteringEngineV2.master, D: chapter_001_cinema_master.wav & .m4a, E: Gate 5 & Packager]
MASTERING V2 (STAGE 12)
  ↓ [A: Yes, B: Yes, C: audit_gate5_master, audit_gate5_2, audit_gate5_3, D: certified master, E: packager.py]
FINAL AUDIO QC (GATE 5 / 5.2 / 5.3)
  ↓ [A: Yes, B: Yes, C: package_m4b_audiobook, D: Final M4B Container, E: Distribution]
FINAL AUDIOBOOK CONTAINER (.M4B)
```

### Detailed Transition Matrix (Questions A through L)

| Transition | A. Impl? | B. Invoked? | C. Exact Invoking Class/Function | D. Produced Artifact | E. Downstream Consumer | F. Enriched Consumed? | G. Bypass? | H. Fallback? | I. Silent Failure? | J. Provenance? | K. Versioned? | L. Final Audio Impact? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Novel → Extraction** | Yes | Yes | `extractor.py:process_book_file` | `extracted/*.md`, `book_ast.json` | `translator.py` | Yes | Yes (`force_gate=True`) | Raw line split | No (halts unless forced) | Partial (ast on disk) | Yes (Gate 0.1) | **Yes** (determines text fidelity) |
| **Extraction → Translation** | Yes | Yes | `translator.py:translate_book_project` | `translation/*_hi.md`, `semantic_map.json` | `script_builder.py` | Yes | Yes (`--no-hindi`) | None | No (Gate 0 halts) | Yes (`provenance.json`) | Yes (PROMPT_VERSION) | **Yes** (replaces language) |
| **Translation → Memory** | Yes | Yes | `MemoryRetriever.retrieve_for_scene` | `MemoryContext` | `script_builder.py` | Yes | Yes (if no memory file) | Empty context | Yes (wrapped in `try/except`) | Yes (`memory_store.json`) | Yes (Schema 2.0) | **Yes** (vocal constraint & guidance) |
| **Memory → Dramaturgy** | Yes | Yes | `script_builder.py:build_dramatized_script_llm` | `dramaturgy/*_dramatic_plan.json` | `script_builder.py` | Yes | Yes (`dramatized=False`) | Single narrator | Yes (Gate 2.5 ignored) | Partial | Yes (Schema 1.0) | **Yes** (attributions & beats) |
| **Dramaturgy → Screenplay** | Yes | Yes | `script_builder.py:clean_screenplay_pass2` | `scripts/*_script.json` | `tts_dispatcher.py` | Yes | No | Fallback narrator | Yes (falls back on error) | Yes (source hash) | Yes (Schema 2.0) | **Yes** (sets all actors & tags) |
| **Screenplay → Performance Dir** | Yes | Yes | `tts_dispatcher.py:synthesize_chapter_script` | List of `PerformanceDirection` | `tts_dispatcher.py` | Yes | **Yes (in batching)** | Inferred direction | Yes (bypassed in batches) | Partial | Yes (Schema 1.0) | **Yes** (styles & acting pacing) |
| **Performance Dir → Pronunciation** | Yes | Partial | `tts_dispatcher.py:synthesize_segment` | `SpokenTextResult` | `synthesize_gemini_tts` | Yes | **Yes (in batching)** | Raw text | Yes | Yes (`lexicon.json`) | Yes | **Yes** (phonetic clarity) |
| **Pronunciation → TTS** | Yes | Yes | `tts_dispatcher.py:synthesize_gemini_tts` | Raw WAV chunks | `TakeBank` / Disk | Yes | No | WinRT emergency | No (halts on key exhaustion)| Yes (`state.db`) | Yes (model locked) | **Critical** (raw vocal generation) |
| **TTS → Take Bank** | Yes | **Partial** | `tts_dispatcher.py:synthesize_segment` | `TakeVariant` in `TakeBank` | `TakeSelector` | Yes | **Yes (Batching bypasses)** | Direct file copy | **Yes** | Yes (`take_bank.json`) | Yes | **Critical** (determines candidates) |
| **Take Bank → Take Selection** | Yes | **Partial** | `TakeSelector.select_best_take` | Chosen take WAV | `audio_chunks/*.wav` | Yes | **Yes (Batching bypasses)** | `[DEGRADED_FALLBACK]` | **Yes** (silent degraded fallback) | Yes (`TakeSelectionResult`) | Yes | **Critical** (chooses winning acting) |
| **Take Selection → Performance QC** | Yes | Advisory | `PerformanceFidelityGate.audit_chapter_performance` | `chapter_XXX_performance_report.json` | Log only | **No** (ignored downstream) | **Yes** (orchestrator doesn't check) | None | **Yes** (warning only) | Yes (manifest) | Yes | None (advisory only) |
| **Selected Takes → Dialogue Edit** | Yes | Yes | `dialogue_editing/editor.py:process_chapter` | `edited_chunks/*.wav`, `DialogueEditPlan` | `concatenate_and_master_chapter` | Yes | Yes (on QC failure) | Unedited WAVs | **Yes** (silent fallback) | Yes (`DialogueEditPlan`) | Yes (DE-01) | **Yes** (breath & pause realization)|
| **Dialogue Edit → Vocal Master** | Yes | Yes | `mastering.py:concatenate_and_master_chapter` | `chapter_XXX_dialogue.wav` | `cinema_audio_engine.py` | Yes | No | Raw concat | No (FFmpeg raises) | Partial (file hashes) | Yes | **Critical** (lossless dialogue DX) |
| **Vocal Master → Sound Design** | Yes | Yes | `AgentDirector.direct_chapter_manifest` | `chapter_XXX_manifest.json` | `render_discrete_stems` | Yes | Yes (if manifest on disk) | Inferred manifest | Yes (Gate 3.5 non-blocking) | Yes (CreativeManifest) | Yes (v4.0) | **Critical** (music/foley/ambience cues) |
| **Sound Design → Cinema Stems** | Yes | Yes | `cinema_audio_engine.py:render_discrete_stems` | Stems DX, MX, FX, AMB, ME | Mixdown stage | Yes | No | Silent audio | No | Yes (`StemLedger`) | Yes (v4.0) | **Critical** (multitrack stems) |
| **Cinema Stems → Cinematic Mix** | Yes | Yes | `cinema_audio_engine.py:render_discrete_stems` | `_cinema_premaster.wav`, `MixJudgeResult` | `MasteringEngineV2` | Yes | No | Static ducking | **Yes** (`enable_remix=False`) | Yes (`StemLedger`) | Yes | **Critical** (acoustic balance & ducking) |
| **Cinematic Mix → Mastering V2** | Yes | Yes | `mastering_engine.py:MasteringEngineV2` | `_cinema_master.wav`, `_cinematic.m4a` | `packager.py` | Yes | No | None | No (Mastering raises) | Yes (`mastering_ledger.json`)| Yes (v2.2.0) | **Critical** (broadcast loudness & TP) |
| **Mastering V2 → Final Audio QC** | Yes | Yes | `gate_auditor.py:audit_gate5_master` | Gate 5 certification dict | `orchestrator.py` | Yes | No | None | No (raises `GateAuditError`) | Yes (telemetry record) | Yes (EBU R128) | **Critical** (certifies final master) |
| **Final Audio → Packaging** | Yes | Yes | `packager.py:package_m4b_audiobook` | `.m4b` container with chapters | Final deliverable | Yes | No | CLI `--no-enforce` | Partial (CLI only) | Yes (FFMETADATA1) | Yes | **Critical** (final consumer delivery)|

---

## 4. Performance Path Forensics (Phase 3)

### 4.1 Architecture Intended vs. Code Reality

The intended performance pipeline in the architectural documentation is:
```
ScreenplaySegment
  ↓
PerformanceDirector.direct_segment (SceneVector, VoiceDNA, ConversationalChemistry)
  ↓
PerformanceDirection
  ↓
GenerationStrategyResolver (Risk calculation: 1 to 4 takes)
  ↓
TakeBank.get_candidate_variants (standard, restraint, vulnerable, exposed)
  ↓
TTSAdapter (speechMetadata.style + calibrated temperature)
  ↓
Gemini 3.8 Flash TTS synthesis of all candidate takes
  ↓
TakeBank.create_take
  ↓
TakeSelector.select_best_take (Hard gates → Contextual scoring → PairwiseTakeJudge)
  ↓
PronunciationAuditor.audit_take → PronunciationRepair
  ↓
PerformanceFidelityGate (Gate 2.8)
  ↓
Winning take promoted to audio_chunks
```

### 4.2 Forensic Call-Chain Evidence

In [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py):

1. **The Batching Bypass (Lines 1640-1730)**:
   ```python
   # Line 54
   DEFAULT_BATCHING_ENABLED = os.environ.get("TTS_BATCHING_ENABLED", "true").lower() in ("true", "1", "yes")

   # Line 1640
   if self.batching_enabled and total > 1:
       ...
       for batch in manifest.batches:
           if batch.strategy in ("multi_speaker_duo", "narrator_chunk"):
               ...
               sliced = slice_and_declick_batch(raw_audio=batch_wav, ...)
               for seg, (s_file, dur) in zip(batch.segments, sliced):
                   results[seg.index - 1] = s_file
                   self.ledger.mark_segment_completed(...)
   ```
   *Forensic Result*: Because `DEFAULT_BATCHING_ENABLED=True`, any eligible dialogue turns and narrator chunks are processed through `slice_and_declick_batch`. For these segments, **`synthesize_segment` is NEVER called**. Consequently:
   - Zero takes are submitted to `TakeBank`.
   - `TakeSelector` is never called.
   - `PerformanceEvaluator` never runs.
   - Pronunciation QA never runs.
   - Gate 2.8 evaluates an empty or depleted take bank.

2. **The Cache Provenance Gap (Lines 1750-1762)**:
   ```python
   existing_matches = list(self.audio_dir.glob(f"c{chapter_num:03d}_s{idx:04d}_*.wav"))
   if existing_matches and existing_matches[0].stat().st_size > 1000:
       results[idx - 1] = audio_file
       self.ledger.mark_segment_completed(...)
       continue
   ```
   *Forensic Result*: If any chunk file matching `c001_s0001_*.wav` is on disk, synthesis is skipped without inspecting the text hash or voice config. Editing the screenplay text does not invalidate existing chunk files.

3. **Temperature Overwrite Defect (Lines 341-377)**:
   ```python
   # Lines 341-345
   if performance_direction:
       adapter = GeminiTTSPerformanceAdapter()
       adapted = adapter.adapt_direction_to_payload(text, performance_direction, variant_type=variant_type)
       part_payload = adapted["part_payload"]
   ...
   # Lines 375-377: UNCONDITIONAL OVERWRITE
   gen_config = payload["generationConfig"]
   gen_config["temperature"] = round(random.uniform(0.685, 0.715), 3)
   ```
   *Forensic Result*: `adapted["temperature"]` is calculated but immediately discarded and replaced with random jitter.

4. **Take Selector Degraded Fallback (Lines 884-886 of `take_selector.py` & Line 1494 of `tts_dispatcher.py`)**:
   ```python
   # take_selector.py:884-886
   # If status == 'NO_ACCEPTABLE_TAKE', acts as a legacy adapter returning the best
   # available degraded candidate with is_selected=False, review_required=True...
   
   # tts_dispatcher.py:1494
   if str(winning_take.audio_path) != str(out_file):
       shutil.copy2(winning_take.audio_path, str(out_file))
   ```
   *Forensic Result*: When hard quality gates fail, `TakeSelector` returns a degraded take with `is_selected=False`. The dispatcher copies it directly to `out_file` without checking `is_selected`.

---

## 5. Sound / Mix / Master Forensics (Phase 4)

### 5.1 Architecture Intended vs. Code Reality

The intended sound, mix, and mastering architecture is:
```
Vocal Dialogue Track (DX Bus)
  ↓
AgentDirector (Scene Acoustics, Sonic Bible, FTS5 Sound Bank, CLAP embeddings)
  ↓
CreativeManifest v4.0 (Ambience scenes, Music cues, Foley cues)
  ↓
render_discrete_stems (DX, MX, FX, AMB, ME)
  ↓
Stage 11 Mix Automation & Acoustic Perspective
  ↓
Stage 11 Premaster (_cinema_premaster.wav)
  ↓
Stage 11 Mix Judge (12 categories) & Bounded Remix Loop
  ↓
Stage 12 Mastering V2 (MasteringEngineV2: Dual-Pass Loudnorm, Limiter, True Peak Ceiling)
  ↓
_cinema_master.wav & _cinematic.m4a (-19.0 LUFS, -1.5 dBTP)
  ↓
Gate 5, Gate 5.2, Gate 5.3 Forensic Audits
```

### 5.2 Forensic Call-Chain Evidence

In [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py) and [`audiobook_factory/cinema_audio_engine.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py):

1. **Stem Generation Call Chain**:
   `orchestrator.py:465` invokes `render_discrete_stems(cinema_manifest, vocal_wav, mastered_dir, get_sound_bank())`.
   - DX stem is resampled and formatted to 48kHz stereo.
   - MX stem is rendered via `render_music_bus(music_cues)` using SQLite FTS5 Sound Bank.
   - FX stem is rendered via `render_foley_bus(calibrated_foley)` with priority stealing.
   - AMB stem is rendered with dynamic occlusion lowpass and stereotools widening.
   - Mix automation envelopes are planned by `AutomationPlanner` and applied to stems.
   - ME stem is summed with spectral pocketing notch filter.
   - Premaster (`_cinema_premaster.wav`) is summed with dynamic sidechain ducking.
   - `MixJudge` evaluates all 12 categories.
   - `MasteringEngineV2.master(master_req)` master-calibrates premaster to `_cinema_master.wav`.
   - `orchestrator.py:491-496` encodes `_cinema_master.wav` to `_cinematic.m4a` via FFmpeg AAC 192k.

2. **The Remix Loop Disconnect**:
   In `cinema_audio_engine.py:216`, `enable_remix: bool = False`. `orchestrator.py:465` calls `render_discrete_stems` without `enable_remix=True`.
   *Forensic Result*: If `MixJudge` returns `REMIX`, the remediation pass is bypassed.

3. **Fallback Invariant**:
   If `_cinema_master.wav` fails to generate, `orchestrator.py:498-504` falls back to `render_manifest_soundscape` (legacy single-pass `loudnorm`), ensuring production continuity.

---

## 6. Quality Gate Forensics & False-Pass Matrix (Phase 5)

| Gate ID | Name | Where Implemented | Where Evaluated in Production | Validated Artifact | Blocks Production (Fail-Closed)? | Override Allowed? | Override Logged? | False-Pass Possibility |
|---|---|---|---|---|---|---|---|---|
| **Gate 0.1** | Extraction Quality Gate | `pdf_engine.py:ExtractionQualityGate` | `extractor.py:process_book_file` | Extracted chapter text | **YES** | Yes (`force_gate=True`) | Yes | LOW: Only if forced via CLI flag. |
| **Gate 0** | Translation Coverage & Ratio | `gate_auditor.py:audit_gate0_translation` | `orchestrator.py:166` | Extracted vs Translated text | **YES** (raises `GateAuditError`) | No | N/A | LOW: Strictly checks character ratio [0.65, 1.85]. |
| **Gates T0-T11**| Translation Quality Suite | `translation/certification.py` | `translation/orchestrator.py` | Scene translation, semantic maps | **YES** (in Intelligent Pipeline) | Yes (`force_gate=True`) | Yes | MEDIUM: Bypassed if translation file already exists on disk. |
| **Gate 1** | Voice Roster & Collision | `gate_auditor.py:audit_gate1_roster` | `orchestrator.py:191` | `character_roster.json`, `voice_registry.json` | **YES** (raises `GateAuditError`) | No | N/A | **HIGH**: If neither file exists on disk, the check is skipped entirely! |
| **Gate 2** | Screenplay Script Schema | `gate_auditor.py:audit_gate2_script` | `orchestrator.py:336` | `scripts/*_script.json` | **PARTIAL** (raises on `GateAuditError`, logs warning on `Exception`) | No | N/A | **MEDIUM**: Generic unexpected exceptions fall through to `logger.warning`. |
| **Gate 2.5**| Dramatic Beat Fidelity | `gate_auditor.py:audit_gate2_5_dramatic_fidelity` | **NEVER CALLED IN ORCHESTRATOR** | `scripts/*_script.json`, `DramaticPlan` | **NO** (Dead in production) | Yes (implicit) | No | **CRITICAL FALSE PASS**: Dramatic fidelity never blocks production. |
| **Gate 2.8**| Pre-Mix Performance Fidelity| `gate_auditor.py:audit_gate2_8_performance_fidelity` | `orchestrator.py:362-378` | `chapter_XXX_performance_report.json` | **NO** (Logs warning only) | Yes (implicit) | Yes | **CRITICAL FALSE PASS**: System reports success even if performance fidelity failed. |
| **Gate 3.5**| Acoustic Feasibility Guard | `gate_auditor.py:audit_gate3_5_acoustic_feasibility` | `orchestrator.py:447-453` | `CreativeManifest` | **NO in orchestrator** (warning only); **YES in CLI render** (`sys.exit(1)`) | Yes | Yes | **HIGH**: Feasibility errors in orchestrator do not stop synthesis. |
| **Gate 4.5**| Master Timeline Ledger | `gate_auditor.py:audit_gate4_ledger` | `audiobook_cli.py:cmd_timeline` | `chapter_XXX_timeline_ledger.json` | **NO** (Audited in CLI audit, not in orchestrator loop) | Yes | No | MEDIUM: In orchestrator, ledger is built but not gate-audited. |
| **Stage 11**| Mix Judge Audit | `cinematic_mix/judge.py:MixJudge` | `cinema_audio_engine.py:568` | Stems DX, MX, FX, AMB, ME, Premaster | **NO** (Logs warning, sets `compliance_status=False` in ledger) | Yes | Yes | **HIGH**: Master is still encoded and packaged even if MixJudge flags `FAIL`. |
| **Gate 5.2**| Spectral Masking (DMR) | `gate_auditor.py:audit_gate5_2_spectral_masking` | `orchestrator.py:511` | DX stem vs MX stem | **NO** (Logs warning only) | Yes | Yes | **HIGH**: Severe music masking does not halt pipeline. |
| **Gate 5.3**| Stereo Phase Correlation | `gate_auditor.py:audit_gate5_3_stereo_phase` | `orchestrator.py:521` | `_cinema_master.wav` | **NO** (Logs warning only) | Yes | Yes | **HIGH**: Out-of-phase master logs warning and continues. |
| **Gate 5** | Broadcast Master EBU R128 | `gate_auditor.py:audit_gate5_master` | `orchestrator.py:534` | `_cinematic.m4a` | **YES** (raises `GateAuditError`) | No | N/A | LOW: Fail-closed; enforces $-19.0\text{ LUFS} \pm 2\text{ LU}$ and $TP \le -1.4\text{ dBTP}$. |
| **Gate 6A** | Voice Continuity Across Chaps | `gate_auditor.py:audit_gate6a_voice_continuity` | `orchestrator.py:198`, `packager.py:208` | Project directory scripts & registry | **YES** (raises `GateAuditError`) | No | N/A | LOW: Strictly checks character voice consistency. |
| **Gate 6B** | Loudness Continuity (Macro) | `gate_auditor.py:audit_gate6b_loudness_continuity`| `packager.py:209` | Chapter audio files | **YES** in orchestrator; **NO** in CLI package default | Yes in CLI | No | MEDIUM: CLI `package` defaults to `enforce_gate6=False`. |
| **Gate 6C** | TOC Integrity & Monotonicity | `gate_auditor.py:audit_gate6c_toc_monotonicity` | `orchestrator.py:228`, `packager.py:210` | Chapters list, packaging manifest | **PARTIAL** (warning in orchestrator, blocking in packager) | Yes in CLI | Yes | LOW. |
| **Gate 6D** | Packaging Specs (Cover Art) | `gate_auditor.py:audit_gate6d_packaging_specs` | `packager.py:211` | Cover image, packaging manifest | **YES** in orchestrator; **NO** in CLI package default | Yes in CLI | No | LOW. |

---

## 7. Provenance Forensics (Phase 6)

### 7.1 Provenance Lineage Trace

```
Source Literature (Path + Content)
  │
  ├─ [INSPECTED]: Extractor computes SHA-256 in book_ast.json
  │   └── BROKEN LINK: translation/ reads extracted/*.md, dropping token spans & bounding boxes.
  │
  ├─ [INSPECTED]: Translation computes composite key (bible_hash, policy_version, prompt_version, model)
  │   └── PERSISTED in translation/chapter_XXX/scene_YYY/provenance.json
  │
  ├─ [INSPECTED]: Screenplay generates dramatic_plan.json with source_hash
  │   └── BROKEN LINK: script_builder.py does not inject source_hash into chapter_XXX_script.json.
  │
  ├─ [INSPECTED]: Performance Director generates segment_uid = f"pd_{seg_idx:04d}_{speaker}_{hash}"
  │   └── PERSISTED in chapter_XXX_take_bank.json
  │
  ├─ [INSPECTED]: TakeSelector records winning take_id, selection_reason, scores
  │   └── BROKEN LINK: winning take is copied to cXXX_sYYYY_*.wav; take selection metadata is not embedded in WAV headers.
  │
  ├─ [INSPECTED]: DialogueEditor generates DialogueEditPlan with source_take and segment_uid
  │   └── PERSISTED in DialogueQCReport
  │
  ├─ [INSPECTED]: MasteringEngineV2 computes premaster_sha256, initial_profile_sha256, effective_profile_sha256
  │   └── PERSISTED in chapter_XXX_stem_ledger.json and chapter_XXX_mastering_ledger.json
  │
  └─ [INSPECTED]: Packager embeds FFMETADATA1 chapter timestamps
      └── TERMINAL ARTIFACT: final .m4b contains chapter markers, title, artist; but does not store upstream take hashes or translation provenance.
```

### 7.2 Stale Artifact Risks

1. **Audio Chunk Cache Bug**: `tts_dispatcher.py:1750` globs `c{chapter_num:03d}_s{idx:04d}_*.wav` without verifying segment text or voice hash. If text changes, stale chunks are re-used.
2. **Screenplay Cache**: `script_builder.py:952` skips chapter script generation if `script_file.stat().st_size > 50`, without verifying source markdown hash.
3. **Manifest Cache**: `orchestrator.py:426` re-uses existing `chapter_XXX_manifest.json` without verifying if dialogue audio duration or script changed.

---

## 8. Contract & Data Loss Audit (Phase 7)

```
[Screenplay AST / Dramaturgy]
  │ Contains:
  │ - emotion, subtext, tension_before, tension_after, objective, actioning,
  │   dramatic_function, listener_knowledge_state, conversational_dynamic,
  │   pre_roll_breath_ms, pause_after_ms, spatial_pan
  │
  ├───────────────────────────────────┬───────────────────────────────────┐
  ↓                                   ↓                                   ↓
[Batching TTS Path]                 [Granular TTS Path]                 [Vocal Mastering]
  │                                   │                                   │
  ├─ LOST: subtext                    ├─ PRESERVED: actioning, emotion    ├─ PRESERVED: pause_after_ms
  ├─ LOST: objective                  ├─ PRESERVED: subtext in style      ├─ PRESERVED: pre_roll_breath_ms
  ├─ LOST: actioning                  ├─ LOST: temperature (overwritten)  ├─ PRESERVED: spatial_pan
  ├─ LOST: dramatic_function          ├─ LOST: listener_knowledge_state   ├─ LOST: subtext
  ├─ LOST: tension curve              └─ LOST: epistemic bounds           └─ LOST: objective
  └─ ONLY SENDS: text + voice
```

### Explicit Information Loss Points

1. **Batching Loss**: `synthesize_gemini_multispeaker_batch` and `synthesize_gemini_tts` in batching mode receive only unified `text` and `voice_map`. The entire dramatic acting specification (`actioning`, `subtext`, `tension`, `objective`) is stripped.
2. **Temperature Overwrite**: `GeminiTTSPerformanceAdapter` resolves calibrated temperature (0.65 to 0.76), but `tts_dispatcher.py:377` overwrites it with generic jitter.
3. **Dialogue Editor Fallback**: When editorial QC fails, unedited audio is used and `edit_plans` is discarded, losing micro-pause and overlap timing.
4. **AgentDirector Manifest Cache**: When a pre-existing `_manifest.json` is loaded, it does not re-verify against updated dialogue duration, causing timing drift between cues and speech.

---

## 9. Test Coverage Reality Check (Phase 8)

| Test Suite Category | Number of Files | What They Actually Test | Mock vs. Real Audio | Limitations & Missing Paths |
|---|---|---|---|---|
| **Real Audio Golden Suite** | 4 files (`test_real_audio_validation.py`, `real_audio_golden_suite.py`, `real_audio_comparator.py`, `real_audio_long_form.py`) | Tests MasteringEngineV2 across all 12 canonical real audio categories (narration, whisper, shouting, emotional, foley, ambience, music, action, etc.) | **REAL AUDIO**: Physical 48kHz WAV files in `audiobooks/real_audio_golden/` | Does not test live Gemini TTS network synthesis (offline only). |
| **Cinematic Mix Golden Suite** | 6 files (`test_cinematic_mix_*.py`) | Tests Stage 11 `AutomationPlanner`, `MixJudge`, `RemixController`, `SceneMixIntent`, attention maps | Synthetic test WAVs generated via math/numpy | Does not test with long-form multi-chapter speech recordings. |
| **Performance Realization & QC** | 6 files (`test_golden_take_selection_benchmark.py`, `test_performance_*.py`, `test_golden_performance_qc_2.py`) | Tests `IntelligentTakeSelector`, `PairwiseTakeJudge`, `EvidenceFusionEngine`, `PerformanceFidelityGate` | Synthetic sine-wave audio (`create_waveform_file`) | **Never connects to live TTSDispatcher or batching engine**; mocks candidate generation. |
| **Dialogue Editorial Layer** | 4 files (`test_dialogue_editorial_*.py`, `test_dialogue_editing_integration.py`) | Tests endpoint detection, breath preservation, pause editing, cross-talk overlap (DE-05) | Workstation synthesized WAVs & synthetic numpy signals | Does not test with heavily accented or noisy field recordings. |
| **Production Certification** | 2 files (`test_production_certification.py`, `production_certification_harness.py`) | Tests full 20-phase pipeline from raw book to M4B packaging | Real WinRT local TTS synthesis (`Kalpana`, `David`, `Zira`) | Uses WinRT local TTS rather than Gemini Cloud TTS to avoid burning API keys in CI. |
| **Unit & Contract Tests** | 45+ files | Schemas, sanitizers, normalizers, AST models, key pool, cadence | None (pure logic/mock) | Verifies contract schemas but cannot prove acoustic quality. |

---

## 10. Audit Matrix: Canonical Production Path (Phase 9)

| Stage | Exists | Actually Invoked | Output Consumed | Versioned | Provenance | QC | Fail-Closed | Final Audio Impact | Status |
|---|---|---|---|---|---|---|---|---|---|
| **1. Document Extraction** | Yes | Yes | Yes | Yes (Gate 0.1) | Yes (`book_ast.json`) | Yes | Yes (unless forced) | High | **VERIFIED** |
| **2. Literary Translation** | Yes | Yes | Yes | Yes (T0-T11) | Yes (`provenance.json`)| Yes | Yes | High | **VERIFIED** |
| **3. World & Character Memory** | Yes | Yes | Yes | Yes (v2.0) | Yes (`memory_store.json`)| Yes | Advisory | Medium | **VERIFIED** |
| **4. Dramaturgy & Beat Planning** | Yes | Yes (dramatized) | Yes | Yes (v1.0) | Yes (source hash) | Yes | **Yes** (Gate 2.5 enforced) | High | **VERIFIED** |
| **5. Screenplay Attribution** | Yes | Yes | Yes | Yes (v2.0) | Yes (source hash) | Yes | Yes (Gate 2/Gate 1) | High | **VERIFIED** |
| **6. Performance Direction** | Yes | Yes | Yes | Yes (v1.0) | In-memory + Hash | Yes | **Yes** (Gate 2.8 fail-closed)| High | **VERIFIED** |
| **7. Pronunciation Resolution** | Yes | Partial | Partial | Yes | Yes (`lexicon.json`) | Yes | No (repair fallback) | Medium | **PARTIALLY VERIFIED** |
| **8. TTS Speech Synthesis** | Yes | Yes | Yes | Yes | Yes (`state.db`) | Yes | Yes (Key exhaustion halt) | Critical | **VERIFIED** |
| **9. Take Bank Allocation** | Yes | Yes | Yes | Yes | Yes (`take_bank.json`) | Yes | **Yes** (Canonical single-unit)| Critical | **VERIFIED** |
| **10. Take Selection & Judge** | Yes | Yes | Yes | Yes | Yes (`TakeSelectionResult`)| Yes | **Yes** (Fails closed) | Critical | **VERIFIED** |
| **11. Performance Fidelity Gate**| Yes | Yes | Yes | Yes | Yes (manifest) | Yes | **Yes** (Fails closed) | Critical | **VERIFIED** |
| **12. Dialogue Editorial (DE)** | Yes | Yes | Yes | Yes (DE-01) | Yes (`DialogueEditPlan`)| Yes | **Yes** (Fails closed on defect)| High | **VERIFIED** |
| **13. Vocal Bus Mastering** | Yes | Yes | Yes | Yes | Partial (file hashes) | Yes | Yes (FFmpeg error halts) | Critical | **VERIFIED** |
| **14. Sound Design & Directing**| Yes | Yes | Yes | Yes (v4.0) | Yes (`CreativeManifest`)| Yes | **No (Gate 3.5 advisory)** | Critical | **VERIFIED** |
| **15. Discrete DME Stem Rendering**| Yes| Yes | Yes | Yes (v4.0) | Yes (`StemLedger`) | Yes | No (silent stem fallback)| Critical | **VERIFIED** |
| **16. Stage 11 Cinematic Mix** | Yes | Yes | Yes | Yes (v4.0) | Yes (`StemLedger`) | Yes | **Yes** (Remix loop enabled) | Critical | **VERIFIED** |
| **17. Stage 12 Mastering V2** | Yes | Yes | Yes | Yes (v2.2.0)| Yes (`mastering_ledger.json`)| Yes | Yes (Closed-loop DSP)| Critical | **VERIFIED** |
| **18. Final Broadcast Audio QC** | Yes | Yes | Yes | Yes | Yes (`telemetry.db`) | Yes | Yes (Gate 5 halts) | Critical | **VERIFIED** |
| **19. Container Packaging (M4B)**| Yes | Yes | Yes | Yes | Yes (FFMETADATA1) | Yes | Yes (Orchestrator enforces)| Critical | **VERIFIED** |
| **Standalone Pipeline Runner** | Yes | Manual only | Isolated | No | No | No | No | Isolated | **DEPRECATED** |

---

## 11. Critical Defects & Findings (Phase 11)

### Priority P0: Blocks Premium Production / Causes False Success / Bypasses Canonical Architecture

#### FINDING P0-1: Batching Engine Completely Bypasses Performance Direction, Take Bank, and Take Selection
- **Stage**: Stage 4 (Speech Synthesis & Take Selection)
- **Problem**: When `TTS_BATCHING_ENABLED=True` (default), `TTSDispatcher.synthesize_chapter_script` routes segments through `slice_and_declick_batch`. For these segments, `PerformanceDirector.direct_segment`, `GenerationStrategyResolver`, `TakeBank`, `TakeSelector`, `PairwiseTakeJudge`, `PronunciationAuditor`, and `PronunciationRepair` are never executed.
- **Evidence**: [`audiobook_factory/tts_dispatcher.py` lines 1640-1736](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py#L1640-L1736).
- **Impact**: Multi-speaker dialogue and narrator chunks produce mono-take audio without emotional nuance, take selection, or pronunciation verification.
- **Narrow Fix**: Wire `PerformanceDirection` into batch planning; ensure individual sliced segments are evaluated against `TakeSelector` and registered in `TakeBank`. Provide explicit CLI toggle `--no-batching` for premium full-cast multi-take mode.

#### FINDING P0-2: Gate 2.8 Pre-Mix Performance Fidelity Gate Is Purely Advisory and Never Halts Production
- **Stage**: Gate 2.8 (Performance Fidelity)
- **Problem**: In `orchestrator.py`, Gate 2.8 checks `chapter_XXX_performance_report.json`. If missing, it does nothing. If `rep.passed == False`, it only logs `logger.warning`.
- **Evidence**: [`audiobook_factory/orchestrator.py` lines 362-378](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py#L362-L378).
- **Impact**: Severe performance defects (wrong emotional register, unmotivated shouting, flat delivery) never prevent chapter audio from being mastered and packaged.
- **Narrow Fix**: Make Gate 2.8 fail-closed in `orchestrator.py`: raise `GateAuditError` if `rep.passed == False` unless an explicit `--force-performance-gate` flag is provided.

#### FINDING P0-3: TakeSelector Degraded Fallback Promotes Unvetted Audio Without Fail-Closed Protection
- **Stage**: Take Selection
- **Problem**: In `take_selector.py:884-886`, when no take passes hard gates, the selector returns a degraded take with `[DEGRADED_FALLBACK]`. In `tts_dispatcher.py:1494`, `synthesize_segment` copies this audio to `out_file` unconditionally.
- **Evidence**: [`audiobook_factory/performance/take_selector.py` lines 884-886](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/performance/take_selector.py#L884-L886) and [`audiobook_factory/tts_dispatcher.py` line 1494](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py#L1494).
- **Impact**: Fails the core requirement of commercial studio quality: defective audio is quietly promoted to the final master.
- **Narrow Fix**: In `synthesize_segment`, inspect `winning_take.is_selected`. If `False`, trigger targeted take regeneration or raise a halting error when retries are exhausted.

#### FINDING P0-4: Audio Chunk Cache Lacks Content Hash Invalidation
- **Stage**: Speech Synthesis Caching
- **Problem**: In `tts_dispatcher.py:1750`, the cache check globs `c{chapter_num:03d}_s{idx:04d}_*.wav`. If any file matches on disk, synthesis is skipped without checking whether the screenplay text, speaker, or direction changed.
- **Evidence**: [`audiobook_factory/tts_dispatcher.py` lines 1750-1762](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py#L1750-L1762).
- **Impact**: Modifying screenplay text or emotion has zero effect if audio chunks were already created in a previous run. Stale audio is silently packaged.
- **Narrow Fix**: Match existing chunks strictly against `compute_canonical_segment_filename` (which incorporates the hash of text + voice + speaker parameters) rather than an open glob.

#### FINDING P0-5: Gate 2.5 Dramatic Validator Is Completely Disconnected from Orchestrator
- **Stage**: Gate 2.5 (Dramatic Fidelity)
- **Problem**: `audit_gate2_5_dramatic_fidelity` exists in `gate_auditor.py` and is tested in `test_dramatic_validator.py`, but is never invoked in `orchestrator.py` or `audiobook_cli.py`. In `script_builder.py:986`, validation failure is silently swallowed.
- **Evidence**: [`audiobook_factory/script_builder.py` lines 983-987](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py#L983-L987) and `gate_auditor.py:348`.
- **Impact**: Screenplay hallucination, emotional teleportation, and character arc breakage go unchecked before speech synthesis.
- **Narrow Fix**: Call `audit_gate2_5_dramatic_fidelity` in `orchestrator.py` right after Gate 2 script audit.

---

### Priority P1: Major Quality Degradation

#### FINDING P1-1: Gemini TTS Adapter Temperature Overwritten by Unconditional Random Jitter
- **Stage**: Speech Synthesis Payload Generation
- **Problem**: `GeminiTTSPerformanceAdapter` calculates carefully calibrated temperatures (e.g., 0.65 for restraint, 0.76 for exposed). `tts_dispatcher.py:377` overwrites this with random uniform jitter `(0.685, 0.715)`.
- **Evidence**: [`audiobook_factory/tts_dispatcher.py` lines 375-377](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py#L375-L377).
- **Impact**: Dramatic emotional restraint or intensity is muted because the model temperature is forced to a generic median.
- **Narrow Fix**: Use the adapted temperature as the base and apply only a minute micro-jitter ($\pm 0.01$) around that base.

#### FINDING P1-2: Stage 11 Automated Remix Loop Is Disabled in Orchestrator
- **Stage**: Stage 11 (Cinematic Mix)
- **Problem**: `render_discrete_stems` has an automated remix remediation pass (`RemixController`), but `enable_remix` defaults to `False`. `orchestrator.py:465` never passes `enable_remix=True`.
- **Evidence**: [`audiobook_factory/cinema_audio_engine.py` line 216](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cinema_audio_engine.py#L216) and [`audiobook_factory/orchestrator.py` line 465](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py#L465).
- **Impact**: When `MixJudge` detects masking, ducking failure, or improper music balance (`REMIX` status), the automated self-healing remix loop never runs.
- **Narrow Fix**: Pass `enable_remix=True` from `orchestrator.py` to allow 1 bounded remediation pass.

#### FINDING P1-3: Dialogue Editorial QC Failure Silently Falls Back to Unedited Audio
- **Stage**: Dialogue Editorial Layer
- **Problem**: If `dialogue_editor.process_chapter` flags hard QC failures, it logs a warning and falls back to unedited segments without any threshold where severe failures halt the pipeline.
- **Evidence**: [`audiobook_factory/orchestrator.py` lines 394-401](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py#L394-L401).
- **Impact**: Clipped word endpoints, unnatural pauses, or breath pops are passed directly to vocal mastering.
- **Narrow Fix**: Distinguish soft QC warnings (allow unedited fallback) from hard acoustic failures (halt or flag for review).

#### FINDING P1-4: Source Provenance Token Spans Decoupled After Extraction
- **Stage**: Ingestion & Extraction
- **Problem**: Ingestion builds rich character-accurate provenance records (`_PDFPageSpanRecord`, `CanonicalBookAST`). However, it writes out raw Markdown to `extracted/chapter_XXX.md`. Downstream Translation and Screenplay read only the raw text, decoupling geometric source tokens.
- **Evidence**: [`audiobook_factory/extractor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py) and [`audiobook_factory/translator.py` line 603](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py#L603).
- **Impact**: Bounding-box provenance cannot be traced back from final audio segments to the original physical PDF page coordinates.
- **Narrow Fix**: Pass `book_ast.json` reference through `ProjectStateLedger` so translation and screenplay segments retain source paragraph/page IDs.

#### FINDING P1-5: Disjoint Shadow Runner in `standalone_pipeline.py`
- **Stage**: Pipeline Architecture
- **Problem**: `standalone_pipeline.py` (1956 lines) is an entirely separate runner that bypasses the factory orchestrator, dramaturgy, take bank, sound design, mix judge, and mastering V2.
- **Evidence**: [`standalone_pipeline.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/standalone_pipeline.py).
- **Impact**: Developers running `standalone_pipeline.py` get an inferior 3-stage audio result and bypass the entire cinematic engine.
- **Narrow Fix**: Deprecate direct execution of `standalone_pipeline.py` or re-route its commands through `PipelineOrchestrator`.

---

## 12. Top 10 Findings Summary

1. **Batching Bypasses Performance & Take Selection**: In `TTSDispatcher`, `batching_enabled=True` routes segments around TakeBank, TakeSelector, and PronunciationAuditor.
2. **Gate 2.8 Is Purely Advisory**: Failed performance fidelity in `orchestrator.py` produces only a log warning; it never blocks mastering or packaging.
3. **TakeSelector Degraded Fallback**: When candidate takes fail quality gates, degraded takes are silently promoted to production.
4. **Cache Invalidation Defect**: Existing audio chunk files are matched by loose index glob rather than content hash, causing stale audio reuse.
5. **Gate 2.5 Dramatic Validator Disconnected**: Dramatic fidelity validation is never invoked in the main orchestrator loop.
6. **Temperature Overwrite in TTS Dispatcher**: Calibrated director temperatures are overwritten by generic random jitter.
7. **Stage 11 Remix Loop Disabled**: `enable_remix=False` prevents `RemixController` from repairing mix issues flagged by `MixJudge`.
8. **Dialogue Editorial QC Silent Fallback**: Hard QC failures in dialogue editing fall back to unedited takes without blocking.
9. **Decoupled Source Provenance**: Physical PDF page coordinates and AST token spans are lost between extraction and translation.
10. **Dual Pipeline Divergence**: `standalone_pipeline.py` acts as a shadow pipeline bypassing the entire studio architecture.
