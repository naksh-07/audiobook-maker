#!/usr/bin/env python3
"""
AudioBookmaker - Pillar 1: Lightweight Layout-Aware PDF Engine & Quality Analyzer Facade.
Maintains 100% backward compatibility by re-exporting modular components from audiobook_factory.pdf.
"""

from __future__ import annotations

from audiobook_factory.pdf import (
    PDFTextSpan,
    PDFLayoutReconstructor,
    PageQualityAudit,
    ExtractionCandidateEvaluation,
    PDFQualityAnalyzer,
    PDFEscalationEngine,
    GeminiVisionPDFExtractor,
    _PDFPageSpanRecord,
    ForensicPDFEngine,
)

# Re-export commonly co-imported symbols for backward compatibility
from audiobook_factory.book_model import (
    CanonicalBlock,
    CanonicalChapter,
    SourceProvenance,
    ConfidenceLevel,
)
from audiobook_factory.normalizer import clean_book_text, normalize_block_text
from audiobook_factory.chapter_segmenter import (
    CHAPTER_PATTERNS,
    COMBINED_CHAPTER_REGEX,
    segment_chapters_from_text,
    split_large_chapter_on_semantic_boundary,
)

__all__ = [
    "PDFTextSpan",
    "PDFLayoutReconstructor",
    "PageQualityAudit",
    "ExtractionCandidateEvaluation",
    "PDFQualityAnalyzer",
    "PDFEscalationEngine",
    "GeminiVisionPDFExtractor",
    "_PDFPageSpanRecord",
    "ForensicPDFEngine",
    "CanonicalBlock",
    "CanonicalChapter",
    "SourceProvenance",
    "ConfidenceLevel",
    "clean_book_text",
    "normalize_block_text",
    "CHAPTER_PATTERNS",
    "COMBINED_CHAPTER_REGEX",
    "segment_chapters_from_text",
    "split_large_chapter_on_semantic_boundary",
]
