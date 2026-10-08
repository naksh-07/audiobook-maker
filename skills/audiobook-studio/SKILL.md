---
name: audiobook-studio
description: >-
  Studio-grade pure vocals-only audiobook production engine. Turns novels into broadcast-ready Hindi/English audiobooks
  with Gemini Flash TTS, 4D formants, and EBU R128 mastering. Use whenever producing audiobooks, casting character voices,
  auditioning dialogue, monitoring synthesis progress, or packaging M4B audiobooks.
---

# Audiobook Studio Skill (Pure Vocals-Only Engine)

This skill governs studio-grade audiobook production on the workstation. It operates the 5-Room Pure Vocals-Only pipeline, managing document extraction, dramatic Hindustani translation, anti-swap screenplay dramaturgy, Gemini Flash TTS synthesis, and broadcast EBU R128 mastering.

---

## 1. Engine Environment & Location

The computational core lives in the canonical workspace:
- **Engine Root**: `c:\Users\Suraj\Documents\antigravity\optimistic-kepler`
- **Virtualenv Python**: `c:\Users\Suraj\Documents\antigravity\optimistic-kepler\.venv\Scripts\python.exe`
- **Projects Directory**: `c:\Users\Suraj\Documents\antigravity\optimistic-kepler\audiobooks\projects`

---

## 2. Zero-CLI Directing Workflows

Instead of having the user type CLI flags, execute pipeline operations programmatically using the Python runtime in the engine root.

### A. Inspect Production Progress & Active Projects
Query the project's SQLite state ledger directly:

```python
import sqlite3
from pathlib import Path

db_path = Path(r"c:\Users\Suraj\Documents\antigravity\optimistic-kepler\audiobooks\projects\<book_slug>\project_state.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Get chapter status
chapters = conn.execute("SELECT chapter_num, title, word_count, scripted_status, mastered_status, m4a_path FROM chapters ORDER BY chapter_num").fetchall()

# Get segment progress
stats = conn.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
        SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
        COALESCE(SUM(duration_sec), 0.0) / 60.0 as total_duration_min
    FROM segments
""").fetchone()

print(f"Progress: {stats['completed']}/{stats['total']} segments ({stats['total_duration_min']:.1f} mins produced)")
```

### B. Produce a Single Chapter (Vocals-Only)
Run chapter production using `audiobook_factory.orchestrator.PipelineOrchestrator`:

```python
from pathlib import Path
from audiobook_factory.orchestrator import PipelineOrchestrator

projects_dir = Path(r"c:\Users\Suraj\Documents\antigravity\optimistic-kepler\audiobooks\projects")
orchestrator = PipelineOrchestrator(projects_dir)
project_dir = projects_dir / "<book_slug>"

result = orchestrator.produce_chapter(
    project_dir=project_dir,
    chapter_num=3,
    voice="Aoede",
    workers=3,
)
print("Master File:", result["master_file"])
```

### C. Ingest & Auto-Produce an Entire Novel
Run the complete end-to-end pipeline:

```python
from pathlib import Path
from audiobook_factory.orchestrator import PipelineOrchestrator

projects_dir = Path(r"c:\Users\Suraj\Documents\antigravity\optimistic-kepler\audiobooks\projects")
orchestrator = PipelineOrchestrator(projects_dir)

m4b_path = orchestrator.run_autonomous_pipeline(
    input_file=Path(r"C:\path\to\novel.epub"),
    hindi=True,
    dramatized=True,
    voice="Aoede",
    workers=3,
)
print("Mastered Audiobook:", m4b_path)
```

---

## 3. Production Gates Checklist

Before synthesizing or packaging, ensure all gates pass:
- **Gate 0.1 (Document Ingestion)**: Clean AST reading order, zero OCR garble.
- **Gate 1 (Voice Roster)**: 0% voice collision in `cast_lock.json`. Every active character has a distinct acoustic persona.
- **Gate 2 (Screenplay Attribution)**: 0% speaker turn inversion ($A \leftrightarrow B$), no quote leakage to Narrator.
- **Gate 2.5 (Dramatic Fidelity)**: Natural emotional arc, zero histrionics or melodramatic shrieking (temp clamped to 0.30–0.52).
- **Gate 5 (Dialogue Editorial & Snapping)**: Hann micro-fades (12ms/18ms) applied at zero-crossings.
- **Gate 6 (Broadcast Master Compliance)**:
  - Integrated loudness: **-19.0 LUFS** ($\pm 0.5$ LUFS).
  - True Peak ceiling: $\le$ **-1.5 dBTP**.
  - Two-pass measured linear loudnorm without pause pumping.
