from __future__ import annotations
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Set

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
from audiobook_factory.pdf.models import (
    PDFTextSpan,
    PageQualityAudit,
    ExtractionCandidateEvaluation,
    _PDFPageSpanRecord,
)
from audiobook_factory.pdf.layout_reconstructor import PDFLayoutReconstructor
from audiobook_factory.pdf.quality_analyzer import PDFQualityAnalyzer
from audiobook_factory.pdf.vision_extractor import PDFEscalationEngine, GeminiVisionPDFExtractor


class ForensicPDFEngine:
    """
    Coordinating PDF ingestion engine.
    Extracts pages locally in human reading order, evaluates quality, selectively escalates
    suspicious pages via a multi-signal quality gate, and reconstructs canonical chapters/blocks
    with lossless page-level provenance.
    """

    def __init__(self, file_path: Path, escalation_engine: Optional[PDFEscalationEngine] = None):
        self.file_path = Path(file_path).resolve()
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {self.file_path}")
        self.escalation_engine = escalation_engine or GeminiVisionPDFExtractor()

    def extract_pages(self) -> Tuple[List[str], List[PageQualityAudit], List[int]]:
        """
        Extracts all pages from PDF in human reading order.
        Returns: (cleaned_pages, page_audits, escalated_page_numbers)
        """
        raw_pages: List[str] = []
        try:
            import pypdf
            reader = pypdf.PdfReader(str(self.file_path))
            for page in reader.pages:
                text = PDFLayoutReconstructor.extract_page_reading_order(page)
                raw_pages.append(text)
        except Exception:
            raw_pages = []

        if not raw_pages:
            return [], [], []

        audits, cleaned_pages = PDFQualityAnalyzer.audit_pages(raw_pages)
        # De-interleave any whitespace-aligned multi-column text revealed after header/footer stripping
        for idx, cp in enumerate(cleaned_pages):
            reconstructed = PDFLayoutReconstructor.reconstruct_multicolumn_text(cp)
            if reconstructed != cp:
                cleaned_pages[idx] = reconstructed
                eval_m = PDFQualityAnalyzer.evaluate_extraction_quality(reconstructed)
                audits[idx].quality_score = eval_m.composite_score
                audits[idx].reading_order_score = eval_m.reading_order_score
                audits[idx].text_integrity_score = eval_m.text_integrity_score

        escalated_pages: List[int] = []

        # Selective escalation with multi-signal quality gate comparison
        for audit in audits:
            if audit.is_suspicious and self.escalation_engine:
                local_candidate = cleaned_pages[audit.page_number - 1]
                healed_text = self.escalation_engine.escalate_page(self.file_path, audit.page_number)
                accepted, reason = PDFQualityAnalyzer.should_accept_escalation(
                    local_text=local_candidate,
                    gemini_text=healed_text,
                    local_audit=audit,
                )
                if accepted and healed_text:
                    cleaned_pages[audit.page_number - 1] = healed_text
                    healed_eval = PDFQualityAnalyzer.evaluate_extraction_quality(healed_text)
                    audit.word_count = healed_eval.word_count
                    audit.char_count = healed_eval.char_count
                    audit.line_count = healed_eval.line_count
                    audit.quality_score = healed_eval.composite_score
                    audit.reading_order_score = healed_eval.reading_order_score
                    audit.text_integrity_score = healed_eval.text_integrity_score
                    audit.status = "HIGH"
                    audit.is_suspicious = False
                    audit.warnings.append(f"Healed via selective vision escalation ({reason})")
                    escalated_pages.append(audit.page_number)
                elif healed_text is not None:
                    audit.warnings.append(f"Escalation candidate rejected by quality gate ({reason})")

        return cleaned_pages, audits, escalated_pages

    def _build_page_provenance_index(
        self,
        cleaned_pages: List[str],
        audits: List[PageQualityAudit],
        escalated_pages: Optional[List[int]] = None,
    ) -> Tuple[str, List[_PDFPageSpanRecord]]:
        """
        Joins non-empty PDF pages (using '\\n' when a paragraph continues mid-sentence across pages,
        or '\\n\\n' otherwise) while building a character-accurate provenance index
        mapping any [doc_char_start, doc_char_end) range back to exact page_number, page_end,
        line_start, line_end, page-local char_offset, confidence, and extraction_method.
        """
        escalated_set = set(escalated_pages or [])
        records: List[_PDFPageSpanRecord] = []
        joined_pieces: List[str] = []
        cursor = 0

        for p_idx, page_text in enumerate(cleaned_pages, 1):
            audit = audits[p_idx - 1] if p_idx - 1 < len(audits) else PageQualityAudit(page_number=p_idx)
            stripped_page = page_text.strip()
            if not stripped_page:
                continue

            if joined_pieces:
                prev_page_str = records[-1].page_text if records else ""
                prev_last_ln = prev_page_str.splitlines()[-1].strip() if prev_page_str else ""
                next_first_ln = stripped_page.splitlines()[0].strip()
                continues_mid_sentence = (
                    bool(prev_last_ln)
                    and bool(next_first_ln)
                    and not prev_last_ln.endswith((".", "!", "?", '"', "'", "”", "’", ")", "]", ":", ";", "।", "*"))
                    and not re.match(COMBINED_CHAPTER_REGEX, prev_last_ln, flags=re.IGNORECASE)
                    and not re.match(COMBINED_CHAPTER_REGEX, next_first_ln, flags=re.IGNORECASE)
                    and next_first_ln[0].islower()
                )
                sep = "\n" if continues_mid_sentence else "\n\n"
                joined_pieces.append(sep)
                cursor += len(sep)

            doc_start = cursor
            joined_pieces.append(stripped_page)
            cursor += len(stripped_page)
            doc_end = cursor

            # Compute 1-indexed line offsets within stripped_page
            line_offsets: List[Tuple[int, int, int]] = []
            ln_cursor = 0
            for ln_num, ln_str in enumerate(stripped_page.splitlines(keepends=True), 1):
                ln_start = ln_cursor
                ln_end = ln_cursor + len(ln_str.rstrip("\r\n"))
                line_offsets.append((ln_start, ln_end, ln_num))
                ln_cursor += len(ln_str)

            method = "vision_fallback" if p_idx in escalated_set else "pdf_pypdf_selective"
            records.append(
                _PDFPageSpanRecord(
                    page_number=p_idx,
                    doc_char_start=doc_start,
                    doc_char_end=doc_end,
                    page_text=stripped_page,
                    line_offsets=line_offsets,
                    confidence=audit.status,
                    extraction_method=method,
                )
            )

        return "".join(joined_pieces), records

    def _resolve_provenance_for_span(
        self,
        doc_start: int,
        doc_end: int,
        records: List[_PDFPageSpanRecord],
        reading_order: int,
    ) -> Tuple[SourceProvenance, ConfidenceLevel]:
        """
        Resolves exact PDF SourceProvenance and ConfidenceLevel for a character span [doc_start, doc_end)
        in the joined document text.
        """
        if not records:
            return (
                SourceProvenance(
                    source_file=str(self.file_path),
                    source_type="pdf",
                    page_number=1,
                    reading_order=reading_order,
                    extraction_method="pdf_pypdf_selective",
                ),
                "HIGH",
            )

        overlapping = [
            r for r in records
            if r.doc_char_end > doc_start and r.doc_char_start < max(doc_end, doc_start + 1)
        ]
        if not overlapping:
            # Find nearest preceding or following page record
            preceding = [r for r in records if r.doc_char_end <= doc_start]
            target = preceding[-1] if preceding else records[0]
            overlapping = [target]

        first_rec = overlapping[0]
        last_rec = overlapping[-1]

        # Compute page-relative character offset and line numbers on the starting page
        rel_start = max(0, doc_start - first_rec.doc_char_start)
        rel_end = min(len(first_rec.page_text), max(rel_start + 1, doc_end - first_rec.doc_char_start))

        line_start = 1
        line_end = 1
        if first_rec.line_offsets:
            matching_lines = [
                ln_num
                for l_s, l_e, ln_num in first_rec.line_offsets
                if l_e >= rel_start and l_s <= rel_end
            ]
            if matching_lines:
                line_start = matching_lines[0]
                line_end = matching_lines[-1]

        # If block spans multiple pages, compute line_end on last_rec
        page_end_val: Optional[int] = None
        if last_rec.page_number != first_rec.page_number:
            page_end_val = last_rec.page_number
            rel_last_end = min(len(last_rec.page_text), max(1, doc_end - last_rec.doc_char_start))
            last_lines = [
                ln_num
                for l_s, _l_e, ln_num in last_rec.line_offsets
                if l_s <= rel_last_end
            ]
            if last_lines:
                line_end = last_lines[-1]

        # Confidence is the most conservative confidence across overlapping pages
        conf_rank = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        inv_rank: Dict[int, ConfidenceLevel] = {0: "LOW", 1: "MEDIUM", 2: "HIGH"}
        min_conf = min(conf_rank.get(r.confidence, 2) for r in overlapping)
        block_conf: ConfidenceLevel = inv_rank[min_conf]

        # Extraction method reflects vision fallback if any contributing page used vision escalation
        methods = {r.extraction_method for r in overlapping}
        ext_method = "vision_fallback" if "vision_fallback" in methods else first_rec.extraction_method

        prov = SourceProvenance(
            source_file=str(self.file_path),
            source_type="pdf",
            page_number=first_rec.page_number,
            page_end=page_end_val,
            line_start=line_start,
            line_end=line_end,
            char_offset=rel_start,
            reading_order=reading_order,
            extraction_method=ext_method,
        )
        return prov, block_conf

    def to_canonical_blocks(
        self,
        cleaned_pages: List[str],
        audits: List[PageQualityAudit],
        escalated_pages: Optional[List[int]] = None,
    ) -> List[CanonicalBlock]:
        """Converts extracted pages into CanonicalBlocks with complete page and line provenance."""
        blocks: List[CanonicalBlock] = []
        global_order = 0
        escalated_set = set(escalated_pages or [])

        for p_idx, (page_text, audit) in enumerate(zip(cleaned_pages, audits), 1):
            stripped_page = page_text.strip()
            if not stripped_page:
                continue

            # Compute line offsets for this page
            line_offsets: List[Tuple[int, int, int]] = []
            ln_cursor = 0
            for ln_num, ln_str in enumerate(stripped_page.splitlines(keepends=True), 1):
                line_offsets.append((ln_cursor, ln_cursor + len(ln_str.rstrip("\r\n")), ln_num))
                ln_cursor += len(ln_str)

            for match in re.finditer(r"(?:[^\n]+(?:\n(?!\n)[^\n]*)*)", stripped_page):
                raw_para = match.group(0)
                para = raw_para.strip()
                if not para:
                    continue

                norm_text, norm_warnings = normalize_block_text(para)
                if not norm_text:
                    continue

                global_order += 1
                p_start = match.start()
                p_end = match.end()
                matching_lines = [
                    ln_num for l_s, l_e, ln_num in line_offsets if l_e >= p_start and l_s <= p_end
                ]
                l_start = matching_lines[0] if matching_lines else 1
                l_end = matching_lines[-1] if matching_lines else l_start

                b_type = "scene_break" if re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", norm_text) else "paragraph"
                method = "vision_fallback" if p_idx in escalated_set else "pdf_pypdf_selective"
                prov = SourceProvenance(
                    source_file=str(self.file_path),
                    source_type="pdf",
                    page_number=p_idx,
                    line_start=l_start,
                    line_end=l_end,
                    char_offset=p_start,
                    reading_order=global_order,
                    extraction_method=method,
                )
                meta: Dict[str, Any] = {}
                if norm_warnings:
                    meta["normalization_warnings"] = norm_warnings

                block = CanonicalBlock(
                    id=f"b-p{p_idx:04d}-{global_order:05d}",
                    type=b_type,
                    raw_text=para,
                    normalized_text=norm_text,
                    provenance=prov,
                    confidence=audit.status,
                    semantic_metadata=meta,
                )
                blocks.append(block)

        return blocks

    def segment_into_canonical_chapters(
        self,
        cleaned_pages: List[str],
        audits: List[PageQualityAudit],
        escalated_pages: Optional[List[int]] = None,
        max_words: int = 12000,
    ) -> List[CanonicalChapter]:
        """
        Segments extracted PDF pages into CanonicalChapters (and production chunks when needed)
        while preserving page_number, line_start, line_end, char_offset, reading_order,
        extraction_method, and confidence across all page joins and chapter reconstructions.
        """
        joined_text, page_records = self._build_page_provenance_index(
            cleaned_pages, audits, escalated_pages=escalated_pages
        )
        if not joined_text.strip():
            return []

        chap_dicts = segment_chapters_from_text(joined_text)
        canonical_chapters: List[CanonicalChapter] = []
        global_reading_order = 0

        for idx, cd in enumerate(chap_dicts, 1):
            title = cd.get("title", f"Chapter {idx}")
            content = cd.get("content", "")
            words = cd.get("words", len(content.split()))
            c_char_start = int(cd.get("char_start", 0))
            is_lit = bool(cd.get("is_literary_chapter", True))
            b_origin = str(cd.get("boundary_origin", "detected_heading"))
            lit_num = cd.get("literary_chapter_number")
            parent_id = f"lit-ch-{lit_num:03d}" if lit_num is not None else None

            if words > max_words:
                splits = split_large_chapter_on_semantic_boundary(
                    title,
                    content,
                    max_words=max_words,
                    base_char_start=c_char_start,
                    is_literary_chapter=is_lit,
                    boundary_origin=b_origin,
                    literary_chapter_number=lit_num,
                    parent_chapter_id=parent_id,
                )
            else:
                splits = [{
                    **cd,
                    "title": title,
                    "content": content,
                    "words": words,
                    "char_start": c_char_start,
                    "char_end": int(cd.get("char_end", c_char_start + len(content))),
                    "parent_chapter_id": parent_id,
                }]

            for part in splits:
                p_title = part["title"]
                p_content = part["content"]
                p_words = part["words"]
                p_char_start = int(part.get("char_start", c_char_start))
                p_unit_type = part.get("unit_type", "literary_chapter" if is_lit else "production_chunk")
                p_is_lit = bool(part.get("is_literary_chapter", is_lit))
                p_is_prod = bool(part.get("is_production_chunk", not p_is_lit))
                p_origin = part.get("boundary_origin", b_origin)
                p_lit_num = part.get("literary_chapter_number", lit_num)
                p_parent_id = part.get("parent_chapter_id", parent_id)
                p_parent_title = part.get("parent_chapter_title", title if is_lit else None)
                p_chunk_idx = part.get("chunk_index", 1)
                p_total_chunks = part.get("total_chunks", 1)

                blocks: List[CanonicalBlock] = []
                p_block_idx = 0

                for match in re.finditer(r"(?:[^\n]+(?:\n(?!\n)[^\n]*)*)", p_content):
                    raw_para = match.group(0)
                    lstrip_len = len(raw_para) - len(raw_para.lstrip())
                    para_clean = raw_para.strip()
                    if not para_clean:
                        continue

                    norm_para, norm_warnings = normalize_block_text(para_clean)
                    if not norm_para:
                        continue

                    p_block_idx += 1
                    global_reading_order += 1
                    block_doc_start = p_char_start + match.start() + lstrip_len
                    block_doc_end = block_doc_start + len(para_clean)

                    prov, block_conf = self._resolve_provenance_for_span(
                        block_doc_start,
                        block_doc_end,
                        page_records,
                        reading_order=global_reading_order,
                    )

                    b_type = "scene_break" if re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", para_clean) else "paragraph"
                    meta: Dict[str, Any] = {"doc_char_start": block_doc_start, "doc_char_end": block_doc_end}
                    if prov.page_end is not None and prov.page_end != prov.page_number:
                        meta["page_span"] = [prov.page_number, prov.page_end]
                    if norm_warnings:
                        meta["normalization_warnings"] = norm_warnings

                    block = CanonicalBlock(
                        id=f"b-ch{len(canonical_chapters)+1:03d}-{p_block_idx:04d}",
                        type=b_type,
                        raw_text=para_clean,
                        normalized_text=norm_para,
                        provenance=prov,
                        confidence=block_conf,
                        semantic_metadata=meta,
                    )
                    blocks.append(block)

                chap_num = len(canonical_chapters) + 1
                page_nums = [b.provenance.page_number for b in blocks if b.provenance.page_number is not None]
                page_ends = [
                    (b.provenance.page_end or b.provenance.page_number)
                    for b in blocks
                    if b.provenance.page_number is not None
                ]
                page_start = min(page_nums) if page_nums else None
                page_end = max(page_ends) if page_ends else None
                if page_start is not None and page_end is not None:
                    src_loc = f"page {page_start}" if page_start == page_end else f"pages {page_start}-{page_end}"
                else:
                    src_loc = None

                # Compute chapter confidence conservatively from block confidences and boundary origin
                if any(b.confidence == "LOW" for b in blocks):
                    chap_conf: ConfidenceLevel = "LOW"
                elif p_origin == "fallback_production_chunk" or any(b.confidence == "MEDIUM" for b in blocks):
                    chap_conf = "MEDIUM"
                else:
                    chap_conf = "HIGH"

                canonical_chap = CanonicalChapter(
                    id=f"ch-{chap_num:03d}",
                    number=chap_num,
                    title=p_title,
                    blocks=blocks,
                    source_location=src_loc,
                    confidence=chap_conf,
                    words=p_words,
                    unit_type=p_unit_type,
                    is_literary_chapter=p_is_lit,
                    is_production_chunk=p_is_prod,
                    boundary_origin=p_origin,
                    parent_chapter_id=p_parent_id,
                    parent_chapter_title=p_parent_title,
                    literary_chapter_number=p_lit_num,
                    chunk_index=p_chunk_idx,
                    total_chunks_in_chapter=p_total_chunks,
                    page_start=page_start,
                    page_end=page_end,
                )
                canonical_chapters.append(canonical_chap)

        return canonical_chapters


