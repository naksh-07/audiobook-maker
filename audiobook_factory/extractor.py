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
    Maintains 100% backward compatibility with legacy API.
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
                            "title": f"Chapter {idx}",
                            "content": item,
                            "words": len(item.split()),
                        })
        elif ext in (".txt", ".md"):
            with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = clean_book_text(f.read())
            raw_chapters = segment_chapters_from_text(raw_text)
        elif ext == ".pdf":
            raw_text = extract_gemini_pdf(source_path)
            raw_chapters = segment_chapters_from_text(raw_text)
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
        if words > 12000:
            split_parts = split_large_chapter_on_semantic_boundary(title, content, max_words=12000)
            guarded_chapters.extend(split_parts)
        else:
            guarded_chapters.append({
                "title": title,
                "content": content,
                "words": words,
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
    if not raw_copy_path.exists():
        try:
            shutil.copy2(input_file, raw_copy_path)
        except Exception:
            pass

    source_manifest = {
        "book_id": book_slug,
        "original_path": str(input_file),
        "source_format": ext.lstrip("."),
        "file_size_bytes": file_size_bytes,
        "sha256": file_sha256,
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
        raw_full_text = "\n\n".join(p for p in cleaned_pages if p.strip())
        
        # Segment into chapters
        chap_dicts = segment_chapters_from_text(raw_full_text)
        canonical_chapters: List[CanonicalChapter] = []

        for idx, cd in enumerate(chap_dicts, 1):
            title = cd.get("title", f"Chapter {idx}")
            content = cd.get("content", "")
            words = cd.get("words", len(content.split()))

            # Check 12k word ceiling
            if words > 12000:
                splits = split_large_chapter_on_semantic_boundary(title, content, max_words=12000)
            else:
                splits = [{"title": title, "content": content, "words": words}]

            for part_idx, part in enumerate(splits, 1):
                p_title = part["title"]
                p_content = part["content"]
                p_words = part["words"]

                # Build blocks with provenance
                blocks: List[CanonicalBlock] = []
                for p_block_idx, para in enumerate(re.split(r"\n{2,}", p_content), 1):
                    para_clean = para.strip()
                    if not para_clean:
                        continue
                    b_type = "scene_break" if re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", para_clean) else "paragraph"
                    prov = SourceProvenance(
                        source_file=str(input_file),
                        source_type="pdf",
                        reading_order=len(blocks) + 1,
                        extraction_method="pdf_pypdf_selective",
                    )
                    block = CanonicalBlock(
                        id=f"b-ch{len(canonical_chapters)+1:03d}-{p_block_idx:04d}",
                        type=b_type,
                        raw_text=para_clean,
                        normalized_text=para_clean,
                        provenance=prov,
                    )
                    blocks.append(block)

                chap_num = len(canonical_chapters) + 1
                canonical_chap = CanonicalChapter(
                    id=f"ch-{chap_num:03d}",
                    number=chap_num,
                    title=p_title,
                    blocks=blocks,
                    words=p_words,
                )
                canonical_chapters.append(canonical_chap)

        suspicious_nums = [a.page_number for a in page_audits if a.is_suspicious]
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

        norm_text = clean_book_text(raw_text)
        chap_dicts = segment_chapters_from_text(norm_text)
        canonical_chapters = []

        for idx, cd in enumerate(chap_dicts, 1):
            title = cd.get("title", f"Chapter {idx}")
            content = cd.get("content", "")
            words = cd.get("words", len(content.split()))

            if words > 12000:
                splits = split_large_chapter_on_semantic_boundary(title, content, max_words=12000)
            else:
                splits = [{"title": title, "content": content, "words": words}]

            for part in splits:
                p_title = part["title"]
                p_content = part["content"]
                p_words = part["words"]

                blocks = []
                for p_block_idx, para in enumerate(re.split(r"\n{2,}", p_content), 1):
                    para_clean = para.strip()
                    if not para_clean:
                        continue
                    b_type = "scene_break" if re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", para_clean) else "paragraph"
                    prov = SourceProvenance(
                        source_file=str(input_file),
                        source_type=ext.lstrip("."),
                        reading_order=len(blocks) + 1,
                        extraction_method="text_parser",
                    )
                    block = CanonicalBlock(
                        id=f"b-ch{len(canonical_chapters)+1:03d}-{p_block_idx:04d}",
                        type=b_type,
                        raw_text=para_clean,
                        normalized_text=para_clean,
                        provenance=prov,
                    )
                    blocks.append(block)

                chap_num = len(canonical_chapters) + 1
                canonical_chap = CanonicalChapter(
                    id=f"ch-{chap_num:03d}",
                    number=chap_num,
                    title=p_title,
                    blocks=blocks,
                    words=p_words,
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
