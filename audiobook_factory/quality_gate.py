#!/usr/bin/env python3
"""
AudioBookmaker - Pillar 1: Extraction Quality Gate Auditor.
Audits canonical book structures before downstream translation and screenplay stages.
Enforces fail-closed protection against corrupted or empty documents while providing
rich, actionable error messages detailing affected pages, exact failures, and remediation.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional

from audiobook_factory.book_model import (
    CanonicalBook,
    ExtractionQualityReport,
    ExtractionGateAuditError,
    GateStatus,
    ConfidenceLevel,
)


class ExtractionQualityAuditor:
    """
    Independent gate auditor verifying document extraction integrity.
    """

    @classmethod
    def audit(cls, book: CanonicalBook, force_gate: bool = False) -> ExtractionQualityReport:
        """
        Audits CanonicalBook and enforces Quality Gate.
        If status is 'REVIEW' and force_gate is False, raises ExtractionGateAuditError.
        """
        errors: List[str] = []
        warnings: List[str] = []

        total_chapters = len(book.chapters)
        total_words = sum(c.words for c in book.chapters)
        total_blocks = sum(len(c.blocks) for c in book.chapters)

        # Defect 1: No chapters extracted
        if not book.chapters:
            errors.append("Zero chapters were detected in the source document.")

        # Defect 2: Dangerously low text coverage
        if total_words < 50 and book.source_type in ("epub", "pdf"):
            errors.append(f"Total extracted word count ({total_words} words) is below the minimum threshold for literary documents.")

        # Defect 3: Empty chapters
        empty_chaps = [c.number for c in book.chapters if c.words < 5]
        if empty_chaps:
            errors.append(f"Chapters {empty_chaps} contain fewer than 5 words.")

        # Check existing report warnings / suspicious pages
        existing_report = book.quality_report
        suspicious_pages = list(existing_report.suspicious_pages)
        total_pages = max(1, existing_report.total_pages_or_docs)

        # Defect 4: Suspicious page ratio > 25%
        if suspicious_pages and (len(suspicious_pages) / total_pages) > 0.25:
            errors.append(
                f"Severe layout/OCR anomalies detected on {len(suspicious_pages)}/{total_pages} pages "
                f"({len(suspicious_pages)/total_pages:.1%})."
            )
        elif suspicious_pages:
            warnings.append(
                f"Minor layout/OCR warnings flagged on {len(suspicious_pages)} pages: {suspicious_pages[:10]}"
            )

        # Inherit existing warnings
        for w in existing_report.warnings:
            if w not in warnings:
                warnings.append(w)

        detected_lit = len(book.get_literary_chapters())
        prod_chunks = len(book.get_production_chunks())
        used_fallback = any(
            c.boundary_origin in ("fallback_production_chunk", "spine_fallback")
            for c in book.chapters
        )
        if used_fallback and detected_lit == 0 and prod_chunks > 0:
            fb_warn = (
                f"No literary chapter headings detected; segmented into {prod_chunks} "
                f"artificial production chunk(s) for processing limits."
            )
            if fb_warn not in warnings:
                warnings.append(fb_warn)

        # Evaluate Gate Status
        if errors:
            gate_status: GateStatus = "REVIEW"
            overall_confidence: ConfidenceLevel = "LOW"
        elif warnings:
            gate_status = "WARN"
            overall_confidence = "MEDIUM"
        else:
            gate_status = "PASS"
            overall_confidence = "HIGH"

        # Update quality report
        report = ExtractionQualityReport(
            overall_confidence=overall_confidence,
            gate_status=gate_status,
            source_type=book.source_type,
            source_path=book.source_path,
            extraction_engine=book.extraction_engine,
            total_pages_or_docs=existing_report.total_pages_or_docs,
            total_words=total_words,
            total_chapters=total_chapters,
            detected_literary_chapters=detected_lit,
            production_chunks=prod_chunks,
            used_fallback_chunking=used_fallback,
            total_blocks=total_blocks,
            suspicious_pages=suspicious_pages,
            fallback_pages=existing_report.fallback_pages,
            fallback_used=existing_report.fallback_used,
            warnings=warnings,
            errors=errors,
            chapter_confidences={c.number: c.confidence for c in book.chapters},
            duration_sec=existing_report.duration_sec,
        )

        book.quality_report = report

        # Enforce Fail-Closed Gate
        if gate_status == "REVIEW" and not force_gate:
            raise ExtractionGateAuditError(report)

        return report
