#!/usr/bin/env python3
"""
Audiobook Factory - Room 4 Multi-Cast TTS & Dialogue Editorial Contracts.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import Field
from audiobook_factory.contracts.base import ContractBaseModel


class SegmentTakeMetadata(ContractBaseModel):
    """Metadata for an individual synthesized audio take stored in TakeBank."""
    segment_uid: str = Field(..., description="Screenplay segment ID")
    take_content_hash: str = Field(..., description="Deterministic SHA-256 take key")
    take_wav_path: str = Field(..., description="Absolute or relative path to WAV file")
    duration_sec: float = Field(..., gt=0.0, description="Measured take duration in seconds")
    sample_rate: int = Field(default=48000, description="Audio sample rate (48kHz)")
    channels: int = Field(default=1, description="1 for mono dialogue take")
    measured_lufs: Optional[float] = Field(default=None, description="Measured integrated LUFS of raw take")
    was_cache_hit: bool = Field(default=False, description="True if loaded from TakeBank cache")


class TimelineCueRecord(ContractBaseModel):
    """Accurate cue timing, micro-fades, and speaker attribution on master dialogue stem."""
    segment_uid: str = Field(..., description="Screenplay segment ID")
    speaker: str = Field(..., description="Character name or Narrator")
    start_time_sec: float = Field(..., ge=0.0, description="Timeline start offset in seconds")
    end_time_sec: float = Field(..., gt=0.0, description="Timeline end offset in seconds")
    fade_in_ms: float = Field(default=12.0, ge=0.0, description="Pre-speech Hann fade in ms")
    fade_out_ms: float = Field(default=18.0, ge=0.0, description="Post-speech Hann fade in ms")
    pause_after_sec: float = Field(default=0.4, ge=0.0, description="Contextual pause after turn")


class TimelineLedger(ContractBaseModel):
    """Complete assembled chronological timeline for a chapter."""
    chapter_id: int = Field(..., ge=1, description="Chapter index")
    total_duration_sec: float = Field(..., gt=0.0, description="Total stem duration in seconds")
    cues: List[TimelineCueRecord] = Field(default_factory=list, description="Ordered timeline cues")


class ChapterDialogueManifest(ContractBaseModel):
    """Manifest emitted by Room 4 Multi-Cast TTS & Editorial assembly."""
    chapter_id: int = Field(..., ge=1, description="Chapter index")
    script_hash: str = Field(..., description="SHA-256 checksum of source ScreenplayScript")
    lossless_dialogue_wav_path: str = Field(..., description="Path to assembled dialogue WAV")
    timeline_ledger: TimelineLedger = Field(..., description="Synchronized timeline ledger")
    takes: List[SegmentTakeMetadata] = Field(default_factory=list, description="TakeBank take records")
