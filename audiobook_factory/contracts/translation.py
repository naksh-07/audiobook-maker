#!/usr/bin/env python3
"""
Audiobook Factory - Room 2 Translation Collective Contracts.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
from typing import List
from pydantic import Field
from audiobook_factory.contracts.base import ContractBaseModel


class TranslatedSentenceRecord(ContractBaseModel):
    """Represents a single translated sentence paired with source provenance."""
    sentence_id: str = Field(..., description="Must exactly match RawSentenceRecord.sentence_id")
    source_text: str = Field(..., description="Original language text")
    translated_text: str = Field(..., description="High-register Hindustani translation")
    terminology_hash: str = Field(default="", description="Hash of active BookBible terms used")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Model self-consistency score")
    user_override: bool = Field(default=False, description="True if manually edited by director")


class TranslationBeatRecord(ContractBaseModel):
    """Represents a dramatic narrative beat containing translated sentences."""
    beat_uid: str = Field(..., description="Unique beat ID, e.g., 'ch03_beat012'")
    narrative_function: str = Field(
        default="DIALOGUE_INTERACTION",
        pattern="^(NARRATIVE_EXPOSITION|DIALOGUE_INTERACTION|VISCERAL_COMBAT|INTIMATE_SCENE|ATMOSPHERIC_TRANSITION)$",
        description="Dramatic function of this beat"
    )
    sentences: List[TranslatedSentenceRecord] = Field(
        default_factory=list,
        description="Translated sentences in this beat"
    )


class TranslationManifest(ContractBaseModel):
    """Manifest emitted by Room 2 Translation Collective for a complete chapter."""
    chapter_id: int = Field(..., ge=1, description="Chapter index")
    source_hash: str = Field(..., description="Matches RawChapterRecord.source_hash")
    translation_mode: str = Field(
        default="RAW_UNRATED",
        pattern="^(CLASSIC_REVERENT|RAW_UNRATED)$",
        description="Active dual-rule translation mode"
    )
    beats: List[TranslationBeatRecord] = Field(
        default_factory=list,
        description="Ordered sequence of translated beats"
    )
