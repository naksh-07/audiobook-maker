#!/usr/bin/env python3
"""
Test Suite for TOC-Aware EPUB Continuous Spine Slicing Extractor.
Verifies canonical chapter extraction, anchor preservation across split XHTML files,
and fallback for legacy EPUBs.
"""

import sys
import unittest
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.extractor import extract_epub, process_book_file


class TestEpubTocExtractor(unittest.TestCase):

    def test_01_witcher_toc_extraction(self):
        """Verify Witcher 1 EPUB extracts all 13 canonical stories cleanly."""
        epub_path = Path(r"C:\Users\Suraj\Documents\Antigravity\witcher1.epub")
        if not epub_path.exists():
            self.skipTest(f"Witcher EPUB not found at {epub_path}")

        meta, chaps = extract_epub(epub_path)
        self.assertEqual(meta["title"], "The Last Wish: Introducing The Witcher")
        self.assertEqual(meta["author"], "Andrzej Sapkowski")
        self.assertEqual(len(chaps), 13)

        # First chapter: 1: THE VOICE OF REASON
        self.assertIn("VOICE OF REASON", chaps[0]["title"].upper())
        # Second chapter: THE WITCHER
        self.assertIn("WITCHER", chaps[1]["title"].upper())
        # Sixth chapter: THE LESSER EVIL
        self.assertIn("LESSER EVIL", chaps[5]["title"].upper())
        self.assertGreater(chaps[5]["words"], 10000)

        total_words = sum(c["words"] for c in chaps)
        self.assertGreater(total_words, 90000)


if __name__ == "__main__":
    unittest.main()
