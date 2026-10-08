#!/usr/bin/env python3
"""
Unit tests for Room 1 Forensic Ingestion Subsystem (room1_ingest).
Tests AST parsing, BookBible/CastLock generation, and Gate 0.1 audit.
"""

from pathlib import Path
import pytest

from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.rooms.room1_ingest.engine import IngestionEngine


class TestRoom1Ingest:
    def test_ingestion_engine_end_to_end(self, tmp_path: Path):
        ledger = PipelineLedger(db_path=tmp_path / "test_ledger.db")
        proj_dir = tmp_path / "project"
        engine = IngestionEngine(project_dir=proj_dir, ledger=ledger)

        # Create sample novel file
        sample_book = tmp_path / "sample_novel.txt"
        sample_book.write_text(
            "# Chapter 1: The First Encounter\n\n"
            "Geralt walked into the tavern. The air was thick with smoke and roast meat.\n"
            "Yennefer was waiting by the fireplace.\n\n"
            "# Chapter 2: The Confrontation\n\n"
            "The stranger drew his silver sword. Silence fell over the crowd.\n",
            encoding="utf-8"
        )

        manifest, bible, cast_lock, gate_audit = engine.process_source(
            source_path=sample_book,
            book_id="witcher_sample",
            title="Witcher Sample",
            author="Sapkowski",
        )

        assert manifest.book_id == "witcher_sample"
        assert len(manifest.chapters) == 2
        assert len(manifest.chapters[0].sentences) >= 2
        assert manifest.chapters[0].sentences[0].sentence_id == "ch01_s001"
        assert gate_audit.decision == "PASSED"
        assert gate_audit.metrics["total_chapters"] == 2
        assert gate_audit.metrics["duplicate_sentence_count"] == 0

        assert (proj_dir / "raw_book_manifest.json").exists()
        assert (proj_dir / "book_bible.json").exists()
        assert (proj_dir / "cast_lock.json").exists()

        # Check ledger record
        stage = ledger.get_stage("ch001_room1_ingest")
        assert stage is not None
        assert stage.status == "COMPLETED"
