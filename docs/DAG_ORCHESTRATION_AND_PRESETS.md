# 🎛️ Dynamic Pipeline Presets & DAG Orchestration Specification

**Standard**: `v6.0-ENTERPRISE-DAG`  
**Package Namespace**: `audiobook_factory.dag`  
**Status**: Autonomous Pipeline Dispatcher & Invalidation Engine  

---

## 1. Overview & Execution Architecture

The **DAG Orchestration Engine** provides high-level automated execution across the 5 standalone production rooms. Rather than executing rigid monolithic scripts, it analyzes input source contracts, checks the SQLite persistence ledger (`pipeline_ledger.db`), resolves cache hits from the TakeBank, and dynamically runs only the stages that are dirty or missing.

```mermaid
flowchart TD
    RunCmd["python -m audiobook_factory.cli.run --preset <PRESET>"] --> Dispatcher{"Preset Dispatcher"}

    Dispatcher -- "AUDIOBOOK_STUDIO" --> P1["Full 5-Room Novel Factory<br/>(Ingest -> Translate -> Screenplay -> TTS -> Master)"]
    Dispatcher -- "ENGLISH_AUDIOBOOK" --> P2["English-Only Novel Pipeline<br/>(Ingest -> Screenplay -> TTS -> Master)"]
    Dispatcher -- "MULTI_HOST_PODCAST" --> P3["Research-to-Podcast Engine<br/>(Topic Ingest -> Banter Script -> Multi-Voice TTS -> -16 LUFS Master)"]
    Dispatcher -- "STANDALONE_TRANSLATION" --> P4["Standalone Translation Service<br/>(Doc Ingest -> Translation Collective -> Text Output)"]
    Dispatcher -- "STANDALONE_TTS_API" --> P5["Batch Speech Synthesis Service<br/>(Script JSON -> TakeBank -> Mastered WAVs)"]

    classDef pStyle fill:#1e1e2e,stroke:#89b4fa,stroke-width:2px,color:#cdd6f4;
    class P1,P2,P3,P4,P5 pStyle;
```

---

## 2. Pipeline Presets Configuration Matrix

| Preset Identifier | Active Rooms | Translation Layer | Audio Loudness Target | Primary Deliverable | Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `AUDIOBOOK_STUDIO` | Rooms 1, 2, 3, 4, 5 | 4-Agent Hindustani Collective | **-19.0 LUFS** / -1.5 dBTP | Chaptered `.m4b` + `.m4a` | Full English-to-Hindi studio novel production |
| `ENGLISH_AUDIOBOOK`| Rooms 1, 3, 4, 5 | **SKIPPED (Bypassed)** | **-19.0 LUFS** / -1.5 dBTP | Chaptered `.m4b` + `.m4a` | Native English multi-voice novel production |
| `MULTI_HOST_PODCAST`| Ingest, Script, 4, 5 | Optional / Direct Script | **-16.0 LUFS** / -1.0 dBTP | Mastered `.mp3` / `.m4a` | Multi-host research summaries & banter podcasts |
| `STANDALONE_TRANSLATION` | Rooms 1, 2 | 4-Agent Hindustani Collective | N/A | `.json` / `.txt` / `.md` | High-fidelity literary document translation |
| `STANDALONE_TTS_API`| Rooms 4, 5 | N/A | Configurable (-19 or -16 LUFS) | Stems `.wav` / `.m4a` | High-throughput multi-voice batch synthesis |

---

## 3. Preset Execution Topologies

### Preset A: `AUDIOBOOK_STUDIO` (Default 5-Room Factory)
```mermaid
flowchart LR
    R1["Room 1: Ingest"] -->|"Gate 0.1"| R2["Room 2: Translate"]
    R2 -->|"Gate 1.0"| R3["Room 3: Screenplay"]
    R3 -->|"Gate 2.0"| R4["Room 4: TTS & Editorial"]
    R4 -->|"Gate 4.0"| R5["Room 5: Master & M4B"]
```
- **Execution Flow**: Ingests novel $\to$ Generates `book_bible.json` and `cast_lock.json` $\to$ Translates each chapter via 4-Agent Collective $\to$ Parses prose into screenplay with anti-swap QA $\to$ Synthesizes via TakeBank and Gemini Flash TTS $\to$ Masters to -19.0 LUFS and packages `.m4b`.

### Preset B: `ENGLISH_AUDIOBOOK` (Bypassed Translation)
```mermaid
flowchart LR
    R1["Room 1: Ingest"] -->|"Gate 0.1"| R3["Room 3: Screenplay (English Direct)"]
    R3 -->|"Gate 2.0"| R4["Room 4: TTS & Editorial"]
    R4 -->|"Gate 4.0"| R5["Room 5: Master & M4B"]
```
- **Execution Flow**: Room 2 is completely bypassed. Room 3 directly converts the AST `RawBookManifest` from Room 1 into an English `ScreenplayScript`.

### Preset C: `MULTI_HOST_PODCAST`
```mermaid
flowchart LR
    Doc["Research Doc / URL / Topic"] --> ScriptGen["Podcast Script Generator<br/>(Host A vs Host B Banter)"]
    ScriptGen --> R4["Room 4: Multi-Voice TTS"]
    R4 --> R5_Pod["Room 5: Podcast Mastering<br/>(-16.0 LUFS Target)"]
    R5_Pod --> Deliverable["Mastered Podcast .mp3 / .m4a"]
```
- **Execution Flow**: Ingests reference materials, generates dual-host banter script, synthesizes with rapid conversational turn latencies (-150ms overlap), and masters to podcast industry standard -16.0 LUFS.

---

## 4. Stage Status Lifecycle & State Machine

Every stage record in `chapter_stage_ledger` transitions through a deterministic state machine:

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> RUNNING : Orchestrator Launch
    RUNNING --> COMPLETED : Gate Check PASSED
    RUNNING --> FAILED : Gate Check FAILED / Exception
    COMPLETED --> DIRTY : Upstream Artifact Changed
    DIRTY --> RUNNING : Reconcile Run
    IDLE --> SKIPPED : Preset Bypassed Room
```

### Stage Status Definitions:
- `IDLE`: Stage is pending execution.
- `RUNNING`: Subsystem currently processing chapter.
- `COMPLETED`: Processing finished; artifact registered and gate passed.
- `FAILED`: Execution or quality gate verification failed; error logged.
- `DIRTY`: Upstream input contract hash changed; downstream artifact is stale.
- `SKIPPED`: Stage bypassed by active preset configuration.

---

## 5. Smart Diff Reconciliation Engine (`diff_reconciler.py`)

The Diff Reconciler eliminates full-pipeline re-runs by calculating the exact blast radius of upstream edits.

### Invalidation Algorithm:
1. **Hash Verification**: Compares the SHA-256 hash of the inbound contract with `input_contract_hash` stored in `chapter_stage_ledger`.
2. **Dirty Flagging**: If hashes differ, marks current stage as `DIRTY`.
3. **Cascading Propagation**: Automatically marks all dependent downstream stages for that specific chapter as `DIRTY`.
4. **TakeBank Protection**: Unchanged dialogue segments retain identical SHA-256 take hashes and are resolved instantly from TakeBank during Room 4 re-runs.

```python
# Standalone Example: Running Diff Reconciliation
from audiobook_factory.dag.diff_reconciler import DiffReconciler

reconciler = DiffReconciler(db_path="./pipeline_ledger.db")
dirty_plan = reconciler.evaluate_project_dirty_stages(project_id="sword-of-destiny")

print(f"Chapters requiring re-run: {dirty_plan.dirty_chapter_count}")
for stage in dirty_plan.stages_to_execute:
    print(f" - Chapter {stage.chapter_id}: {stage.room_name} ({stage.reason})")
```

---

## 6. Top-Level CLI Command Reference

```bash
# 1. Run Full 5-Room Audiobook Pipeline
python -m audiobook_factory.cli.run \
    --preset AUDIOBOOK_STUDIO \
    --source "books/Sword_of_Destiny.epub" \
    --project-dir "./projects/sword_of_destiny" \
    --workers 4

# 2. Run English-Only Novel Pipeline (Room 2 Bypassed)
python -m audiobook_factory.cli.run \
    --preset ENGLISH_AUDIOBOOK \
    --source "books/Dune.epub" \
    --project-dir "./projects/dune"

# 3. Reconcile Dirty Stages After Manual Script / Translation Edits
python -m audiobook_factory.cli.run \
    --reconcile-dirty \
    --project-dir "./projects/sword_of_destiny"

# 4. Generate Multi-Host Podcast
python -m audiobook_factory.cli.run \
    --preset MULTI_HOST_PODCAST \
    --source "papers/quantum_computing.pdf" \
    --project-dir "./projects/quantum_podcast" \
    --target-lufs -16.0
```
