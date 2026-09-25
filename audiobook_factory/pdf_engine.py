#!/usr/bin/env python3
"""
AudioBookmaker - Pillar 1: Lightweight Layout-Aware PDF Engine & Quality Analyzer.
Provides:
- Coordinate-aware & multi-column human reading-order text extraction via pypdf.
- Lightweight page-level quality analysis (density, multi-column indicators, headers/footers, OCR noise).
- Multi-signal quality comparison gate for selective Gemini Vision escalation.
- Reassembly into canonical chapters and blocks with lossless page-level provenance.
"""

from __future__ import annotations
import os
import re
import json
import base64
import statistics
import urllib.request
import urllib.error
from dataclasses import dataclass
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
from audiobook_factory.chapter_segmenter import (
    CHAPTER_PATTERNS,
    COMBINED_CHAPTER_REGEX,
    segment_chapters_from_text,
    split_large_chapter_on_semantic_boundary,
)


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


class PDFLayoutReconstructor:
    """
    Reconstructs human reading order from multi-column and complex-layout PDF pages.
    Supports both geometric coordinate spans (from pypdf content streams) and
    whitespace-aligned multi-column text layouts.
    """

    @classmethod
    def extract_positioned_spans(cls, page: Any) -> List[PDFTextSpan]:
        """
        Extracts positioned text spans from a pypdf PageObject using its content stream
        and text state matrices. Returns an empty list if geometric ops are unavailable.
        """
        try:
            from pypdf.generic import ContentStream
            from pypdf._text_extraction._layout_mode._text_state_manager import TextStateManager
            from pypdf._text_extraction._layout_mode._fixed_width_page import (
                recurse_to_target_op,
                resolve_font,
            )

            if "/Contents" not in page:
                return []
            fonts = page._layout_mode_fonts()
            ops = iter(ContentStream(page["/Contents"].get_object(), page.pdf, "bytes").operations)
            state_mgr = TextStateManager()
            tj_ops = []
            for operands, op in ops:
                if op in (b"BT", b"q"):
                    _, sub_tjs = recurse_to_target_op(
                        ops, state_mgr, b"ET" if op == b"BT" else b"Q", fonts, True
                    )
                    tj_ops.extend(sub_tjs)
                elif op == b"Tf":
                    state_mgr.set_font(resolve_font(fonts, operands[0]), operands[1])
                else:
                    state_mgr.set_state_param(op, operands)

            raw_spans: List[PDFTextSpan] = []
            seq = 0
            for tj in tj_ops:
                if not tj.text or not tj.text.strip():
                    continue
                fh = float(tj.font_height) if tj.font_height and tj.font_height > 0 else 12.0
                sw = float(tj.space_tx) if tj.space_tx and tj.space_tx > 0 else max(2.5, fh * 0.28)
                flip_v = bool(tj.flip_vertical)
                y_dir = 1.0 if flip_v else -1.0

                # Handle embedded newlines inside a single Tj string
                if "\n" in tj.text:
                    sub_lines = tj.text.split("\n")
                    y_cursor = float(tj.ty)
                    for sub_ln in sub_lines:
                        if not sub_ln.strip():
                            y_cursor += y_dir * (fh * 0.9)
                            continue
                        seq += 1
                        est_w = max(float(tj.displaced_tx) - float(tj.tx), len(sub_ln.strip()) * sw)
                        raw_spans.append(
                            PDFTextSpan(
                                text=sub_ln,
                                x0=float(tj.tx),
                                y=y_cursor,
                                x1=float(tj.tx) + est_w,
                                font_height=fh,
                                space_width=sw,
                                flip_vertical=flip_v,
                                seq_order=seq,
                            )
                        )
                        y_cursor += y_dir * (fh * 1.2)
                else:
                    seq += 1
                    est_x1 = max(float(tj.displaced_tx), float(tj.tx) + len(tj.text.strip()) * sw)
                    raw_spans.append(
                        PDFTextSpan(
                            text=tj.text,
                            x0=float(tj.tx),
                            y=float(tj.ty),
                            x1=est_x1,
                            font_height=fh,
                            space_width=sw,
                            flip_vertical=flip_v,
                            seq_order=seq,
                        )
                    )
            return raw_spans
        except Exception:
            return []

    @classmethod
    def _merge_baseline_segments(cls, raw_spans: List[PDFTextSpan]) -> List[PDFTextSpan]:
        """
        Groups character/word spans lying on the same horizontal baseline into line segments,
        splitting into separate segments whenever a horizontal column gutter gap is encountered.
        """
        if not raw_spans:
            return []

        flip_v = raw_spans[0].flip_vertical
        # Sort by top-to-bottom y, then x0, then seq_order
        sorted_by_y = sorted(
            raw_spans,
            key=lambda s: (s.y if flip_v else -s.y, s.x0, s.seq_order),
        )

        # Group into baseline rows
        rows: List[List[PDFTextSpan]] = []
        for sp in sorted_by_y:
            if not rows:
                rows.append([sp])
                continue
            prev_row = rows[-1]
            ref_y = prev_row[0].y
            tol = 0.45 * max(prev_row[0].font_height, sp.font_height, 8.0)
            if abs(sp.y - ref_y) <= tol:
                prev_row.append(sp)
            else:
                rows.append([sp])

        line_segments: List[PDFTextSpan] = []
        seq = 0
        for row in rows:
            # Sort left-to-right within the row
            row.sort(key=lambda s: (s.x0, s.seq_order))
            cur = PDFTextSpan(
                text=row[0].text,
                x0=row[0].x0,
                y=row[0].y,
                x1=row[0].x1,
                font_height=row[0].font_height,
                space_width=row[0].space_width,
                flip_vertical=row[0].flip_vertical,
                seq_order=row[0].seq_order,
            )
            for frag in row[1:]:
                gap = frag.x0 - cur.x1
                # A normal word space is ~1x space_width; column gutters are >= 14pt and > 3.5x space_width
                gutter_threshold = max(3.5 * max(cur.space_width, frag.space_width), 14.0)
                if gap > gutter_threshold:
                    cur.text = cur.text.strip()
                    if cur.text:
                        seq += 1
                        cur.seq_order = seq
                        line_segments.append(cur)
                    cur = PDFTextSpan(
                        text=frag.text,
                        x0=frag.x0,
                        y=frag.y,
                        x1=frag.x1,
                        font_height=frag.font_height,
                        space_width=frag.space_width,
                        flip_vertical=frag.flip_vertical,
                        seq_order=frag.seq_order,
                    )
                else:
                    need_space = (
                        gap > 0.30 * min(cur.space_width, frag.space_width)
                        and not cur.text.endswith((" ", "-"))
                        and not frag.text.startswith((" ", ".", ",", ";", ":", "!", "?", ")", "]"))
                    )
                    cur.text = f"{cur.text} {frag.text}" if need_space else f"{cur.text}{frag.text}"
                    cur.x1 = max(cur.x1, frag.x1)
                    cur.font_height = max(cur.font_height, frag.font_height)

            cur.text = cur.text.strip()
            if cur.text:
                seq += 1
                cur.seq_order = seq
                line_segments.append(cur)

        return line_segments

    @classmethod
    def _find_vertical_column_gutter(
        cls, spans: List[PDFTextSpan]
    ) -> Optional[Tuple[float, float]]:
        """
        Detects a vertical column gutter (g_left, g_right) among line segments,
        even when centered headers, subheadings, or footers bridge across the gutter.
        Requires that the left and right column groups have overlapping vertical y-extents
        and genuine side-by-side multi-column lines (or dense parallel column stacks) within
        that vertical band, preventing false splits on single-column dialogue/epigraphs.
        """
        if len(spans) < 2:
            return None

        min_x = min(s.x0 for s in spans)
        max_x = max(s.x1 for s in spans)
        total_w = max_x - min_x
        if total_w < 80.0:
            return None

        min_gutter_w = max(12.0, 0.025 * total_w)
        flip_v = spans[0].flip_vertical
        top_y = lambda s: s.y if flip_v else -s.y
        sorted_fhs = sorted(s.font_height for s in spans)
        body_fh = sorted_fhs[len(sorted_fhs) // 2]
        tol_y = body_fh * 0.65

        # Collect candidate x_cut split points from pairs of horizontally separated spans
        candidate_cuts_set = set()
        for a in spans:
            for b in spans:
                if b.x0 - a.x1 >= min_gutter_w:
                    candidate_cuts_set.add(round(0.5 * (a.x1 + b.x0), 1))

        if not candidate_cuts_set:
            return None

        best_gutter: Optional[Tuple[float, float]] = None
        best_score: Tuple[int, int, float, float] = (-1, -1, -1.0, 0.0)

        for x_cut in sorted(candidate_cuts_set):
            left_group = [s for s in spans if s.x1 <= x_cut + 0.5]
            right_group = [s for s in spans if s.x0 >= x_cut - 0.5]
            if not left_group or not right_group:
                continue

            g_left = max(s.x1 for s in left_group)
            g_right = min(s.x0 for s in right_group)
            gutter_width = g_right - g_left
            if gutter_width < min_gutter_w:
                continue

            # Verify vertical overlap between left_group and right_group
            l_min_y = min(top_y(s) for s in left_group)
            l_max_y = max(top_y(s) for s in left_group)
            r_min_y = min(top_y(s) for s in right_group)
            r_max_y = max(top_y(s) for s in right_group)

            overlap_top = max(l_min_y, r_min_y) - tol_y
            overlap_bot = min(l_max_y, r_max_y) + tol_y
            if overlap_bot < overlap_top:
                continue

            crossing_group = [
                s for s in spans if s.x0 < g_right - 0.5 and s.x1 > g_left + 0.5
            ]
            left_in_band = [
                s for s in left_group if overlap_top <= top_y(s) <= overlap_bot
            ]
            right_in_band = [
                s for s in right_group if overlap_top <= top_y(s) <= overlap_bot
            ]
            crossing_in_band = [
                s for s in crossing_group if overlap_top <= top_y(s) <= overlap_bot
            ]

            if not left_in_band or not right_in_band:
                continue

            # Count genuine side-by-side horizontal row pairs (left and right segments sharing a baseline row)
            same_row_pairs = 0
            for r_sp in right_in_band:
                row_tol = 0.65 * max(r_sp.font_height, body_fh)
                if any(abs(top_y(l_sp) - top_y(r_sp)) <= row_tol for l_sp in left_in_band):
                    same_row_pairs += 1

            # Check if both sides form dense vertical column stacks (for columns with independent leading)
            def _is_dense_column_stack(col_spans: List[PDFTextSpan]) -> bool:
                if len(col_spans) < 3:
                    return False
                ys = sorted(top_y(s) for s in col_spans)
                dys = [ys[i + 1] - ys[i] for i in range(len(ys) - 1) if ys[i + 1] - ys[i] > 1.0]
                if not dys:
                    return False
                dys.sort()
                median_dy = dys[len(dys) // 2]
                return median_dy <= 2.2 * body_fh

            min_side_count = min(len(left_in_band), len(right_in_band))
            has_parallel_rows = same_row_pairs >= 2 or (
                same_row_pairs >= 1 and len(spans) <= 4 and min_side_count >= 1
            )
            has_dense_staggered_cols = (
                min_side_count >= 3
                and _is_dense_column_stack(left_in_band)
                and _is_dense_column_stack(right_in_band)
            )
            if not (has_parallel_rows or has_dense_staggered_cols):
                continue

            # Ensure multi-column spans dominate any mid-band spanning banners
            col_count_in_band = len(left_in_band) + len(right_in_band)
            if col_count_in_band <= 2 * len(crossing_in_band):
                continue

            # Score prefers side-by-side row pairs, balanced column support, wider gutter, and leftmost split first
            support = min_side_count * 10 + col_count_in_band
            score = (same_row_pairs, support, round(gutter_width, 1), -g_left)
            if score > best_score:
                best_score = score
                best_gutter = (g_left, g_right)

        return best_gutter

    @classmethod
    def _order_blocks_xy_cut(
        cls, spans: List[PDFTextSpan], base_col_index: int = 1
    ) -> List[List[PDFTextSpan]]:
        """
        Recursively decomposes page spans into ordered single-column blocks:
        1. Splits horizontally around full-width or centered spanning banners/headers/footers.
        2. Splits vertically across multi-column gutters (Left Column -> Right Column).
        """
        if not spans:
            return []

        flip_v = spans[0].flip_vertical
        top_y = lambda s: s.y if flip_v else -s.y
        spans_sorted_y = sorted(spans, key=lambda s: (top_y(s), s.x0))

        gutter = cls._find_vertical_column_gutter(spans_sorted_y)
        if gutter is None:
            for s in spans_sorted_y:
                if s.column_index is None:
                    s.column_index = base_col_index
            return [spans_sorted_y]

        g_left, g_right = gutter
        x_split = 0.5 * (g_left + g_right)

        # Identify spanning/centered lines that bridge across the vertical column gutter
        spanning_indices: List[int] = []
        for idx, s in enumerate(spans_sorted_y):
            if s.x0 < g_right - 1.0 and s.x1 > g_left + 1.0:
                spanning_indices.append(idx)

        if spanning_indices:
            # Partition horizontally around spanning banners
            ordered_blocks: List[List[PDFTextSpan]] = []
            cur_band: List[PDFTextSpan] = []
            for idx, s in enumerate(spans_sorted_y):
                if idx in spanning_indices:
                    if cur_band:
                        ordered_blocks.extend(cls._order_blocks_xy_cut(cur_band, base_col_index=1))
                        cur_band = []
                    s.column_index = 1
                    ordered_blocks.append([s])
                else:
                    cur_band.append(s)
            if cur_band:
                ordered_blocks.extend(cls._order_blocks_xy_cut(cur_band, base_col_index=1))
            return ordered_blocks

        # No spanning lines in this band: split into left column and right region
        left_col = [s for s in spans_sorted_y if 0.5 * (s.x0 + s.x1) < x_split]
        right_region = [s for s in spans_sorted_y if 0.5 * (s.x0 + s.x1) >= x_split]

        for s in left_col:
            s.column_index = base_col_index

        result: List[List[PDFTextSpan]] = []
        if left_col:
            result.append(sorted(left_col, key=lambda s: (top_y(s), s.x0)))
        if right_region:
            result.extend(cls._order_blocks_xy_cut(right_region, base_col_index=base_col_index + 1))
        return result

    @classmethod
    def _assemble_paragraphs_from_blocks(cls, blocks: List[List[PDFTextSpan]]) -> str:
        """
        Assembles ordered single-column span blocks into paragraphs (\n\n between paragraphs,
        \n within wrapped paragraph lines), joining cross-column mid-sentence continuations.
        """
        if not blocks:
            return ""

        paragraphs: List[str] = []

        for b_idx, block in enumerate(blocks):
            if not block:
                continue
            if len(block) == 1:
                paragraphs.append(block[0].text.strip())
                continue

            flip_v = block[0].flip_vertical
            top_y = lambda s: s.y if flip_v else -s.y
            col_min_x = min(s.x0 for s in block)

            dys = [
                top_y(block[i]) - top_y(block[i - 1])
                for i in range(1, len(block))
                if (top_y(block[i]) - top_y(block[i - 1])) > 1.0
            ]
            median_fh = statistics.median(s.font_height for s in block)
            typical_dy = statistics.median(dys) if dys else (median_fh * 1.2)
            typical_dy = max(typical_dy, median_fh * 0.85)

            cur_lines: List[str] = [block[0].text.strip()]
            for i in range(1, len(block)):
                prev_s = block[i - 1]
                curr_s = block[i]
                dy = top_y(curr_s) - top_y(prev_s)

                is_para_gap = dy > max(1.38 * typical_dy, 1.55 * max(prev_s.font_height, curr_s.font_height))
                is_font_jump = abs(curr_s.font_height - prev_s.font_height) >= 2.0
                is_heading_or_break = bool(
                    re.match(COMBINED_CHAPTER_REGEX, curr_s.text.strip(), flags=re.IGNORECASE)
                    or re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", curr_s.text.strip())
                    or re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", prev_s.text.strip())
                )
                is_indented_new_para = (
                    (curr_s.x0 - col_min_x) >= max(10.0, 2.5 * curr_s.space_width)
                    and prev_s.text.rstrip().endswith((".", "!", "?", '"', "”", "’", "।"))
                )

                if is_para_gap or is_font_jump or is_heading_or_break or is_indented_new_para:
                    paragraphs.append("\n".join(cur_lines))
                    cur_lines = [curr_s.text.strip()]
                else:
                    cur_lines.append(curr_s.text.strip())

            if cur_lines:
                col_first_para = "\n".join(cur_lines)
                paragraphs.append(col_first_para)

        # Merge cross-column mid-sentence continuations if previous paragraph ended mid-sentence
        # and next paragraph starts with a lowercase continuation word
        merged_paragraphs: List[str] = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            if merged_paragraphs:
                prev_p = merged_paragraphs[-1]
                prev_ends_mid_sentence = (
                    not prev_p.rstrip().endswith((".", "!", "?", ":", ";", '"', "'", "”", "’", "।", "*"))
                    and not re.match(COMBINED_CHAPTER_REGEX, prev_p.splitlines()[-1].strip(), flags=re.IGNORECASE)
                )
                curr_starts_lower = bool(para and (para[0].islower() or para.startswith(("—", "–"))))
                if prev_ends_mid_sentence and curr_starts_lower:
                    if prev_p.endswith("-"):
                        merged_paragraphs[-1] = prev_p[:-1] + para
                    else:
                        merged_paragraphs[-1] = prev_p + "\n" + para
                    continue
            merged_paragraphs.append(para)

        return "\n\n".join(merged_paragraphs)

    @classmethod
    def reconstruct_from_spans(cls, raw_spans: List[PDFTextSpan]) -> str:
        """Reconstructs clean reading-order text from positioned PDFTextSpans."""
        if not raw_spans:
            return ""
        segments = cls._merge_baseline_segments(raw_spans)
        if not segments:
            return ""
        ordered_blocks = cls._order_blocks_xy_cut(segments)
        return cls._assemble_paragraphs_from_blocks(ordered_blocks)

    @classmethod
    def reconstruct_multicolumn_text(cls, page_text: str) -> str:
        """
        Reconstructs reading order from layout-spaced text where two or more columns
        appear on the same line separated by wide whitespace gutters (4+ spaces).
        Leaves normal single-column text untouched.
        """
        if not page_text or not page_text.strip():
            return page_text

        lines = page_text.splitlines()
        # Check how many lines have an internal wide whitespace gap (4+ spaces between non-spaces)
        gutter_matches: List[Optional[List[str]]] = []
        multi_col_line_count = 0
        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                gutter_matches.append(None)
                continue
            parts = [p.strip() for p in re.split(r"\s{4,}", stripped) if p.strip()]
            if len(parts) >= 2:
                multi_col_line_count += 1
                gutter_matches.append(parts)
            else:
                gutter_matches.append([stripped])

        non_empty_count = sum(1 for g in gutter_matches if g is not None)
        if multi_col_line_count < 2 or multi_col_line_count < 0.35 * max(1, non_empty_count):
            return page_text

        # De-interleave contiguous bands of multi-column lines while keeping full-width lines in place
        output_blocks: List[str] = []
        cur_band_cols: Dict[int, List[str]] = {}

        def flush_band():
            if not cur_band_cols:
                return
            for col_idx in sorted(cur_band_cols.keys()):
                col_text = "\n".join(cur_band_cols[col_idx]).strip()
                if col_text:
                    output_blocks.append(col_text)
            cur_band_cols.clear()

        for idx, parts in enumerate(gutter_matches):
            if parts is None:
                # Blank line inside a band acts as a paragraph break within columns
                if cur_band_cols:
                    for col_idx in cur_band_cols:
                        if cur_band_cols[col_idx] and cur_band_cols[col_idx][-1] != "":
                            cur_band_cols[col_idx].append("")
                continue
            if len(parts) == 1:
                # Full-width line (e.g., header/title/footer)
                flush_band()
                output_blocks.append(parts[0])
            else:
                for col_idx, cell in enumerate(parts):
                    cur_band_cols.setdefault(col_idx, []).append(cell)

        flush_band()
        return "\n\n".join(b for b in output_blocks if b.strip())

    @classmethod
    def extract_page_reading_order(cls, page: Any) -> str:
        """
        Extracts text from a pypdf PageObject in human reading order.
        Uses geometric coordinate XY-cut reconstruction when content stream ops are available,
        and falls back to extract_text() + whitespace column de-interleaving otherwise.
        """
        spans = cls.extract_positioned_spans(page)
        if spans:
            reconstructed = cls.reconstruct_from_spans(spans)
            if reconstructed.strip():
                return reconstructed

        try:
            raw_text = page.extract_text() or ""
        except Exception:
            raw_text = ""
        return cls.reconstruct_multicolumn_text(raw_text)


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


class PDFQualityAnalyzer:
    """
    Heuristic analyzer for PDF page extraction quality and escalation candidate comparison.
    Evaluates density, repeated headers/footers, OCR symbol noise, reading-order coherence,
    and column layout anomalies.
    """

    REFUSAL_PATTERNS = (
        r"\bi cannot extract\b",
        r"\bi am unable to\b",
        r"\bas an ai\b",
        r"\bi'm sorry,?\s+but i can'?t\b",
        r"\bcannot assist with this request\b",
        r"^(?:sure[,!]?\s+|certainly[,!]?\s+)?here\s+is\s+the\s+(?:extracted|transcribed|ocr|markdown|prose)\b",
        r"^below\s+is\s+the\s+(?:extracted|transcribed)\b",
        r"^```",
    )

    @classmethod
    def evaluate_extraction_quality(cls, text: str) -> ExtractionCandidateEvaluation:
        """
        Computes reading-order, text-integrity, sentence-coherence, and anomaly signals
        for a page text candidate.
        """
        cleaned = (text or "").strip()
        if not cleaned:
            return ExtractionCandidateEvaluation(
                reading_order_score=0.0,
                text_integrity_score=0.0,
                sentence_coherence_score=0.0,
                composite_score=0.0,
                anomaly_count=1,
                anomalies=["Empty page text."],
            )

        lines = [ln.strip() for ln in cleaned.splitlines() if ln.strip()]
        words = cleaned.split()
        word_count = len(words)
        char_count = len(cleaned)
        line_count = len(lines)
        anomalies: List[str] = []

        # 1. Text Integrity & Anomaly Signals
        replacement_chars = cleaned.count("\ufffd")
        if replacement_chars > 0:
            anomalies.append(f"Contains {replacement_chars} Unicode replacement characters (\\ufffd).")

        symbols = len(
            re.findall(
                r"[^a-zA-Z0-9\s\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F\.,'\"‘’“”\?\!\-\—\–\:\;\(\)\[\]…\/]",
                cleaned,
            )
        )
        symbol_ratio = symbols / max(1, char_count)
        if char_count > 30 and symbol_ratio > 0.08:
            anomalies.append(f"High OCR symbol/noise ratio ({symbol_ratio:.1%}).")

        # Count clean lexical words vs gibberish/corrupted tokens
        clean_words = 0
        gibberish_words = 0
        for w in words:
            w_stripped = w.strip(".,'\"‘’“”?!-—–:;()[]…/")
            if not w_stripped:
                continue
            # Token with internal noise symbols or replacement char
            if "\ufffd" in w_stripped or re.search(
                r"[^a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F\-'’]", w_stripped
            ):
                gibberish_words += 1
            elif (
                re.search(r"[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F]", w_stripped)
                and re.search(r"\d", w_stripped)
                and len(w_stripped) > 4
            ):
                # Mixed alphanumeric OCR glitch like 'th3r3' or '1lI0O'
                gibberish_words += 1
            else:
                clean_words += 1

        gibberish_ratio = gibberish_words / max(1, word_count)
        if gibberish_ratio > 0.15 and word_count >= 5:
            anomalies.append(f"High gibberish/corrupt token ratio ({gibberish_ratio:.1%}).")

        # Check for LLM refusal / conversational preamble leakage
        lower_text = cleaned.lower()
        refusal_detected = any(re.search(pat, lower_text) for pat in cls.REFUSAL_PATTERNS)
        if refusal_detected:
            anomalies.append("Detected LLM refusal or meta-response text.")

        # Check for severe n-gram repetition loops
        repetition_anomaly = False
        if word_count >= 24:
            norm_tokens = [w.lower().strip(".,'\"?!") for w in words]
            fourgrams: Dict[Tuple[str, ...], int] = {}
            for i in range(len(norm_tokens) - 3):
                fg = tuple(norm_tokens[i : i + 4])
                fourgrams[fg] = fourgrams.get(fg, 0) + 1
            max_repeat = max(fourgrams.values()) if fourgrams else 0
            if max_repeat >= 5 and (max_repeat * 4) / word_count > 0.30:
                repetition_anomaly = True
                anomalies.append(f"Severe 4-gram repetition loop detected ({max_repeat}x).")

        # 2. Reading-Order & Line-Flow Coherence Signals
        short_lines = [
            ln for ln in lines
            if 0 < len(ln) < 30
            and not re.match(COMBINED_CHAPTER_REGEX, ln, flags=re.IGNORECASE)
            and not re.match(r"^(\*|\-|\_)\s*\1\s*\1+$", ln)
        ]
        short_ratio = len(short_lines) / max(1, line_count)
        lowercase_starts = sum(1 for ln in lines if ln and ln[0].islower())

        if line_count >= 10 and short_ratio > 0.50 and lowercase_starts > 4:
            anomalies.append(f"Fragmented multi-column line wrapping (short ratio {short_ratio:.1%}).")

        # Check mid-sentence abrupt line jumps / column interleaving
        mid_sentence_breaks = 0
        if line_count >= 2:
            for i in range(line_count - 1):
                cur_ln = lines[i]
                nxt_ln = lines[i + 1]
                cur_ends_open = not cur_ln.endswith((".", "!", "?", ":", ";", '"', "'", "”", "’", "।", "*"))
                # Interleaved column symptom: short line ending mid-clause followed by Capitalized unrelated start,
                # or many short fragmented lowercase lines
                if len(cur_ln) < 35 and cur_ends_open:
                    mid_sentence_breaks += 1
                elif re.search(r"\S\s{4,}\S", cur_ln):
                    mid_sentence_breaks += 1
        mid_break_ratio = mid_sentence_breaks / max(1, line_count)
        if mid_break_ratio > 0.45 and line_count >= 4:
            anomalies.append(f"Disrupted reading order / column interleaving ({mid_break_ratio:.1%}).")

        # 3. Compute Normalized Scores in [0.0, 1.0]
        integrity_penalty = (
            min(0.60, symbol_ratio * 4.0)
            + min(0.50, replacement_chars * 0.20)
            + min(0.60, gibberish_ratio * 2.0)
            + (0.80 if refusal_detected else 0.0)
            + (0.50 if repetition_anomaly else 0.0)
        )
        text_integrity_score = max(0.0, round(1.0 - integrity_penalty, 4))

        reading_order_penalty = 0.0
        if line_count >= 6:
            reading_order_penalty += max(0.0, (short_ratio - 0.25) * 0.85)
            reading_order_penalty += max(0.0, (mid_break_ratio - 0.20) * 0.75)
        elif line_count >= 2 and mid_break_ratio > 0.50:
            reading_order_penalty += 0.35
        # Penalize unresolved wide internal whitespace gutters
        wide_gutter_lines = sum(1 for ln in lines if re.search(r"\S\s{5,}\S", ln))
        if wide_gutter_lines >= 2:
            reading_order_penalty += min(0.45, (wide_gutter_lines / max(1, line_count)) * 0.6)
        reading_order_score = max(0.0, round(1.0 - reading_order_penalty, 4))

        # Sentence coherence: presence of valid terminal punctuation and reasonable sentence structure
        has_terminal = any(cleaned.endswith(p) or p in cleaned for p in (".", "!", "?", "।", '"', "”", "’"))
        sentence_coherence_score = 1.0 if has_terminal else 0.65
        if word_count < 5:
            sentence_coherence_score *= 0.60
        if lowercase_starts > 0.65 * max(1, line_count) and line_count >= 6:
            sentence_coherence_score *= 0.70
        sentence_coherence_score = round(max(0.0, min(1.0, sentence_coherence_score)), 4)

        composite_score = round(
            0.40 * reading_order_score
            + 0.45 * text_integrity_score
            + 0.15 * sentence_coherence_score,
            4,
        )

        return ExtractionCandidateEvaluation(
            word_count=word_count,
            clean_word_count=clean_words,
            char_count=char_count,
            line_count=line_count,
            symbol_noise_ratio=round(symbol_ratio, 4),
            replacement_char_count=replacement_chars,
            gibberish_token_ratio=round(gibberish_ratio, 4),
            short_fragment_ratio=round(short_ratio, 4),
            mid_sentence_break_ratio=round(mid_break_ratio, 4),
            repetition_anomaly=repetition_anomaly,
            refusal_detected=refusal_detected,
            reading_order_score=reading_order_score,
            text_integrity_score=text_integrity_score,
            sentence_coherence_score=sentence_coherence_score,
            composite_score=composite_score,
            anomaly_count=len(anomalies),
            anomalies=anomalies,
        )

    @classmethod
    def compare_extraction_candidates(
        cls,
        local_text: str,
        gemini_text: Optional[str],
        local_audit: Optional[PageQualityAudit] = None,
    ) -> Dict[str, Any]:
        """
        Compares local pypdf extraction against Gemini Vision escalation output across
        reading-order, text-integrity, anomaly count, and content coverage signals.
        Does NOT blindly prefer whichever candidate has more words.
        """
        local_eval = cls.evaluate_extraction_quality(local_text or "")
        if not gemini_text or not gemini_text.strip():
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Gemini escalation returned empty text.",
                "local_score": local_eval.composite_score,
                "gemini_score": 0.0,
                "local_eval": local_eval,
                "gemini_eval": None,
            }

        gemini_eval = cls.evaluate_extraction_quality(gemini_text)

        # Hard disqualifiers for Gemini candidate
        if gemini_eval.refusal_detected:
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Rejected Gemini output due to refusal/meta-chatter detection.",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        if gemini_eval.repetition_anomaly and not local_eval.repetition_anomaly:
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Rejected Gemini output due to severe repetition loop anomaly.",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        if gemini_eval.replacement_char_count > local_eval.replacement_char_count:
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Rejected Gemini output because it introduced Unicode replacement characters.",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        if gemini_eval.text_integrity_score < 0.65 and gemini_eval.text_integrity_score <= local_eval.text_integrity_score:
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": f"Rejected Gemini output due to low text integrity ({gemini_eval.text_integrity_score:.2f}).",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        # Truncation guard: if local had substantial clean prose, reject Gemini if it lost >45% of clean words
        if (
            local_eval.clean_word_count >= 25
            and local_eval.text_integrity_score >= 0.70
            and gemini_eval.clean_word_count < int(0.55 * local_eval.clean_word_count)
        ):
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": (
                    f"Rejected Gemini output due to content truncation "
                    f"({gemini_eval.clean_word_count} vs {local_eval.clean_word_count} clean words)."
                ),
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        # Case 1: Sparse / low-density local extraction (e.g. scanned page or missing font map)
        if local_eval.clean_word_count < 15:
            if (
                gemini_eval.clean_word_count > local_eval.clean_word_count
                and gemini_eval.composite_score >= 0.70
                and gemini_eval.anomaly_count == 0
            ):
                return {
                    "accept_gemini": True,
                    "winner": "gemini",
                    "reason": (
                        f"Accepted Gemini output: recovered clean prose ({gemini_eval.clean_word_count} clean words, "
                        f"score {gemini_eval.composite_score:.2f} vs {local_eval.composite_score:.2f})."
                    ),
                    "local_score": local_eval.composite_score,
                    "gemini_score": gemini_eval.composite_score,
                    "local_eval": local_eval,
                    "gemini_eval": gemini_eval,
                }
            return {
                "accept_gemini": False,
                "winner": "local",
                "reason": "Rejected Gemini output on low-density page: insufficient quality or clean words.",
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        # Case 2: Populated local page with layout/reading-order or OCR anomalies
        # Accept Gemini even if it has equal or slightly fewer words (e.g. due to healed hyphens or stripped noise),
        # provided it has stronger reading-order, text-integrity, or fewer anomalies!
        has_adequate_coverage = gemini_eval.clean_word_count >= int(0.65 * local_eval.clean_word_count)
        stronger_reading_order = (
            gemini_eval.reading_order_score > local_eval.reading_order_score + 0.08
            and gemini_eval.text_integrity_score >= local_eval.text_integrity_score - 0.03
        )
        stronger_integrity = (
            gemini_eval.text_integrity_score > local_eval.text_integrity_score + 0.08
            and gemini_eval.reading_order_score >= local_eval.reading_order_score - 0.03
        )
        fewer_anomalies = (
            gemini_eval.anomaly_count < local_eval.anomaly_count
            and gemini_eval.composite_score >= local_eval.composite_score
        )
        higher_composite = gemini_eval.composite_score > local_eval.composite_score + 0.04

        if has_adequate_coverage and (stronger_reading_order or stronger_integrity or fewer_anomalies or higher_composite):
            return {
                "accept_gemini": True,
                "winner": "gemini",
                "reason": (
                    f"Accepted Gemini output based on superior quality signals "
                    f"(score {gemini_eval.composite_score:.2f} vs {local_eval.composite_score:.2f}, "
                    f"reading_order {gemini_eval.reading_order_score:.2f} vs {local_eval.reading_order_score:.2f}, "
                    f"integrity {gemini_eval.text_integrity_score:.2f} vs {local_eval.text_integrity_score:.2f})."
                ),
                "local_score": local_eval.composite_score,
                "gemini_score": gemini_eval.composite_score,
                "local_eval": local_eval,
                "gemini_eval": gemini_eval,
            }

        return {
            "accept_gemini": False,
            "winner": "local",
            "reason": (
                f"Retained local extraction: Gemini candidate did not improve quality "
                f"(score {gemini_eval.composite_score:.2f} vs local {local_eval.composite_score:.2f})."
            ),
            "local_score": local_eval.composite_score,
            "gemini_score": gemini_eval.composite_score,
            "local_eval": local_eval,
            "gemini_eval": gemini_eval,
        }

    @classmethod
    def should_accept_escalation(
        cls,
        local_text: str,
        gemini_text: Optional[str],
        local_audit: Optional[PageQualityAudit] = None,
    ) -> Tuple[bool, str]:
        """Convenience wrapper returning (accept_bool, diagnostic_reason)."""
        comp = cls.compare_extraction_candidates(local_text, gemini_text, local_audit=local_audit)
        return bool(comp["accept_gemini"]), str(comp["reason"])

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
                symbols = len(
                    re.findall(
                        r"[^a-zA-Z0-9\s\u00C0-\u024F\u1E00-\u1EFF\u0900-\u097F\.,'\"‘’“”\?\!\-\—\–\:\;\(\)\[\]…\/]",
                        cleaned_text,
                    )
                )
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

            eval_metrics = cls.evaluate_extraction_quality(cleaned_text)
            status: ConfidenceLevel = "LOW" if is_suspicious else "HIGH"
            audits.append(PageQualityAudit(
                page_number=p_idx,
                status=status,
                word_count=word_count,
                char_count=char_count,
                line_count=line_count,
                is_suspicious=is_suspicious,
                warnings=warnings,
                quality_score=eval_metrics.composite_score,
                reading_order_score=eval_metrics.reading_order_score,
                text_integrity_score=eval_metrics.text_integrity_score,
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
                # Strip optional markdown code fences and conversational LLM preambles without mutating literary typography
                text = re.sub(r"^```(?:markdown|md|text)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
                text = re.sub(r"\n?```\s*$", "", text.strip())
                text = re.sub(
                    r"^(?:sure[,!]?\s+|certainly[,!]?\s+)?(?:here|below)\s+is\s+the\s+(?:extracted|transcribed|ocr|markdown|prose)[^\n]*:\s*\n+",
                    "",
                    text.strip(),
                    flags=re.IGNORECASE,
                )
                return text.strip()
        except Exception:
            return None


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

