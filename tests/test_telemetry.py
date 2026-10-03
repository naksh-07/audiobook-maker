#!/usr/bin/env python3
"""
Tests for Production Telemetry Engine in audiobook_factory.telemetry
===================================================================
Verifies SQLite schema creation, WAL pragma enforcement, stage timers,
API call tracking, acoustic metrics recording, and JSON report generation.
"""

import json
import tempfile
import sqlite3
from pathlib import Path
import pytest

from audiobook_factory.telemetry import ProductionTelemetryLedger, get_telemetry_ledger


def test_telemetry_db_initialization_and_wal():
    """Verifies that ProductionTelemetryLedger creates tables with WAL mode and 30s busy timeout."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "telemetry.db"
        ledger = ProductionTelemetryLedger(db_path=db_path)

        assert db_path.exists()
        with ledger._connection() as conn:
            # Check WAL mode and busy timeout
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
            assert mode.lower() == "wal"
            assert timeout >= 30000

            # Verify tables exist
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
            assert "production_runs" in tables
            assert "stage_telemetry" in tables
            assert "api_telemetry" in tables
            assert "acoustic_telemetry" in tables


def test_stage_timer_and_recording():
    """Verifies that stage_timer context manager records stage execution and durations."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "telemetry.db"
        ledger = ProductionTelemetryLedger(db_path=db_path)
        run_id = "test_run_001"
        ledger.start_run(run_id, "proj-test", "The Test Novel", config={"dramatized": True})

        with ledger.stage_timer(run_id, "Document Extraction", 1, metadata={"pages": 42}):
            # Simulate work
            pass

        with ledger._connection() as conn:
            row = conn.execute("SELECT * FROM stage_telemetry WHERE run_id = ?", (run_id,)).fetchone()
            assert row is not None
            assert row["stage_name"] == "Document Extraction"
            assert row["stage_num"] == 1
            assert row["status"] == "SUCCESS"
            assert row["duration_sec"] >= 0.0
            meta = json.loads(row["metadata_json"])
            assert meta["pages"] == 42


def test_api_telemetry_and_rate_limits():
    """Verifies API call metrics, token counting, cost summation, and 429 detection."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "telemetry.db"
        ledger = ProductionTelemetryLedger(db_path=db_path)
        run_id = "test_run_002"
        ledger.start_run(run_id, "proj-test", "API Test Book")

        # Record normal TTS call
        ledger.record_api_call(
            run_id=run_id,
            service="gemini-tts",
            endpoint="synthesize",
            status_code=200,
            latency_sec=1.25,
            is_rate_limit=False,
            prompt_tokens=150,
            completion_tokens=400,
            est_cost_usd=0.0005,
        )

        # Record 429 rate limit spike
        ledger.record_api_call(
            run_id=run_id,
            service="gemini-tts",
            endpoint="synthesize",
            status_code=429,
            latency_sec=0.15,
            is_rate_limit=True,
            prompt_tokens=0,
            completion_tokens=0,
            est_cost_usd=0.0,
        )

        with ledger._connection() as conn:
            rows = conn.execute("SELECT * FROM api_telemetry WHERE run_id = ?", (run_id,)).fetchall()
            assert len(rows) == 2
            assert rows[0]["status_code"] == 200
            assert rows[1]["status_code"] == 429
            assert rows[1]["is_rate_limit"] == 1


def test_acoustic_telemetry_recording():
    """Verifies acoustic deliverables recording (LUFS, True Peak, LRA, phase)."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "telemetry.db"
        ledger = ProductionTelemetryLedger(db_path=db_path)
        run_id = "test_run_003"
        ledger.start_run(run_id, "proj-test", "Acoustic Test")

        ledger.record_acoustic_metrics(
            run_id=run_id,
            chapter_num=1,
            duration_sec=320.5,
            integrated_lufs=-19.2,
            true_peak_dbtp=-1.6,
            loudness_range_lu=7.4,
            phase_correlation=0.985,
        )

        with ledger._connection() as conn:
            row = conn.execute("SELECT * FROM acoustic_telemetry WHERE run_id = ?", (run_id,)).fetchone()
            assert row is not None
            assert row["chapter_num"] == 1
            assert row["integrated_lufs"] == -19.2
            assert row["true_peak_dbtp"] == -1.6
            assert row["phase_correlation"] == 0.985


def test_telemetry_report_json_export():
    """Verifies that generate_report outputs schema v1.0 JSON report with aggregated metrics."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        db_path = td_path / "telemetry.db"
        report_file = td_path / "TELEMETRY_REPORT.json"

        ledger = ProductionTelemetryLedger(db_path=db_path)
        run_id = "test_run_004"
        ledger.start_run(run_id, "proj-dastan", "Dastan-e-Hastinapur", config={"voice": "Aoede"})

        ledger.record_stage(run_id, "Extraction", 1, duration_sec=2.5, status="SUCCESS")
        ledger.record_stage(run_id, "Translation", 2, duration_sec=12.0, status="SUCCESS")
        ledger.record_api_call(run_id, "gemini-text", "generateContent", 200, 1.1, False, 1000, 500, 0.002)
        ledger.record_api_call(run_id, "gemini-text", "generateContent", 429, 0.1, True, 0, 0, 0.0)
        ledger.record_acoustic_metrics(run_id, 1, 115.66, -19.4, -1.7, 6.2, 0.980)

        ledger.end_run(run_id, status="SUCCESS")

        report = ledger.generate_report(run_id, output_path=report_file)

        assert report_file.exists()
        assert report["schema_version"] == "1.0"
        assert report["run_id"] == run_id
        assert report["project_id"] == "proj-dastan"
        assert len(report["stages"]) == 2
        assert report["api_metrics"]["total_calls"] == 2
        assert report["api_metrics"]["rate_limits_429"] == 1
        assert len(report["acoustic_deliverables"]) == 1
        assert report["acoustic_deliverables"][0]["phase_correlation"] == 0.980


def test_unregistered_run_auto_registration():
    """Verifies that calling telemetry logging without prior start_run auto-registers the run without FK errors."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "telemetry.db"
        ledger = ProductionTelemetryLedger(db_path=db_path)
        unregistered_run = "ghost_run_999"

        # Record metrics on a run that was never explicitly started via start_run
        ledger.record_acoustic_metrics(
            run_id=unregistered_run,
            chapter_num=2,
            duration_sec=120.0,
            integrated_lufs=-19.0,
            true_peak_dbtp=-1.5,
            loudness_range_lu=5.0,
            phase_correlation=0.85,
        )

        ledger.record_api_call(
            run_id=unregistered_run,
            service="gemini-tts",
            endpoint="synthesize",
            status_code=200,
            latency_sec=1.1,
        )

        with ledger._connection() as conn:
            run_row = conn.execute("SELECT * FROM production_runs WHERE run_id = ?", (unregistered_run,)).fetchone()
            assert run_row is not None
            assert run_row["status"] == "RUNNING"

            acoustic_row = conn.execute("SELECT * FROM acoustic_telemetry WHERE run_id = ?", (unregistered_run,)).fetchone()
            assert acoustic_row is not None
            assert acoustic_row["chapter_num"] == 2


def test_incident_telemetry_recording():
    """Verifies that incident_telemetry records 429s, safety trips, and error details."""
    with tempfile.TemporaryDirectory() as td:
        db_path = Path(td) / "telemetry.db"
        ledger = ProductionTelemetryLedger(db_path=db_path)
        run_id = "test_run_incident"

        ledger.record_incident(
            run_id=run_id,
            stage_name="LLM Generation",
            incident_type="RATE_LIMIT_429",
            details={"model": "gemini-2.5-flash", "wait_sec": 12.5},
        )

        with ledger._connection() as conn:
            rows = conn.execute("SELECT * FROM incident_telemetry WHERE run_id = ?", (run_id,)).fetchall()
            assert len(rows) == 1
            assert rows[0]["incident_type"] == "RATE_LIMIT_429"
            details = json.loads(rows[0]["details_json"])
            assert details["model"] == "gemini-2.5-flash"
            assert details["wait_sec"] == 12.5

