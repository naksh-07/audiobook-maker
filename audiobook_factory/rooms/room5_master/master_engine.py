#!/usr/bin/env python3
"""
Audiobook Factory - Room 5 Broadcast Vocal Mastering Engine.
Standard: v6.0-ENTERPRISE-DAG
Executes Two-Pass Measured Linear EBU R128 (-19.0 LUFS) vocal loudness normalization,
evaluates Gate 5.0 compliance, and packages chaptered .m4b deliverable containers.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from audiobook_factory.contracts.editorial import ChapterDialogueManifest
from audiobook_factory.contracts.mastering import (
    ChapterMarker,
    ContainerM4BManifest,
    LoudnessComplianceReport,
    MasterArtifact,
)
from audiobook_factory.contracts.ledger import (
    ChapterStageRecord,
    GateAuditRecord,
    StageArtifactRecord,
)
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.core.mastering.loudnorm import (
    MasteringSpec,
    TwoPassLoudnormEngine,
)
from audiobook_factory.core.mastering.packager import (
    ChapterMetadata,
    M4BPackager,
)


class BroadcastMasteringEngine:
    """
    Room 5 Broadcast Vocal Mastering Subsystem.
    Applies Two-Pass Measured Linear Loudnorm, verifies EBU R128 broadcast compliance,
    and packages complete chaptered M4B audiobook deliverables.
    """

    def __init__(
        self,
        project_dir: Union[str, Path] = "./projects/default",
        ledger: Optional[PipelineLedger] = None,
        spec: Optional[MasteringSpec] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.spec = spec or MasteringSpec()
        self.loudnorm_engine = TwoPassLoudnormEngine(spec=self.spec)
        self.packager = M4BPackager()

    def master_chapter(
        self,
        dialogue_manifest: ChapterDialogueManifest,
        project_id: str = "default",
        target_lufs: float = -19.0,
    ) -> Tuple[MasterArtifact, GateAuditRecord]:
        """
        Masters input dialogue stem WAV to certified EBU R128 M4A chapter deliverable.
        """
        in_wav = Path(dialogue_manifest.lossless_dialogue_wav_path)
        out_m4a = self.project_dir / f"chapter_{dialogue_manifest.chapter_id:03d}_mastered.m4a"

        self.spec.target_lufs = target_lufs
        artifact = self.loudnorm_engine.master_dialogue_stem(
            input_wav_path=in_wav,
            output_file_path=out_m4a,
            chapter_id=dialogue_manifest.chapter_id,
        )

        gate_audit = self.audit_gate_5_0(artifact)

        # Update SQLite Ledger if attached
        if self.ledger:
            stage_uid = f"ch{dialogue_manifest.chapter_id:03d}_room5_master"
            stage_rec = ChapterStageRecord(
                chapter_stage_uid=stage_uid,
                project_id=project_id,
                chapter_id=dialogue_manifest.chapter_id,
                room_name="ROOM5_MASTER",
                input_contract_hash=dialogue_manifest.compute_sha256_hash(),
                output_contract_hash=artifact.compute_sha256_hash(),
                status="COMPLETED" if gate_audit.decision == "PASSED" else "FAILED",
            )
            self.ledger.set_stage_status(stage_rec)
            self.ledger.record_gate_audit(gate_audit)

            artifact_rec = StageArtifactRecord(
                artifact_uid=f"art_master_ch{dialogue_manifest.chapter_id:03d}",
                chapter_stage_uid=stage_uid,
                artifact_type="MASTERED_M4A",
                relative_file_path=out_m4a.name,
                sha256_checksum=artifact.compute_sha256_hash(),
                file_size_bytes=out_m4a.stat().st_size,
            )
            self.ledger.register_artifact(artifact_rec)

        return artifact, gate_audit

    def audit_gate_5_0(
        self,
        artifact: MasterArtifact,
    ) -> GateAuditRecord:
        """Audits Gate 5.0: EBU R128 Integrated LUFS, True Peak Hard Ceiling, and LRA tolerances."""
        comp = artifact.compliance
        lufs_diff = abs(comp.integrated_lufs - self.spec.target_lufs)
        lufs_pass = (lufs_diff <= 0.6)
        tp_pass = (comp.true_peak_dbfs <= self.spec.true_peak_ceiling + 0.1)
        lra_pass = (comp.loudness_range_lu <= self.spec.loudness_range + 1.0)

        is_passed = lufs_pass and tp_pass and lra_pass and artifact.duration_sec > 0
        failures = []
        if not lufs_pass:
            failures.append(f"Integrated loudness {comp.integrated_lufs} LUFS breaches target {self.spec.target_lufs} LUFS.")
        if not tp_pass:
            failures.append(f"True Peak {comp.true_peak_dbfs} dBTP breaches ceiling {self.spec.true_peak_ceiling} dBTP.")
        if not lra_pass:
            failures.append(f"LRA {comp.loudness_range_lu} LU exceeds max dynamic range {self.spec.loudness_range} LU.")

        return GateAuditRecord(
            audit_uid=f"gate50_ch{artifact.chapter_id:03d}_{artifact.compute_sha256_hash()[:8]}",
            chapter_stage_uid=f"ch{artifact.chapter_id:03d}_room5_master",
            gate_name="GATE_5_0_MASTER",
            decision="PASSED" if is_passed else "FAILED",
            metrics={
                "integrated_lufs": comp.integrated_lufs,
                "true_peak_dbfs": comp.true_peak_dbfs,
                "loudness_range_lu": comp.loudness_range_lu,
                "is_compliant": is_passed,
            },
            failure_reasons=failures,
        )

    def package_audiobook(
        self,
        master_artifacts: List[MasterArtifact],
        book_id: str = "audiobook",
        title: str = "Audiobook",
        author: str = "Unknown Author",
        cover_image_path: Optional[Union[str, Path]] = None,
    ) -> ContainerM4BManifest:
        """
        Assembles all mastered chapter deliverables into single M4B container with cover art.
        """
        audio_files = [a.mastered_audio_path for a in master_artifacts]
        chapters_meta: List[ChapterMetadata] = []
        cum_time_ms = 0

        for a in master_artifacts:
            dur_ms = int(a.duration_sec * 1000.0)
            meta = ChapterMetadata(
                chapter_index=a.chapter_id,
                title=f"Chapter {a.chapter_id}",
                start_ms=cum_time_ms,
                end_ms=cum_time_ms + dur_ms,
            )
            chapters_meta.append(meta)
            cum_time_ms += dur_ms

        out_m4b_path = self.project_dir / f"{book_id}.m4b"
        return self.packager.package_container(
            audio_files=audio_files,
            chapters=chapters_meta,
            output_m4b_path=out_m4b_path,
            book_id=book_id,
            title=title,
            author=author,
            cover_image_path=cover_image_path,
        )
