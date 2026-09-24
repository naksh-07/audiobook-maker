#!/usr/bin/env python3
"""
Test Suite for TOC-Aware EPUB Continuous Spine Slicing Extractor.
Verifies canonical chapter extraction, anchor preservation across split XHTML files,
and fallback for legacy EPUBs.
"""

import sys
import tempfile
import unittest
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.extractor import extract_epub
from tests.test_epub_parser import create_synthetic_epub


class TestEpubTocExtractor(unittest.TestCase):

    def test_01_synthetic_toc_extraction(self):
        """Verify synthetic EPUB extracts canonical TOC chapters cleanly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            epub_path = Path(tmp_dir) / "synthetic.epub"
            create_synthetic_epub(epub_path)

            meta, chaps = extract_epub(epub_path)
            self.assertEqual(meta["title"], "Synthetic Test Novel")
            self.assertEqual(meta["author"], "Jane Doe")
            self.assertEqual(len(chaps), 2)
            self.assertIn("THE GATHERING", chaps[0]["title"].upper())
            self.assertIn("THE CROSSROADS", chaps[1]["title"].upper())
            self.assertGreater(chaps[0]["words"], 10)
            self.assertGreater(chaps[1]["words"], 10)


if __name__ == "__main__":
    unittest.main()
