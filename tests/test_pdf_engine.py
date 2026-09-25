#!/usr/bin/env python3
"""
Unit Tests for Lightweight Layout-Aware PDF Engine and Quality Analyzer.
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from audiobook_factory.pdf_engine import (
    PDFQualityAnalyzer,
    PageQualityAudit,
    PDFEscalationEngine,
    ForensicPDFEngine,
)


class TestPDFEngine(unittest.TestCase):

    def test_running_headers_and_footers_stripping(self):
        # 4 pages with recurring header "The Last Wish" and footer "Page 10" / "HarperCollins"
        pages = [
            "The Last Wish\n\nGeralt rode slowly into the village of Blaviken.\n\nHarperCollins Publishers",
            "The Last Wish\n\nThe townsfolk stared from shuttered windows.\n\nHarperCollins Publishers",
            "The Last Wish\n\nA small boy threw a pebble and ran away.\n\nHarperCollins Publishers",
            "The Last Wish\n\nThe innkeeper bowed nervously at the threshold.\n\nHarperCollins Publishers",
        ]
        audits, cleaned = PDFQualityAnalyzer.audit_pages(pages)
        self.assertEqual(len(cleaned), 4)
        for p in cleaned:
            self.assertNotIn("The Last Wish", p)
            self.assertNotIn("HarperCollins Publishers", p)
            self.assertTrue(len(p.split()) > 5)

    def test_low_density_page_detection(self):
        pages = [
            "This is a normal novel page with plenty of narrative prose detailing the long journey across the mountains.",
            "Only three words.",  # Suspicious low density
        ]
        audits, cleaned = PDFQualityAnalyzer.audit_pages(pages)
        self.assertFalse(audits[0].is_suspicious)
        self.assertTrue(audits[1].is_suspicious)
        self.assertEqual(audits[1].status, "LOW")
        self.assertTrue(any("Low text density" in w for w in audits[1].warnings))

    def test_ocr_symbol_noise_detection(self):
        # Page with extreme OCR noise
        noisy_page = "Geralt ### @@@ $$$ ^^^ %%% &*&*&* &&& $$$ ~~~ sword."
        audits, _ = PDFQualityAnalyzer.audit_pages([noisy_page])
        self.assertTrue(audits[0].is_suspicious)
        self.assertTrue(any("symbol/noise ratio" in w for w in audits[0].warnings))

    def test_multi_column_indicator(self):
        # 12 short lines with lowercase continuations
        column_lines = [
            "the soldier marched",
            "through the valley",
            "while the captain",
            "watched from above",
            "and the cavalry",
            "formed the flank",
            "in defensive order",
            "under heavy fire",
            "from the archers",
            "stationed on the ridge",
            "awaiting command",
            "to advance forward",
        ]
        page = "\n".join(column_lines)
        audits, _ = PDFQualityAnalyzer.audit_pages([page])
        self.assertTrue(audits[0].is_suspicious)
        self.assertTrue(any("multi-column" in w for w in audits[0].warnings))

    def test_selective_escalation_engine_mock(self):
        # Mock escalation engine that heals suspicious page 2
        mock_escalator = MagicMock(spec=PDFEscalationEngine)
        mock_escalator.escalate_page.return_value = "Healed full page text with rich descriptive narrative and twenty words."

        raw_pages = [
            "Normal page one text with plenty of content describing the great journeys of the ancient kings across the western mountains.",
            "Short corrupt.",  # Suspicious (< 15 words)
        ]
        audits, cleaned = PDFQualityAnalyzer.audit_pages(raw_pages)
        self.assertTrue(audits[1].is_suspicious)

        # Trigger mock escalation on suspicious page
        for audit in audits:
            if audit.is_suspicious:
                healed = mock_escalator.escalate_page(Path("dummy.pdf"), audit.page_number)
                accepted, _ = PDFQualityAnalyzer.should_accept_escalation(
                    cleaned[audit.page_number - 1], healed, local_audit=audit
                )
                if accepted and healed:
                    cleaned[audit.page_number - 1] = healed
                    audit.is_suspicious = False
                    audit.status = "HIGH"

        mock_escalator.escalate_page.assert_called_once_with(Path("dummy.pdf"), 2)
        self.assertFalse(audits[1].is_suspicious)
        self.assertIn("Healed full page", cleaned[1])

    def _build_synthetic_pdf(self, file_path: Path, page_streams: list[bytes]) -> Path:
        """Helper to construct a real valid PDF with custom content streams per page."""
        import pypdf
        from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject

        writer = pypdf.PdfWriter()
        for content_bytes in page_streams:
            page = writer.add_blank_page(width=612, height=792)
            stream = DecodedStreamObject()
            stream.set_data(content_bytes)
            page[NameObject("/Contents")] = writer._add_object(stream)
            font_dict = DictionaryObject({
                NameObject("/F1"): DictionaryObject({
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                })
            })
            page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): font_dict})

        with open(file_path, "wb") as f:
            writer.write(f)
        return file_path

    def test_multicolumn_and_complex_layout_reading_order(self):
        """
        Improvement 1: Verify multi-column PDF with full-width header, interleaved left/right
        column lines in the PDF stream, paragraph vertical gaps, and bottom spanning footer
        is extracted in true human reading order.
        """
        import tempfile

        # Stream deliberately interleaves Left Column (x=50) and Right Column (x=330) at same Y
        stream_page_1 = b"""
BT
/F1 16 Tf
1 0 0 1 160 750 Tm (Chapter 1: The Divided Kingdom) Tj
/F1 11 Tf
1 0 0 1 50 700 Tm (Left paragraph one opens the chronicle) Tj
1 0 0 1 330 700 Tm (Right paragraph one follows column one) Tj
1 0 0 1 50 685 Tm (and continues down the left margin.) Tj
1 0 0 1 330 685 Tm (with the eastern frontier account.) Tj
1 0 0 1 50 645 Tm (Left paragraph two begins after a gap) Tj
1 0 0 1 330 645 Tm (Right paragraph two concludes the page) Tj
1 0 0 1 50 630 Tm (completing the western dispatch.) Tj
1 0 0 1 330 630 Tm (before the royal seal is affixed.) Tj
1 0 0 1 140 570 Tm (End of Royal Proclamation Across Both Columns) Tj
ET
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = self._build_synthetic_pdf(Path(tmp_dir) / "multicol.pdf", [stream_page_1])
            engine = ForensicPDFEngine(pdf_path, escalation_engine=None)
            cleaned_pages, audits, _ = engine.extract_pages()

            self.assertEqual(len(cleaned_pages), 1)
            page_text = cleaned_pages[0]

            # Verify human reading order:
            # 1. Full-width title
            # 2. Left para 1 (both lines together)
            # 3. Left para 2 (both lines together)
            # 4. Right para 1 (both lines together)
            # 5. Right para 2 (both lines together)
            # 6. Full-width bottom banner
            idx_title = page_text.find("Chapter 1: The Divided Kingdom")
            idx_lp1_a = page_text.find("Left paragraph one opens the chronicle")
            idx_lp1_b = page_text.find("and continues down the left margin.")
            idx_lp2_a = page_text.find("Left paragraph two begins after a gap")
            idx_lp2_b = page_text.find("completing the western dispatch.")
            idx_rp1_a = page_text.find("Right paragraph one follows column one")
            idx_rp1_b = page_text.find("with the eastern frontier account.")
            idx_rp2_a = page_text.find("Right paragraph two concludes the page")
            idx_rp2_b = page_text.find("before the royal seal is affixed.")
            idx_footer = page_text.find("End of Royal Proclamation Across Both Columns")

            ordered_indices = [
                idx_title,
                idx_lp1_a,
                idx_lp1_b,
                idx_lp2_a,
                idx_lp2_b,
                idx_rp1_a,
                idx_rp1_b,
                idx_rp2_a,
                idx_rp2_b,
                idx_footer,
            ]
            for pos in ordered_indices:
                self.assertNotEqual(pos, -1, f"Missing expected segment in extracted text:\n{page_text}")
            self.assertEqual(
                ordered_indices,
                sorted(ordered_indices),
                f"Reading order violated! Extracted text was:\n{page_text}",
            )

    def test_out_of_order_pdf_stream_sorted_top_to_bottom(self):
        """Improvement 1: Verify out-of-order vertical stream ops are sorted into top-to-bottom order."""
        import tempfile

        # Stream writes bottom paragraph (y=500) BEFORE top paragraph (y=720)
        stream = b"""
BT
/F1 12 Tf
1 0 0 1 50 500 Tm (Second paragraph located lower on the page.) Tj
1 0 0 1 50 720 Tm (First paragraph located at the top of the page.) Tj
ET
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_path = self._build_synthetic_pdf(Path(tmp_dir) / "out_of_order.pdf", [stream])
            engine = ForensicPDFEngine(pdf_path, escalation_engine=None)
            cleaned_pages, _, _ = engine.extract_pages()
            page_text = cleaned_pages[0]
            self.assertLess(
                page_text.find("First paragraph located at the top"),
                page_text.find("Second paragraph located lower"),
            )

    def test_gemini_escalation_quality_gate_comparison(self):
        """
        Improvement 3: Verify Gemini escalation quality gate compares reading order,
        text integrity, and anomaly signals rather than blindly checking word count.
        """
        # Scenario A: Local text has MORE words (42 words) due to fragmented multi-column
        # interleaving and OCR noise tokens, while Gemini has FEWER words (36 words)
        # in clean, coherent reading order. Gemini MUST be preferred!
        local_fragmented = "\n".join([
            "the soldier marched ###",
            "while the general",
            "through the dark",
            "studied the ancient",
            "valley of shadows",
            "map in silence",
            "under heavy rain",
            "by candlelight.",
            "seeking shelter",
            "before midnight",
            "near the river",
            "arrived at last @@@.",
        ])
        gemini_clean_fewer_words = (
            "The soldier marched through the dark valley of shadows under heavy rain, "
            "seeking shelter near the river.\n\n"
            "Meanwhile, the general studied the ancient map in silence by candlelight "
            "before midnight arrived at last."
        )
        self.assertLess(len(gemini_clean_fewer_words.split()), len(local_fragmented.split()))

        accept_a, reason_a = PDFQualityAnalyzer.should_accept_escalation(
            local_text=local_fragmented,
            gemini_text=gemini_clean_fewer_words,
        )
        self.assertTrue(accept_a, f"Expected Gemini with better reading order/integrity to win: {reason_a}")

        # Scenario B: Gemini output has MORE words than local, but contains severe OCR noise / \ufffd
        # or repetition loops. Local MUST be preferred!
        local_sparse_but_clean = "Geralt dismounted Roach slowly at the crossroads and drew his silver blade."
        gemini_noisy_more_words = (
            "Geralt \ufffd\ufffd ### @@@ $$$ %%% ^^^ &&& dismounted Roach slowly at the crossroads "
            "and drew his silver blade \ufffd ### @@@ $$$ %%% ^^^ &&& ~~~ *** !!! ???."
        )
        self.assertGreater(len(gemini_noisy_more_words.split()), len(local_sparse_but_clean.split()))
        accept_b, reason_b = PDFQualityAnalyzer.should_accept_escalation(
            local_text=local_sparse_but_clean,
            gemini_text=gemini_noisy_more_words,
        )
        self.assertFalse(accept_b, f"Expected noisy Gemini with replacement chars to be rejected: {reason_b}")

        # Scenario C: Gemini output has MORE words due to a 4-gram repetition hallucination loop.
        gemini_repetition_loop = " ".join(["the wind howled endlessly"] * 12)
        self.assertGreater(len(gemini_repetition_loop.split()), len(local_sparse_but_clean.split()))
        accept_c, reason_c = PDFQualityAnalyzer.should_accept_escalation(
            local_text=local_sparse_but_clean,
            gemini_text=gemini_repetition_loop,
        )
        self.assertFalse(accept_c, f"Expected repetitive Gemini output to be rejected: {reason_c}")

        # Scenario D: Gemini returns an LLM refusal with more words than a short local page.
        gemini_refusal = (
            "I'm sorry, but I can't extract the text from this PDF page because as an AI "
            "I am unable to process this specific document image request."
        )
        accept_d, _ = PDFQualityAnalyzer.should_accept_escalation(
            local_text="Short chapter note.",
            gemini_text=gemini_refusal,
        )
        self.assertFalse(accept_d)

    def test_pdf_provenance_preserved_through_chapter_segmentation(self):
        """
        Improvement 2: Verify page_number, line_start, line_end, char_offset, reading_order,
        extraction_method, and raw_text are preserved across multi-page joins and mid-page
        chapter boundaries.
        """
        import tempfile
        from audiobook_factory.extractor import process_book_file

        p1 = b"""
BT
/F1 14 Tf
1 0 0 1 50 740 Tm (Chapter 1: The Northern Watch) Tj
/F1 11 Tf
1 0 0 1 50 700 Tm (The watchtower stood silent above the frozen gorge for centuries.) Tj
1 0 0 1 50 660 Tm (Sentries patrolled the battlements wrapped in heavy wolf pelts.) Tj
ET
"""
        p2 = b"""
BT
/F1 11 Tf
1 0 0 1 50 720 Tm (Below the cliffs, the river groaned beneath a sheet of black ice.) Tj
1 0 0 1 50 680 Tm (No traveler had crossed the bridge since the first blizzard fell.) Tj
ET
"""
        # Page 3 finishes Chapter 1 at top, then starts Chapter 2 mid-page!
        p3 = b"""
BT
/F1 11 Tf
1 0 0 1 50 730 Tm (At dawn, the horn sounded three times from the high turret.) Tj
/F1 14 Tf
1 0 0 1 50 650 Tm (Chapter 2: The Signal Fire) Tj
/F1 11 Tf
1 0 0 1 50 610 Tm (Flames leaped across the dry pine beacons along the mountain ridge.) Tj
ET
"""
        p4 = b"""
BT
/F1 11 Tf
1 0 0 1 50 720 Tm (Riders saddled their horses in the courtyard before the gates opened.) Tj
ET
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pdf_file = self._build_synthetic_pdf(tmp_path / "watchtower.pdf", [p1, p2, p3, p4])
            out_dir = tmp_path / "projects"

            meta = process_book_file(pdf_file, out_dir)
            book_json_path = out_dir / meta["book_id"] / "canonical" / "book.json"
            self.assertTrue(book_json_path.exists())

            import json
            from audiobook_factory.book_model import CanonicalBook
            book = CanonicalBook.model_validate_json(book_json_path.read_text(encoding="utf-8"))

            self.assertEqual(len(book.chapters), 2)
            ch1, ch2 = book.chapters[0], book.chapters[1]

            # Chapter 1 spans pages 1-3
            self.assertEqual(ch1.title, "Chapter 1: The Northern Watch")
            self.assertEqual(ch1.page_start, 1)
            self.assertEqual(ch1.page_end, 3)
            self.assertEqual(ch1.source_location, "pages 1-3")
            self.assertTrue(ch1.is_literary_chapter)
            self.assertFalse(ch1.is_production_chunk)

            ch1_pages = [b.provenance.page_number for b in ch1.blocks]
            self.assertIn(1, ch1_pages)
            self.assertIn(2, ch1_pages)
            self.assertIn(3, ch1_pages)

            # Chapter 2 starts mid-page 3 and ends on page 4
            self.assertEqual(ch2.title, "Chapter 2: The Signal Fire")
            self.assertEqual(ch2.page_start, 3)
            self.assertEqual(ch2.page_end, 4)
            self.assertEqual(ch2.source_location, "pages 3-4")

            ch2_pages = [b.provenance.page_number for b in ch2.blocks]
            self.assertEqual(ch2_pages, [3, 4])

            # Verify every single block across the book has full provenance
            all_blocks = [b for c in book.chapters for b in c.blocks]
            reading_orders = [b.provenance.reading_order for b in all_blocks]
            self.assertEqual(reading_orders, list(range(1, len(all_blocks) + 1)))
            for b in all_blocks:
                self.assertIsNotNone(b.provenance.page_number)
                self.assertIsNotNone(b.provenance.line_start)
                self.assertIsNotNone(b.provenance.line_end)
                self.assertIsNotNone(b.provenance.char_offset)
                self.assertEqual(b.provenance.source_type, "pdf")
                self.assertTrue(b.raw_text.strip())

    def test_single_column_dialogue_and_accented_latin_and_cross_page_provenance(self):
        """
        Verify audit edge-case hardening:
        1. Single-column page with short dialogue and right-aligned dates/signatures is NOT split into columns.
        2. Accented Latin words (Dantès, Château, café) are treated as clean tokens, and conversational LLM preambles are rejected.
        3. Mid-sentence cross-page continuation preserves page_number=1 and page_end=2 on the unified block.
        """
        from audiobook_factory.pdf_engine import PDFLayoutReconstructor, PDFTextSpan

        # 1. Single-column dialogue + right-aligned epigraph/date/signature
        dialogue_spans = [
            PDFTextSpan(text="Yes, said he.", x0=72, y=740, x1=160, font_height=12),
            PDFTextSpan(text="October 14, 1888", x0=320, y=710, x1=450, font_height=12),
            PDFTextSpan(text="No, said she.", x0=72, y=680, x1=160, font_height=12),
            PDFTextSpan(text="Nevermore!", x0=72, y=660, x1=150, font_height=12),
            PDFTextSpan(text="Yours truly, Edgar", x0=310, y=620, x1=450, font_height=12),
            PDFTextSpan(text="P.S. Burn this.", x0=72, y=590, x1=170, font_height=12),
        ]
        self.assertIsNone(PDFLayoutReconstructor._find_vertical_column_gutter(dialogue_spans))

        # 2. Accented Latin words & LLM conversational preamble rejection
        accented_eval = PDFQualityAnalyzer.evaluate_extraction_quality(
            "Edmond Dantès escaped from the Château d'If in Marseille and met René at a café in Zürich."
        )
        self.assertEqual(accented_eval.gibberish_token_ratio, 0.0)
        self.assertEqual(accented_eval.anomaly_count, 0)

        accept_preamble, _ = PDFQualityAnalyzer.should_accept_escalation(
            local_text="Short noisy fragment ###",
            gemini_text="Here is the extracted text from the book page:\n\nThe carriage rattled down the road.",
        )
        self.assertFalse(accept_preamble)

        # 3. Cross-page mid-sentence continuation populates page_end=2
        engine = ForensicPDFEngine.__new__(ForensicPDFEngine)
        engine.file_path = Path("cross_page.pdf")
        pages = [
            "Chapter 1: The Crossing\n\nThis paragraph begins at the bottom of page one and continues",
            "across the page boundary onto page two without interruption.",
        ]
        audits, cleaned = PDFQualityAnalyzer.audit_pages(pages)
        chapters = engine.segment_into_canonical_chapters(cleaned, audits, [])
        self.assertEqual(len(chapters), 1)
        cross_block = chapters[0].blocks[-1]
        self.assertEqual(cross_block.provenance.page_number, 1)
        self.assertEqual(cross_block.provenance.page_end, 2)


if __name__ == "__main__":
    unittest.main()


