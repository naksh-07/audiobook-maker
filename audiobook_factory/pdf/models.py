from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict
from audiobook_factory.book_model import ConfidenceLevel


@dataclass
class PDFTextSpan:
    """Positioned text fragment extracted from a PDF content stream."""
    text: str
    x0: float
    y: float
    x1: float
    font_height: float = 12.0
    space_width: float = 3.5
    flip_vertical: bool = False
    seq_order: int = 0
    column_index: Optional[int] = None


class PageQualityAudit(BaseModel):
    """Quality diagnostic for a single PDF page."""
    model_config = ConfigDict(extra="ignore")

    page_number: int
    status: ConfidenceLevel = "HIGH"
    word_count: int = 0
    char_count: int = 0
    line_count: int = 0
    is_suspicious: bool = False
    warnings: List[str] = Field(default_factory=list)
    quality_score: float = 1.0
    reading_order_score: float = 1.0
    text_integrity_score: float = 1.0


class ExtractionCandidateEvaluation(BaseModel):
    """Quantitative quality evaluation of a single page extraction candidate (local or Gemini)."""
    model_config = ConfigDict(extra="ignore")

    word_count: int = 0
    clean_word_count: int = 0
    char_count: int = 0
    line_count: int = 0
    symbol_noise_ratio: float = 0.0
    replacement_char_count: int = 0
    gibberish_token_ratio: float = 0.0
    short_fragment_ratio: float = 0.0
    mid_sentence_break_ratio: float = 0.0
    repetition_anomaly: bool = False
    refusal_detected: bool = False
    reading_order_score: float = 1.0
    text_integrity_score: float = 1.0
    sentence_coherence_score: float = 1.0
    composite_score: float = 1.0
    anomaly_count: int = 0
    anomalies: List[str] = Field(default_factory=list)


@dataclass
class _PDFPageSpanRecord:
    """Internal provenance record mapping joined document character offsets back to PDF page & lines."""
    page_number: int
    doc_char_start: int
    doc_char_end: int
    page_text: str
    line_offsets: List[Tuple[int, int, int]]  # (page_rel_start, page_rel_end, line_number_1based)
    confidence: ConfidenceLevel
    extraction_method: str
