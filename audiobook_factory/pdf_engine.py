#!/usr/bin/env python3
"""
AudioBookmaker - Pillar 1: Lightweight Layout-Aware PDF Engine & Quality Analyzer.
Provides:
- Fast local text extraction via pypdf.
- Lightweight page-level quality analysis (density, multi-column indicators, headers/footers, OCR noise).
- Modular selective escalation for suspicious pages only (Gemini Vision fallback).
- Reassembly into canonical chapters with page-level provenance.
"""

from __future__ import annotations
import os
import re
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Set
from pydantic import BaseModel, Field, ConfigDict

from audiobook_factory.book_model import (
    CanonicalBlock,
    CanonicalChapter,
    SourceProvenance,
    ConfidenceLevel,
)
from audiobook_factory.normalizer import clean_book_text, normalize_block_text


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


class PDFQualityAnalyzer:
    """
    Lightweight heuristic analyzer for PDF page extraction quality.
    Evaluates density, repeated headers/footers, OCR symbol noise, and column layout anomalies.
    """

    @classmethod
    def audit_pages(cls, raw_pages: List[str]) -> Tuple[List[PageQualityAudit], List[str]]:
        """
        Audits raw page text and strips detected running headers/footers across consecutive pages.
        Returns: (List[PageQualityAudit], cleaned_pages)
        """
        audits: List[PageQualityAudit] = []
        cleaned_pages: List[str] = []

        # Step 1: Detect recurring headers (first lines) and footers (last lines)
        header_candidates: Dict[str, Set[int]] = {}
        footer_candidates: Dict[str, Set[int]] = {}

        for p_idx, page in enumerate(raw_pages, 1):
            lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
            if len(lines) >= 3:
                first_line = lines[0].lower()
                last_line = lines[-1].lower()
                # Ignore pure numbers as page numbers are handled separately
                if not first_line.isdigit() and len(first_line) > 3:
                    header_candidates.setdefault(first_line, set()).add(p_idx)
                if not last_line.isdigit() and len(last_line) > 3:
                    footer_candidates.setdefault(last_line, set()).add(p_idx)

        # Lines repeating across >= 3 pages are designated running headers/footers
        running_headers = {text for text, pages in header_candidates.items() if len(pages) >= 3}
        running_footers = {text for text, pages in footer_candidates.items() if len(pages) >= 3}

        # Step 2: Per-page quality analysis
        for p_idx, page in enumerate(raw_pages, 1):
            lines = [ln.strip() for ln in page.splitlines()]
            # Filter out running headers and footers
            filtered_lines: List[str] = []
            for idx, ln in enumerate(lines):
                ln_lower = ln.strip().lower()
                if idx == 0 and ln_lower in running_headers:
                    continue
                if idx == len(lines) - 1 and ln_lower in running_footers:
                    continue
                filtered_lines.append(ln)

            cleaned_text = "\n".join(filtered_lines).strip()
            cleaned_pages.append(cleaned_text)

            words = cleaned_text.split()
            word_count = len(words)
            char_count = len(cleaned_text)
            line_count = len(filtered_lines)

            warnings: List[str] = []
            is_suspicious = False

            # Signal 1: Blank or abnormally low text density on interior page
            if 0 < word_count < 15 and char_count < 80:
                warnings.append(f"Low text density ({word_count} words on page).")
                is_suspicious = True

            # Signal 2: OCR noise / symbol density (e.g. broken scanned text)
            if char_count > 50:
                symbols = len(re.findall(r"[^a-zA-Z0-9\s\u0900-\u097F\.,'\"\?\!\-\—]", cleaned_text))
                symbol_ratio = symbols / char_count
                if symbol_ratio > 0.08:
                    warnings.append(f"High symbol/noise ratio ({symbol_ratio:.1%}). Likely OCR defect.")
                    is_suspicious = True

            # Signal 3: Unicode replacement character
            if "\ufffd" in cleaned_text:
                warnings.append("Page contains Unicode replacement characters (\\ufffd).")
                is_suspicious = True

            # Signal 4: Multi-column interleaving indicator (many short lines with lowercase start)
            if line_count >= 10:
                short_lines = [ln for ln in filtered_lines if 0 < len(ln) < 30]
                short_ratio = len(short_lines) / line_count
                lowercase_starts = sum(1 for ln in filtered_lines if ln and ln[0].islower())
                if short_ratio > 0.50 and lowercase_starts > 4:
                    warnings.append(f"Possible multi-column or fragmented line wrapping (short ratio {short_ratio:.1%}).")
                    is_suspicious = True

            status: ConfidenceLevel = "LOW" if is_suspicious else "HIGH"
            audits.append(PageQualityAudit(
                page_number=p_idx,
                status=status,
                word_count=word_count,
                char_count=char_count,
                line_count=line_count,
                is_suspicious=is_suspicious,
                warnings=warnings,
            ))

        return audits, cleaned_pages


class PDFEscalationEngine:
    """Interface for escalating suspicious PDF pages."""

    def escalate_page(self, pdf_path: Path, page_num: int) -> Optional[str]:
        raise NotImplementedError


class GeminiVisionPDFExtractor(PDFEscalationEngine):
    """
    Selective Gemini Multimodal Document Escalator.
    Only called when local extraction identifies suspicious pages and API key is present.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            try:
                from audiobook_factory.key_manager import get_persistent_key_pool
                self.api_key = get_persistent_key_pool().get_key(service="text")
            except Exception:
                pass

    def escalate_page(self, pdf_path: Path, page_num: int) -> Optional[str]:
        """
        Extracts a single suspicious page via Gemini Multimodal document API.
        If pypdf is available, creates a single-page temporary PDF to minimize token usage.
        """
        if not self.api_key:
            return None

        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_path))
            if page_num > len(reader.pages):
                return None

            writer = pypdf.PdfWriter()
            writer.add_page(reader.pages[page_num - 1])

            import io
            buf = io.BytesIO()
            writer.write(buf)
            buf.seek(0)
            page_bytes = buf.read()
        except Exception:
            return None

        # Call Gemini API with single page PDF
        b64_data = base64.b64encode(page_bytes).decode("utf-8")
        model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"

        prompt = (
            "Extract all prose text from this book page in clean Markdown reading order. "
            "Strip running headers and footers. Do not summarize."
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": "application/pdf", "data": b64_data}},
                    ]
                }
            ]
        }

        try:
            headers = {"Content-Type": "application/json"}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return clean_book_text(text)
        except Exception:
            return None


class ForensicPDFEngine:
    """
    Coordinating PDF ingestion engine.
    Extracts pages locally, evaluates quality, selectively escalates suspicious pages,
    and returns structured pages with provenance.
    """

    def __init__(self, file_path: Path, escalation_engine: Optional[PDFEscalationEngine] = None):
        self.file_path = Path(file_path).resolve()
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {self.file_path}")
        self.escalation_engine = escalation_engine or GeminiVisionPDFExtractor()

    def extract_pages(self) -> Tuple[List[str], List[PageQualityAudit], List[int]]:
        """
        Extracts all pages from PDF.
        Returns: (cleaned_pages, page_audits, escalated_page_numbers)
        """
        raw_pages: List[str] = []
        try:
            import pypdf
            reader = pypdf.PdfReader(str(self.file_path))
            for page in reader.pages:
                text = page.extract_text() or ""
                raw_pages.append(text)
        except Exception as e:
            raw_pages = []

        if not raw_pages:
            return [], [], []

        audits, cleaned_pages = PDFQualityAnalyzer.audit_pages(raw_pages)
        escalated_pages: List[int] = []

        # Selective escalation: only escalate suspicious pages if escalation engine is active
        for audit in audits:
            if audit.is_suspicious and self.escalation_engine:
                healed_text = self.escalation_engine.escalate_page(self.file_path, audit.page_number)
                if healed_text and len(healed_text.split()) > audit.word_count:
                    cleaned_pages[audit.page_number - 1] = healed_text
                    audit.status = "HIGH"
                    audit.is_suspicious = False
                    audit.warnings.append("Healed via selective vision escalation.")
                    escalated_pages.append(audit.page_number)

        return cleaned_pages, audits, escalated_pages

    def to_canonical_blocks(self, cleaned_pages: List[str], audits: List[PageQualityAudit]) -> List[CanonicalBlock]:
        """Converts extracted pages into CanonicalBlocks with page provenance."""
        blocks: List[CanonicalBlock] = []
        global_order = 0

        for p_idx, (page_text, audit) in enumerate(zip(cleaned_pages, audits), 1):
            if not page_text.strip():
                continue

            paragraphs = re.split(r"\n{2,}", page_text)
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                global_order += 1
                norm_text, _ = normalize_block_text(para)
                if not norm_text:
                    continue

                # Conservative classification
                b_type = "scene_break" if re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", norm_text) else "paragraph"
                prov = SourceProvenance(
                    source_file=str(self.file_path),
                    source_type="pdf",
                    page_number=p_idx,
                    reading_order=global_order,
                    extraction_method="pdf_pypdf_selective",
                )
                block = CanonicalBlock(
                    id=f"b-p{p_idx:04d}-{global_order:05d}",
                    type=b_type,
                    raw_text=para,
                    normalized_text=norm_text,
                    provenance=prov,
                    confidence=audit.status,
                )
                blocks.append(block)

        return blocks
