#!/usr/bin/env python3
"""
AudioBookmaker - Pillar 1: Canonical Book Model & Forensic Provenance.
Defines strongly typed Pydantic v2 data models for literary document ingestion:
- CanonicalBook, CanonicalChapter, CanonicalBlock, SourceProvenance
- ExtractionQualityReport, ExtractionGateAuditError
Preserves raw source fidelity and provides actionable gate feedback.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


BlockType = Literal[
    "paragraph",
    "heading",
    "dialogue",
    "scene_break",
    "quote",
    "poetry",
    "list",
    "note",
    "unknown",
]

ConfidenceLevel = Literal["HIGH", "MEDIUM", "LOW"]
GateStatus = Literal["PASS", "WARN", "REVIEW"]


class ExtractionGateAuditError(ValueError):
    """
    Raised when the Extraction Quality Gate detects severe extraction anomalies (status == 'REVIEW').
    Provides actionable diagnostics including affected pages/chapters and recommended remediation.
    """
    def __init__(self, report: "ExtractionQualityReport", message: Optional[str] = None):
        self.report = report
        actionable_msg = message or report.format_actionable_error()
        super().__init__(actionable_msg)


class SourceProvenance(BaseModel):
    """
    Forensic provenance metadata tracking the exact origin of a text block.
    Answers: 'Where in the original document did this text come from?'
    """
    model_config = ConfigDict(extra="ignore")

    source_file: str = Field(..., description="Absolute or relative path to the original source file")
    source_type: str = Field(..., description="Document format: 'epub', 'pdf', 'txt', 'md'")
    page_number: Optional[int] = Field(default=None, description="Page number for PDF documents (1-indexed)")
    spine_item: Optional[str] = Field(default=None, description="EPUB manifest spine item href (e.g. 'OEBPS/ch01.xhtml')")
    html_tag: Optional[str] = Field(default=None, description="Source HTML tag name (e.g. 'p', 'h2', 'blockquote')")
    html_id: Optional[str] = Field(default=None, description="Source HTML id or anchor name")
    line_start: Optional[int] = Field(default=None, description="Starting line in source text (1-indexed)")
    line_end: Optional[int] = Field(default=None, description="Ending line in source text (1-indexed)")
    char_offset: Optional[int] = Field(default=None, description="Character offset in source file or chapter")
    reading_order: Optional[int] = Field(default=None, description="Global reading order index across document")
    extraction_method: str = Field(default="local", description="Engine used (e.g. 'pypdf', 'epub_dom', 'vision_fallback')")


class CanonicalBlock(BaseModel):
    """
    An atomic literary block with sacred raw text, normalized text, and provenance.
    Conservative by design: defaults to 'paragraph' or 'unknown' unless structure is certain.
    """
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique deterministic block identifier (e.g. 'b-001-00042')")
    type: BlockType = Field(default="paragraph", description="Conservative semantic classification")
    raw_text: str = Field(..., description="Sacred, unmutated source text exactly as extracted")
    normalized_text: str = Field(..., description="Clean, non-destructive normalized text for speech synthesis")
    provenance: SourceProvenance = Field(..., description="Forensic source provenance")
    confidence: ConfidenceLevel = Field(default="HIGH", description="Confidence in block fidelity and reading order")
    semantic_metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata (e.g. heading level, quote author)")


class CanonicalChapter(BaseModel):
    """
    Structured chapter containing ordered CanonicalBlocks and provenance.
    """
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Stable chapter identifier (e.g. 'ch-001')")
    number: int = Field(..., description="Chapter sequence number (1-indexed)")
    title: str = Field(..., description="Chapter title as found or inferred")
    blocks: List[CanonicalBlock] = Field(default_factory=list, description="Ordered canonical content blocks")
    source_location: Optional[str] = Field(default=None, description="Document source location summary")
    confidence: ConfidenceLevel = Field(default="HIGH", description="Confidence in chapter boundaries and completeness")
    words: int = Field(default=0, description="Total word count in chapter")

    def get_raw_text(self) -> str:
        """Returns concatenated unmutated raw text of all blocks."""
        return "\n\n".join(b.raw_text for b in self.blocks if b.raw_text.strip())

    def to_markdown(self) -> str:
        """Projects canonical blocks into clean, literary Markdown."""
        lines: List[str] = [f"# {self.title}\n"]
        for b in self.blocks:
            text = b.normalized_text.strip()
            if not text:
                continue
            if b.type == "heading":
                lvl = int(b.semantic_metadata.get("level", 2))
                prefix = "#" * max(2, min(lvl, 6))
                lines.append(f"{prefix} {text}")
            elif b.type == "scene_break":
                lines.append("* * *")
            elif b.type == "quote":
                quote_lines = [f"> {line}" for line in text.splitlines()]
                lines.append("\n".join(quote_lines))
            else:
                lines.append(text)
        return "\n\n".join(lines).strip() + "\n"

    def to_plain_text(self) -> str:
        """Projects canonical blocks into plain continuous text."""
        return "\n\n".join(b.normalized_text.strip() for b in self.blocks if b.normalized_text.strip())


class ExtractionQualityReport(BaseModel):
    """
    Machine-readable quality audit report for the ingestion stage.
    Flags PASS, WARN, or REVIEW and provides actionable diagnostics.
    """
    model_config = ConfigDict(extra="ignore")

    overall_confidence: ConfidenceLevel = Field(default="HIGH", description="Overall qualitative extraction confidence")
    gate_status: GateStatus = Field(default="PASS", description="Gate audit status: PASS, WARN, or REVIEW")
    source_type: str = Field(default="unknown", description="Source format (epub, pdf, txt, md)")
    source_path: str = Field(default="", description="Path to source document")
    extraction_engine: str = Field(default="universal", description="Primary extraction engine employed")
    total_pages_or_docs: int = Field(default=0, description="Total pages (PDF) or spine documents (EPUB)")
    total_words: int = Field(default=0, description="Total words extracted across all chapters")
    total_chapters: int = Field(default=0, description="Number of chapters detected and segmented")
    total_blocks: int = Field(default=0, description="Total canonical content blocks")
    suspicious_pages: List[int] = Field(default_factory=list, description="Pages flagged with layout or OCR noise (1-indexed)")
    fallback_pages: List[int] = Field(default_factory=list, description="Pages where fallback escalation was triggered")
    fallback_used: bool = Field(default=False, description="Whether escalation fallback was activated")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal extraction warnings")
    errors: List[str] = Field(default_factory=list, description="Fatal or critical quality issues requiring review")
    chapter_confidences: Dict[int, str] = Field(default_factory=dict, description="Per-chapter confidence ratings")
    duration_sec: float = Field(default=0.0, description="Extraction duration in seconds")

    def format_actionable_error(self) -> str:
        """Formats an actionable failure report with affected regions and remediation options."""
        lines = [
            "=" * 78,
            "  [FATAL] EXTRACTION QUALITY GATE AUDIT: REVIEW REQUIRED",
            "=" * 78,
            f"Source Document : {self.source_path}",
            f"Format / Engine : {self.source_type.upper()} via {self.extraction_engine}",
            f"Extraction Stats: {self.total_chapters} chapters, {self.total_words} words, {self.total_blocks} blocks",
            f"Overall Status  : {self.gate_status} (Confidence: {self.overall_confidence})",
            "",
            "CRITICAL QUALITY DEFECTS DETECTED:",
        ]
        if self.errors:
            for err in self.errors:
                lines.append(f"  • {err}")
        else:
            lines.append("  • Extraction confidence is below acceptable threshold for broadcast production.")

        if self.suspicious_pages:
            lines.append(f"\nAffected Suspicious Pages ({len(self.suspicious_pages)}): {self.suspicious_pages[:25]}" +
                         ("..." if len(self.suspicious_pages) > 25 else ""))

        lines.extend([
            "",
            "RECOMMENDED REMEDIATION:",
            "  1. Verify the source file integrity (e.g. check for corrupt scanned pages, DRM, or multi-column layout).",
            "  2. For scanned or complex layout PDFs, ensure GEMINI_API_KEY is configured to enable visual OCR escalation.",
            "  3. If you have verified the extracted chapters manually and wish to proceed anyway,",
            "     rerun with the '--force-gate' flag to bypass the Quality Gate fail-closed check.",
            "=" * 78,
        ])
        return "\n".join(lines)


class CanonicalBook(BaseModel):
    """
    Top-level canonical literary book representation.
    Serves as the single source of truth for the entire AudioBookmaker pipeline.
    """
    model_config = ConfigDict(extra="ignore")

    book_id: str = Field(..., description="Unique slug or book identifier")
    title: str = Field(..., description="Book title")
    author: str = Field(default="Unknown Author", description="Author name")
    source_type: str = Field(..., description="Source format (epub, pdf, txt, md)")
    source_path: str = Field(..., description="Path to input source file")
    extraction_engine: str = Field(default="universal", description="Primary extraction engine used")
    quality_report: ExtractionQualityReport = Field(default_factory=ExtractionQualityReport, description="Ingestion quality report")
    chapters: List[CanonicalChapter] = Field(default_factory=list, description="Ordered canonical chapters")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw metadata preserved from source container")

    def save_canonical(self, canonical_dir: Path) -> Path:
        """Serializes the canonical book model and quality report to disk."""
        canonical_dir = Path(canonical_dir).resolve()
        canonical_dir.mkdir(parents=True, exist_ok=True)

        book_path = canonical_dir / "book.json"
        with open(book_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

        report_path = canonical_dir / "quality_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(self.quality_report.model_dump_json(indent=2))

        return book_path

    def project_legacy_extracted(self, extracted_dir: Path) -> List[Path]:
        """
        Projects canonical chapters into backward-compatible chapter_XXX.md files.
        Guarantees that downstream translation and screenplay stages receive the exact format expected.
        """
        extracted_dir = Path(extracted_dir).resolve()
        extracted_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: List[Path] = []

        for chap in self.chapters:
            file_name = f"chapter_{chap.number:03d}.md"
            out_file = extracted_dir / file_name
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(chap.to_markdown())
            saved_paths.append(out_file)

        return saved_paths

    def to_legacy_metadata(self) -> Dict[str, Any]:
        """Generates backward-compatible metadata.json structure matching existing format."""
        total_words = sum(c.words for c in self.chapters)
        saved_chapters = []
        for c in self.chapters:
            saved_chapters.append({
                "number": c.number,
                "title": c.title,
                "file": f"chapter_{c.number:03d}.md",
                "words": c.words,
                "estimated_minutes": round(c.words / 140, 1),
            })

        return {
            "book_id": self.book_id,
            "source_file": self.source_path,
            "title": self.title,
            "author": self.author,
            "format": self.source_type,
            "total_chapters": len(self.chapters),
            "total_words": total_words,
            "estimated_total_hours": round(total_words / (140 * 60), 2),
            "chapters": saved_chapters,
            "extraction_quality": {
                "gate_status": self.quality_report.gate_status,
                "confidence": self.quality_report.overall_confidence,
                "warnings": len(self.quality_report.warnings),
                "errors": len(self.quality_report.errors),
            },
        }
