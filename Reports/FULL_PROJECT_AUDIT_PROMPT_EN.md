# 🔍 Comprehensive Engine-Level Read-Only Audit Prompt
**Repository**: `naksh-07/audiobook-maker`  
**Target Scope**: General-Purpose Audiobook Maker Engine & Studio Production Pipeline (Whole System Audit)  
**Execution Mode**: Pure Read-Only Analytical Review (Zero Source Modifications)

---

## 🎯 Master Audit Directive (Copy & Paste for Next Agent)

```markdown
# Autonomous Read-Only Forensic Audit: General-Purpose Audiobook Maker Engine

## 1. Mission Overview & Scope
You are acting as a Principal Systems Architect, Lead Audio DSP Engineer, and Application Security Auditor.
Your objective is to conduct an exhaustive, multi-dimensional, read-only forensic audit of the entire **`audiobook-maker` framework**.

> [!IMPORTANT]
> **Scope Clarification**: You are auditing the general-purpose **software engine and production framework**, NOT any specific book or single audiobook project (such as Witcher). Evaluate the repository's capability to reliably ingest, translate, attribute, synthesize, master, and package ANY arbitrary novel (EPUB, PDF, TXT) into a Hollywood-grade audio drama container.
>
> **Strict Invariant**: This audit is **100% READ-ONLY**. Do NOT modify, edit, or delete any source files, database records, or project assets. Do NOT execute commands that alter state.

---

## 2. Subsystems Under Investigation

Inspect every layer of the engine:
1. **Document Ingestion & Chapter Segmentation**
   - [`audiobook_factory/extractor.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/extractor.py)
2. **Linguistic Translation & Localization Memory**
   - [`audiobook_factory/translator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/translator.py)
   - [`audiobook_factory/sanitizer.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sanitizer.py)
3. **Screenplay Dialogue Attribution & Data Healing**
   - [`audiobook_factory/script_builder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/script_builder.py)
4. **Cinematic Sound Direction & Foley Mining**
   - [`audiobook_factory/scene_director.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/scene_director.py)
   - [`audiobook_factory/foley_miner.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/foley_miner.py)
   - [`audiobook_factory/sound_bank.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/sound_bank.py)
   - [`audiobook_factory/catalog_seeder.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/catalog_seeder.py)
5. **Speech Synthesis & Quota Ledger Engine**
   - [`audiobook_factory/tts_dispatcher.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/tts_dispatcher.py)
   - [`audiobook_factory/key_manager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/key_manager.py)
   - [`audiobook_factory/cadence.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/cadence.py)
6. **5-Track Multitrack Audio Mixing & Self-Healing DSP**
   - [`audiobook_factory/ffmpeg_agent.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/ffmpeg_agent.py)
   - [`audiobook_factory/soundscape.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/soundscape.py)
   - [`audiobook_factory/mastering.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/mastering.py)
   - [`ffmpeg_mastering/audio_master.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/ffmpeg_mastering/audio_master.py)
7. **Packaging, Ledger Synchronization & CLI Orchestration**
   - [`audiobook_factory/packager.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/packager.py)
   - [`audiobook_factory/timeline_ledger.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/timeline_ledger.py)
   - [`audiobook_factory/state.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/state.py)
   - [`audiobook_factory/orchestrator.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_factory/orchestrator.py)
   - [`audiobook_cli.py`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/audiobook_cli.py)
8. **Agent & MCP Ecosystem**
   - [`C:\Users\Suraj\.gemini\config\scripts\ffmpeg_audio_mcp.py`](file:///C:/Users/Suraj/.gemini/config/scripts/ffmpeg_audio_mcp.py)
   - [`C:\Users\Suraj\.gemini\antigravity\mcp\ffmpeg-audio\`](file:///C:/Users/Suraj/.gemini/antigravity/mcp/ffmpeg-audio/)
   - [`.agents/skills/audio-engineer-ffmpeg/SKILL.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/.agents/skills/audio-engineer-ffmpeg/SKILL.md)
   - [`.agents/skills/novel-audiobook-factory/SKILL.md`](file:///c:/Users/Suraj/Documents/Antigravity/Audiobook/.agents/skills/novel-audiobook-factory/SKILL.md)

---

## 3. Forensic Audit Pillars (7 Dimensions)

### Pillar 1: Ingestion & Document Parsing Robustness
1. **Large Document Scaling**: How does `extractor.py` handle massive texts (150,000+ words, 800+ pages)? Is parsing streamed, or does it attempt to hold entire uncompressed DOMs in memory?
2. **Boundary Detection & Heuristics**: Are scene breaks (`***`, `---`, extra linebreaks) and non-standard chapter headings (Roman numerals, Prologue, Epilogue, named chapters without numbers) reliably detected across diverse publishing formats?
3. **Typography & Encoding Hygiene**: How are soft hyphens, typographic ligatures (fi, fl), non-breaking spaces, and corrupted OCR artifacts sanitized prior to downstream synthesis?

### Pillar 2: Translation Fidelity & Context Window Safety
1. **Linguistic Continuity**: How does the engine maintain cross-chapter character consistency and honorific registers (*Aap/Tum/Tu*) without leaking prompt instructions into the generated text?
2. **Safety Block Resilience**: When upstream LLM safety filters trigger on fantasy violence, battle scenes, or adult prose, does the pipeline crash, halt, or execute an intelligent fallback?
3. **Compound Sentence Integrity**: Is text chunked at semantic sentence boundaries, or can clauses and spoken dialogue be severed mid-sentence?

### Pillar 3: Screenplay Attribution & JSON Healing Architecture
1. **Dialogue Attribution Accuracy**: How does the sliding-window attribution mechanism prevent character role swapping or pronoun confusion in multi-character dialogue scenes?
2. **LLM Data Healer Resilience**: Does the self-healing JSON recovery loop handle severely truncated arrays, escaped quotation marks, and malformed trailing characters without entering infinite retry recursion?
3. **Zero-Content-Loss Invariant**: Is there any failure mode in `script_builder.py` where speech or narration segments can be silently omitted or discarded?

### Pillar 4: Concurrency, Quotas & Key Pool Orchestration
1. **Rate Limit Defenses (15 RPM / 10 RPD)**: How does `key_manager.py` protect against 429 cascades across multiple concurrent workers?
2. **SQLite Thread Safety & Lock Contention**: Is `key_pool_state.db` configured with WAL (Write-Ahead Logging) and proper busy timeouts to prevent `sqlite3.OperationalError: database is locked` during high-concurrency bursts?
3. **Graceful Checkpoint Halt**: When all active keys reach their daily quota (`AllKeysExhaustedTodayError`), does the pipeline cleanly checkpoint progress and exit without leaving intermediate corrupt states?
4. **Timezone Rollover Precision**: Is the Midnight PT rollover computed dynamically and accurately with respect to local workstation time (IST)?

### Pillar 5: Multitrack Audio DSP & Acoustic Sound Design
1. **5-Track Bus Hierarchy**: Are input streams (`[0:a]` Dialogue, `[1:a]` BGM, `[2:a]` Ambience, `[3:a]` Foley) validated when specific tracks are absent (e.g., chapters with zero Foley cues)?
2. **Sidechain Compression Dynamics**: Evaluate the sidechain ducking curve (`threshold=0.04`, `ratio=8.0`, `attack=120ms`, `release=750ms`). Does it introduce audible audio pumping, breathing, or unnatural volume jumps?
3. **Spectral Carving & Consonant Clarity**: Is the 2.2kHz parametric notch cut (`-5.5dB`) on the BGM track acoustically optimal across varied musical genres (orchestral, ambient, synth)?
4. **Broadcast EBU R128 Mastering**: Is loudness normalization (`Integrated -19 LUFS`, `True Peak -1.5 dBFS`, `LRA 11`) dual-pass or single-pass? Can sudden dynamic bursts clip the digital ceiling before the limiter?
5. **Self-Healing Filter Validation**: Can `test_filter_graph` in `ffmpeg_agent.py` stall or hang if FFmpeg encounters circular filter loops or unexpected interactive prompts?

### Pillar 6: Code Hygiene, Reliability & Zero-Dependency Invariant
1. **Zero-Placeholder Guarantee**: Audit the entire codebase for forbidden stubs (`TODO`, `FIXME`, `pass`, empty mock implementations).
2. **Exception Handling Hygiene**: Identify all bare `except:` or `except Exception: pass` blocks that silently swallow errors without telemetry logging.
3. **Zero-Dependency Standard**: Confirm that `pyproject.toml` maintains its zero external runtime dependency requirement (standard Python libraries + system FFmpeg binary only).

### Pillar 7: Security, Secret Hygiene & Directory Safety
1. **Credential & Secret Scrubbing**: Verify that `.env`, `.env.*`, `*.key`, `*.token`, `*.db`, and candidate key files are strictly ignored by `.gitignore`.
2. **Hardcoded Secret Inspection**: Scan all Python modules, tests, and configuration files to ensure no API keys, private tokens, hardware serials, or private LAN IPs are hardcoded.
3. **Path Traversal & Injection**: Verify that book slugs, chapter names, and output file arguments cannot trigger path traversal attacks (`../`) or command injection through FFmpeg argument lists.

---

## 4. Required Report Structure

Your final audit report must strictly follow this format:

```markdown
# 🔬 Architectural & Forensic Audit Report: Audiobook Maker Framework

## 1. Executive Summary & Production Readiness Score (0–100)
- Overall System Maturity Score
- Autonomous Self-Healing & Resilience Score
- Audio Drama DSP & Broadcast Mastering Score
- Security, Secrets & Workspace Cleanliness Score

## 2. Critical Failure Points (P0 / Showstoppers)
For each critical issue found:
- **Location**: `[file_path:line_range]`
- **Mechanism**: How the failure is triggered.
- **Impact**: Pipeline crash, silent data loss, audio distortion, or key exhaustion.
- **Root Cause**: Why the current code fails.

## 3. High & Medium Risks (P1 / P2)
- Edge-case parser failures, concurrency race conditions, audio pumping risks, quota leaks.

## 4. Agentic & MCP Ecosystem Review
- Evaluation of the `ffmpeg-audio` MCP server, `audio-engineer` subagent, and local self-healing loops.
- Opportunities where LLM agency should replace fragile heuristics.

## 5. Prioritized Remediation Roadmap
- **Immediate Fixes (P0/P1)**: Surgical code adjustments.
- **Architectural Hardening (P2)**: Scalability and long-term durability enhancements.
```
```
