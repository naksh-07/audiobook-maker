#!/usr/bin/env python3
"""
Unit Tests for Canonical Book Model, Provenance, and Quality Reporting.
"""

import json
import tempfile
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


class TestBookModel(unittest.TestCase):

    def test_canonical_block_and_provenance(self):
        prov = SourceProvenance(
            source_file="test_novel.epub",
            source_type="epub",
            spine_item="OEBPS/ch01.xhtml",
            html_tag="p",
            html_id="p-42",
            reading_order=1,
            extraction_method="epub_dom",
        )
        block = CanonicalBlock(
            id="b-001-00001",
            type="paragraph",
            raw_text="The witcher rode slowly through the forest gate.",
            normalized_text="The witcher rode slowly through the forest gate.",
            provenance=prov,
            confidence="HIGH",
        )
        self.assertEqual(block.type, "paragraph")
        self.assertEqual(block.provenance.spine_item, "OEBPS/ch01.xhtml")
        self.assertEqual(block.provenance.html_id, "p-42")

    def test_canonical_chapter_projections(self):
        prov = SourceProvenance(source_file="book.epub", source_type="epub")
        blocks = [
            CanonicalBlock(
                id="b-1",
                type="heading",
                raw_text="The Voice of Reason",
                normalized_text="The Voice of Reason",
                provenance=prov,
                semantic_metadata={"level": 2},
            ),
            CanonicalBlock(
                id="b-2",
                type="paragraph",
                raw_text="Geralt awoke with the scent of chamomile in the air.",
                normalized_text="Geralt awoke with the scent of chamomile in the air.",
                provenance=prov,
            ),
            CanonicalBlock(
                id="b-3",
                type="scene_break",
                raw_text="* * *",
                normalized_text="* * *",
                provenance=prov,
            ),
            CanonicalBlock(
                id="b-4",
                type="quote",
                raw_text="Evil is evil, Stregobor.",
                normalized_text="Evil is evil, Stregobor.",
                provenance=prov,
            ),
        ]
        chapter = CanonicalChapter(
            id="ch-001",
            number=1,
            title="The Voice of Reason",
            blocks=blocks,
            words=20,
        )
        md = chapter.to_markdown()
        self.assertIn("# The Voice of Reason", md)
        self.assertIn("## The Voice of Reason", md)
        self.assertIn("Geralt awoke", md)
        self.assertIn("* * *", md)
        self.assertIn("> Evil is evil, Stregobor.", md)

    def test_canonical_book_serialization_and_legacy_projection(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir) / "witcher_test"
            canonical_dir = project_dir / "canonical"
            extracted_dir = project_dir / "extracted"

            prov = SourceProvenance(source_file="witcher.epub", source_type="epub")
            block = CanonicalBlock(
                id="b-1",
                type="paragraph",
                raw_text="Chapter one text.",
                normalized_text="Chapter one text.",
                provenance=prov,
            )
            chap = CanonicalChapter(
                id="ch-001",
                number=1,
                title="The Witcher",
                blocks=[block],
                words=3,
            )
            report = ExtractionQualityReport(
                overall_confidence="HIGH",
                gate_status="PASS",
                source_type="epub",
                source_path="witcher.epub",
                total_chapters=1,
                total_words=3,
                total_blocks=1,
            )
            book = CanonicalBook(
                book_id="witcher_test",
                title="The Last Wish",
                author="Andrzej Sapkowski",
                source_type="epub",
                source_path="witcher.epub",
                quality_report=report,
                chapters=[chap],
            )

            # Test canonical persistence
            book.save_canonical(canonical_dir)
            self.assertTrue((canonical_dir / "book.json").exists())
            self.assertTrue((canonical_dir / "quality_report.json").exists())

            # Test legacy projection
            projected = book.project_legacy_extracted(extracted_dir)
            self.assertEqual(len(projected), 1)
            self.assertTrue((extracted_dir / "chapter_001.md").exists())
            content = (extracted_dir / "chapter_001.md").read_text(encoding="utf-8")
            self.assertIn("# The Witcher", content)
            self.assertIn("Chapter one text.", content)

            # Test legacy metadata
            meta = book.to_legacy_metadata()
            self.assertEqual(meta["book_id"], "witcher_test")
            self.assertEqual(meta["title"], "The Last Wish")
            self.assertEqual(meta["total_chapters"], 1)
            self.assertEqual(meta["total_words"], 3)
            self.assertEqual(meta["extraction_quality"]["gate_status"], "PASS")

    def test_actionable_quality_gate_error(self):
        report = ExtractionQualityReport(
            overall_confidence="LOW",
            gate_status="REVIEW",
            source_type="pdf",
            source_path="corrupt_scanned.pdf",
            total_chapters=0,
            total_words=12,
            total_blocks=2,
            suspicious_pages=[1, 2, 3],
            errors=["Extracted word count (12) suspiciously below book threshold (1000 words)."],
        )
        error_msg = report.format_actionable_error()
        self.assertIn("EXTRACTION QUALITY GATE AUDIT: REVIEW REQUIRED", error_msg)
        self.assertIn("corrupt_scanned.pdf", error_msg)
        self.assertIn("Affected Suspicious Pages", error_msg)
        self.assertIn("--force-gate", error_msg)

        # Test raising ExtractionGateAuditError
        with self.assertRaises(ExtractionGateAuditError) as ctx:
            raise ExtractionGateAuditError(report)
        self.assertIn("--force-gate", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
