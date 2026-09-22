# 🔍 Comprehensive Read-Only Project Audit Prompt
**Repository**: `naksh-07/audiobook-maker`  
**Execution Mode**: **READ-ONLY AUDIT & FORENSIC CODE REVIEW** (Zero modifications, pure analytical evaluation)

---

## 🎯 Master Audit Directive (Copy & Paste for Next Agent)

```markdown
# Autonomous Read-Only Forensic Audit: Studio Audiobook Production Engine

## Mission Overview
You are acting as an elite Principal Software Architect, Audio Drama Sound Engineer, and Application Security Auditor.
Your task is to conduct an exhaustive, multi-dimensional, read-only forensic audit of the `audiobook-maker` codebase.
DO NOT MODIFY ANY SOURCE FILES, DO NOT RUN MODIFYING OR DELETING SCRIPTS.
Your output must be a structured, highly technical, uncompromising audit report.

---

## 1. Scope of Investigation

Inspect the following modules and subsystems across all layers:
- `audiobook_factory/extractor.py` (Document parsing: EPUB, PDF, TXT)
- `audiobook_factory/translator.py` (Sense-for-sense dramatic Hindustani translation)
- `audiobook_factory/script_builder.py` (Screenplay attribution & Data Healer)
- `audiobook_factory/scene_director.py` (Scene environments & emotional scoring)
- `audiobook_factory/foley_miner.py` (Diegetic sound cues & physical action extraction)
- `audiobook_factory/sound_bank.py` & `audiobook_factory/catalog_seeder.py` (FTS5 audio asset index)
- `audiobook_factory/tts_dispatcher.py` & `audiobook_factory/key_manager.py` (Gemini 3.1 Flash TTS pool & token bucket)
- `audiobook_factory/ffmpeg_agent.py` & `audiobook_factory/soundscape.py` (5-track multitrack mixing & self-healing filter graphs)
- `audiobook_factory/mastering.py` & `audiobook_factory/packager.py` (EBU R128 mastering & M4B packaging)
- `audiobook_factory/timeline_ledger.py` & `audiobook_factory/state.py` (Millisecond timeline & state persistence)
- `C:\Users\Suraj\.gemini\config\scripts\ffmpeg_audio_mcp.py` & `C:\Users\Suraj\.gemini\antigravity\mcp\ffmpeg-audio\` (MCP ecosystem)
- `.agents/skills/` & `.agents/memory/` (Project skills, decisions, active context)

---

## 2. Forensic Audit Vectors (7 Pillars)

### Pillar A: Ingestion & Document Extraction Integrity
1. Memory & File Streaming: Does `extractor.py` load entire large PDFs (500+ pages) into RAM at once, or is it streamed page-by-page?
2. Boundary Detection: How robust is chapter splitting? Can edge-case headings (e.g. Roman numerals, prologue/epilogue, unnumbered chapters) be missed?
3. Encoding & Artifacts: How are soft hyphens, ligatures, OCR errors, and non-UTF-8 characters sanitized?

### Pillar B: Linguistic Translation & Context Preservation
1. Two-Pass Memory Glossary: Are character names and honorifics (*Aap/Tum/Tu*) strictly consistent across chapters?
2. Safety Block & Content Filtering: If Google AI Studio triggers safety filters on combat or dark fantasy prose, what happens? Does it crash, hallucinate, or cleanly fall back?
3. Token Limits & Chunk Slicing: Can a translation chunk cut off a compound sentence or dialogue mid-word?

### Pillar C: Screenplay Attribution & JSON Recovery
1. Speaker Attribution Drift: How does the sliding-window algorithm prevent character attribution from confusing minor characters with the protagonist?
2. Data Healer Resilience: Does the new LLM-based truncation healer handle malformed strings, escaped quotes, or unclosed objects without infinite looping?
3. Zero-Content-Loss Guarantee: Is there any scenario where narrator text or dialogue is silently dropped or swallowed by an unhandled parser exception?

### Pillar D: Key Pool, Quota & Network Concurrency
1. Rate Limiting (15 RPM / 10 RPD): How does `key_manager.py` prevent 429 cascades across concurrent threads?
2. SQLite Concurrency & Locking: Is SQLite accessed safely across concurrent worker threads with WAL mode and proper transaction locks?
3. Graceful Checkpoint Halt: When `AllKeysExhaustedTodayError` is raised, does the process save its exact segment index cleanly without corrupting the state ledger?
4. Rollover Timing: How is the Midnight PT rollover computed? Does local timezone drift (IST vs PT) cause premature key retries?

### Pillar E: Audio Engineering, FFmpeg DSP & Self-Healing
1. 5-Track Mixing Graph: Are input streams (`[0:a]` Voice, `[1:a]` BGM, `[2:a]` Ambience, `[3:a]` Foley) always guarded against missing tracks?
2. Self-Healing Tool Loop: Can `test_filter_graph` hang if FFmpeg encounters an interactive prompt or circular filter loop?
3. Spectral Carving & Sidechain Ducking: Are the compression parameters (`attack=120`, `release=750`, `ratio=8.0`, `threshold=0.04`) acoustically balanced, or could they cause noticeable audio pumping/breathing?
4. Loudness Normalization: Does the EBU R128 filter (`loudnorm=I=-19:TP=-1.5:LRA=11`) run in single-pass or dual-pass mode? Could extreme transients cause clipping before the limiter?

### Pillar F: Code Hygiene, Reliability & Zero-Dependency Invariant
1. Dead Code & Stubs: Search for any empty functions, `pass` blocks, `TODO` markers, or unexercised legacy code paths.
2. Exception Hygiene: Flag every broad `except Exception:` block that suppresses errors without proper logging.
3. Zero-Dependency Invariant: Verify that `pyproject.toml` retains its zero external runtime dependency standard (using only standard library + system FFmpeg).

### Pillar G: Security, Secrets & Workspace Cleanliness
1. Git Hygiene: Verify that `.env`, `.env.*`, `*.key`, `*.token`, `*.db`, `key_pool_state.db` are strictly ignored by `.gitignore`.
2. Hardcoded Secrets: Scan all scripts for hardcoded API keys, tokens, local IP addresses, or sensitive credentials.
3. Path Injection: Check if user-supplied book titles or chapter names can cause path traversal in filesystem calls.

---

## 3. Required Report Structure

Deliver your findings strictly using this format:

```markdown
# 🔬 Project Forensic Audit Report: Audiobook Factory

## 1. Executive Summary & Production Readiness Score (0-100)
- Architecture Maturity
- Security & Secret Scrubbing
- Audio Engineering Fidelity
- Autonomous Resilience (Self-Healing Score)

## 2. Critical Failure Points (Showstoppers / P0)
- Exact file, line range, failure mechanism, and impact.

## 3. High & Medium Risks (P1 / P2)
- Edge cases, quota edge conditions, audio pumping risks, parser vulnerabilities.

## 4. Architectural & Agentic Opportunities
- Where can LLM agents further replace fragile heuristics?
- Recommended enhancements to the FFmpeg MCP server and subagent protocols.

## 5. Prioritized Remediation Roadmap
- Immediate fixes (Quick wins)
- Structural hardening
```
```
