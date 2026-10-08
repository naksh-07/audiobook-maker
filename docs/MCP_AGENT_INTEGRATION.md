# 🤖 AI Agent & MCP Integration Guide

**Standard**: `v6.0-ENTERPRISE-DAG` & `v6.0-STUDIO-UI`  
**Host Platform**: Google Antigravity IDE & MCP Tool Ecosystem  
**Classification**: Autonomous Agent Orchestration & Tool Protocols  

---

## 📖 Overview

**Audiobook Studio** is designed as a first-class citizen of the **Google Antigravity** ecosystem. AI agents (such as `@audiobook-director`, Claude, Gemini, and Cursor) can programmatically orchestrate the entire 5-room audio pipeline, inspect SQLite persistence ledgers, perform surgical single-beat edits, and verify acoustic telemetry with mathematical predictability.

---

## 🛠️ Specialized Antigravity Agent Skills

The plugin registers three specialized skills in `skills/`:

```text
skills/
├── audiobook-studio/           # Director controls, project status, zero-CLI programmatic API
├── audio-engineer-ffmpeg/      # Studio vocal DSP, 4D formants, EBU R128 mastering curves
└── novel-audiobook-factory/    # Autonomous novel ingestion, translation, and M4B packaging
```

### 1. `audiobook-studio`
- **Scope**: Studio director commands, TakeBank inspection, and SQLite ledger querying.
- **Trigger**: Activates on conversational requests: *"Show active audiobook projects"*, *"Check KeyPool health"*, *"Audition line with Puck voice"*.

### 2. `novel-audiobook-factory`
- **Scope**: Autonomous 5-room production pipeline for books and manuscripts.
- **Workflow**: Coordinates Room 1 (Forensic Ingestion), Room 2 (Translation Collective), Room 3 (Screenplay & Anti-Swap), Room 4 (TakeBank TTS), and Room 5 (Broadcast Mastering).

### 3. `audio-engineer-ffmpeg`
- **Scope**: Studio vocal DSP, 4D acoustic formants, and broadcast loudness mastering.
- **Capabilities**:
  - Calculates 4D acoustic formant parameters (pitch $\pm 4-12\%$, tempo $0.85-1.15\times$, parametric EQ profiles).
  - Configures DE-01 through DE-07 Hann micro-fades (12ms/18ms) and dynamic pause realization.
  - Masters audio to EBU R128 (-19.0 LUFS integrated, $\le -1.5\text{ dBTP}$ True Peak).

---

## 💬 The `@audiobook-director` Agent Persona

Located at `agents/audiobook-director.md`, the `@audiobook-director` agent acts as a resident studio director inside the Antigravity chat interface.

### Example Director Commands:
- *"Produce chapter 3 of Sword of Destiny with Aoede as lead narrator"*
- *"Patch beat ch03_beat012 with refined Hindustani dialogue and re-render"*
- *"Audition Geralt's voice with pitch -6% and bass boost"*
- *"Run Gate 2 Anti-Swap attribution audit on chapter 3"*
- *"Check 120+ KeyPool health and active daily quotas"*

---

## 📐 Machine-Readable Data Contracts for Agents (`schema_version: "2.0"`)

Agents do not parse fragile terminal logs. Every subsystem interacts strictly through validated **Pydantic v2** JSON artifacts and SQLite tables:

| Contract Artifact | Emitted By | Read By | Purpose |
|---|---|---|---|
| `raw_book_manifest.json` | `room1_ingest` | `room2_translate`, `room3_screenplay` | Monotonic AST of source sentences with character offsets. |
| `book_bible.json` | `room1_ingest` | `room2_translate`, `room3_screenplay` | World facts, transliteration maps, and character sociolects. |
| `cast_lock.json` | `room1_ingest` | `room3_screenplay`, `room4_synth` | Locked character $\to$ voice and formant mappings. |
| `chapter_XXX_translation.json` | `room2_translate` | `room3_screenplay` | High-register Hindustani beats with confidence scores. |
| `chapter_XXX_screenplay.json` | `room3_screenplay` | `room4_synth` | Attributed dialogue turns with 4D formant parameters and user locks. |
| `timeline_ledger.json` | `room4_synth` | `room5_master`, Studio UI | Sample-accurate timestamps, cue durations, and micro-fades. |
| `pipeline_ledger.db` | All Rooms / Core | Orchestrator, Studio UI, Agents | Transactional SQLite WAL database tracking project state and cache. |

---

## 🛡️ Agent Safety & Architectural Invariants

1. **TakeBank Cache Safety**:
   Agents must never delete `.audiobook_cache/takes/` files manually. Cache eviction is managed strictly via the LRU disk manager in `audiobook_factory.core.cache`.
2. **Fail-Closed Verification**:
   If a quality gate fails (e.g., Gate 2.0 detects a speaker turn swap $A \leftrightarrow B$), the agent must halt execution, report the exact failing beat, and remediate the attribution rather than forcing downstream synthesis.
3. **User Lock Preservation**:
   Segments with `provenance.user_locked: true` are immutable. Reconciliation passes must never overwrite human-directed casting or formants.
4. **Permissive API Configuration**:
   All generative TTS and LLM requests must use `BLOCK_NONE` safety settings to prevent false-positive censorship of dramatic literature.
