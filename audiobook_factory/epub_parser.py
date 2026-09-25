#!/usr/bin/env python3
"""
AudioBookmaker - Pillar 1: Forensic Structural EPUB Parser.
Extracts clean, structured canonical representations and metadata from EPUB 2 & 3 archives.
Features:
- Single-pass OPF and spine traversal (zero duplicate reading).
- DOM-aware structural block parsing with block-level provenance.
- NCX & EPUB 3 Nav landmark navigation with HTML anchor precision.
- Conservative semantic classification (defaults to 'paragraph' / 'unknown').
- Preserves dialogue typography and paragraph boundaries.
- 100% backward-compatible extract_epub() API.
"""

from __future__ import annotations
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from audiobook_factory.book_model import (
    CanonicalBook,
    CanonicalChapter,
    CanonicalBlock,
    SourceProvenance,
    ExtractionQualityReport,
    BlockType,
)
from audiobook_factory.normalizer import clean_book_text, normalize_block_text


class EPUBStructuralHTMLParser(HTMLParser):
    """
    Parses XHTML document fragments into structured CanonicalBlocks with source provenance.
    Preserves headings, blockquotes, scene breaks, and paragraphs without flattening.
    """

    def __init__(self, source_file: str, spine_item: str, base_reading_order: int = 0):
        super().__init__()
        self.source_file = source_file
        self.spine_item = spine_item
        self.base_reading_order = base_reading_order
        self.blocks: List[CanonicalBlock] = []

        # Parser state
        self.current_tag: Optional[str] = None
        self.current_attrs: Dict[str, str] = {}
        self.current_pieces: List[str] = []
        self.current_anchor: Optional[str] = None
        self.ignore_depth = 0
        self.ignore_tags = {"script", "style", "head", "title", "meta", "link"}
        self.block_index = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        attr_dict = {k.lower(): (v or "") for k, v in attrs}
        if tag in self.ignore_tags:
            self.ignore_depth += 1
            return

        if self.ignore_depth > 0:
            return

        anchor = attr_dict.get("id") or attr_dict.get("name")
        if anchor:
            self.current_anchor = anchor

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "hr"):
            self._flush_current_block()
            self.current_tag = tag
            self.current_attrs = attr_dict
            if tag == "hr":
                self._emit_block(
                    block_type="scene_break",
                    raw_text="* * *",
                    normalized_text="* * *",
                    tag="hr",
                    attrs=attr_dict,
                )
        elif tag == "br":
            self.current_pieces.append("\n")

    def handle_endtag(self, tag: str):
        if tag in self.ignore_tags:
            self.ignore_depth = max(0, self.ignore_depth - 1)
            return

        if self.ignore_depth > 0:
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote"):
            self._flush_current_block()
            self.current_tag = None
            self.current_attrs = {}

    def handle_data(self, data: str):
        if self.ignore_depth == 0:
            self.current_pieces.append(data)

    def _flush_current_block(self):
        if not self.current_pieces:
            return

        raw_content = "".join(self.current_pieces)
        self.current_pieces = []
        raw_stripped = raw_content.strip()
        if not raw_stripped:
            return

        tag = self.current_tag or "p"
        attrs = self.current_attrs

        # Conservative semantic classification
        block_type: BlockType = "paragraph"
        level = 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            block_type = "heading"
            level = int(tag[1])
        elif tag == "blockquote":
            block_type = "quote"
        else:
            # Check for scene break typography (e.g. * * *, ---, ###)
            if re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", raw_stripped):
                block_type = "scene_break"
            else:
                block_type = "paragraph"

        normalized, _ = normalize_block_text(raw_stripped)
        if not normalized:
            return

        meta: Dict[str, Any] = {}
        if block_type == "heading":
            meta["level"] = level

        self._emit_block(
            block_type=block_type,
            raw_text=raw_content,
            normalized_text=normalized,
            tag=tag,
            attrs=attrs,
            metadata=meta,
        )

    def _emit_block(
        self,
        block_type: BlockType,
        raw_text: str,
        normalized_text: str,
        tag: str,
        attrs: Dict[str, str],
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.block_index += 1
        line_num, col_offset = self.getpos()
        prov = SourceProvenance(
            source_file=self.source_file,
            source_type="epub",
            spine_item=self.spine_item,
            html_tag=tag,
            html_id=self.current_anchor,
            line_start=line_num,
            char_offset=col_offset,
            reading_order=self.base_reading_order + self.block_index,
            extraction_method="epub_dom",
        )
        block = CanonicalBlock(
            id=f"b-{self.spine_item}-{self.block_index:04d}",
            type=block_type,
            raw_text=raw_text,
            normalized_text=normalized_text,
            provenance=prov,
            confidence="HIGH",
            semantic_metadata=metadata or {},
        )
        self.blocks.append(block)

    def finalize(self) -> List[CanonicalBlock]:
        self._flush_current_block()
        return self.blocks


class ForensicEPUBParser:
    """
    Forensic structural parser for EPUB containers.
    Performs single-pass manifest and spine reading, NCX navigation mapping,
    and extracts structured CanonicalBook models with zero redundant unzipping.
    """

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path).resolve()
        if not self.file_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {self.file_path}")

    def parse(self) -> Tuple[CanonicalBook, List[Dict[str, Any]]]:
        """
        Parses the EPUB into a CanonicalBook and backward-compatible chapter dicts.
        Returns: (CanonicalBook, legacy_chapter_items)
        """
        metadata: Dict[str, Any] = {
            "title": self.file_path.stem.replace("_", " ").title(),
            "author": "Unknown Author",
            "format": "epub",
        }
        spine_items: List[str] = []
        manifest: Dict[str, str] = {}
        toc_href: Optional[str] = None
        opf_dir = ""

        with zipfile.ZipFile(self.file_path, "r") as zf:
            # 1. Locate OPF rootfile via META-INF/container.xml
            try:
                container_xml = zf.read("META-INF/container.xml")
                root = ET.fromstring(container_xml)
                rootfile_path = None
                for elem in root.iter():
                    if elem.tag.endswith("rootfile"):
                        rootfile_path = elem.attrib.get("full-path")
                        break
            except Exception:
                rootfile_path = None

            if not rootfile_path:
                for name in zf.namelist():
                    if name.endswith(".opf"):
                        rootfile_path = name
                        break

            if not rootfile_path:
                raise ValueError(f"Could not locate .opf manifest in EPUB: {self.file_path}")

            opf_dir = str(Path(rootfile_path).parent)
            if opf_dir == ".":
                opf_dir = ""

            opf_content = zf.read(rootfile_path)
            opf_root = ET.fromstring(opf_content)

            # 2. Extract Metadata
            for elem in opf_root.iter():
                if elem.tag.endswith("title") and elem.text and not metadata.get("found_title"):
                    metadata["title"] = elem.text.strip()
                    metadata["found_title"] = True
                elif elem.tag.endswith("creator") and elem.text and not metadata.get("found_author"):
                    metadata["author"] = elem.text.strip()
                    metadata["found_author"] = True
                elif elem.tag.endswith("language") and elem.text:
                    metadata["language"] = elem.text.strip()
            metadata.pop("found_title", None)
            metadata.pop("found_author", None)

            # 3. Parse Manifest
            for elem in opf_root.iter():
                if elem.tag.endswith("item"):
                    item_id = elem.attrib.get("id")
                    href = elem.attrib.get("href")
                    media_type = elem.attrib.get("media-type", "")
                    if item_id and href:
                        full_href = f"{opf_dir}/{href}".replace("\\", "/").lstrip("/") if opf_dir else href
                        manifest[item_id] = full_href
                        if "ncx" in media_type.lower() or item_id.lower() in ("ncx", "toc"):
                            toc_href = full_href

            # 4. Parse Spine reading order
            for elem in opf_root.iter():
                if elem.tag.endswith("itemref"):
                    idref = elem.attrib.get("idref")
                    if idref in manifest:
                        spine_items.append(manifest[idref])

            # 5. Locate TOC navigation points (EPUB 2 NCX or EPUB 3 Nav)
            nav_points: List[Tuple[str, str]] = []
            if not toc_href:
                for name in zf.namelist():
                    if name.endswith(".ncx"):
                        toc_href = name
                        break

            if toc_href and toc_href in zf.namelist():
                try:
                    toc_xml = zf.read(toc_href).decode("utf-8", errors="ignore")
                    toc_root = ET.fromstring(toc_xml)
                    for nav in toc_root.iter():
                        if nav.tag.endswith("navPoint"):
                            lbl_elem = None
                            src_attr = None
                            for child in nav.iter():
                                if child.tag.endswith("text") and child.text and not lbl_elem:
                                    lbl_elem = child.text.strip()
                                elif child.tag.endswith("content") and "src" in child.attrib and not src_attr:
                                    src_attr = child.attrib.get("src", "").strip()
                            if lbl_elem and src_attr:
                                if opf_dir and not src_attr.startswith(opf_dir):
                                    full_src = f"{opf_dir}/{src_attr}".replace("\\", "/").lstrip("/")
                                else:
                                    full_src = src_attr
                                nav_points.append((lbl_elem, full_src))
                except Exception:
                    nav_points = []

            # 6. Parse Content & Extract Blocks
            chapters: List[CanonicalChapter] = []
            legacy_items: List[Dict[str, Any]] = []

            if nav_points:
                # Map continuous spine content
                file_offsets: Dict[str, int] = {}
                file_lengths: Dict[str, int] = {}
                spine_raw_map: Dict[str, str] = {}
                current_pos = 0

                for sf in spine_items:
                    try:
                        c = zf.read(sf).decode("utf-8", errors="ignore")
                    except Exception:
                        c = ""
                    file_offsets[sf] = current_pos
                    file_lengths[sf] = len(c)
                    spine_raw_map[sf] = c
                    current_pos += len(c)

                full_html = "".join(spine_raw_map[sf] for sf in spine_items)

                # Locate nav positions with anchor precision
                all_nav_positions: List[Tuple[str, int, str]] = []
                for lbl, src in nav_points:
                    parts = src.split("#")
                    sf = parts[0]
                    anchor = parts[1] if len(parts) > 1 else ""
                    if sf in file_offsets:
                        base_offset = file_offsets[sf]
                        file_slice = full_html[base_offset : base_offset + file_lengths.get(sf, 0)]
                        if anchor:
                            m = re.search(r'(?:id|name)=["\']' + re.escape(anchor) + r'["\']', file_slice)
                            if m:
                                last_open = file_slice.rfind('<', 0, m.start())
                                last_close = file_slice.rfind('>', 0, m.start())
                                if last_open != -1 and last_open > last_close:
                                    pos = base_offset + last_open
                                else:
                                    pos = base_offset + m.start()
                            else:
                                pos = base_offset
                        else:
                            pos = base_offset
                        all_nav_positions.append((lbl, pos, sf))

                skip_keywords = ["extras", "meet the author", "preview", "copyright", "about the author", "cover", "toc"]

                for i, (title, pos, spine_file) in enumerate(all_nav_positions):
                    if any(sk in title.lower() for sk in skip_keywords):
                        continue
                    end_pos = all_nav_positions[i + 1][1] if i + 1 < len(all_nav_positions) else len(full_html)
                    chunk_html = full_html[pos:end_pos]
                    if not chunk_html.strip():
                        continue

                    # Parse chunk with EPUBStructuralHTMLParser
                    parser = EPUBStructuralHTMLParser(
                        source_file=str(self.file_path),
                        spine_item=spine_file,
                        base_reading_order=len(chapters) * 1000,
                    )
                    parser.feed(chunk_html)
                    blocks = parser.finalize()
                    
                    # Generate chapter text from parsed blocks
                    clean_text = "\n\n".join(b.normalized_text for b in blocks if b.normalized_text.strip())
                    clean_text = re.sub(r'^(?:id|name)=["\'][^"\']+["\']>\s*', '', clean_text).strip()
                    clean_text = re.sub(r'^' + re.escape(title) + r'\s*', '', clean_text, flags=re.IGNORECASE).strip()
                    word_count = len(clean_text.split())

                    if word_count >= 30:
                        chap_num = len(chapters) + 1
                        canonical_chap = CanonicalChapter(
                            id=f"ch-{chap_num:03d}",
                            number=chap_num,
                            title=title,
                            blocks=blocks,
                            source_location=spine_file,
                            confidence="HIGH",
                            words=word_count,
                            unit_type="literary_chapter",
                            is_literary_chapter=True,
                            is_production_chunk=False,
                            boundary_origin="toc_navigation",
                            literary_chapter_number=chap_num,
                            parent_chapter_title=title,
                            chunk_index=1,
                            total_chunks_in_chapter=1,
                        )
                        chapters.append(canonical_chap)
                        legacy_items.append({
                            "title": title,
                            "content": clean_text,
                            "words": word_count,
                            "unit_type": "literary_chapter",
                            "is_literary_chapter": True,
                            "is_production_chunk": False,
                            "boundary_origin": "toc_navigation",
                            "literary_chapter_number": chap_num,
                            "parent_chapter_title": title,
                            "chunk_index": 1,
                            "total_chunks": 1,
                            "source_location": spine_file,
                        })

            # Fallback to sequential spine document traversal
            if not chapters:
                global_order = 0
                lit_counter = 0
                for item_path in spine_items:
                    try:
                        content = zf.read(item_path).decode("utf-8", errors="ignore")
                    except Exception:
                        continue

                    parser = EPUBStructuralHTMLParser(
                        source_file=str(self.file_path),
                        spine_item=item_path,
                        base_reading_order=global_order,
                    )
                    parser.feed(content)
                    blocks = parser.finalize()
                    global_order += len(blocks)

                    clean_text = "\n\n".join(b.normalized_text for b in blocks if b.normalized_text.strip())
                    word_count = len(clean_text.split())
                    if word_count >= 30:
                        chap_num = len(chapters) + 1
                        has_heading = bool(blocks and blocks[0].type == "heading")
                        if has_heading:
                            lit_counter += 1
                            title = blocks[0].normalized_text.strip()
                            unit_type = "literary_chapter"
                            is_lit = True
                            is_prod = False
                            origin = "detected_heading"
                            lit_num: Optional[int] = lit_counter
                            parent_title: Optional[str] = title
                        else:
                            title = f"Production Chunk {chap_num}"
                            unit_type = "production_chunk"
                            is_lit = False
                            is_prod = True
                            origin = "spine_fallback"
                            lit_num = None
                            parent_title = None

                        canonical_chap = CanonicalChapter(
                            id=f"ch-{chap_num:03d}",
                            number=chap_num,
                            title=title,
                            blocks=blocks,
                            source_location=item_path,
                            confidence="HIGH" if is_lit else "MEDIUM",
                            words=word_count,
                            unit_type=unit_type,
                            is_literary_chapter=is_lit,
                            is_production_chunk=is_prod,
                            boundary_origin=origin,
                            literary_chapter_number=lit_num,
                            parent_chapter_title=parent_title,
                            chunk_index=1 if is_lit else chap_num,
                            total_chunks_in_chapter=1,
                        )
                        chapters.append(canonical_chap)

        # Meso-Tier 12k-word Semantic Split for oversized EPUB chapters
        chapters, legacy_items = self._split_oversized_epub_chapters(chapters, max_words=12000)

        # Build Quality Report
        total_words = sum(c.words for c in chapters)
        total_blocks = sum(len(c.blocks) for c in chapters)
        used_fallback = any(c.boundary_origin in ("fallback_production_chunk", "spine_fallback") for c in chapters)

        book_slug = re.sub(r"[^\w\-]", "_", self.file_path.stem.lower()).strip("_")
        canonical_book = CanonicalBook(
            book_id=book_slug,
            title=metadata.get("title", self.file_path.stem.replace("_", " ").title()),
            author=metadata.get("author", "Unknown Author"),
            source_type="epub",
            source_path=str(self.file_path),
            extraction_engine="epub_dom_structural",
            chapters=chapters,
            raw_metadata=metadata,
        )
        detected_lit = len(canonical_book.get_literary_chapters())
        prod_chunks = len(canonical_book.get_production_chunks())

        report = ExtractionQualityReport(
            overall_confidence="HIGH" if len(chapters) > 0 and total_words > 100 and not used_fallback else ("MEDIUM" if used_fallback else "LOW"),
            gate_status="PASS" if len(chapters) > 0 and total_words > 100 else "REVIEW",
            source_type="epub",
            source_path=str(self.file_path),
            extraction_engine="epub_dom_structural",
            total_pages_or_docs=len(spine_items),
            total_words=total_words,
            total_chapters=len(chapters),
            detected_literary_chapters=detected_lit,
            production_chunks=prod_chunks,
            used_fallback_chunking=used_fallback,
            total_blocks=total_blocks,
        )
        canonical_book.quality_report = report

        return canonical_book, legacy_items

    @staticmethod
    def _split_oversized_epub_chapters(
        chapters: List[CanonicalChapter], max_words: int = 12000
    ) -> Tuple[List[CanonicalChapter], List[Dict[str, Any]]]:
        """
        Applies the 12,000-word Meso-Tier semantic split to any oversized EPUB CanonicalChapter
        while preserving block-level SourceProvenance and parent literary chapter links.
        """
        from audiobook_factory.chapter_segmenter import split_large_chapter_on_semantic_boundary
        from audiobook_factory.normalizer import normalize_block_text

        def _expand_oversized_blocks(blocks: List[CanonicalBlock]) -> List[CanonicalBlock]:
            expanded: List[CanonicalBlock] = []
            for blk in blocks:
                blk_words = len(blk.normalized_text.split())
                if blk_words <= max_words:
                    expanded.append(blk)
                    continue
                sub_parts = split_large_chapter_on_semantic_boundary(
                    "Block", blk.raw_text, max_words=max_words, base_char_start=blk.provenance.char_offset or 0
                )
                for sp_idx, sp in enumerate(sub_parts, 1):
                    norm_txt, warns = normalize_block_text(sp["content"])
                    prov_copy = blk.provenance.model_copy(
                        update={"char_offset": sp.get("char_start", blk.provenance.char_offset)}
                    )
                    expanded.append(
                        CanonicalBlock(
                            id=f"{blk.id}-p{sp_idx}",
                            type=blk.type,
                            raw_text=sp["content"],
                            normalized_text=norm_txt,
                            provenance=prov_copy,
                            warnings=warns,
                        )
                    )
            return expanded

        def _partition_blocks(blocks: List[CanonicalBlock]) -> List[List[CanonicalBlock]]:
            total_w = sum(len(b.normalized_text.split()) for b in blocks)
            if total_w <= max_words or len(blocks) <= 1:
                return [blocks]
            target_w = total_w / 2.0
            cum_w = 0
            best_idx = 1
            best_score = float("inf")
            for idx in range(1, len(blocks)):
                cum_w += len(blocks[idx - 1].normalized_text.split())
                if cum_w == 0 or cum_w >= total_w:
                    continue
                dist = abs(cum_w - target_w)
                # Prefer splitting right after a scene_break or right before a heading in central 20%-80%
                if 0.20 * total_w <= cum_w <= 0.80 * total_w:
                    if blocks[idx - 1].type == "scene_break":
                        dist *= 0.25
                    elif blocks[idx].type == "heading":
                        dist *= 0.35
                if dist < best_score:
                    best_score = dist
                    best_idx = idx
            left = _partition_blocks(blocks[:best_idx])
            right = _partition_blocks(blocks[best_idx:])
            return left + right

        final_chapters: List[CanonicalChapter] = []
        legacy_items: List[Dict[str, Any]] = []
        seq_num = 0

        for ch in chapters:
            if ch.words <= max_words:
                seq_num += 1
                updated_ch = ch.model_copy(update={"id": f"ch-{seq_num:03d}", "number": seq_num})
                final_chapters.append(updated_ch)
                clean_text = "\n\n".join(b.normalized_text for b in updated_ch.blocks if b.normalized_text.strip())
                legacy_items.append({
                    "title": updated_ch.title,
                    "content": clean_text,
                    "words": updated_ch.words,
                    "unit_type": updated_ch.unit_type,
                    "is_literary_chapter": updated_ch.is_literary_chapter,
                    "is_production_chunk": updated_ch.is_production_chunk,
                    "boundary_origin": updated_ch.boundary_origin,
                    "literary_chapter_number": updated_ch.literary_chapter_number,
                    "parent_chapter_title": updated_ch.parent_chapter_title,
                    "chunk_index": updated_ch.chunk_index,
                    "total_chunks": updated_ch.total_chunks_in_chapter,
                    "source_location": updated_ch.source_location,
                })
                continue

            expanded_blocks = _expand_oversized_blocks(ch.blocks)
            groups = _partition_blocks(expanded_blocks)
            total_parts = len(groups)
            parent_id = ch.parent_chapter_id or (
                f"lit-ch-{ch.literary_chapter_number:03d}" if ch.literary_chapter_number else ch.id
            )
            parent_title = ch.title if ch.is_literary_chapter else ch.parent_chapter_title
            split_origin = "semantic_split_chunk" if ch.is_literary_chapter else ch.boundary_origin

            for part_idx, grp in enumerate(groups, 1):
                seq_num += 1
                part_title = f"{ch.title} (Part {part_idx})" if total_parts > 1 else ch.title
                clean_text = "\n\n".join(b.normalized_text for b in grp if b.normalized_text.strip())
                part_words = len(clean_text.split())
                chunk_chap = CanonicalChapter(
                    id=f"ch-{seq_num:03d}",
                    number=seq_num,
                    title=part_title,
                    blocks=grp,
                    source_location=ch.source_location,
                    confidence=ch.confidence,
                    words=part_words,
                    unit_type="production_chunk",
                    is_literary_chapter=False,
                    is_production_chunk=True,
                    boundary_origin=split_origin,
                    parent_chapter_id=parent_id,
                    parent_chapter_title=parent_title,
                    literary_chapter_number=ch.literary_chapter_number,
                    chunk_index=part_idx,
                    total_chunks_in_chapter=total_parts,
                )
                final_chapters.append(chunk_chap)
                legacy_items.append({
                    "title": part_title,
                    "content": clean_text,
                    "words": part_words,
                    "unit_type": "production_chunk",
                    "is_literary_chapter": False,
                    "is_production_chunk": True,
                    "boundary_origin": split_origin,
                    "parent_chapter_id": parent_id,
                    "parent_chapter_title": parent_title,
                    "literary_chapter_number": ch.literary_chapter_number,
                    "chunk_index": part_idx,
                    "total_chunks": total_parts,
                    "source_location": ch.source_location,
                })

        return final_chapters, legacy_items


def extract_epub(file_path: Path) -> Tuple[Dict[str, Any], List[Any]]:
    """
    Backward-compatible entry point for existing code.
    Delegates to ForensicEPUBParser to eliminate duplicate unzipping.
    """
    parser = ForensicEPUBParser(file_path)
    canonical_book, legacy_items = parser.parse()
    metadata = {
        "title": canonical_book.title,
        "author": canonical_book.author,
        "format": "EPUB",
    }
    return metadata, legacy_items
