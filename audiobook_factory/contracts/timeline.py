#!/usr/bin/env python3
"""
Audiobook Factory - Timeline Contracts (Gate 4.5).
Defines TimelineSegment and TimelineLedger for sample-accurate audio transcript
and millisecond timeline tracking.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class TimelineSegment(BaseModel):
    """
    Sample-accurate audio transcript & millisecond timeline entry (Gate 4.5).
    Formed immediately following speech synthesis to provide an immutable, auditable millisecond map.
    Preserves the full Devanagari/Hindi transcript text without truncation.
    """
    model_config = ConfigDict(extra="ignore")

    uid: Optional[str] = Field(default=None, description="Matching ScreenplaySegment UID")

    segment_index: int = Field(..., ge=1, description="1-indexed sequence number matching ScreenplaySegment")
    speaker: str = Field(..., description="Canonical English character name matching CharacterRoster")
    text: str = Field(..., min_length=1, description="Complete unabridged speech text spoken in this chunk")
    audio_file: str = Field(..., description="Filename or relative path to the generated WAV chunk")
    duration_ms: int = Field(..., ge=0, description="Exact sample duration in milliseconds")
    start_ms: int = Field(..., ge=0, description="Cumulative timeline start timestamp in milliseconds")
    end_ms: int = Field(..., ge=0, description="Cumulative timeline end timestamp in milliseconds")
    pause_after_ms: int = Field(default=400, ge=0, description="Silence gap padding after segment in milliseconds")
    emotion: str = Field(default="neutral", description="Dramatic emotion category")
    delivery_style: str = Field(default="neutral", description="Style of line delivery")
    spatial_pan: float = Field(default=0.0, ge=-1.0, le=1.0, description="Stereo azimuth pan from -1.0 to +1.0")
    acoustic_env: str = Field(default="temple_stone_hall", description="Acoustic room impulse setting")
    sfx_cues: List[str] = Field(default_factory=list, description="Associated physical Foley tags")
    music_mood: str = Field(default="neutral", description="Underlying musical mood")
    pre_roll_breath_ms: int = Field(default=0, ge=0, description="Organic breath intake Foley duration before speech")
    word_alignments: List[Dict[str, Any]] = Field(default_factory=list, description="Serialized WordAlignment objects containing exact start/end ms for every spoken token")

    @field_validator("sfx_cues", mode="before")
    @classmethod
    def normalize_sfx_cues(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        res = []
        for item in v:
            if isinstance(item, dict):
                tag = str(item.get("tag", item.get("name", item.get("sfx", ""))))
                if tag:
                    res.append(tag)
            elif isinstance(item, str) and item.strip():
                res.append(item.strip())
        return res


class TimelineLedger(BaseModel):
    """
    Master Timeline & Audio Transcript Ledger (Gate 4.5).
    Strictly read-only source-of-truth for the Audio Drama Director and Foley Designer agents
    to lock BGM cue timestamps, dynamic ducking envelopes, and tactile SFX placement down to the millisecond.
    """
    model_config = ConfigDict(extra="ignore")

    ledger_version: str = Field(default="2.0", description="Ledger schema specification version")
    project_id: str = Field(default="", description="Associated project identifier")
    chapter_id: str = Field(..., description="Unique chapter identifier (e.g. 'chapter_005')")
    total_segments: int = Field(..., ge=0, description="Total number of speech segments")
    total_dialogue_duration_ms: int = Field(..., ge=0, description="Sum of raw speech audio durations in milliseconds")
    total_timeline_duration_ms: int = Field(..., ge=0, description="Total chapter timeline duration including pauses in milliseconds")
    total_silence_duration_ms: int = Field(default=0, ge=0, description="Sum of dialogue pauses in milliseconds")
    silence_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage of pause silence in vocal track")
    segments: List[TimelineSegment] = Field(default_factory=list, description="Chronological timeline segments")

    def get_segment(self, index: int) -> Optional[TimelineSegment]:
        """Lookup a segment by 1-based index."""
        for s in self.segments:
            if s.segment_index == index:
                return s
        return None

    def find_segment_at_ms(self, timestamp_ms: int) -> Optional[TimelineSegment]:
        """Find the active speech segment at a given millisecond timestamp."""
        for s in self.segments:
            if s.start_ms <= timestamp_ms <= s.end_ms:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimelineLedger:
        return cls.model_validate(data)

    def to_json(self, indent: int = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> TimelineLedger:
        return cls.model_validate_json(json_str)

    @classmethod
    def from_file(cls, path: str | Path) -> TimelineLedger:
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())
