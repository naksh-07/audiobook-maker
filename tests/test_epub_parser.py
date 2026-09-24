#!/usr/bin/env python3
"""
Unit and Integration Tests for Forensic Structural EPUB Parser.
Tests synthetic structural EPUBs, NCX navigation, and spine fallbacks.
"""

import io
import zipfile
import tempfile
import unittest
from pathlib import Path

from audiobook_factory.epub_parser import (
    EPUBStructuralHTMLParser,
    ForensicEPUBParser,
    extract_epub,
)


def create_synthetic_epub(epub_path: Path) -> Path:
    """Creates a well-formed synthetic EPUB for structural testing."""
    container_xml = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>"""

    content_opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Synthetic Test Novel</dc:title>
    <dc:creator>Jane Doe</dc:creator>
    <dc:language>en</dc:language>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="ch1" href="ch01.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch02.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
  </spine>
</package>"""

    toc_ncx = """<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <navMap>
    <navPoint id="nav1" playOrder="1">
      <navLabel><text>Chapter 1: The Gathering</text></navLabel>
      <content src="ch01.xhtml#ch1_start"/>
    </navPoint>
    <navPoint id="nav2" playOrder="2">
      <navLabel><text>Chapter 2: The Crossroads</text></navLabel>
      <content src="ch02.xhtml"/>
    </navPoint>
  </navMap>
</ncx>"""

    ch01_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter 1</title></head>
<body>
  <div id="ch1_start">
    <h1>Chapter 1: The Gathering</h1>
    <p>The dawn broke over the misty hills, cold and grey.</p>
    <hr/>
    <blockquote>“Beware the shadow at the pass,” she whispered softly.</blockquote>
    <p>He nodded in silence, gripping his hilt tightly.</p>
    <p class="scenebreak">* * *</p>
    <p>By midday, they had reached the crossroads of the northern vales.</p>
  </div>
</body>
</html>"""

    ch02_xhtml = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Chapter 2</title></head>
<body>
  <h2>Chapter 2: The Crossroads</h2>
  <p>Four stone markers pointed toward different realms of the ancient world.</p>
  <p>The wind began to howl fiercely through the pines and barren rocks.</p>
  <p>They prepared their encampment as dusk fell upon the wild frontier.</p>
</body>
</html>"""

    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", content_opf)
        zf.writestr("OEBPS/toc.ncx", toc_ncx)
        zf.writestr("OEBPS/ch01.xhtml", ch01_xhtml)
        zf.writestr("OEBPS/ch02.xhtml", ch02_xhtml)

    return epub_path


class TestForensicEPUBParser(unittest.TestCase):

    def test_structural_html_parser(self):
        sample_html = """
        <div id="start">
          <h1>Prologue</h1>
          <p>The night was still.</p>
          <hr/>
          <blockquote>“Silence is golden.”</blockquote>
          <p>* * *</p>
          <p>And then came the thunder.</p>
        </div>
        """
        parser = EPUBStructuralHTMLParser(source_file="test.epub", spine_item="ch01.xhtml")
        parser.feed(sample_html)
        blocks = parser.finalize()

        types = [b.type for b in blocks]
        self.assertIn("heading", types)
        self.assertIn("paragraph", types)
        self.assertIn("scene_break", types)
        self.assertIn("quote", types)

        # Check provenance
        h_block = next(b for b in blocks if b.type == "heading")
        self.assertEqual(h_block.provenance.spine_item, "ch01.xhtml")
        self.assertEqual(h_block.semantic_metadata.get("level"), 1)

    def test_synthetic_epub_extraction(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "synthetic.epub"
            create_synthetic_epub(epub_path)

            parser = ForensicEPUBParser(epub_path)
            book, legacy_items = parser.parse()

            self.assertEqual(book.title, "Synthetic Test Novel")
            self.assertEqual(book.author, "Jane Doe")
            self.assertEqual(len(book.chapters), 2)
            self.assertEqual(book.chapters[0].title, "Chapter 1: The Gathering")
            self.assertEqual(book.chapters[1].title, "Chapter 2: The Crossroads")

            # Check blocks inside chapter 1
            ch1_blocks = book.chapters[0].blocks
            self.assertTrue(any(b.type == "heading" for b in ch1_blocks))
            self.assertTrue(any(b.type == "quote" for b in ch1_blocks))
            self.assertTrue(any(b.type == "scene_break" for b in ch1_blocks))

            # Check legacy backward-compatible format
            self.assertEqual(len(legacy_items), 2)
            self.assertIn("Chapter 1: The Gathering", legacy_items[0]["title"])
            self.assertIn("The dawn broke", legacy_items[0]["content"])

    def test_backward_compatible_extract_epub_api(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "synthetic.epub"
            create_synthetic_epub(epub_path)

            meta, chapters = extract_epub(epub_path)
            self.assertEqual(meta["title"], "Synthetic Test Novel")
            self.assertEqual(meta["author"], "Jane Doe")
            self.assertEqual(len(chapters), 2)


if __name__ == "__main__":
    unittest.main()
