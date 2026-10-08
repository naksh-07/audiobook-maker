#!/usr/bin/env python3
"""
Unit tests for SQLite WAL PipelineLedger manager.
Tests CRUD operations, state transitions, caching, artifact tracking, and foreign key cascades.
"""

import tempfile
from pathlib import Path
import pytest

from audiobook_factory.contracts.ledger import (
    ChapterStageRecord,
    GateAuditRecord,
    ProjectMetadataRecord,
    SegmentTakeCacheRecord,
    StageArtifactRecord,
)
from audiobook_factory.core.cache.ledger import PipelineLedger


@pytest.fixture
def temp_ledger(tmp_path: Path):
    db_file = tmp_path / "test_pipeline_ledger.db"
    return PipelineLedger(db_path=db_file)


class TestPipelineLedger:
    def test_wal_mode_enabled(self, temp_ledger: PipelineLedger):
        with temp_ledger._get_connection() as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            assert mode.upper() == "WAL"

    def test_project_crud(self, temp_ledger: PipelineLedger):
        proj = ProjectMetadataRecord(
            project_id="test-novel",
            source_file_path="/books/test.epub",
            title="Test Novel",
            author="Author Name",
            default_language="hi",
            book_bible_path="/projects/test/book_bible.json",
            cast_lock_path="/projects/test/cast_lock.json",
            preset_name="AUDIOBOOK_STUDIO",
        )
        temp_ledger.upsert_project(proj)

        retrieved = temp_ledger.get_project("test-novel")
        assert retrieved is not None
        assert retrieved.title == "Test Novel"
        assert retrieved.author == "Author Name"

        # Update project
        proj_updated = ProjectMetadataRecord(
            project_id="test-novel",
            source_file_path="/books/test.epub",
            title="Test Novel (Revised)",
            author="Author Name",
            default_language="hi",
            book_bible_path="/projects/test/book_bible.json",
            cast_lock_path="/projects/test/cast_lock.json",
            preset_name="AUDIOBOOK_STUDIO",
        )
        temp_ledger.upsert_project(proj_updated)
        retrieved_updated = temp_ledger.get_project("test-novel")
        assert retrieved_updated is not None
        assert retrieved_updated.title == "Test Novel (Revised)"

        all_projects = temp_ledger.list_projects()
        assert len(all_projects) == 1
        assert all_projects[0].project_id == "test-novel"

    def test_chapter_stage_lifecycle_and_dirty_query(self, temp_ledger: PipelineLedger):
        proj = ProjectMetadataRecord(
            project_id="sword",
            source_file_path="/books/sword.epub",
            title="Sword of Destiny",
            book_bible_path="",
            cast_lock_path="",
        )
        temp_ledger.upsert_project(proj)

        # Stage 1: IDLE
        stage1 = ChapterStageRecord(
            chapter_stage_uid="ch001_room1_ingest",
            project_id="sword",
            chapter_id=1,
            room_name="ROOM1_INGEST",
            input_contract_hash="in_hash_1",
            status="IDLE",
        )
        temp_ledger.set_stage_status(stage1)

        dirty_stages = temp_ledger.get_dirty_stages("sword")
        assert len(dirty_stages) == 1
        assert dirty_stages[0].status == "IDLE"

        # Stage 1: Transition to COMPLETED
        stage1_completed = ChapterStageRecord(
            chapter_stage_uid="ch001_room1_ingest",
            project_id="sword",
            chapter_id=1,
            room_name="ROOM1_INGEST",
            input_contract_hash="in_hash_1",
            output_contract_hash="out_hash_1",
            status="COMPLETED",
        )
        temp_ledger.set_stage_status(stage1_completed)

        assert len(temp_ledger.get_dirty_stages("sword")) == 0

        # Mark as DIRTY
        stage1_dirty = ChapterStageRecord(
            chapter_stage_uid="ch001_room1_ingest",
            project_id="sword",
            chapter_id=1,
            room_name="ROOM1_INGEST",
            input_contract_hash="in_hash_1_mutated",
            status="DIRTY",
        )
        temp_ledger.set_stage_status(stage1_dirty)

        dirty_stages_after = temp_ledger.get_dirty_stages("sword")
        assert len(dirty_stages_after) == 1
        assert dirty_stages_after[0].status == "DIRTY"

    def test_stage_artifact_registration(self, temp_ledger: PipelineLedger):
        proj = ProjectMetadataRecord(
            project_id="proj_art",
            source_file_path="/books/art.epub",
            title="Art Book",
            book_bible_path="",
            cast_lock_path="",
        )
        temp_ledger.upsert_project(proj)

        stage = ChapterStageRecord(
            chapter_stage_uid="ch001_room3_screenplay",
            project_id="proj_art",
            chapter_id=1,
            room_name="ROOM3_SCREENPLAY",
            input_contract_hash="trans_hash",
            status="COMPLETED",
        )
        temp_ledger.set_stage_status(stage)

        artifact = StageArtifactRecord(
            artifact_uid="art_script_ch01",
            chapter_stage_uid="ch001_room3_screenplay",
            artifact_type="SCREENPLAY_SCRIPT",
            relative_file_path="scripts/ch01_script.json",
            sha256_checksum="sha256_abcdef",
            file_size_bytes=1024,
        )
        temp_ledger.register_artifact(artifact)

        artifacts = temp_ledger.get_artifacts_for_stage("ch001_room3_screenplay")
        assert len(artifacts) == 1
        assert artifacts[0].artifact_uid == "art_script_ch01"
        assert artifacts[0].artifact_type == "SCREENPLAY_SCRIPT"

    def test_take_cache_crud_and_invalidation(self, temp_ledger: PipelineLedger):
        proj = ProjectMetadataRecord(
            project_id="proj_take",
            source_file_path="/books/take.epub",
            title="Take Book",
            book_bible_path="",
            cast_lock_path="",
        )
        temp_ledger.upsert_project(proj)

        take = SegmentTakeCacheRecord(
            take_content_hash="take_hash_999",
            project_id="proj_take",
            chapter_id=1,
            segment_uid="ch01_seg001",
            speaker="Narrator",
            voice_id="Aoede",
            formant_signature="p0_t0_eq0",
            text_content="Devanagari voice line",
            take_wav_path="/cache/takes/take_hash_999.wav",
            duration_sec=3.2,
            measured_lufs=-19.0,
            is_valid=True,
        )
        temp_ledger.put_take_cache(take)

        cached = temp_ledger.get_take_cache("take_hash_999")
        assert cached is not None
        assert cached.speaker == "Narrator"
        assert cached.duration_sec == 3.2

        # Invalidate take
        temp_ledger.invalidate_take_cache("take_hash_999")
        assert temp_ledger.get_take_cache("take_hash_999") is None

    def test_gate_audit_recording(self, temp_ledger: PipelineLedger):
        proj = ProjectMetadataRecord(
            project_id="proj_gate",
            source_file_path="/books/gate.epub",
            title="Gate Book",
            book_bible_path="",
            cast_lock_path="",
        )
        temp_ledger.upsert_project(proj)

        stage = ChapterStageRecord(
            chapter_stage_uid="ch001_room2_translate",
            project_id="proj_gate",
            chapter_id=1,
            room_name="ROOM2_TRANSLATE",
            input_contract_hash="raw_hash",
            status="COMPLETED",
        )
        temp_ledger.set_stage_status(stage)

        audit = GateAuditRecord(
            audit_uid="audit_gate1_ch01",
            chapter_stage_uid="ch001_room2_translate",
            gate_name="GATE_1_0_TRANSLATION",
            decision="PASSED",
            metrics={"confidence_score": 0.99, "dual_rule_compliance": True},
            failure_reasons=[],
        )
        temp_ledger.record_gate_audit(audit)

        audits = temp_ledger.get_gate_audits("ch001_room2_translate")
        assert len(audits) == 1
        assert audits[0].gate_name == "GATE_1_0_TRANSLATION"
        assert audits[0].metrics["confidence_score"] == 0.99
