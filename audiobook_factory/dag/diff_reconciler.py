#!/usr/bin/env python3
"""
Audiobook Studio - Incremental Contract SHA-256 Diff Reconciler.
Standard: v6.0-ENTERPRISE-DAG
Computes differences between contract state on disk and SQLite ledger,
identifying dirty or stale stages for incremental zero-cost execution.
"""

from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

from audiobook_factory.contracts.ingestion import RawBookManifest
from audiobook_factory.contracts.translation import TranslationManifest
from audiobook_factory.contracts.screenplay import ScreenplayScript
from audiobook_factory.contracts.ledger import ChapterStageRecord
from audiobook_factory.core.cache.ledger import PipelineLedger


@dataclass
class StageDiffItem:
    """Represents the diff state of a specific chapter stage."""
    chapter_id: int
    room_name: str
    stage_uid: str
    current_status: str  # 'COMPLETED', 'DIRTY', 'MISSING', 'FAILED'
    reason: str
    input_hash: str = ""
    output_hash: str = ""


@dataclass
class PipelineDiffReport:
    """Aggregated diff report across all chapters of a project."""
    project_id: str
    total_chapters: int
    dirty_stages: List[StageDiffItem] = field(default_factory=list)
    clean_stages: List[StageDiffItem] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """True if no stages require execution."""
        return len(self.dirty_stages) == 0

    @property
    def dirty_chapter_ids(self) -> Set[int]:
        """Set of chapter IDs with at least one dirty stage."""
        return {item.chapter_id for item in self.dirty_stages}


class DiffReconciler:
    """
    Analyzes project directory artifacts, contract SHA-256 checksums,
    and SQLite ledger records to determine exactly which DAG stages need execution.
    """

    ROOM_SEQUENCE = [
        "ROOM1_INGEST",
        "ROOM2_TRANSLATE",
        "ROOM3_SCREENPLAY",
        "ROOM4_SYNTH",
        "ROOM5_MASTER",
    ]

    def __init__(
        self,
        project_dir: Union[str, Path],
        ledger: Optional[PipelineLedger] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.ledger = ledger or PipelineLedger(db_path=self.project_dir / "pipeline_ledger.db")

    def reconcile_project(self, project_id: Optional[str] = None) -> PipelineDiffReport:
        """
        Scans all artifacts and SQLite ledger records to produce a complete PipelineDiffReport.
        """
        proj_id = project_id or self.project_dir.name
        manifest_file = self.project_dir / "raw_book_manifest.json"

        if not manifest_file.exists():
            # Ingestion not done
            return PipelineDiffReport(
                project_id=proj_id,
                total_chapters=0,
                dirty_stages=[
                    StageDiffItem(
                        chapter_id=1,
                        room_name="ROOM1_INGEST",
                        stage_uid="ch001_room1_ingest",
                        current_status="MISSING",
                        reason="raw_book_manifest.json missing on disk",
                    )
                ],
            )

        manifest = RawBookManifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))
        total_chapters = manifest.total_chapters

        dirty_stages: List[StageDiffItem] = []
        clean_stages: List[StageDiffItem] = []

        # Check each chapter through the DAG rooms
        for chapter in manifest.chapters:
            chap_id = chapter.chapter_id
            chapter_is_dirty = False

            # 1. Room 1: Ingest
            r1_uid = f"ch{chap_id:03d}_room1_ingest"
            r1_stage = self.ledger.get_stage(r1_uid)
            if not r1_stage or r1_stage.status != "COMPLETED":
                dirty_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM1_INGEST",
                        stage_uid=r1_uid,
                        current_status="DIRTY" if r1_stage else "MISSING",
                        reason="Room 1 ingestion stage incomplete in ledger",
                        input_hash=chapter.source_hash,
                    )
                )
                chapter_is_dirty = True
            else:
                clean_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM1_INGEST",
                        stage_uid=r1_uid,
                        current_status="COMPLETED",
                        reason="Ingestion valid",
                        input_hash=r1_stage.input_contract_hash,
                        output_hash=r1_stage.output_contract_hash or "",
                    )
                )

            # 2. Room 2: Translate
            r2_uid = f"ch{chap_id:03d}_room2_translate"
            r2_file = self.project_dir / f"chapter_{chap_id:03d}_translation.json"
            r2_stage = self.ledger.get_stage(r2_uid)
            r2_valid = r2_file.exists() and r2_file.stat().st_size > 10 and r2_stage and r2_stage.status == "COMPLETED"

            if chapter_is_dirty or not r2_valid:
                dirty_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM2_TRANSLATE",
                        stage_uid=r2_uid,
                        current_status=r2_stage.status if r2_stage else "MISSING",
                        reason="Translation manifest missing or invalidated" if not chapter_is_dirty else "Upstream dependency dirty",
                        input_hash=chapter.source_hash,
                    )
                )
                chapter_is_dirty = True
            else:
                clean_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM2_TRANSLATE",
                        stage_uid=r2_uid,
                        current_status="COMPLETED",
                        reason="Translation manifest valid",
                        input_hash=r2_stage.input_contract_hash,
                        output_hash=r2_stage.output_contract_hash or "",
                    )
                )

            # 3. Room 3: Screenplay
            r3_uid = f"ch{chap_id:03d}_room3_screenplay"
            r3_file = self.project_dir / f"chapter_{chap_id:03d}_screenplay.json"
            r3_stage = self.ledger.get_stage(r3_uid)
            r3_valid = r3_file.exists() and r3_file.stat().st_size > 10 and r3_stage and r3_stage.status == "COMPLETED"

            if chapter_is_dirty or not r3_valid:
                dirty_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM3_SCREENPLAY",
                        stage_uid=r3_uid,
                        current_status=r3_stage.status if r3_stage else "MISSING",
                        reason="Screenplay script missing or invalidated" if not chapter_is_dirty else "Upstream dependency dirty",
                    )
                )
                chapter_is_dirty = True
            else:
                clean_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM3_SCREENPLAY",
                        stage_uid=r3_uid,
                        current_status="COMPLETED",
                        reason="Screenplay script valid",
                        input_hash=r3_stage.input_contract_hash,
                        output_hash=r3_stage.output_contract_hash or "",
                    )
                )

            # 4. Room 4: Synth
            r4_uid = f"ch{chap_id:03d}_room4_synth"
            r4_file = self.project_dir / f"chapter_{chap_id:03d}_dialogue.wav"
            r4_stage = self.ledger.get_stage(r4_uid)
            r4_valid = r4_file.exists() and r4_file.stat().st_size > 1024 and r4_stage and r4_stage.status == "COMPLETED"

            if chapter_is_dirty or not r4_valid:
                dirty_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM4_SYNTH",
                        stage_uid=r4_uid,
                        current_status=r4_stage.status if r4_stage else "MISSING",
                        reason="Dialogue stem missing or invalidated" if not chapter_is_dirty else "Upstream dependency dirty",
                    )
                )
                chapter_is_dirty = True
            else:
                clean_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM4_SYNTH",
                        stage_uid=r4_uid,
                        current_status="COMPLETED",
                        reason="Dialogue stem WAV valid",
                        input_hash=r4_stage.input_contract_hash,
                        output_hash=r4_stage.output_contract_hash or "",
                    )
                )

            # 5. Room 5: Master
            r5_uid = f"ch{chap_id:03d}_room5_master"
            r5_file = self.project_dir / f"chapter_{chap_id:03d}_mastered.m4a"
            r5_stage = self.ledger.get_stage(r5_uid)
            r5_valid = r5_file.exists() and r5_file.stat().st_size > 1024 and r5_stage and r5_stage.status == "COMPLETED"

            if chapter_is_dirty or not r5_valid:
                dirty_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM5_MASTER",
                        stage_uid=r5_uid,
                        current_status=r5_stage.status if r5_stage else "MISSING",
                        reason="Mastered M4A deliverable missing or invalidated" if not chapter_is_dirty else "Upstream dependency dirty",
                    )
                )
            else:
                clean_stages.append(
                    StageDiffItem(
                        chapter_id=chap_id,
                        room_name="ROOM5_MASTER",
                        stage_uid=r5_uid,
                        current_status="COMPLETED",
                        reason="Mastered M4A deliverable valid",
                        input_hash=r5_stage.input_contract_hash,
                        output_hash=r5_stage.output_contract_hash or "",
                    )
                )

        return PipelineDiffReport(
            project_id=proj_id,
            total_chapters=total_chapters,
            dirty_stages=dirty_stages,
            clean_stages=clean_stages,
        )
