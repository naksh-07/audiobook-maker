# 🤖 AI Agent & MCP Integration Guide

## 📖 Overview

**Audiobook Maker v4.0** is built from the ground up to support autonomous agentic operation. Large Language Model (LLM) agents (such as Antigravity, Claude, Gemini, OpenDevin, and Cursor) can programmatically orchestrate the entire audio drama pipeline, direct soundscapes, audit acoustic properties, and recover from failures with mathematical predictability.

---

## 🛠️ Specialized Agent Skills

The repository includes two specialized agent skills located in [`.agents/skills/`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/.agents/skills/):

```text
.agents/skills/
├── novel-audiobook-factory/
│   ├── SKILL.md
│   └── ...
└── audio-engineer-ffmpeg/
    ├── SKILL.md
    └── ...
```

### 1. `novel-audiobook-factory`
- **Scope**: Autonomous end-to-end studio audiobook production engine.
- **Trigger**: Activates whenever the user provides a novel or manuscript (`.epub`, `.pdf`, `.txt`, `.md`) and requests an audiobook.
- **Workflow**: Coordinates document extraction, literary Hindustani translation, sliding-window screenplay attribution, speech synthesis via Gemini 3.1 Flash TTS, SQLite Sound Bank search, -16dB dynamic ducking, and single-pass M4B packaging.

### 2. `audio-engineer-ffmpeg`
- **Scope**: Hollywood-grade audio drama mixing, acoustic sound design, and FFmpeg mastering.
- **Capabilities**:
  - Designs 5-track audio hierarchies (Vocals, BGM, Ambience Bed, Foley SFX, Master Out).
  - Configures dynamic sidechain compression (-16dB ducking with 0.018 linear threshold).
  - Calculates 2.2kHz spectral notch filters (`equalizer=f=2200:t=q:w=1.5:g=-5.5`).
  - Assembles self-healing FFmpeg `filter_complex` graphs.
  - Enforces EBU R128 (-19 LUFS) broadcast loudness and True Peak ceilings (-1.5 dBTP).

---

## 🔌 Model Context Protocol (MCP) Tool Suite

The [`ffmpeg_mastering`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/ffmpeg_mastering/) module exposes MCP tools defined in [`mcp_tool_schema.json`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/ffmpeg_mastering/mcp_tool_schema.json) for runtime interaction by MCP-enabled client agents:

### 1. `master_audio`
Applies the 5-stage studio vocal chain (60Hz subsonic cut, de-esser, lowpass, SOXR 48kHz polyphase resampler, and EBU R128 loudnorm) to any audio file.

```json
{
  "name": "master_audio",
  "parameters": {
    "input_file": "/absolute/path/to/raw_speech.wav",
    "output_file": "/absolute/path/to/mastered_speech.m4a",
    "target_lufs": -19.0,
    "format": "m4a"
  }
}
```

### 2. `sidechain_duck_audio`
Dynamically ducks background music under spoken dialogue using FFmpeg sidechain compression.

```json
{
  "name": "sidechain_duck_audio",
  "parameters": {
    "vocal_file": "/absolute/path/to/vocal_stem.wav",
    "bgm_file": "/absolute/path/to/bgm_score.wav",
    "output_file": "/absolute/path/to/ducked_mix.m4a",
    "duck_attenuation_db": -16.0
  }
}
```

### 3. `audit_audio_levels`
Executes FFmpeg `astats` and `ebur128` filters to extract objective acoustic telemetry: Integrated Loudness, True Peak, dynamic range, and DC offset.

```json
{
  "name": "audit_audio_levels",
  "parameters": {
    "audio_file": "/absolute/path/to/rendered_master.m4a"
  }
}
```

---

## 📐 Machine-Readable Data Contracts for Agents

Agents do not need to parse fragile text logs. Every subsystem emits deterministic, validated **Pydantic v2** JSON artifacts:

| Artifact | Emitted By | Read By | Purpose |
|---|---|---|---|
| `chapter_XXX_script.json` | `ScriptBuilder` | `TTSDispatcher`, `AgentDirector` | Standardized screenplay with dialogue, emotion, and spatial azimuth pan. |
| `chapter_XXX_timeline_ledger.json` | `timeline_ledger.py` | `AgentDirector`, `ManifestRenderer` | Sample-accurate millisecond timestamps and full Devanagari transcripts. |
| `chapter_XXX_manifest.json` | `AgentDirector` | `ManifestRenderer`, `GateAuditor` | Full acoustic blueprint: silence percentage, BGM cues, and Foley cues. |
| `chapter_XXX_stem_ledger.json` | `CinemaAudioEngine` | `GateAuditor`, Mastering Engineer | Multi-stem compliance metrics (DX, MX, FX, AMB, ME). |
| `project_state.json` | `ProjectStateLedger` | `PipelineOrchestrator` | Transaction-safe checkpoint ledger tracking completed stages. |

---

## 🛡️ Agent Safety & Idempotency Rules

When developing or running autonomous agents in this ecosystem, adhere to these architectural invariants:

1. **Auto-Janitor Safety Shield**:
   Synthesized speech WAV chunks consume Google AI Studio API quota. Agents must **NEVER** purge raw WAV chunks in `audio_chunks/` unless the final master audio file exists and has been verified with $> 1000$ bytes on disk.
2. **Fail-Closed Verification**:
   If an audio probe or gate check fails, the gate returns `AuditResult(passed=False)`. Agents must halt downstream rendering and remediate upstream defects rather than forcing pipeline progression.
3. **Atomic State Commits**:
   All state updates use atomic file replacement (`atomic_write_json`), ensuring partial writes or sudden agent timeouts never leave corrupt JSON files on disk.
4. **Idempotent Chapter Resumption**:
   If an agent's context window expires or runs out of steps, restarting the CLI command automatically resumes from the last completed checkpoint without re-running finished chapters.
