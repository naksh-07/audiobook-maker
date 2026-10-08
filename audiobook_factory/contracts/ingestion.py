#!/usr/bin/env python3
"""
Audiobook Factory - Room 1 Ingestion Contracts.
Standard: v6.0-ENTERPRISE-DAG
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import Field
from audiobook_factory.contracts.base import ContractBaseModel


class RawSentenceRecord(ContractBaseModel):
    """Represents a single atomic extracted sentence from source document."""
    sentence_id: str = Field(
        ...,
        description="Deterministic sentence ID, e.g., 'ch01_p002_s01'"
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Sanitized source sentence text in original script/language"
    )
    source_char_offset: int = Field(
        ...,
        ge=0,
        description="Character offset in raw source stream"
    )
    page_number: Optional[int] = Field(
        default=None,
        ge=1,
        description="Physical source page number if extracted from PDF"
    )


class RawChapterRecord(ContractBaseModel):
    """Represents an extracted chapter structure containing ordered sentences."""
    chapter_id: int = Field(
        ...,
        ge=1,
        description="Monotonic 1-indexed chapter number"
    )
    title: str = Field(
        ...,
        description="Chapter heading title or 'Chapter X'"
    )
    source_hash: str = Field(
        ...,
        description="SHA-256 checksum of raw un-tokenized chapter text"
    )
    sentences: List[RawSentenceRecord] = Field(
        default_factory=list,
        description="Ordered sequence of raw sentences"
    )


class RawBookManifest(ContractBaseModel):
    """Root AST manifest for an ingested book/source document."""
    book_id: str = Field(
        ...,
        description="Slugified unique book identifier, e.g., 'sword-of-destiny'"
    )
    title: str = Field(..., description="Full book title")
    author: str = Field(default="Unknown Author", description="Author name")
    source_file_path: str = Field(..., description="Absolute path to input EPUB/PDF/TXT")
    total_chapters: int = Field(..., ge=1, description="Total number of extracted chapters")
    chapters: List[RawChapterRecord] = Field(
        default_factory=list,
        description="Ordered list of extracted chapters"
    )
