#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 7: SQLite-Backed Project State Ledger.
Provides ACID-compliant, transaction-safe resume checkpoints and segment-level tracking.
Ensures zero token loss and instantaneous recovery upon network drops or restart.
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


import contextlib


class ProjectStateLedger:
    """Manages chapter and segment state in SQLite (project_state.db)."""

    def __init__(self, project_dir: Path):
        path = Path(project_dir).resolve()
        if path.suffix == ".db":
            self.db_path = path
            self.project_dir = path.parent
        else:
            self.project_dir = path
            self.db_path = self.project_dir / "project_state.db"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextlib.contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS project_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chapters (
                    chapter_num INTEGER PRIMARY KEY,
                    title TEXT,
                    word_count INTEGER DEFAULT 0,
                    translated_status TEXT DEFAULT 'PENDING',
                    scripted_status TEXT DEFAULT 'PENDING',
                    mastered_status TEXT DEFAULT 'PENDING',
                    m4a_path TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS segments (
                    id TEXT PRIMARY KEY,
                    chapter_num INTEGER NOT NULL,
                    seg_num INTEGER NOT NULL,
                    speaker TEXT NOT NULL,
                    voice_persona TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    audio_path TEXT,
                    duration_sec REAL DEFAULT 0.0,
                    retry_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (chapter_num) REFERENCES chapters(chapter_num)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_segments_chap ON segments(chapter_num);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_segments_status ON segments(status);")
            # Auto-recover orphaned in-progress segments from previous crashes
            conn.execute("UPDATE segments SET status = 'PENDING', updated_at = CURRENT_TIMESTAMP WHERE status = 'IN_PROGRESS';")

    def set_meta(self, key: str, value: Any):
        val_str = json.dumps(value) if not isinstance(value, str) else value
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO project_meta (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP;",
                (key, val_str)
            )

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._connection() as conn:
            row = conn.execute("SELECT value FROM project_meta WHERE key = ?;", (key,)).fetchone()
            if not row:
                return default
            try:
                return json.loads(row["value"])
            except Exception:
                return row["value"]

    def register_chapter(self, chapter_num: int, title: str, word_count: int = 0):
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO chapters (chapter_num, title, word_count, updated_at) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(chapter_num) DO UPDATE SET title = excluded.title, word_count = excluded.word_count, updated_at = CURRENT_TIMESTAMP;",
                (chapter_num, title, word_count)
            )

    def register_script_segments(self, chapter_num: int, script: List[Dict[str, Any]], voice_map: Dict[str, Any], default_voice: str = "Aoede"):
        """Bulk registers script items into segments table if not already present."""
        import hashlib

        with self._connection() as conn:
            for seg_num_idx, item in enumerate(script, 1):
                seg_num = item.get("index", seg_num_idx)
                text = item.get("text", "").strip()
                speaker = item.get("speaker", "Narrator")
                voice_cfg = voice_map.get(speaker, voice_map.get("Narrator", {}))
                voice = voice_cfg.get("voice", default_voice) if isinstance(voice_cfg, dict) else default_voice

                cache_key = f"{text}|{voice}".encode("utf-8")
                seg_hash = hashlib.md5(cache_key).hexdigest()[:8]
                seg_id = f"c{chapter_num:03d}_s{seg_num:04d}_{seg_hash}"

                conn.execute(
                    "INSERT OR IGNORE INTO segments (id, chapter_num, seg_num, speaker, voice_persona, text_content, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'PENDING');",
                    (seg_id, chapter_num, seg_num, speaker, voice, text)
                )
            conn.execute(
                "UPDATE chapters SET scripted_status = 'COMPLETED', updated_at = CURRENT_TIMESTAMP WHERE chapter_num = ?;",
                (chapter_num,)
            )

    def reset_orphaned_segments(self, chapter_num: Optional[int] = None) -> int:
        """Reset segments stuck in IN_PROGRESS from interrupted runs back to PENDING."""
        query = "UPDATE segments SET status = 'PENDING', updated_at = CURRENT_TIMESTAMP WHERE status = 'IN_PROGRESS'"
        params = []
        if chapter_num is not None:
            query += " AND chapter_num = ?"
            params.append(chapter_num)
        with self._connection() as conn:
            cur = conn.execute(query, params)
            return cur.rowcount

    def get_pending_segments(self, chapter_num: Optional[int] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM segments WHERE status IN ('PENDING', 'FAILED', 'IN_PROGRESS')"
        params = []
        if chapter_num is not None:
            query += " AND chapter_num = ?"
            params.append(chapter_num)
        query += " ORDER BY chapter_num ASC, seg_num ASC;"

        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def mark_segment_started(self, segment_id: str):
        with self._connection() as conn:
            conn.execute(
                "UPDATE segments SET status = 'IN_PROGRESS', updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (segment_id,)
            )

    def mark_segment_completed(self, segment_id: str, audio_path: str, duration_sec: float):
        with self._connection() as conn:
            conn.execute(
                "UPDATE segments SET status = 'COMPLETED', audio_path = ?, duration_sec = ?, error_message = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (audio_path, duration_sec, segment_id)
            )

    def mark_segment_failed(self, segment_id: str, error_message: str):
        with self._connection() as conn:
            conn.execute(
                "UPDATE segments SET status = 'FAILED', retry_count = retry_count + 1, error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?;",
                (error_message, segment_id)
            )

    def get_chapter_segments(self, chapter_num: int) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM segments WHERE chapter_num = ? ORDER BY seg_num ASC;",
                (chapter_num,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_progress(self) -> Dict[str, Any]:
        with self._connection() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total_segments,
                    SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
                    SUM(duration_sec) as total_duration_sec
                FROM segments;
            """).fetchone()

            total = row["total_segments"] or 0
            completed = row["completed"] or 0
            pct = round((completed / total * 100), 1) if total > 0 else 0.0

            return {
                "total_segments": total,
                "completed": completed,
                "in_progress": row["in_progress"] or 0,
                "failed": row["failed"] or 0,
                "pending": row["pending"] or 0,
                "progress_percent": pct,
                "total_duration_min": round((row["total_duration_sec"] or 0.0) / 60.0, 1),
            }
