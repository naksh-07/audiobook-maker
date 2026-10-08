#!/usr/bin/env python3
"""
Audiobook Studio - Enterprise Multi-Room DAG Pipeline Orchestrator.
Standard: v6.0-ENTERPRISE-DAG
Coordinates Room 1 through Room 5 subsystems, executing incremental runs,
managing transaction-safe SQLite checkpoints, and halting on gate breaches.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from audiobook_factory.contracts.ingestion import RawBookManifest
from audiobook_factory.contracts.lore import BookBible, CastLock
from audiobook_factory.contracts.translation import TranslationManifest
from audiobook_factory.contracts.screenplay import ScreenplayScript
from audiobook_factory.contracts.editorial import ChapterDialogueManifest
from audiobook_factory.contracts.mastering import ContainerM4BManifest, MasterArtifact
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.core.cache.take_bank import TakeBank
from audiobook_factory.dag.diff_reconciler import DiffReconciler, PipelineDiffReport
from audiobook_factory.rooms.room1_ingest.engine import IngestionEngine
from audiobook_factory.rooms.room2_translate.collective import TranslationCollective
from audiobook_factory.rooms.room3_screenplay.dramaturge import ScreenplayDramaturge
from audiobook_factory.rooms.room4_synth.synth_engine import SynthesisAndEditorialEngine
from audiobook_factory.rooms.room5_master.master_engine import BroadcastMasteringEngine


@dataclass
class PipelineExecutionResult:
    """Execution outcome summary for a pipeline run."""
    project_id: str
    success: bool
    total_chapters: int
    executed_stages: List[str] = field(default_factory=list)
    skipped_stages: List[str] = field(default_factory=list)
    failed_stages: List[str] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)
    container_m4b_path: Optional[str] = None
    error_message: Optional[str] = None


class DAGPipelineOrchestrator:
    """
    Central DAG Pipeline Orchestrator for Audiobook Studio.
    Automates end-to-end execution across Room 1 to Room 5 with incremental diff gating.
    """

    def __init__(
        self,
        project_dir: Union[str, Path],
        ledger: Optional[PipelineLedger] = None,
        take_bank: Optional[TakeBank] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger or PipelineLedger(db_path=self.project_dir / "pipeline_ledger.db")
        self.take_bank = take_bank or TakeBank(cache_dir=self.project_dir / ".cache", ledger=self.ledger)

        # Subsystems
        self.ingest_engine = IngestionEngine(project_dir=self.project_dir, ledger=self.ledger)
        self.translate_collective = TranslationCollective(project_dir=self.project_dir, ledger=self.ledger)
        self.screenplay_dramaturge = ScreenplayDramaturge(project_dir=self.project_dir, ledger=self.ledger)
        self.synth_engine = SynthesisAndEditorialEngine(
            project_dir=self.project_dir,
            take_bank=self.take_bank,
            ledger=self.ledger,
        )
        self.master_engine = BroadcastMasteringEngine(project_dir=self.project_dir, ledger=self.ledger)
        self.diff_reconciler = DiffReconciler(project_dir=self.project_dir, ledger=self.ledger)

    def run_pipeline(
        self,
        source_path: Optional[Union[str, Path]] = None,
        project_id: Optional[str] = None,
        title: Optional[str] = None,
        author: str = "Unknown Author",
        chapters: Optional[List[int]] = None,
        target_room: str = "PACKAGE",
        fidelity: str = "RAW_UNRATED",
        max_workers: int = 4,
        cover_image_path: Optional[Union[str, Path]] = None,
        fail_fast: bool = True,
    ) -> PipelineExecutionResult:
        """
        Executes complete or incremental DAG pipeline through to target_room.
        """
        proj_id = project_id or self.project_dir.name
        manifest_file = self.project_dir / "raw_book_manifest.json"

        executed_stages: List[str] = []
        skipped_stages: List[str] = []
        failed_stages: List[str] = []
        artifacts: Dict[str, str] = {}

        # ---------------------------------------------------------------------
        # 1. Room 1: Ingestion
        # ---------------------------------------------------------------------
        manifest: Optional[RawBookManifest] = None
        bible: Optional[BookBible] = None
        cast_lock: Optional[CastLock] = None

        if source_path:
            src_p = Path(source_path).resolve()
            manifest, bible, cast_lock, gate01 = self.ingest_engine.process_source(
                source_path=src_p,
                book_id=proj_id,
                title=title,
                author=author,
                fidelity_tier=fidelity,
            )
            executed_stages.append("ROOM1_INGEST")
            if gate01.decision != "PASSED" and fail_fast:
                return PipelineExecutionResult(
                    project_id=proj_id,
                    success=False,
                    total_chapters=manifest.total_chapters if manifest else 0,
                    executed_stages=executed_stages,
                    failed_stages=["ROOM1_INGEST"],
                    error_message=f"Gate 0.1 Ingestion audit failed: {gate01.failure_reasons}",
                )
        elif manifest_file.exists():
            manifest = RawBookManifest.model_validate_json(manifest_file.read_text(encoding="utf-8"))
            bible_f = self.project_dir / "book_bible.json"
            cast_f = self.project_dir / "cast_lock.json"
            bible = BookBible.model_validate_json(bible_f.read_text(encoding="utf-8")) if bible_f.exists() else None
            cast_lock = CastLock.model_validate_json(cast_f.read_text(encoding="utf-8")) if cast_f.exists() else None
            skipped_stages.append("ROOM1_INGEST")
        else:
            return PipelineExecutionResult(
                project_id=proj_id,
                success=False,
                total_chapters=0,
                failed_stages=["ROOM1_INGEST"],
                error_message="No source file provided and raw_book_manifest.json does not exist.",
            )

        artifacts["manifest"] = str(manifest_file)
        if target_room == "ROOM1_INGEST":
            return PipelineExecutionResult(
                project_id=proj_id,
                success=True,
                total_chapters=manifest.total_chapters,
                executed_stages=executed_stages,
                skipped_stages=skipped_stages,
                artifacts=artifacts,
            )

        # ---------------------------------------------------------------------
        # 2. Diff Reconciliation & Incremental Scheduling
        # ---------------------------------------------------------------------
        diff_report = self.diff_reconciler.reconcile_project(project_id=proj_id)
        target_chapters = chapters or [c.chapter_id for c in manifest.chapters]

        mastered_artifacts: List[MasterArtifact] = []

        for ch_record in manifest.chapters:
            chap_id = ch_record.chapter_id
            if chap_id not in target_chapters:
                continue

            # Check if stages are dirty for this chapter
            dirty_rooms = {
                item.room_name for item in diff_report.dirty_stages if item.chapter_id == chap_id
            }

            # -----------------------------------------------------------------
            # Room 2: Translation
            # -----------------------------------------------------------------
            trans_file = self.project_dir / f"chapter_{chap_id:03d}_translation.json"
            trans_manifest: Optional[TranslationManifest] = None

            if "ROOM2_TRANSLATE" in dirty_rooms or not trans_file.exists():
                trans_manifest, gate10 = self.translate_collective.translate_chapter(
                    chapter=ch_record,
                    bible=bible,
                    mode=fidelity,
                    project_id=proj_id,
                )
                executed_stages.append(f"ch{chap_id:03d}_room2_translate")
                if gate10.decision != "PASSED" and fail_fast:
                    failed_stages.append(f"ch{chap_id:03d}_room2_translate")
                    return PipelineExecutionResult(
                        project_id=proj_id,
                        success=False,
                        total_chapters=manifest.total_chapters,
                        executed_stages=executed_stages,
                        failed_stages=failed_stages,
                        error_message=f"Gate 1.0 Translation audit failed on Chapter {chap_id}: {gate10.failure_reasons}",
                    )
            else:
                trans_manifest = TranslationManifest.model_validate_json(trans_file.read_text(encoding="utf-8"))
                skipped_stages.append(f"ch{chap_id:03d}_room2_translate")

            artifacts[f"ch{chap_id:03d}_translation"] = str(trans_file)
            if target_room == "ROOM2_TRANSLATE":
                continue

            # -----------------------------------------------------------------
            # Room 3: Screenplay
            # -----------------------------------------------------------------
            script_file = self.project_dir / f"chapter_{chap_id:03d}_screenplay.json"
            script: Optional[ScreenplayScript] = None

            if "ROOM3_SCREENPLAY" in dirty_rooms or not script_file.exists():
                script, gate20 = self.screenplay_dramaturge.build_screenplay(
                    manifest=trans_manifest,
                    cast_lock=cast_lock,
                    project_id=proj_id,
                )
                executed_stages.append(f"ch{chap_id:03d}_room3_screenplay")
                if gate20.decision != "PASSED" and fail_fast:
                    failed_stages.append(f"ch{chap_id:03d}_room3_screenplay")
                    return PipelineExecutionResult(
                        project_id=proj_id,
                        success=False,
                        total_chapters=manifest.total_chapters,
                        executed_stages=executed_stages,
                        failed_stages=failed_stages,
                        error_message=f"Gate 2.0 Anti-Swap audit failed on Chapter {chap_id}: {gate20.failure_reasons}",
                    )
            else:
                script = ScreenplayScript.model_validate_json(script_file.read_text(encoding="utf-8"))
                skipped_stages.append(f"ch{chap_id:03d}_room3_screenplay")

            artifacts[f"ch{chap_id:03d}_screenplay"] = str(script_file)
            if target_room == "ROOM3_SCREENPLAY":
                continue

            # -----------------------------------------------------------------
            # Room 4: TTS & Editorial Dialogue Stem
            # -----------------------------------------------------------------
            stem_file = self.project_dir / f"chapter_{chap_id:03d}_dialogue.wav"
            dialogue_manifest: Optional[ChapterDialogueManifest] = None

            if "ROOM4_SYNTH" in dirty_rooms or not stem_file.exists():
                dialogue_manifest, gate40 = self.synth_engine.synthesize_chapter(
                    script=script,
                    project_id=proj_id,
                    max_workers=max_workers,
                )
                executed_stages.append(f"ch{chap_id:03d}_room4_synth")
                if gate40.decision != "PASSED" and fail_fast:
                    failed_stages.append(f"ch{chap_id:03d}_room4_synth")
                    return PipelineExecutionResult(
                        project_id=proj_id,
                        success=False,
                        total_chapters=manifest.total_chapters,
                        executed_stages=executed_stages,
                        failed_stages=failed_stages,
                        error_message=f"Gate 4.0 Audio audit failed on Chapter {chap_id}: {gate40.failure_reasons}",
                    )
            else:
                # Build lightweight manifest from existing stem
                from audiobook_factory.contracts.editorial import TimelineCueRecord, TimelineLedger
                dialogue_manifest = ChapterDialogueManifest(
                    chapter_id=chap_id,
                    script_hash=script.compute_sha256_hash(),
                    lossless_dialogue_wav_path=str(stem_file),
                    timeline_ledger=TimelineLedger(chapter_id=chap_id, total_duration_sec=1.0, cues=[]),
                    takes=[],
                )
                skipped_stages.append(f"ch{chap_id:03d}_room4_synth")

            artifacts[f"ch{chap_id:03d}_dialogue"] = str(stem_file)
            if target_room == "ROOM4_SYNTH":
                continue

            # -----------------------------------------------------------------
            # Room 5: Broadcast Mastering
            # -----------------------------------------------------------------
            master_file = self.project_dir / f"chapter_{chap_id:03d}_mastered.m4a"
            master_art: Optional[MasterArtifact] = None

            if "ROOM5_MASTER" in dirty_rooms or not master_file.exists():
                master_art, gate50 = self.master_engine.master_chapter(
                    dialogue_manifest=dialogue_manifest,
                    project_id=proj_id,
                    target_lufs=-19.0,
                )
                executed_stages.append(f"ch{chap_id:03d}_room5_master")
                if gate50.decision != "PASSED" and fail_fast:
                    failed_stages.append(f"ch{chap_id:03d}_room5_master")
                    return PipelineExecutionResult(
                        project_id=proj_id,
                        success=False,
                        total_chapters=manifest.total_chapters,
                        executed_stages=executed_stages,
                        failed_stages=failed_stages,
                        error_message=f"Gate 5.0 Broadcast Mastering audit failed on Chapter {chap_id}: {gate50.failure_reasons}",
                    )
            else:
                from audiobook_factory.contracts.mastering import LoudnessComplianceReport
                master_art = MasterArtifact(
                    chapter_id=chap_id,
                    mastered_audio_path=str(master_file),
                    duration_sec=10.0,
                    compliance=LoudnessComplianceReport(
                        integrated_lufs=-19.0,
                        true_peak_dbfs=-2.0,
                        loudness_range_lu=5.0,
                        is_compliant=True,
                    ),
                )
                skipped_stages.append(f"ch{chap_id:03d}_room5_master")

            artifacts[f"ch{chap_id:03d}_mastered"] = str(master_file)
            mastered_artifacts.append(master_art)

        # ---------------------------------------------------------------------
        # 3. Room 5 Packager: M4B Container
        # ---------------------------------------------------------------------
        container_m4b: Optional[str] = None
        if target_room == "PACKAGE" and len(mastered_artifacts) > 0:
            m4b_manifest = self.master_engine.package_audiobook(
                master_artifacts=mastered_artifacts,
                book_id=proj_id,
                title=title or manifest.title,
                author=author or manifest.author,
                cover_image_path=cover_image_path,
            )
            container_m4b = m4b_manifest.container_m4b_path
            artifacts["container_m4b"] = container_m4b
            executed_stages.append("CONTAINER_PACKAGE")

        return PipelineExecutionResult(
            project_id=proj_id,
            success=len(failed_stages) == 0,
            total_chapters=manifest.total_chapters,
            executed_stages=executed_stages,
            skipped_stages=skipped_stages,
            failed_stages=failed_stages,
            artifacts=artifacts,
            container_m4b_path=container_m4b,
        )
