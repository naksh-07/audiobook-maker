#!/usr/bin/env python3
"""
Unit Tests for Extraction Quality Gate Auditor.
"""

import unittest
from pathlib import Path

from audiobook_factory.book_model import (
    CanonicalBook,
    CanonicalChapter,
    CanonicalBlock,
    SourceProvenance,
    ExtractionQualityReport,
    ExtractionGateAuditError,
)
from audiobook_factory.quality_gate import ExtractionQualityAuditor


class TestQualityGate(unittest.TestCase):

    def _create_mock_book(self, num_chapters: int, words_per_chap: int, suspicious_pages: list = None) -> CanonicalBook:
        prov = SourceProvenance(source_file="test.epub", source_type="epub")
        chapters = []
        for i in range(1, num_chapters + 1):
            block = CanonicalBlock(
                id=f"b-{i}",
                type="paragraph",
                raw_text="The journey began at sunrise. " * (words_per_chap // 5),
                normalized_text="The journey began at sunrise. " * (words_per_chap // 5),
                provenance=prov,
            )
            chap = CanonicalChapter(
                id=f"ch-{i:03d}",
                number=i,
                title=f"Chapter {i}",
                blocks=[block],
                words=words_per_chap,
            )
            chapters.append(chap)

        report = ExtractionQualityReport(
            source_type="epub",
            source_path="test.epub",
            total_pages_or_docs=10,
            suspicious_pages=suspicious_pages or [],
        )

        return CanonicalBook(
            book_id="mock_book",
            title="Mock Novel",
            source_type="epub",
            source_path="test.epub",
            quality_report=report,
            chapters=chapters,
        )

    def test_gate_pass_healthy_book(self):
        book = self._create_mock_book(num_chapters=3, words_per_chap=500)
        report = ExtractionQualityAuditor.audit(book, force_gate=False)
        self.assertEqual(report.gate_status, "PASS")
        self.assertEqual(report.overall_confidence, "HIGH")
        self.assertEqual(len(report.errors), 0)

    def test_gate_warn_minor_suspicious_pages(self):
        # 1 suspicious page out of 10 (10% <= 25%)
        book = self._create_mock_book(num_chapters=3, words_per_chap=500, suspicious_pages=[2])
        report = ExtractionQualityAuditor.audit(book, force_gate=False)
        self.assertEqual(report.gate_status, "WARN")
        self.assertEqual(report.overall_confidence, "MEDIUM")
        self.assertGreaterEqual(len(report.warnings), 1)

    def test_gate_review_fail_closed_zero_chapters(self):
        book = self._create_mock_book(num_chapters=0, words_per_chap=0)
        with self.assertRaises(ExtractionGateAuditError) as ctx:
            ExtractionQualityAuditor.audit(book, force_gate=False)
        self.assertIn("Zero chapters were detected", str(ctx.exception))
        self.assertIn("--force-gate", str(ctx.exception))

    def test_gate_review_fail_closed_high_suspicious_ratio(self):
        # 4 suspicious pages out of 10 (40% > 25%)
        book = self._create_mock_book(num_chapters=2, words_per_chap=200, suspicious_pages=[1, 2, 3, 4])
        with self.assertRaises(ExtractionGateAuditError) as ctx:
            ExtractionQualityAuditor.audit(book, force_gate=False)
        self.assertIn("Severe layout/OCR anomalies", str(ctx.exception))
        self.assertIn("[1, 2, 3, 4]", str(ctx.exception))

    def test_gate_review_force_override(self):
        # Even with 0 chapters, force_gate=True returns report instead of raising
        book = self._create_mock_book(num_chapters=0, words_per_chap=0)
        report = ExtractionQualityAuditor.audit(book, force_gate=True)
        self.assertEqual(report.gate_status, "REVIEW")
        self.assertGreaterEqual(len(report.errors), 1)


if __name__ == "__main__":
    unittest.main()
