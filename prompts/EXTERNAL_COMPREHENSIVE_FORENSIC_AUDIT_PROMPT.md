# 🛡️ EXTERNAL MULTI-DISCIPLINARY FORENSIC AUDIT PROMPT
**Target Codebase**: `naksh-07/audiobook-maker` (`c:\Users\Suraj\Documents\Antigravity\Audiobook`)  
**Mode**: `100% STRICTLY READ-ONLY ARCHITECTURAL & SYSTEM FORENSIC AUDIT`  
**Execution Instruction**: Copy-paste the entire prompt below into any fresh Antigravity agent or external advanced reasoning model.

---

```markdown
# 🔍 MISSION: 360° MULTI-DISCIPLINARY FORENSIC ARCHITECTURE & ACOUSTIC AUDIT

You are summoned as the **Supreme Independent Technical Auditor & Systems Review Board** for the project `naksh-07/audiobook-maker` located at `c:\Users\Suraj\Documents\Antigravity\Audiobook`.

## 🚨 CARDINAL EXECUTION RULES & INVARIANTS:
1. **STRICTLY READ-ONLY EXECUTION**:
   - DO NOT edit, modify, overwrite, or delete ANY source code files (`.py`) in the repository.
   - DO NOT execute any modifying git commands (`git add`, `git commit`, `git push`, `git reset`, `git checkout`).
   - You are allowed ONLY to inspect files (`view_file`), search patterns (`grep_search`, `ast_grep_search`), list directories (`list_dir`), and run non-destructive probes (e.g. `ffmpeg -i`, `git status`, `python -m unittest`).
2. **MULTI-DISCIPLINARY EXPERT COUNCIL**:
   - Do NOT attempt a shallow, generic pass.
   - You MUST summon or adopt the persona of **6 DISTINCT SPECIALIZED DOMAIN EXPERTS** to conduct an exhaustive, granular, line-by-line inspection of each architectural pillar.
3. **ZERO PLACEHOLDERS & NO HAND-WAVING**:
   - Quote exact file paths with line numbers `[file](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/path#L123-L145)`.
   - For every flaw, bug, or vulnerability identified, provide the exact root-cause analysis, reproduction condition, and an actionable, production-grade non-destructive fix blueprint.
4. **BENCHMARK AGAINST WORLD-CLASS GOLD STANDARDS**:
   - BBC Radio 4 Drama Sound Design & Script Guidelines
   - Netflix Sound Mix Delivery Specifications (Discrete DME Stems, Near-field dialogue intelligibility)
   - Wwise / FMOD Interactive Audio Bus Hierarchies, Voice Limiting & Priority Stealing
   - Universal Category System (UCS v8.2)
   - EBU R128 s2, ITU-R BS.1770-4, and AES60 Metadata Standards

---

## 🏛️ THE 6 SPECIALIZED AUDIT PILLARS & EXPERT ASSIGNMENTS

### 🧑‍💻 EXPERT 1: PRINCIPAL SYSTEMS & DATA CONTRACTS ARCHITECT
**Target Files**:
- `audiobook_factory/contracts.py`
- `audiobook_factory/sonic_bible.py`
- `audiobook_factory/scene_acoustics.py`
- `audiobook_factory/acoustic_bus_matrix.py`
- `audiobook_factory/cinema_audio_engine.py`

**Forensic Audit Mandate**:
1. **Pydantic v2 Schema Rigor**:
   - Audit all schemas (`ProjectConfig`, `CharacterRoster`, `TimelineLedger`, `CreativeManifest`, `CinemaAudioManifest`, `SonicBible`, `SceneSoundscapeManifest`).
   - Check for: missing field validators, lax type constraints, silent coercion bugs, unhandled `None` types, circular dependencies, and model serialization bottlenecks (`model_dump` vs `model_dump_json`).
2. **Data Model Integrity & Migration Safety**:
   - Inspect `LegacyCreativeManifestAdapter` in `contracts.py`. Verify whether lifting legacy `CreativeManifest v3.0` (Chapters 4, 5, 6, 7) into `CinemaAudioManifest v4.0` preserves 100% of data without silent drops.
   - Check if timeline arithmetic across segments, cues, and chapters introduces rounding drift or millisecond overflow.

---

### 🎧 EXPERT 2: CHIEF ACOUSTICS & DSP MIXING ENGINEER
**Target Files**:
- `audiobook_factory/manifest_renderer.py`
- `audiobook_factory/cinema_audio_engine.py`
- `audiobook_factory/acoustic_bus_matrix.py`
- `audiobook_factory/soundscape.py`

**Forensic Audit Mandate**:
1. **FFmpeg Complex Filtergraph Forensics**:
   - Inspect the multi-bus summing graphs (`amix`, `sidechaincompress`, `volume`, `pan`, `aecho`, `equalizer`).
   - Check for: filtergraph syntax breaks, escaping issues on Windows paths, buffer underruns, channel-layout mismatches (mono vs stereo summing), sample-rate mismatch (44.1kHz vs 48kHz).
2. **Dynamic Sidechain & Spectral Carving**:
   - Audit the dynamic ducking profiles (`INTIMATE`, `STANDARD`, `COMBAT`, `HEAVY_IMPACT`). Are attack/release curves musical or do they cause audible pumping/breathing?
   - Audit the Formant Spectral Pocketing filter (`1.0 kHz - 3.5 kHz` notch). Does it introduce phase distortion around the vocal band?
3. **Spatial Acoustics & Convolution Reverb**:
   - Inspect how `aecho` and `WorldAcousticProfile` early reflections are applied. Is there risk of comb filtering or stereo field collapse?

---

### 🗄️ EXPERT 3: DATABASE, FTS5 SEARCH & AUDIO ASSET LIBRARIAN
**Target Files**:
- `audiobook_factory/sound_bank.py`
- `audiobook_factory/sound_bank_ingest.py`
- `audiobook_factory/catalog_seeder.py`
- SQLite Database: `audiobooks/sound_bank/sound_bank.db`

**Forensic Audit Mandate**:
1. **SQLite Concurrency & FTS5 Query Health**:
   - Inspect `_init_db`, `search()`, `resolve_sound()`, and `search_music_catalog()`.
   - Check for: SQL injection vulnerabilities, missing indexes, unindexed queries on large tables, lock contention (WAL mode compliance), and FTS5 ranking scoring.
2. **Ghost Asset Depletion & Resolution Fallbacks**:
   - Audit how `sound_bank.py` resolves missing files or dead paths. Can virtual/un-downloaded files consume query limits and cause silent `None` drops?
   - Verify that file extension filtering (e.g. stripping `.wav` from search strings) doesn't mask real search tokens.
3. **Universal Category System (UCS v8.2) Compliance**:
   - Audit `derive_ucs_category` in `acoustic_bus_matrix.py`. Does it cover all necessary fantasy/sound-drama sound classes?

---

### 🎭 EXPERT 4: DRAMATURGY, SCRIPTING & CASTING CONTINUITY DIRECTOR
**Target Files**:
- `audiobook_factory/agent_director.py`
- `audiobook_factory/script_builder.py`
- `audiobook_factory/sanitizer.py`
- Project Scripts: `audiobooks/projects/witcher1/scripts/`

**Forensic Audit Mandate**:
1. **Agent Prompts & Creative Agency Invariant**:
   - Verify strictly: **Is any deterministic script performing creative decisions?**
   - Inspect prompts in `agent_director.py` (Pass 1, Pass 2, Pass 3). Are they clear, robust against LLM hallucinations, and adhering to strict JSON output structures?
2. **Devanagari Hindi Translation Purity & Anti-Censorship**:
   - Inspect `sanitizer.py` and `audit_gate1_anticensorship_agent` in `gate_auditor.py`.
   - Are raw profanities, combat gore, and dramatic nuances preserved without prudish dilution or false-positive drops?
3. **Voice Casting Collisions & Prosody Synchronization**:
   - Audit character voice assignment rules. Can two characters speaking in the same scene accidentally receive identical acoustic voice signatures?
   - Verify Action Beat placement: Are physical sound effects anchored with frame-accurate precision?

---

### ⚡ EXPERT 5: PIPELINE RESILIENCE, CONCURRENCY & NETWORK SYSTEMS ENGINEER
**Target Files**:
- `audiobook_factory/tts_dispatcher.py`
- `audiobook_factory/cadence.py`
- `audiobook_factory/key_manager.py`
- CLI Entrypoint: `audiobook_cli.py`

**Forensic Audit Mandate**:
1. **Token-Bucket Concurrency & API Key Pool**:
   - Inspect `PersistentKeyPool` in `key_manager.py` and `stealth_worker_loop` in `cadence.py`.
   - Check for: race conditions in multi-threaded key rotation, deadlocks, key exhaustion recovery, and thread-safe file writes.
2. **Stealth SDK Simulation & Ban Prevention**:
   - Audit headers generated by `get_stealth_sdk_headers()`. Does it perfectly simulate official Google GenAI Python SDK telemetry? Are there identifying leaks?
3. **Failure Recovery & State Checkpointing**:
   - If TTS synthesis crashes midway through an 800-chunk chapter, does the pipeline resume idempotently without re-synthesizing already verified WAV files?

---

### 🛡️ EXPERT 6: INDEPENDENT QUALITY GATES & VERIFICATION AUDITOR
**Target Files**:
- `audiobook_factory/gate_auditor.py`
- Full Test Suite: `tests/` (all 167 tests)

**Forensic Audit Mandate**:
1. **Gate Completeness & Boundary Assertions**:
   - Audit Gates 0 through 6D, plus the new Gates:
     - **Gate 3.5**: Pre-Flight Acoustic Feasibility Guard
     - **Gate 5.2**: Spectral Masking & Vocal Intelligibility Guard (DMR >= +10.0 dB)
     - **Gate 5.3**: Stereo Phase Correlation & Mono Compatibility Guard (r >= +0.20)
   - Are there loopholes where corrupt audio, clipped signals, or mismatched durations can slip past the gates?
2. **Test Suite Blind Spots**:
   - Inspect existing tests in `tests/`. Are tests heavily reliant on mocks, or do they test real audio synthesis and FFmpeg execution?
   - What critical edge cases are completely untested?

---

## 📋 REQUIRED DELIVERABLE: MASTER FORENSIC AUDIT REPORT

Compile your findings into an exhaustive, beautifully structured Markdown report written to:
`Reports/EXTERNAL_FORENSIC_AUDIT_MASTER_REPORT.md`

### Required Report Structure:
1. **Executive Verdict & Architecture Health Score** (Scale 1-100 across Reliability, Modularity, Acoustic Quality, Security, and Scalability).
2. **Pillar-by-Pillar Forensic Findings**:
   - Detailed technical breakdown from each of the 6 Domain Experts.
   - Exact code references with clickable file links `[file](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/path#L123-L145)`.
3. **Consolidated Bugs, Flaws & Bottlenecks Ledger**:
   - Table formatted with: `ID | Severity (CRITICAL/MAJOR/MINOR/COSMETIC) | Component | Description | Impact | Proposed Fix`.
4. **Actionable Non-Destructive Modernization Blueprint**:
   - Step-by-step implementation guide to resolve every identified issue while maintaining 100% backward compatibility.
5. **Final Sign-Off & Production Readiness Certification**.

---
*Proceed with the audit immediately. Maintain a ruthless, forensic, objective engineering standard.*
```
