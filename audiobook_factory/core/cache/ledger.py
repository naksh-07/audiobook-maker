#!/usr/bin/env python3
"""
Audiobook Factory - SQLite WAL Pipeline Ledger Manager.
Standard: v6.0-ENTERPRISE-DAG
Provides transaction-safe persistence for project metadata, stage execution state,
stage artifacts, Tier 1 TakeBank audio cache, and gate audit telemetry.
"""

from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional

from audiobook_factory.contracts.ledger import (
    ChapterStageRecord,
    GateAuditRecord,
    ProjectMetadataRecord,
    SegmentTakeCacheRecord,
    StageArtifactRecord,
)


class PipelineLedger:
    """
    SQLite WAL Manager for high-precision DAG stage status, artifact tracking,
    Tier 1 TakeBank metadata, and quality gate audit ledgers.
    """

    def __init__(self, db_path: str | Path = "pipeline_ledger.db"):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Yields an SQLite connection configured with WAL mode and foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initializes database schema and performance indexes."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- 1. Project Global Master Record
                CREATE TABLE IF NOT EXISTS project_metadata (
                    project_id TEXT PRIMARY KEY,
                    source_file_path TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author TEXT DEFAULT 'Unknown Author',
                    default_language TEXT DEFAULT 'hi',
                    book_bible_path TEXT NOT NULL,
                    cast_lock_path TEXT NOT NULL,
                    preset_name TEXT DEFAULT 'AUDIOBOOK_STUDIO',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                -- 2. Stage Execution DAG Ledger
                CREATE TABLE IF NOT EXISTS chapter_stage_ledger (
                    chapter_stage_uid TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    chapter_id INTEGER NOT NULL,
                    room_name TEXT NOT NULL CHECK(room_name IN ('ROOM1_INGEST', 'ROOM2_TRANSLATE', 'ROOM3_SCREENPLAY', 'ROOM4_SYNTH', 'ROOM5_MASTER')),
                    input_contract_hash TEXT NOT NULL,
                    output_contract_hash TEXT,
                    status TEXT NOT NULL CHECK(status IN ('IDLE', 'RUNNING', 'COMPLETED', 'FAILED', 'DIRTY', 'SKIPPED')),
                    error_message TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    FOREIGN KEY(project_id) REFERENCES project_metadata(project_id) ON DELETE CASCADE
                );

                -- 3. Stage Artifact Registry
                CREATE TABLE IF NOT EXISTS stage_artifacts (
                    artifact_uid TEXT PRIMARY KEY,
                    chapter_stage_uid TEXT NOT NULL,
                    artifact_type TEXT NOT NULL CHECK(artifact_type IN ('JSON_MANIFEST', 'SCREENPLAY_SCRIPT', 'DIALOGUE_WAV', 'TIMELINE_LEDGER', 'MASTERED_M4A', 'CONTAINER_M4B')),
                    relative_file_path TEXT NOT NULL,
                    sha256_checksum TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    schema_version TEXT DEFAULT '2.0',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(chapter_stage_uid) REFERENCES chapter_stage_ledger(chapter_stage_uid) ON DELETE CASCADE
                );

                -- 4. Tier 1 TakeBank Audio Cache
                CREATE TABLE IF NOT EXISTS segment_take_cache (
                    take_content_hash TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    chapter_id INTEGER NOT NULL,
                    segment_uid TEXT NOT NULL,
                    speaker TEXT NOT NULL,
                    voice_id TEXT NOT NULL,
                    formant_signature TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    take_wav_path TEXT NOT NULL,
                    duration_sec REAL NOT NULL,
                    measured_lufs REAL,
                    is_valid INTEGER DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(project_id) REFERENCES project_metadata(project_id) ON DELETE CASCADE
                );

                -- 5. Gate Audit Records & Forensic Metrics
                CREATE TABLE IF NOT EXISTS gate_audit_records (
                    audit_uid TEXT PRIMARY KEY,
                    chapter_stage_uid TEXT NOT NULL,
                    gate_name TEXT NOT NULL,
                    decision TEXT NOT NULL CHECK(decision IN ('PASSED', 'FAILED', 'REVIEW_REQUIRED')),
                    metrics_json TEXT NOT NULL,
                    failure_reasons_json TEXT DEFAULT '[]',
                    evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(chapter_stage_uid) REFERENCES chapter_stage_ledger(chapter_stage_uid) ON DELETE CASCADE
                );

                -- Performance Indexes
                CREATE INDEX IF NOT EXISTS idx_stage_lookup ON chapter_stage_ledger(project_id, chapter_id, room_name);
                CREATE INDEX IF NOT EXISTS idx_cache_hash ON segment_take_cache(take_content_hash);
                CREATE INDEX IF NOT EXISTS idx_cache_proj_chap ON segment_take_cache(project_id, chapter_id);
                CREATE INDEX IF NOT EXISTS idx_artifact_stage ON stage_artifacts(chapter_stage_uid);
                CREATE INDEX IF NOT EXISTS idx_gate_stage ON gate_audit_records(chapter_stage_uid);
            """)

    # -------------------------------------------------------------------------
    # Project Metadata CRUD
    # -------------------------------------------------------------------------

    def upsert_project(self, project: ProjectMetadataRecord) -> None:
        """Inserts or updates project master metadata."""
        now = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO project_metadata (
                    project_id, source_file_path, title, author, default_language,
                    book_bible_path, cast_lock_path, preset_name, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    source_file_path = excluded.source_file_path,
                    title = excluded.title,
                    author = excluded.author,
                    default_language = excluded.default_language,
                    book_bible_path = excluded.book_bible_path,
                    cast_lock_path = excluded.cast_lock_path,
                    preset_name = excluded.preset_name,
                    updated_at = excluded.updated_at;
            """, (
                project.project_id,
                project.source_file_path,
                project.title,
                project.author,
                project.default_language,
                project.book_bible_path,
                project.cast_lock_path,
                project.preset_name,
                project.created_at,
                now,
            ))

    def get_project(self, project_id: str) -> Optional[ProjectMetadataRecord]:
        """Retrieves project metadata by project_id."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM project_metadata WHERE project_id = ?;", (project_id,)
            ).fetchone()
            if not row:
                return None
            return ProjectMetadataRecord(
                project_id=row["project_id"],
                source_file_path=row["source_file_path"],
                title=row["title"],
                author=row["author"],
                default_language=row["default_language"],
                book_bible_path=row["book_bible_path"],
                cast_lock_path=row["cast_lock_path"],
                preset_name=row["preset_name"],
                created_at=str(row["created_at"]) if row["created_at"] else None,
                updated_at=str(row["updated_at"]) if row["updated_at"] else None,
            )

    def list_projects(self) -> List[ProjectMetadataRecord]:
        """Lists all registered projects."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM project_metadata ORDER BY updated_at DESC;").fetchall()
            return [
                ProjectMetadataRecord(
                    project_id=r["project_id"],
                    source_file_path=r["source_file_path"],
                    title=r["title"],
                    author=r["author"],
                    default_language=r["default_language"],
                    book_bible_path=r["book_bible_path"],
                    cast_lock_path=r["cast_lock_path"],
                    preset_name=r["preset_name"],
                    created_at=str(r["created_at"]) if r["created_at"] else None,
                    updated_at=str(r["updated_at"]) if r["updated_at"] else None,
                )
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Chapter Stage DAG Ledger CRUD
    # -------------------------------------------------------------------------

    def set_stage_status(self, stage: ChapterStageRecord) -> None:
        """Inserts or updates execution state of a chapter stage."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO chapter_stage_ledger (
                    chapter_stage_uid, project_id, chapter_id, room_name,
                    input_contract_hash, output_contract_hash, status,
                    error_message, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chapter_stage_uid) DO UPDATE SET
                    input_contract_hash = excluded.input_contract_hash,
                    output_contract_hash = excluded.output_contract_hash,
                    status = excluded.status,
                    error_message = excluded.error_message,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at;
            """, (
                stage.chapter_stage_uid,
                stage.project_id,
                stage.chapter_id,
                stage.room_name,
                stage.input_contract_hash,
                stage.output_contract_hash,
                stage.status,
                stage.error_message,
                stage.started_at,
                stage.completed_at,
            ))

    def get_stage(self, chapter_stage_uid: str) -> Optional[ChapterStageRecord]:
        """Retrieves a single chapter stage record."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM chapter_stage_ledger WHERE chapter_stage_uid = ?;", (chapter_stage_uid,)
            ).fetchone()
            if not row:
                return None
            return ChapterStageRecord(
                chapter_stage_uid=row["chapter_stage_uid"],
                project_id=row["project_id"],
                chapter_id=row["chapter_id"],
                room_name=row["room_name"],
                input_contract_hash=row["input_contract_hash"],
                output_contract_hash=row["output_contract_hash"],
                status=row["status"],
                error_message=row["error_message"],
                started_at=str(row["started_at"]) if row["started_at"] else None,
                completed_at=str(row["completed_at"]) if row["completed_at"] else None,
            )

    def get_chapter_stages(self, project_id: str, chapter_id: int) -> List[ChapterStageRecord]:
        """Retrieves all stages for a given project chapter ordered by stage progression."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM chapter_stage_ledger 
                WHERE project_id = ? AND chapter_id = ?
                ORDER BY chapter_stage_uid ASC;
            """, (project_id, chapter_id)).fetchall()
            return [
                ChapterStageRecord(
                    chapter_stage_uid=r["chapter_stage_uid"],
                    project_id=r["project_id"],
                    chapter_id=r["chapter_id"],
                    room_name=r["room_name"],
                    input_contract_hash=r["input_contract_hash"],
                    output_contract_hash=r["output_contract_hash"],
                    status=r["status"],
                    error_message=r["error_message"],
                    started_at=str(r["started_at"]) if r["started_at"] else None,
                    completed_at=str(r["completed_at"]) if r["completed_at"] else None,
                )
                for r in rows
            ]

    def get_dirty_stages(self, project_id: str) -> List[ChapterStageRecord]:
        """Retrieves all DIRTY or IDLE stages requiring execution for a project."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM chapter_stage_ledger 
                WHERE project_id = ? AND status IN ('DIRTY', 'IDLE', 'FAILED')
                ORDER BY chapter_id ASC, chapter_stage_uid ASC;
            """, (project_id,)).fetchall()
            return [
                ChapterStageRecord(
                    chapter_stage_uid=r["chapter_stage_uid"],
                    project_id=r["project_id"],
                    chapter_id=r["chapter_id"],
                    room_name=r["room_name"],
                    input_contract_hash=r["input_contract_hash"],
                    output_contract_hash=r["output_contract_hash"],
                    status=r["status"],
                    error_message=r["error_message"],
                    started_at=str(r["started_at"]) if r["started_at"] else None,
                    completed_at=str(r["completed_at"]) if r["completed_at"] else None,
                )
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Stage Artifact Registry CRUD
    # -------------------------------------------------------------------------

    def register_artifact(self, artifact: StageArtifactRecord) -> None:
        """Registers an artifact file emitted by a stage."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO stage_artifacts (
                    artifact_uid, chapter_stage_uid, artifact_type,
                    relative_file_path, sha256_checksum, file_size_bytes,
                    schema_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, '2.0', COALESCE(?, CURRENT_TIMESTAMP))
                ON CONFLICT(artifact_uid) DO UPDATE SET
                    relative_file_path = excluded.relative_file_path,
                    sha256_checksum = excluded.sha256_checksum,
                    file_size_bytes = excluded.file_size_bytes;
            """, (
                artifact.artifact_uid,
                artifact.chapter_stage_uid,
                artifact.artifact_type,
                artifact.relative_file_path,
                artifact.sha256_checksum,
                artifact.file_size_bytes,
                artifact.created_at,
            ))

    def get_artifacts_for_stage(self, chapter_stage_uid: str) -> List[StageArtifactRecord]:
        """Retrieves all registered artifacts for a given stage."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM stage_artifacts WHERE chapter_stage_uid = ?;
            """, (chapter_stage_uid,)).fetchall()
            return [
                StageArtifactRecord(
                    artifact_uid=r["artifact_uid"],
                    chapter_stage_uid=r["chapter_stage_uid"],
                    artifact_type=r["artifact_type"],
                    relative_file_path=r["relative_file_path"],
                    sha256_checksum=r["sha256_checksum"],
                    file_size_bytes=r["file_size_bytes"],
                    created_at=str(r["created_at"]) if r["created_at"] else None,
                )
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Tier 1 TakeBank Cache CRUD
    # -------------------------------------------------------------------------

    def put_take_cache(self, take: SegmentTakeCacheRecord) -> None:
        """Caches a synthesized take record in SQLite."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO segment_take_cache (
                    take_content_hash, project_id, chapter_id, segment_uid,
                    speaker, voice_id, formant_signature, text_content,
                    take_wav_path, duration_sec, measured_lufs, is_valid, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                ON CONFLICT(take_content_hash) DO UPDATE SET
                    take_wav_path = excluded.take_wav_path,
                    duration_sec = excluded.duration_sec,
                    measured_lufs = excluded.measured_lufs,
                    is_valid = excluded.is_valid;
            """, (
                take.take_content_hash,
                take.project_id,
                take.chapter_id,
                take.segment_uid,
                take.speaker,
                take.voice_id,
                take.formant_signature,
                take.text_content,
                take.take_wav_path,
                take.duration_sec,
                take.measured_lufs,
                1 if take.is_valid else 0,
                take.created_at,
            ))

    def get_take_cache(self, take_content_hash: str) -> Optional[SegmentTakeCacheRecord]:
        """Retrieves a cached take record by its SHA-256 hash if valid."""
        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT * FROM segment_take_cache WHERE take_content_hash = ? AND is_valid = 1;
            """, (take_content_hash,)).fetchone()
            if not row:
                return None
            return SegmentTakeCacheRecord(
                take_content_hash=row["take_content_hash"],
                project_id=row["project_id"],
                chapter_id=row["chapter_id"],
                segment_uid=row["segment_uid"],
                speaker=row["speaker"],
                voice_id=row["voice_id"],
                formant_signature=row["formant_signature"],
                text_content=row["text_content"],
                take_wav_path=row["take_wav_path"],
                duration_sec=row["duration_sec"],
                measured_lufs=row["measured_lufs"],
                is_valid=bool(row["is_valid"]),
                created_at=str(row["created_at"]) if row["created_at"] else None,
            )

    def invalidate_take_cache(self, take_content_hash: str) -> None:
        """Marks a cached take as invalid."""
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE segment_take_cache SET is_valid = 0 WHERE take_content_hash = ?;
            """, (take_content_hash,))

    # -------------------------------------------------------------------------
    # Gate Audit Records CRUD
    # -------------------------------------------------------------------------

    def record_gate_audit(self, audit: GateAuditRecord) -> None:
        """Stores a quality gate evaluation result."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO gate_audit_records (
                    audit_uid, chapter_stage_uid, gate_name,
                    decision, metrics_json, failure_reasons_json, evaluated_at
                ) VALUES (?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                ON CONFLICT(audit_uid) DO UPDATE SET
                    decision = excluded.decision,
                    metrics_json = excluded.metrics_json,
                    failure_reasons_json = excluded.failure_reasons_json,
                    evaluated_at = excluded.evaluated_at;
            """, (
                audit.audit_uid,
                audit.chapter_stage_uid,
                audit.gate_name,
                audit.decision,
                json.dumps(audit.metrics, ensure_ascii=False),
                json.dumps(audit.failure_reasons, ensure_ascii=False),
                audit.evaluated_at,
            ))

    def get_gate_audits(self, chapter_stage_uid: str) -> List[GateAuditRecord]:
        """Retrieves all gate audits for a specific stage."""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM gate_audit_records WHERE chapter_stage_uid = ? ORDER BY evaluated_at ASC;
            """, (chapter_stage_uid,)).fetchall()
            return [
                GateAuditRecord(
                    audit_uid=r["audit_uid"],
                    chapter_stage_uid=r["chapter_stage_uid"],
                    gate_name=r["gate_name"],
                    decision=r["decision"],
                    metrics=json.loads(r["metrics_json"]) if r["metrics_json"] else {},
                    failure_reasons=json.loads(r["failure_reasons_json"]) if r["failure_reasons_json"] else [],
                    evaluated_at=str(r["evaluated_at"]) if r["evaluated_at"] else None,
                )
                for r in rows
            ]
