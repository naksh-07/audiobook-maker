#!/usr/bin/env python3
"""
Audiobook Factory - Room 5 Broadcast Mastering & M4B Container Contracts.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import Field
from audiobook_factory.contracts.base import ContractBaseModel


class LoudnessComplianceReport(ContractBaseModel):
    """EBU R128 and True Peak compliance verification report."""
    integrated_lufs: float = Field(..., description="Measured integrated loudness (Target: -19.0 LUFS ±0.5)")
    true_peak_dbfs: float = Field(..., description="Measured True Peak (Hard ceiling: <= -1.5 dBTP)")
    loudness_range_lu: float = Field(..., description="Loudness range (Target: <= 6.5 LU)")
    threshold_lufs: float = Field(default=-70.0, description="Measurement threshold")
    is_compliant: bool = Field(..., description="True if within Audible/EBU R128 tolerances")


class MasterArtifact(ContractBaseModel):
    """Single-chapter mastered deliverable record."""
    chapter_id: int = Field(..., ge=1, description="Chapter index")
    mastered_audio_path: str = Field(..., description="Path to 48kHz / 24-bit mastered M4A/WAV")
    duration_sec: float = Field(..., gt=0.0, description="Total mastered duration in seconds")
    compliance: LoudnessComplianceReport = Field(..., description="Mastering compliance metrics")


class ChapterMarker(ContractBaseModel):
    """MP4 chapter navigation cue point."""
    chapter_index: int = Field(..., ge=1, description="Chapter number")
    title: str = Field(..., description="Chapter title")
    start_time_ms: int = Field(..., ge=0, description="Start time in milliseconds")
    end_time_ms: int = Field(..., gt=0, description="End time in milliseconds")


class ContainerM4BManifest(ContractBaseModel):
    """Final packaged full-book M4B container with chapter metadata and artwork."""
    book_id: str = Field(..., description="Project slug")
    container_m4b_path: str = Field(..., description="Path to .m4b deliverable container")
    total_duration_sec: float = Field(..., gt=0.0, description="Total audiobook duration in seconds")
    file_size_bytes: int = Field(..., gt=0, description="Container size on disk in bytes")
    cover_image_path: Optional[str] = Field(default=None, description="Embedded cover art image path")
    chapters: List[ChapterMarker] = Field(default_factory=list, description="Ordered chapter markers")
