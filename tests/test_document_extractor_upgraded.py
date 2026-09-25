#!/usr/bin/env python3
"""
Comprehensive Integration & Verification Suite for Upgraded Document Ingestion Pipeline.
Verifies:
1. Sacred raw source preservation (raw/ directory + sha256 checksums).
2. Strongly typed Canonical Book Model & provenance (canonical/book.json).
3. Independent Extraction Quality Gate auditing (PASS, WARN, REVIEW).
4. Backward-compatible projection (extracted/chapter_XXX.md + metadata.json).
5. Downstream screenplay script compatibility.
6. Multi-format ingestion (EPUB, TXT, Markdown).
7. Meso-tier 12,000 word semantic splitting.
"""

import os
import json
import zipfile
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.extractor import (
    process_book_file,
    extract_chapters,
    extract_epub,
    clean_book_text,
    segment_chapters_from_text,
    split_large_chapter_on_semantic_boundary,
)
from audiobook_factory.book_model import (
    CanonicalBook,
    ExtractionGateAuditError,
)
from audiobook_factory.script_builder import build_narrator_script


def make_test_epub(file_path: Path, title: str = "Test Fantasy Novel", author: str = "A. Author") -> Path:
    """Helper to build a valid test EPUB archive."""
    container_xml = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/package.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    package_opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="chapter2.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="c1"/>
    <itemref idref="c2"/>
  </spine>
</package>"""

    toc_ncx = """<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <navMap>
    <navPoint id="np1" playOrder="1">
      <navLabel><text>Chapter 1: The Dragon's Ridge</text></navLabel>
      <content src="chapter1.xhtml#ch1"/>
    </navPoint>
    <navPoint id="np2" playOrder="2">
      <navLabel><text>Chapter 2: The Whispering Woods</text></navLabel>
      <content src="chapter2.xhtml"/>
    </navPoint>
  </navMap>
</ncx>"""

    ch1_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
  <div id="ch1">
    <h1>Chapter 1: The Dragon's Ridge</h1>
    <p>The cold mountain wind swept across the rocky escarpment, carrying the smell of sulfur.</p>
    <p>A hunter stood upon the jagged precipice, gazing down into the smoking caldera below.</p>
    <hr/>
    <blockquote>“Few dare to climb this high,” warned the old ranger from behind.</blockquote>
    <p>“Only those with nothing left to lose,” the hunter replied in a calm, measured voice.</p>
  </div>
</body>
</html>"""

    ch2_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<body>
  <h2>Chapter 2: The Whispering Woods</h2>
  <p>Beneath the canopy of towering ancient silver firs, the daylight was swallowed by emerald shadow.</p>
  <p>Soft rustling echoed from the underbrush, accompanied by the distant chittering of forest spirits.</p>
  <p>The path narrowed until it disappeared entirely among mossy roots and damp fallen leaves.</p>
</body>
</html>"""

    with zipfile.ZipFile(file_path, "w") as zf:
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/package.opf", package_opf)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)
        zf.writestr("OEBPS/chapter1.xhtml", ch1_xhtml)
        zf.writestr("OEBPS/chapter2.xhtml", ch2_xhtml)

    return file_path


class TestDocumentExtractorUpgraded(unittest.TestCase):

    def test_01_full_epub_ingestion_and_directory_structure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            epub_file = make_test_epub(tmp_path / "dragon_novel.epub")
            projects_dir = tmp_path / "projects"

            # Execute universal entrypoint
            meta = process_book_file(epub_file, projects_dir)

            book_dir = projects_dir / meta["book_id"]
            raw_dir = book_dir / "raw"
            canonical_dir = book_dir / "canonical"
            extracted_dir = book_dir / "extracted"

            # 1. Verify Raw preservation
            self.assertTrue(raw_dir.exists())
            self.assertTrue((raw_dir / "source_original.epub").exists())
            self.assertTrue((raw_dir / "source_manifest.json").exists())
            manifest = json.loads((raw_dir / "source_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["book_id"], meta["book_id"])
            self.assertIn("sha256", manifest)

            # 2. Verify Canonical Model
            self.assertTrue(canonical_dir.exists())
            self.assertTrue((canonical_dir / "book.json").exists())
            self.assertTrue((canonical_dir / "quality_report.json").exists())
            canonical_json = json.loads((canonical_dir / "book.json").read_text(encoding="utf-8"))
            self.assertEqual(len(canonical_json["chapters"]), 2)
            self.assertEqual(canonical_json["title"], "Test Fantasy Novel")
            
            # Verify block-level provenance in canonical chapter
            ch1 = canonical_json["chapters"][0]
            self.assertEqual(ch1["title"], "Chapter 1: The Dragon's Ridge")
            self.assertGreaterEqual(len(ch1["blocks"]), 3)
            self.assertEqual(ch1["blocks"][0]["provenance"]["source_type"], "epub")
            self.assertIn("chapter1.xhtml", ch1["blocks"][0]["provenance"]["spine_item"])

            # 3. Verify Legacy Extracted Projections
            self.assertTrue(extracted_dir.exists())
            self.assertTrue((extracted_dir / "chapter_001.md").exists())
            self.assertTrue((extracted_dir / "chapter_002.md").exists())
            ch1_content = (extracted_dir / "chapter_001.md").read_text(encoding="utf-8")
            self.assertIn("# Chapter 1: The Dragon's Ridge", ch1_content)
            self.assertIn("cold mountain wind", ch1_content)
            self.assertIn('> "Few dare to climb this high,"', ch1_content)

            # 4. Verify Project Metadata
            self.assertTrue((book_dir / "metadata.json").exists())
            self.assertEqual(meta["total_chapters"], 2)
            self.assertEqual(meta["extraction_quality"]["gate_status"], "PASS")

            # 5. Verify Downstream Screenplay Handoff
            script = build_narrator_script(ch1_content, is_hindi=False)
            self.assertGreaterEqual(len(script), 3)
            self.assertEqual(script[0]["speaker"], "Narrator")

    def test_02_text_novel_ingestion(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            txt_file = tmp_path / "simple_novel.txt"
            txt_file.write_text(
                """
Chapter 1: The Awakening

The sun rose gently over the eastern valleys.
Geralt opened his eyes and reached for his boots.

Chapter 2: The Blaviken Contract

In the bustling market square, merchants shouted their wares.
A woman in a hooded cloak watched the witcher from across the fountain.
""",
                encoding="utf-8",
            )
            projects_dir = tmp_path / "projects"
            meta = process_book_file(txt_file, projects_dir)

            book_dir = projects_dir / meta["book_id"]
            self.assertTrue((book_dir / "canonical" / "book.json").exists())
            self.assertTrue((book_dir / "extracted" / "chapter_001.md").exists())
            self.assertEqual(meta["total_chapters"], 2)
            self.assertEqual(meta["extraction_quality"]["gate_status"], "PASS")

    def test_03_quality_gate_review_fail_closed_and_force_override(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            empty_file = tmp_path / "corrupt_stub.txt"
            empty_file.write_text("", encoding="utf-8")  # Zero text
            projects_dir = tmp_path / "projects"

            # Fail-closed by default
            with self.assertRaises(ExtractionGateAuditError) as ctx:
                process_book_file(empty_file, projects_dir, force_gate=False)
            self.assertIn("EXTRACTION QUALITY GATE AUDIT: REVIEW REQUIRED", str(ctx.exception))
            self.assertIn("--force-gate", str(ctx.exception))

            # Force override allows execution
            meta = process_book_file(empty_file, projects_dir, force_gate=True)
            self.assertEqual(meta["extraction_quality"]["gate_status"], "REVIEW")

    def test_04_meso_tier_semantic_splitting_integration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            big_txt = tmp_path / "huge_novel.txt"
            part_a = "The warriors marched through the deep snow. " * 1000  # ~7,000 words
            divider = "\n\n* * *\n\n"
            part_b = "At midnight they saw the fortress fires. " * 1000  # ~7,000 words
            big_txt.write_text(f"Chapter 1: The March\n\n{part_a}{divider}{part_b}", encoding="utf-8")

            projects_dir = tmp_path / "projects"
            meta = process_book_file(big_txt, projects_dir)

            # 14,000 words auto-split into 2 parts
            self.assertEqual(meta["total_chapters"], 2)
            self.assertEqual(meta["detected_literary_chapters"], 1)
            self.assertEqual(meta["production_chunks"], 2)
            self.assertFalse(meta["used_fallback_chunking"])
            self.assertEqual(meta["chapters"][0]["title"], "Chapter 1: The March (Part 1)")
            self.assertEqual(meta["chapters"][1]["title"], "Chapter 1: The March (Part 2)")
            self.assertEqual(meta["chapters"][0]["unit_type"], "production_chunk")
            self.assertFalse(meta["chapters"][0]["is_literary_chapter"])
            self.assertTrue(meta["chapters"][0]["is_production_chunk"])
            self.assertEqual(meta["chapters"][0]["parent_chapter_title"], "Chapter 1: The March")
            self.assertEqual(meta["chapters"][0]["literary_chapter_number"], 1)
            self.assertLessEqual(meta["chapters"][0]["words"], 12000)
            self.assertLessEqual(meta["chapters"][1]["words"], 12000)

            # Verify CanonicalBook reconstructs the 1 true literary chapter while tracking 2 production chunks
            book_dir = projects_dir / meta["book_id"]
            book = CanonicalBook.model_validate_json((book_dir / "canonical" / "book.json").read_text(encoding="utf-8"))
            lit_chaps = book.get_literary_chapters()
            prod_chunks = book.get_production_chunks()
            self.assertEqual(len(lit_chaps), 1)
            self.assertEqual(lit_chaps[0].title, "Chapter 1: The March")
            self.assertTrue(lit_chaps[0].is_literary_chapter)
            self.assertEqual(len(prod_chunks), 2)

    def test_05_source_manifest_and_orchestrator_force_gate(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            novel_txt = tmp_path / "test_book.txt"
            novel_txt.write_text("Chapter 1: The Beginning\n\nIt was a dark and stormy night.", encoding="utf-8")
            projects_dir = tmp_path / "projects"

            meta = process_book_file(novel_txt, projects_dir)
            book_dir = projects_dir / meta["book_id"]
            manifest_file = book_dir / "raw" / "source_manifest.json"
            self.assertTrue(manifest_file.exists())
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            self.assertIn("archived_copy", manifest_data)
            self.assertTrue(Path(manifest_data["archived_copy"]).exists())

            # Test orchestrator signature accepts force_gate
            from audiobook_factory.orchestrator import PipelineOrchestrator
            import inspect
            orch = PipelineOrchestrator(projects_dir)
            sig = inspect.signature(orch.run_autonomous_pipeline)
            self.assertIn("force_gate", sig.parameters)
            self.assertEqual(sig.parameters["force_gate"].default, False)

    def test_06_unchaptered_fallback_chunks_and_raw_text_preservation(self):
        """
        Verifies:
        - Unchaptered documents produce explicit 'production_chunk' units (not fake literary chapters).
        - Sacred raw_text on CanonicalBlock is preserved unmutated while normalized_text is cleaned.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            unchaptered_txt = tmp_path / "raw_manuscript.txt"
            raw_paragraph = "“Evil is evil[1],” Geralt said—looking into the dark woods…"
            unchaptered_txt.write_text(
                (raw_paragraph + "\n\n") * 8,
                encoding="utf-8",
            )
            projects_dir = tmp_path / "projects"

            meta = process_book_file(unchaptered_txt, projects_dir)
            self.assertEqual(meta["detected_literary_chapters"], 0)
            self.assertEqual(meta["production_chunks"], 1)
            self.assertTrue(meta["used_fallback_chunking"])
            self.assertEqual(meta["chapters"][0]["title"], "Production Chunk 1")
            self.assertEqual(meta["chapters"][0]["unit_type"], "production_chunk")
            self.assertFalse(meta["chapters"][0]["is_literary_chapter"])
            self.assertTrue(meta["chapters"][0]["is_production_chunk"])

            book_dir = projects_dir / meta["book_id"]
            book = CanonicalBook.model_validate_json((book_dir / "canonical" / "book.json").read_text(encoding="utf-8"))
            self.assertEqual(len(book.get_literary_chapters()), 0)
            self.assertEqual(len(book.get_production_chunks()), 1)

            # Verify sacred raw_text is unmutated while normalized_text has normalized quotes/footnotes
            first_block = book.chapters[0].blocks[0]
            self.assertEqual(first_block.raw_text, raw_paragraph)
            self.assertIn("[1]", first_block.raw_text)
            self.assertIn("“", first_block.raw_text)
            self.assertNotIn("[1]", first_block.normalized_text)
            self.assertIn('"Evil is evil,"', first_block.normalized_text)
            self.assertEqual(first_block.provenance.line_start, 1)


if __name__ == "__main__":
    unittest.main()

