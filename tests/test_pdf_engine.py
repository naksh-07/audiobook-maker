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
                if healed:
                    cleaned[audit.page_number - 1] = healed
                    audit.is_suspicious = False
                    audit.status = "HIGH"

        mock_escalator.escalate_page.assert_called_once_with(Path("dummy.pdf"), 2)
        self.assertFalse(audits[1].is_suspicious)
        self.assertIn("Healed full page", cleaned[1])


if __name__ == "__main__":
    unittest.main()
