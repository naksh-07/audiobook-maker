#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 4: Production Telemetry Engine & Performance Ledger.
Tracks end-to-end pipeline execution telemetry:
- Stage-by-stage latencies & success rates
- Gemini API token usage, latencies, rate limits (429s), and estimated costs
- Acoustic mastering deliverables (LUFS, True Peak, LRA, phase correlation)
- SQLite WAL ledger persistence in audiobooks/telemetry.db
- JSON export (TELEMETRY_REPORT.json) for auditing & CI/CD certification
"""

from __future__ import annotations
import os
import time
import json
import sqlite3
import threading
import contextlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Generator

from audiobook_factory.logger import logger

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TELEMETRY_DIR = WORKSPACE_DIR / "audiobooks"
DEFAULT_TELEMETRY_DB = DEFAULT_TELEMETRY_DIR / "telemetry.db"


class ProductionTelemetryLedger:
    """Thread-safe SQLite production telemetry ledger."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_TELEMETRY_DB).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextlib.contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create telemetry tables with optimal indexing."""
        with self._lock, self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS production_runs (
                    run_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    book_title TEXT,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    total_duration_sec REAL,
                    status TEXT DEFAULT 'RUNNING',
                    error_message TEXT,
                    config_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stage_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    stage_num INTEGER NOT NULL,
                    duration_sec REAL NOT NULL,
                    status TEXT DEFAULT 'SUCCESS',
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(run_id) REFERENCES production_runs(run_id)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    service TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    latency_sec REAL NOT NULL,
                    is_rate_limit INTEGER DEFAULT 0,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    est_cost_usd REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(run_id) REFERENCES production_runs(run_id)
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS acoustic_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    chapter_num INTEGER NOT NULL,
                    duration_sec REAL NOT NULL,
                    integrated_lufs REAL NOT NULL,
                    true_peak_dbtp REAL NOT NULL,
                    loudness_range_lu REAL NOT NULL,
                    phase_correlation REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(run_id) REFERENCES production_runs(run_id)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stage_run ON stage_telemetry(run_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_run ON api_telemetry(run_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_acoustic_run ON acoustic_telemetry(run_id);")
            # Auto-reconcile any orphan telemetry records by registering missing production runs
            conn.execute("""
                INSERT OR IGNORE INTO production_runs (run_id, project_id, start_time, status)
                SELECT DISTINCT run_id, 'reconciled_run', 0.0, 'COMPLETED'
                FROM acoustic_telemetry
                WHERE run_id NOT IN (SELECT run_id FROM production_runs);
            """)

    def start_run(
        self,
        run_id: str,
        project_id: str,
        book_title: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register the start of a production run."""
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO production_runs
                (run_id, project_id, book_title, start_time, status, config_json)
                VALUES (?, ?, ?, ?, 'RUNNING', ?);
                """,
                (
                    run_id,
                    project_id,
                    book_title,
                    time.time(),
                    json.dumps(config or {}, ensure_ascii=False),
                ),
            )

    def end_run(self, run_id: str, status: str = "SUCCESS", error: str = "") -> None:
        """Register the completion or failure of a production run."""
        now = time.time()
        with self._lock, self._connection() as conn:
            row = conn.execute("SELECT start_time FROM production_runs WHERE run_id = ?", (run_id,)).fetchone()
            start_t = row["start_time"] if row else now
            total_dur = round(now - start_t, 2)
            conn.execute(
                """
                UPDATE production_runs
                SET end_time = ?, total_duration_sec = ?, status = ?, error_message = ?
                WHERE run_id = ?;
                """,
                (now, total_dur, status, error, run_id),
            )

    def record_stage(
        self,
        run_id: str,
        stage_name: str,
        stage_num: int,
        duration_sec: float,
        status: str = "SUCCESS",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record stage execution telemetry."""
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                INSERT INTO stage_telemetry
                (run_id, stage_name, stage_num, duration_sec, status, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    run_id,
                    stage_name,
                    stage_num,
                    round(duration_sec, 3),
                    status,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

    @contextlib.contextmanager
    def stage_timer(
        self,
        run_id: str,
        stage_name: str,
        stage_num: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Generator[None, None, None]:
        """Context manager to accurately time and record stage duration."""
        t0 = time.perf_counter()
        status = "SUCCESS"
        meta = dict(metadata or {})
        try:
            yield
        except Exception as e:
            status = "FAILED"
            meta["error"] = str(e)
            raise
        finally:
            elapsed = time.perf_counter() - t0
            self.record_stage(
                run_id=run_id,
                stage_name=stage_name,
                stage_num=stage_num,
                duration_sec=elapsed,
                status=status,
                metadata=meta,
            )

    def record_api_call(
        self,
        run_id: str,
        service: str,
        endpoint: str,
        status_code: int,
        latency_sec: float,
        is_rate_limit: bool = False,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        est_cost_usd: float = 0.0,
    ) -> None:
        """Record external API call latency, tokens, cost, and rate-limiting status."""
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                INSERT INTO api_telemetry
                (run_id, service, endpoint, status_code, latency_sec, is_rate_limit, prompt_tokens, completion_tokens, est_cost_usd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    run_id,
                    service,
                    endpoint,
                    status_code,
                    round(latency_sec, 3),
                    1 if is_rate_limit else 0,
                    prompt_tokens,
                    completion_tokens,
                    round(est_cost_usd, 6),
                ),
            )

    def record_acoustic_metrics(
        self,
        run_id: str,
        chapter_num: int,
        duration_sec: float,
        integrated_lufs: float,
        true_peak_dbtp: float,
        loudness_range_lu: float,
        phase_correlation: float,
    ) -> None:
        """Record master delivery acoustic parameters."""
        with self._lock, self._connection() as conn:
            conn.execute(
                """
                INSERT INTO acoustic_telemetry
                (run_id, chapter_num, duration_sec, integrated_lufs, true_peak_dbtp, loudness_range_lu, phase_correlation)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    run_id,
                    chapter_num,
                    round(duration_sec, 2),
                    round(integrated_lufs, 2),
                    round(true_peak_dbtp, 2),
                    round(loudness_range_lu, 2),
                    round(phase_correlation, 3),
                ),
            )

    def generate_report(self, run_id: str, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Synthesizes a structured JSON telemetry report aggregating stage timings,
        API performance, and acoustic deliverables.
        """
        with self._lock, self._connection() as conn:
            run = conn.execute("SELECT * FROM production_runs WHERE run_id = ?", (run_id,)).fetchone()
            if not run:
                raise ValueError(f"Run ID '{run_id}' not found in telemetry ledger.")

            stages = conn.execute(
                "SELECT * FROM stage_telemetry WHERE run_id = ? ORDER BY stage_num ASC, id ASC",
                (run_id,),
            ).fetchall()

            apis = conn.execute(
                "SELECT * FROM api_telemetry WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()

            acoustics = conn.execute(
                "SELECT * FROM acoustic_telemetry WHERE run_id = ? ORDER BY chapter_num ASC",
                (run_id,),
            ).fetchall()

        total_api_calls = len(apis)
        total_rate_limits = sum(1 for a in apis if a["is_rate_limit"] == 1)
        total_prompt_tokens = sum(a["prompt_tokens"] for a in apis)
        total_completion_tokens = sum(a["completion_tokens"] for a in apis)
        total_cost_usd = round(sum(a["est_cost_usd"] for a in apis), 4)
        avg_api_latency = round(sum(a["latency_sec"] for a in apis) / max(total_api_calls, 1), 3)

        report: Dict[str, Any] = {
            "schema_version": "1.0",
            "run_id": run["run_id"],
            "project_id": run["project_id"],
            "book_title": run["book_title"],
            "status": run["status"],
            "error_message": run["error_message"],
            "total_duration_sec": run["total_duration_sec"],
            "stages": [
                {
                    "stage_num": s["stage_num"],
                    "stage_name": s["stage_name"],
                    "duration_sec": s["duration_sec"],
                    "status": s["status"],
                    "metadata": json.loads(s["metadata_json"] or "{}"),
                }
                for s in stages
            ],
            "api_metrics": {
                "total_calls": total_api_calls,
                "rate_limits_429": total_rate_limits,
                "avg_latency_sec": avg_api_latency,
                "total_prompt_tokens": total_prompt_tokens,
                "total_completion_tokens": total_completion_tokens,
                "estimated_cost_usd": total_cost_usd,
            },
            "acoustic_deliverables": [
                {
                    "chapter_num": ac["chapter_num"],
                    "duration_sec": ac["duration_sec"],
                    "integrated_lufs": ac["integrated_lufs"],
                    "true_peak_dbtp": ac["true_peak_dbtp"],
                    "loudness_range_lu": ac["loudness_range_lu"],
                    "phase_correlation": ac["phase_correlation"],
                }
                for ac in acoustics
            ],
        }

        if output_path:
            out_file = Path(output_path).resolve()
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"[*] Telemetry report exported to {out_file}")

        return report


_global_telemetry_ledger: Optional[ProductionTelemetryLedger] = None
_ledger_lock = threading.Lock()


def get_telemetry_ledger(db_path: Optional[Path] = None) -> ProductionTelemetryLedger:
    """Return the thread-safe global ProductionTelemetryLedger instance."""
    global _global_telemetry_ledger
    with _ledger_lock:
        if _global_telemetry_ledger is None or db_path is not None:
            _global_telemetry_ledger = ProductionTelemetryLedger(db_path=db_path)
        return _global_telemetry_ledger
