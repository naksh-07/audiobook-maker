#!/usr/bin/env python3
"""
Audiobook Factory - Ledger, DAG Stage, and Quality Gate Contracts.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import Field
from audiobook_factory.contracts.base import ContractBaseModel


class ProjectMetadataRecord(ContractBaseModel):
    """Global master record for an audiobook production project in SQLite."""
    project_id: str = Field(..., description="Unique slugified project ID")
    source_file_path: str = Field(..., description="Absolute path to input source book/file")
    title: str = Field(..., description="Book or podcast title")
    author: str = Field(default="Unknown Author", description="Author or host name")
    default_language: str = Field(default="hi", description="Primary target language code")
    book_bible_path: str = Field(default="", description="Path to book_bible.json")
    cast_lock_path: str = Field(default="", description="Path to cast_lock.json")
    preset_name: str = Field(default="AUDIOBOOK_STUDIO", description="Active DAG preset")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp")
    updated_at: Optional[str] = Field(default=None, description="ISO timestamp")


class ChapterStageRecord(ContractBaseModel):
    """Atomic stage status record for a single chapter in the DAG."""
    chapter_stage_uid: str = Field(..., description="Deterministic stage UID, e.g. 'ch003_room3_screenplay'")
    project_id: str = Field(..., description="Project slug")
    chapter_id: int = Field(..., ge=1, description="Chapter index")
    room_name: str = Field(
        ...,
        pattern="^(ROOM1_INGEST|ROOM2_TRANSLATE|ROOM3_SCREENPLAY|ROOM4_SYNTH|ROOM5_MASTER)$",
        description="Subsystem room identifier"
    )
    input_contract_hash: str = Field(..., description="SHA-256 hash of inbound contract")
    output_contract_hash: Optional[str] = Field(default=None, description="SHA-256 hash of outbound contract")
    status: str = Field(
        default="IDLE",
        pattern="^(IDLE|RUNNING|COMPLETED|FAILED|DIRTY|SKIPPED)$",
        description="State machine status"
    )
    error_message: Optional[str] = Field(default=None, description="Error trace if FAILED")
    started_at: Optional[str] = Field(default=None, description="ISO timestamp")
    completed_at: Optional[str] = Field(default=None, description="ISO timestamp")


class StageArtifactRecord(ContractBaseModel):
    """Registered immutable file artifact produced by a completed stage."""
    artifact_uid: str = Field(..., description="Unique artifact identifier")
    chapter_stage_uid: str = Field(..., description="References chapter_stage_ledger")
    artifact_type: str = Field(
        ...,
        pattern="^(JSON_MANIFEST|SCREENPLAY_SCRIPT|DIALOGUE_WAV|TIMELINE_LEDGER|MASTERED_M4A|CONTAINER_M4B)$",
        description="Artifact category"
    )
    relative_file_path: str = Field(..., description="Project-relative path to artifact file")
    sha256_checksum: str = Field(..., description="File SHA-256 checksum on disk")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp")


class SegmentTakeCacheRecord(ContractBaseModel):
    """Tier 1 TakeBank content-addressed take record in SQLite."""
    take_content_hash: str = Field(..., description="SHA-256(text + speaker + voice + formants + speed + temp)")
    project_id: str = Field(..., description="Project slug")
    chapter_id: int = Field(..., ge=1, description="Chapter index")
    segment_uid: str = Field(..., description="Screenplay segment ID")
    speaker: str = Field(..., description="Speaker name")
    voice_id: str = Field(..., description="Voice identifier")
    formant_signature: str = Field(default="p0_t0_eq0", description="Formant signature")
    text_content: str = Field(..., description="Text content synthesized")
    take_wav_path: str = Field(..., description="Path to cached .wav file")
    duration_sec: float = Field(..., gt=0.0, description="Duration in seconds")
    measured_lufs: Optional[float] = Field(default=None, description="Measured integrated LUFS")
    is_valid: bool = Field(default=True, description="Cache validity flag")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp")


class GateAuditRecord(ContractBaseModel):
    """Deterministic quality gate evaluation report."""
    audit_uid: str = Field(..., description="Unique audit evaluation ID")
    chapter_stage_uid: str = Field(..., description="References chapter_stage_ledger")
    gate_name: str = Field(
        ...,
        pattern="^(GATE_0_1_INGEST|GATE_1_0_TRANSLATION|GATE_2_0_SCREENPLAY|GATE_4_0_AUDIO|GATE_5_0_MASTER)$",
        description="Quality gate identifier"
    )
    decision: str = Field(
        ...,
        pattern="^(PASSED|FAILED|REVIEW_REQUIRED)$",
        description="Quality gate pass/fail decision"
    )
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Numerical & boolean metrics")
    failure_reasons: List[str] = Field(default_factory=list, description="Descriptions of any violations")
    evaluated_at: Optional[str] = Field(default=None, description="ISO timestamp")
