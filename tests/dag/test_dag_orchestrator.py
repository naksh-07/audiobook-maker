#!/usr/bin/env python3
"""
Automated Integration Test Suite for DAG Pipeline Orchestrator & Diff Reconciler.
Standard: v6.0-ENTERPRISE-DAG
"""

import json
from pathlib import Path
import pytest

from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.core.cache.take_bank import TakeBank
from audiobook_factory.dag.diff_reconciler import DiffReconciler
from audiobook_factory.dag.orchestrator import DAGPipelineOrchestrator


class TestDAGOrchestrator:
    def test_end_to_end_dag_pipeline_execution(self, tmp_path: Path):
        proj_dir = tmp_path / "project"
        source_file = tmp_path / "saga.txt"
        source_file.write_text(
            "# Chapter 1: The Encounter\n\n"
            "Geralt drew his silver sword.\n"
            "Yennefer stood beside him in silence.\n\n"
            "# Chapter 2: The Battle\n\n"
            "The monster leaped from the dark cavern.\n"
            "Steel clashed against bone and blood.\n",
            encoding="utf-8"
        )

        ledger = PipelineLedger(db_path=proj_dir / "pipeline_ledger.db")
        take_bank = TakeBank(cache_dir=proj_dir / ".cache", ledger=ledger)
        orchestrator = DAGPipelineOrchestrator(
            project_dir=proj_dir,
            ledger=ledger,
            take_bank=take_bank,
        )

        # Run 1: Full pipeline execution
        res1 = orchestrator.run_pipeline(
            source_path=source_file,
            project_id="witcher_saga",
            title="Witcher Saga",
            author="Sapkowski",
            target_room="PACKAGE",
            fidelity="RAW_UNRATED",
        )

        assert res1.success is True
        assert res1.total_chapters == 2
        assert "ROOM1_INGEST" in res1.executed_stages
        assert "ch001_room2_translate" in res1.executed_stages
        assert "ch002_room2_translate" in res1.executed_stages
        assert "ch001_room3_screenplay" in res1.executed_stages
        assert "ch002_room3_screenplay" in res1.executed_stages
        assert "ch001_room4_synth" in res1.executed_stages
        assert "ch002_room4_synth" in res1.executed_stages
        assert "ch001_room5_master" in res1.executed_stages
        assert "ch002_room5_master" in res1.executed_stages
        assert "CONTAINER_PACKAGE" in res1.executed_stages
        assert res1.container_m4b_path is not None
        assert Path(res1.container_m4b_path).exists()

        # Run 2: Incremental execution without modifications -> All skipped
        res2 = orchestrator.run_pipeline(
            project_id="witcher_saga",
            target_room="PACKAGE",
            fidelity="RAW_UNRATED",
        )

        assert res2.success is True
        assert "ROOM1_INGEST" in res2.skipped_stages
        assert "ch001_room2_translate" in res2.skipped_stages
        assert "ch002_room2_translate" in res2.skipped_stages
        assert "ch001_room3_screenplay" in res2.skipped_stages
        assert "ch002_room3_screenplay" in res2.skipped_stages
        assert "ch001_room4_synth" in res2.skipped_stages
        assert "ch002_room4_synth" in res2.skipped_stages
        assert "ch001_room5_master" in res2.skipped_stages
        assert "ch002_room5_master" in res2.skipped_stages

        # Run 3: Surgically patch Chapter 2 translation beat
        orchestrator.translate_collective.patch_beat(
            chapter_id=2,
            beat_uid="ch02_beat001",
            patched_sentences=[
                {"translated_text": "राक्षस अंधेरी गुफा से बाहर कूद पड़ा।"},
                {"translated_text": "लोहे की तलवार हड्डियों और खून से टकराई।"},
            ],
            project_id="witcher_saga",
        )

        # Run 4: Incremental rerun after Chapter 2 patch -> Chapter 1 skipped, Chapter 2 re-run
        res3 = orchestrator.run_pipeline(
            project_id="witcher_saga",
            target_room="PACKAGE",
            fidelity="RAW_UNRATED",
        )

        assert res3.success is True
        # Chapter 1 stages must remain SKIPPED (0 re-synthesis)
        assert "ch001_room3_screenplay" in res3.skipped_stages
        assert "ch001_room4_synth" in res3.skipped_stages
        assert "ch001_room5_master" in res3.skipped_stages

        # Chapter 2 downstream stages must be EXECUTED
        assert "ch002_room3_screenplay" in res3.executed_stages
        assert "ch002_room4_synth" in res3.executed_stages
        assert "ch002_room5_master" in res3.executed_stages
        assert Path(res3.container_m4b_path).exists()

    def test_diff_reconciler_empty_directory(self, tmp_path: Path):
        empty_dir = tmp_path / "empty_project"
        empty_dir.mkdir(parents=True, exist_ok=True)
        reconciler = DiffReconciler(project_dir=empty_dir)

        report = reconciler.reconcile_project(project_id="empty")
        assert report.is_clean is False
        assert len(report.dirty_stages) == 1
        assert report.dirty_stages[0].room_name == "ROOM1_INGEST"
        assert report.dirty_stages[0].current_status == "MISSING"
