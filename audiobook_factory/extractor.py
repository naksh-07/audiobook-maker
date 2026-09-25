#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 1: Universal Document Extractor (Forensic Ingestion).
Extracts clean, structured text, chapters, and rich provenance from EPUB, PDF, TXT, and Markdown files.
Coordinates:
- Canonical Book Model & Block-level Provenance (book_model.py)
- Non-destructive Literary Normalizer (normalizer.py)
- Structural DOM EPUB Parser (epub_parser.py)
- Layout-Aware PDF Engine & Quality Analyzer (pdf_engine.py)
- Multi-tier Chapter Segmenter & Meso-tier Splitter (chapter_segmenter.py)
- Independent Extraction Quality Gate (quality_gate.py)
"""

from __future__ import annotations
import os
import re
import json
import shutil
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# Core component imports
from audiobook_factory.book_model import (
    CanonicalBook,
    CanonicalChapter,
    CanonicalBlock,
    SourceProvenance,
    ExtractionQualityReport,
    ExtractionGateAuditError,
)
from audiobook_factory.normalizer import clean_book_text, normalize_block_text
from audiobook_factory.epub_parser import (
    ForensicEPUBParser,
    EPUBStructuralHTMLParser,
    extract_epub,
)
from audiobook_factory.pdf_engine import (
    ForensicPDFEngine,
    GeminiVisionPDFExtractor,
    PDFQualityAnalyzer,
    PageQualityAudit,
)
from audiobook_factory.chapter_segmenter import (
    segment_chapters_from_text,
    split_large_chapter_on_semantic_boundary,
)
from audiobook_factory.quality_gate import ExtractionQualityAuditor

# Legacy alias for backward compatibility
TextHTMLParser = EPUBStructuralHTMLParser


def extract_gemini_pdf(file_path: Path, api_key: str | None = None) -> str:
    """
    Extract clean structured Markdown from PDF using local pypdf parser with selective Gemini fallback.
    Maintains 100% backward compatibility with legacy API.
    """
    file_path = Path(file_path).resolve()
    engine = ForensicPDFEngine(
        file_path=file_path,
        escalation_engine=GeminiVisionPDFExtractor(api_key=api_key),
    )
    pages, _, _ = engine.extract_pages()
    full_text = "\n\n".join(p for p in pages if p.strip())
    return clean_book_text(full_text)


def extract_chapters(source: str | Path) -> List[Dict[str, Any]]:
    """
    Universal chapter extractor: accepts file path or raw text string.
    Enforces Meso-Tier 12,000 word ceiling by splitting oversized chapters on semantic boundaries.
    Preserves provenance and literary-chapter vs. production-chunk metadata while maintaining
    100% backward compatibility with legacy API.
    """
    raw_chapters: List[Dict[str, Any]] = []

    is_file = False
    if isinstance(source, Path):
        is_file = source.is_file()
    elif isinstance(source, str) and len(source) < 300 and ("\n" not in source):
        try:
            is_file = Path(source).is_file()
        except Exception:
            is_file = False

    if is_file:
        source_path = Path(source).resolve()
        ext = source_path.suffix.lower()
        if ext == ".epub":
            _, epub_chapters = extract_epub(source_path)
            for idx, item in enumerate(epub_chapters, 1):
                if isinstance(item, dict):
                    raw_chapters.append(item)
                else:
                    sub = segment_chapters_from_text(item)
                    if sub:
                        raw_chapters.extend(sub)
                    else:
                        raw_chapters.append({
                            "title": f"Production Chunk {idx}",
                            "content": item,
                            "words": len(item.split()),
                            "unit_type": "production_chunk",
                            "is_literary_chapter": False,
                            "is_production_chunk": True,
                            "boundary_origin": "spine_fallback",
                            "literary_chapter_number": None,
                            "parent_chapter_title": None,
                            "chunk_index": idx,
                            "total_chunks": 1,
                        })
        elif ext in (".txt", ".md"):
            with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = clean_book_text(f.read())
            raw_chapters = segment_chapters_from_text(raw_text)
        elif ext == ".pdf":
            pdf_engine = ForensicPDFEngine(source_path)
            cleaned_pages, page_audits, escalated_pages = pdf_engine.extract_pages()
            canon_chaps = pdf_engine.segment_into_canonical_chapters(
                cleaned_pages, page_audits, escalated_pages=escalated_pages, max_words=12000
            )
            guarded_pdf_chapters: List[Dict[str, Any]] = []
            for c in canon_chaps:
                guarded_pdf_chapters.append({
                    "title": c.title,
                    "content": c.to_plain_text(),
                    "words": c.words,
                    "unit_type": c.unit_type,
                    "is_literary_chapter": c.is_literary_chapter,
                    "is_production_chunk": c.is_production_chunk,
                    "boundary_origin": c.boundary_origin,
                    "literary_chapter_number": c.literary_chapter_number,
                    "parent_chapter_id": c.parent_chapter_id,
                    "parent_chapter_title": c.parent_chapter_title,
                    "chunk_index": c.chunk_index,
                    "total_chunks": c.total_chunks_in_chapter,
                    "page_start": c.page_start,
                    "page_end": c.page_end,
                    "source_location": c.source_location,
                })
            return guarded_pdf_chapters
        else:
            raise ValueError(f"Unsupported file format: {ext}")
    else:
        raw_text = clean_book_text(str(source))
        raw_chapters = segment_chapters_from_text(raw_text)

    # Meso-Tier 12,000 word guard
    guarded_chapters: List[Dict[str, Any]] = []
    for chap in raw_chapters:
        title = chap.get("title", "Chapter")
        content = chap.get("content", "")
        words = chap.get("words", len(content.split()))
        is_lit = bool(chap.get("is_literary_chapter", True))
        b_origin = str(chap.get("boundary_origin", "detected_heading"))
        lit_num = chap.get("literary_chapter_number")
        c_start = int(chap.get("char_start", 0))

        if words > 12000:
            split_parts = split_large_chapter_on_semantic_boundary(
                title,
                content,
                max_words=12000,
                base_char_start=c_start,
                is_literary_chapter=is_lit,
                boundary_origin=b_origin,
                literary_chapter_number=lit_num,
            )
            guarded_chapters.extend(split_parts)
        else:
            guarded_chapters.append({
                **chap,
                "title": title,
                "content": content,
                "words": words,
                "unit_type": chap.get("unit_type", "literary_chapter" if is_lit else "production_chunk"),
                "is_literary_chapter": is_lit,
                "is_production_chunk": bool(chap.get("is_production_chunk", not is_lit)),
                "boundary_origin": b_origin,
                "literary_chapter_number": lit_num,
                "parent_chapter_title": chap.get("parent_chapter_title", title if is_lit else None),
                "chunk_index": chap.get("chunk_index", 1),
                "total_chunks": chap.get("total_chunks", 1),
            })

    return guarded_chapters


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 checksum of an input file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def process_book_file(
    input_file: Path,
    output_base_dir: Path,
    force_gate: bool = False,
) -> Dict[str, Any]:
    """
    Universal pipeline entrypoint:
    Ingests book file (EPUB, PDF, TXT, MD), builds canonical structured representation,
    preserves raw source, runs independent Quality Gate audit, and projects legacy chapter Markdown.
    
    Directory Structure Created:
    - <project_dir>/raw/            : Sacred source archive and source_manifest.json
    - <project_dir>/canonical/      : book.json and quality_report.json
    - <project_dir>/extracted/      : chapter_001.md, chapter_002.md... (for downstream stages)
    - <project_dir>/metadata.json   : Legacy project metadata with quality summary
    """
    t_start = time.time()
    input_file = Path(input_file).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Input book file not found: {input_file}")

    book_slug = re.sub(r"[^\w\-]", "_", input_file.stem.lower()).strip("_")
    project_dir = output_base_dir / book_slug
    raw_dir = project_dir / "raw"
    canonical_dir = project_dir / "canonical"
    extracted_dir = project_dir / "extracted"

    raw_dir.mkdir(parents=True, exist_ok=True)
    canonical_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    file_size_bytes = input_file.stat().st_size
    file_sha256 = compute_sha256(input_file)
    ext = input_file.suffix.lower()

    print(f"[*] Ingesting book: '{input_file.name}' (Format: {ext.upper()}, Size: {file_size_bytes / (1024*1024):.2f} MB)...")

    # 1. Preserve Raw Source
    raw_copy_path = raw_dir / f"source_original{ext}"
    raw_copied = False
    if not raw_copy_path.exists():
        try:
            shutil.copy2(input_file, raw_copy_path)
            raw_copied = True
        except Exception as copy_err:
            print(f"[!] WARNING: Failed to archive raw source to '{raw_copy_path}': {copy_err}")
    else:
        raw_copied = True

    source_manifest = {
        "book_id": book_slug,
        "original_path": str(input_file),
        "source_format": ext.lstrip("."),
        "file_size_bytes": file_size_bytes,
        "sha256": file_sha256,
        "archived_copy": str(raw_copy_path) if raw_copied else None,
        "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with open(raw_dir / "source_manifest.json", "w", encoding="utf-8") as f:
        json.dump(source_manifest, f, indent=2)

    # 2. Extract Document based on format
    canonical_book: Optional[CanonicalBook] = None

    if ext == ".epub":
        # Single-pass EPUB extraction
        parser = ForensicEPUBParser(input_file)
        canonical_book, _ = parser.parse()

    elif ext == ".pdf":
        pdf_engine = ForensicPDFEngine(input_file)
        cleaned_pages, page_audits, escalated_pages = pdf_engine.extract_pages()
        canonical_chapters = pdf_engine.segment_into_canonical_chapters(
            cleaned_pages,
            page_audits,
            escalated_pages=escalated_pages,
            max_words=12000,
        )

        suspicious_nums = [a.page_number for a in page_audits if a.is_suspicious]
        page_warnings: List[str] = []
        for a in page_audits:
            for w in a.warnings:
                msg = f"Page {a.page_number}: {w}"
                if msg not in page_warnings:
                    page_warnings.append(msg)

        report = ExtractionQualityReport(
            source_type="pdf",
            source_path=str(input_file),
            extraction_engine="pdf_layout_selective",
            total_pages_or_docs=len(page_audits),
            total_words=sum(c.words for c in canonical_chapters),
            total_chapters=len(canonical_chapters),
            total_blocks=sum(len(c.blocks) for c in canonical_chapters),
            suspicious_pages=suspicious_nums,
            fallback_pages=escalated_pages,
            fallback_used=len(escalated_pages) > 0,
            warnings=page_warnings,
        )

        canonical_book = CanonicalBook(
            book_id=book_slug,
            title=input_file.stem.replace("_", " ").title(),
            source_type="pdf",
            source_path=str(input_file),
            extraction_engine="pdf_layout_selective",
            quality_report=report,
            chapters=canonical_chapters,
        )

    elif ext in (".txt", ".md"):
        with open(input_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()

        # Preserve sacred raw text (only normalize CRLF line endings for offset indexing)
        raw_doc = raw_text.replace("\r\n", "\n").replace("\r", "\n")

        # Build line-offset lookup table for accurate line_start/line_end provenance
        line_offsets: List[Tuple[int, int, int]] = []
        ln_cursor = 0
        for ln_num, ln_str in enumerate(raw_doc.splitlines(keepends=True), 1):
            line_offsets.append((ln_cursor, ln_cursor + len(ln_str.rstrip("\n")), ln_num))
            ln_cursor += len(ln_str)

        chap_dicts = segment_chapters_from_text(raw_doc)
        canonical_chapters = []
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

            if words > 12000:
                splits = split_large_chapter_on_semantic_boundary(
                    title,
                    content,
                    max_words=12000,
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

                blocks = []
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

                    matching_lines = [
                        ln_num
                        for l_s, l_e, ln_num in line_offsets
                        if l_e >= block_doc_start and l_s <= block_doc_end
                    ]
                    l_start = matching_lines[0] if matching_lines else 1
                    l_end = matching_lines[-1] if matching_lines else l_start

                    b_type = "scene_break" if re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", para_clean) else "paragraph"
                    prov = SourceProvenance(
                        source_file=str(input_file),
                        source_type=ext.lstrip("."),
                        line_start=l_start,
                        line_end=l_end,
                        reading_order=global_reading_order,
                        char_offset=block_doc_start,
                        extraction_method="text_parser",
                    )
                    meta: Dict[str, Any] = {}
                    if norm_warnings:
                        meta["normalization_warnings"] = norm_warnings

                    block = CanonicalBlock(
                        id=f"b-ch{len(canonical_chapters)+1:03d}-{p_block_idx:04d}",
                        type=b_type,
                        raw_text=para_clean,
                        normalized_text=norm_para,
                        provenance=prov,
                        semantic_metadata=meta,
                    )
                    blocks.append(block)

                chap_num = len(canonical_chapters) + 1
                chap_conf = "MEDIUM" if p_origin == "fallback_production_chunk" else "HIGH"
                canonical_chap = CanonicalChapter(
                    id=f"ch-{chap_num:03d}",
                    number=chap_num,
                    title=p_title,
                    blocks=blocks,
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
                )
                canonical_chapters.append(canonical_chap)

        report = ExtractionQualityReport(
            source_type=ext.lstrip("."),
            source_path=str(input_file),
            extraction_engine="text_parser",
            total_pages_or_docs=1,
            total_words=sum(c.words for c in canonical_chapters),
            total_chapters=len(canonical_chapters),
            total_blocks=sum(len(c.blocks) for c in canonical_chapters),
        )

        canonical_book = CanonicalBook(
            book_id=book_slug,
            title=input_file.stem.replace("_", " ").title(),
            source_type=ext.lstrip("."),
            source_path=str(input_file),
            extraction_engine="text_parser",
            quality_report=report,
            chapters=canonical_chapters,
        )

    else:
        raise ValueError(f"Unsupported file format: {ext}")

    canonical_book.quality_report.duration_sec = round(time.time() - t_start, 2)

    # 3. Independent Quality Gate Audit (Fail-Closed on REVIEW unless force_gate is True)
    ExtractionQualityAuditor.audit(canonical_book, force_gate=force_gate)

    # 4. Save Canonical Representations
    canonical_book.save_canonical(canonical_dir)

    # 5. Project Legacy Markdown Output (extracted/chapter_XXX.md)
    canonical_book.project_legacy_extracted(extracted_dir)

    # 6. Generate and Save Legacy Project Metadata
    legacy_metadata = canonical_book.to_legacy_metadata()
    with open(project_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(legacy_metadata, f, indent=2, ensure_ascii=False)

    total_words = legacy_metadata["total_words"]
    total_chapters = legacy_metadata["total_chapters"]
    est_hours = legacy_metadata["estimated_total_hours"]
    gate = canonical_book.quality_report.gate_status

    print(f"[+] Ingestion complete: {total_chapters} chapters ({total_words} words, ~{est_hours} hrs) [Gate: {gate}] -> {project_dir}")
    return legacy_metadata
