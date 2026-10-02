from __future__ import annotations
import re
import statistics
from typing import List, Dict, Any, Tuple, Optional, Set

from audiobook_factory.pdf.models import PDFTextSpan
from audiobook_factory.chapter_segmenter import COMBINED_CHAPTER_REGEX


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

            # Deduplicate faux-bold / drop-shadow multi-stroke overprints (identical text at microscopic offset)
            deduped_row: List[PDFTextSpan] = []
            for sp in row:
                if deduped_row:
                    last = deduped_row[-1]
                    if (
                        last.text == sp.text
                        and abs(sp.x0 - last.x0) <= 0.65 * max(last.space_width, sp.space_width, 2.5)
                        and abs(sp.y - last.y) <= 0.45 * max(last.font_height, sp.font_height, 8.0)
                    ):
                        last.x1 = max(last.x1, sp.x1)
                        continue
                deduped_row.append(sp)
            row = deduped_row
            if not row:
                continue

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


