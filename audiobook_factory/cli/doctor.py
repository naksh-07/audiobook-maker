#!/usr/bin/env python3
"""
Audiobook Studio - System Diagnostic Doctor.
Standard: v6.0-ENTERPRISE-DAG
Performs forensic diagnostic checks on FFmpeg, Gemini KeyPool, SQLite ledger, and DSP environment.
"""

from __future__ import annotations
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def check_ffmpeg() -> Dict[str, Any]:
    """Inspects FFmpeg installation and version."""
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        return {
            "status": "FAIL",
            "binary_path": None,
            "version": None,
            "error": "FFmpeg executable not found in PATH."
        }
    try:
        proc = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "Unknown version"
        return {
            "status": "OK",
            "binary_path": ffmpeg_bin,
            "version": first_line,
            "error": None,
        }
    except Exception as e:
        return {
            "status": "FAIL",
            "binary_path": ffmpeg_bin,
            "version": None,
            "error": str(e),
        }


def check_gemini_keypool(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Inspects Gemini API Key availability and KeyPool database."""
    env_keys = [k for k in ["GEMINI_API_KEY", "GOOGLE_API_KEY"] if os.environ.get(k)]
    pool_keys_count = 0
    pool_db_status = "NOT_FOUND"

    default_pool_db = db_path or Path("keys_pool.db")
    if default_pool_db.exists():
        try:
            conn = sqlite3.connect(str(default_pool_db))
            row = conn.execute("SELECT COUNT(*) FROM api_keys;").fetchone()
            pool_keys_count = row[0] if row else 0
            pool_db_status = "OK"
            conn.close()
        except Exception:
            pool_db_status = "CORRUPT"

    total_keys = len(env_keys) + pool_keys_count
    status = "OK" if total_keys > 0 else "WARN"

    return {
        "status": status,
        "env_keys_present": env_keys,
        "pool_db_status": pool_db_status,
        "pool_keys_count": pool_keys_count,
        "total_active_keys": total_keys,
    }


def check_ledger_db(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Inspects SQLite WAL pipeline ledger readiness."""
    target_db = db_path or Path("pipeline_ledger.db")
    if not target_db.exists():
        return {
            "status": "UNINITIALIZED",
            "db_path": str(target_db),
            "journal_mode": None,
            "tables": [],
        }
    try:
        conn = sqlite3.connect(str(target_db))
        conn.row_factory = sqlite3.Row
        j_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        conn.close()
        return {
            "status": "OK",
            "db_path": str(target_db),
            "journal_mode": j_mode.upper(),
            "tables": tables,
        }
    except Exception as e:
        return {
            "status": "FAIL",
            "db_path": str(target_db),
            "journal_mode": None,
            "error": str(e),
        }


def run_doctor_diagnostics(project_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Runs complete diagnostic check and returns structured report."""
    proj = project_dir or Path.cwd()
    report = {
        "platform": {
            "os": sys.platform,
            "python_version": sys.version.split()[0],
            "project_dir": str(proj.resolve()),
        },
        "ffmpeg": check_ffmpeg(),
        "keypool": check_gemini_keypool(),
        "ledger": check_ledger_db(proj / "pipeline_ledger.db"),
    }
    return report


def format_doctor_report(report: Dict[str, Any]) -> str:
    """Renders human-readable colored report."""
    lines = [
        "==================================================",
        " 🩺 Audiobook Studio System Diagnostic Doctor",
        " Standard: v6.0-ENTERPRISE-DAG",
        "==================================================",
        f" [Platform]: OS={report['platform']['os']} | Python={report['platform']['python_version']}",
        f" [Directory]: {report['platform']['project_dir']}",
        "--------------------------------------------------",
        f" [FFmpeg]: {report['ffmpeg']['status']}",
        f"   - Binary: {report['ffmpeg']['binary_path']}",
        f"   - Version: {report['ffmpeg']['version'] or report['ffmpeg']['error']}",
        "--------------------------------------------------",
        f" [KeyPool]: {report['keypool']['status']}",
        f"   - Total Keys: {report['keypool']['total_active_keys']}",
        f"   - Env Keys: {', '.join(report['keypool']['env_keys_present']) if report['keypool']['env_keys_present'] else 'None'}",
        f"   - Pool DB: {report['keypool']['pool_db_status']} ({report['keypool']['pool_keys_count']} keys)",
        "--------------------------------------------------",
        f" [Ledger DB]: {report['ledger']['status']}",
        f"   - Path: {report['ledger']['db_path']}",
        f"   - Journal: {report['ledger'].get('journal_mode', 'N/A')}",
        "==================================================",
    ]
    return "\n".join(lines)
