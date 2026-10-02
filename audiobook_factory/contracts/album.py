#!/usr/bin/env python3
"""
Audiobook Factory - Album & Book Master Contracts.
Defines macro-tier contracts: BookPackagingSpecs, BookChapterMarker,
BookTableOfContents, BookVoiceRoster, GlobalLoreBible, and BookMasterManifest.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


class BookPackagingSpecs(BaseModel):
    """Macro-tier packaging specifications for final distribution container (e.g. M4B)."""
    model_config = ConfigDict(extra="ignore")

    cover_art_path: Optional[Path] = None
    codec: str = "aac"
    bitrate: str = "192k"
    sample_rate: int = 44100
    faststart: bool = True
    min_cover_resolution: int = 2400


class BookChapterMarker(BaseModel):
    """Sample-accurate chapter marker for publication table of contents."""
    model_config = ConfigDict(extra="ignore")

    chapter_index: int = Field(..., ge=1, description="1-indexed chapter sequence number")
    title: str = Field(..., description="Display title for the chapter")
    start_ms: int = Field(..., ge=0, description="Start offset on book timeline in milliseconds")
    end_ms: int = Field(..., ge=0, description="End offset on book timeline in milliseconds")
    duration_ms: int = Field(..., ge=0, description="Duration in milliseconds")
    integrated_lufs: float = Field(default=-19.0, description="Integrated loudness of chapter audio in LUFS")
    true_peak_dbfs: float = Field(default=-1.5, description="True peak ceiling of chapter audio in dBFS/dBTP")
    audio_file: Optional[Path] = Field(default=None, description="Path to mastered chapter audio file")


class BookTableOfContents(BaseModel):
    """Macro-level table of contents container for entire audiobook."""
    model_config = ConfigDict(extra="ignore")

    chapters: List[BookChapterMarker] = Field(default_factory=list, description="Ordered chapter markers")
    total_duration_ms: int = Field(default=0, ge=0, description="Total book duration in milliseconds")


class BookVoiceRoster(BaseModel):
    """Global cross-chapter voice casting map."""
    model_config = ConfigDict(extra="ignore")

    character_voices: Dict[str, str] = Field(default_factory=dict, description="Character to voice ID mapping")
    narrator_voice: str = Field(default="Charon", description="Global narrator voice ID")


class GlobalLoreBible(BaseModel):
    """Book-level lore, recurring terms, and canonical pronunciation lexicon."""
    model_config = ConfigDict(extra="ignore")

    lexicon: Dict[str, str] = Field(default_factory=dict, description="Canonical proper nouns to phonetic Devanagari spellings")
    series_title: Optional[str] = Field(default=None, description="Book series title")
    book_number: Optional[int] = Field(default=None, description="Volume or book number in series")


class BookMasterManifest(BaseModel):
    """
    Macro-Tier Book Master Manifest aggregating voice roster, lore bible, TOC, and packaging.
    Immutable top-level source of truth for full book packaging and Gate 6 verification.
    """
    model_config = ConfigDict(extra="ignore")

    title: str = Field(..., description="Canonical book title")
    author: str = Field(..., description="Canonical author name")
    narrator: str = Field(default="Charon", description="Lead narrator voice or name")
    translator_credits: Optional[str] = Field(default=None, description="Translator credits or persona")
    series_title: Optional[str] = Field(default=None, description="Series title")
    book_number: Optional[int] = Field(default=None, description="Book number in series")
    total_duration_ms: int = Field(default=0, ge=0, description="Cumulative audiobook duration in milliseconds")
    global_integrated_lufs: float = Field(default=-19.0, description="Target integrated loudness across full book")
    voice_roster: BookVoiceRoster = Field(default_factory=BookVoiceRoster, description="Global character voice casting map")
    lore_bible: GlobalLoreBible = Field(default_factory=GlobalLoreBible, description="Global lore bible and lexicon")
    toc: BookTableOfContents = Field(default_factory=BookTableOfContents, description="Table of contents chapter tree")
    packaging_specs: BookPackagingSpecs = Field(default_factory=BookPackagingSpecs, description="M4B packaging specifications")

    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to JSON-serializable dictionary."""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BookMasterManifest:
        """Instantiate BookMasterManifest from dictionary."""
        return cls.model_validate(data)

    def to_json(self, indent: int = 2) -> str:
        """Serialize BookMasterManifest to JSON string."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> BookMasterManifest:
        """Deserialize BookMasterManifest from JSON string."""
        return cls.model_validate_json(json_str)

    @classmethod
    def from_file(cls, path: str | Path) -> BookMasterManifest:
        """Load BookMasterManifest from file."""
        with open(path, "r", encoding="utf-8") as f:
            return cls.model_validate_json(f.read())
