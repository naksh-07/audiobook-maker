#!/usr/bin/env python3
"""
Unit Tests for Non-Destructive Literary Normalizer.
"""

import unittest
from audiobook_factory.normalizer import clean_book_text, normalize_block_text


class TestNormalizer(unittest.TestCase):

    def test_unicode_nfc_and_zero_width_hygiene(self):
        precomposed = "\u0958"  # क़
        raw = f"Zero\u200bwidth\ufeff test with {precomposed}."
        cleaned = clean_book_text(raw)
        self.assertNotIn("\u200b", cleaned)
        self.assertNotIn("\ufeff", cleaned)
        self.assertIn("\u0915\u093c", cleaned)

    def test_hyphenated_linebreak_healing(self):
        raw = "This is an impor-\ntant docu-\n\nment."
        cleaned = clean_book_text(raw)
        self.assertIn("important", cleaned)
        self.assertIn("document", cleaned)

    def test_safe_footnote_stripping(self):
        raw = "Geralt drew his silver sword[1] and turned[42] toward the striga."
        cleaned = clean_book_text(raw)
        self.assertEqual(cleaned, "Geralt drew his silver sword and turned toward the striga.")

    def test_running_headers_and_page_numbers(self):
        raw = """
Chapter 1: The Voice of Reason

Page 42 of 300

The evening mist rose over the lake.

- 43 -

A boat emerged from the reeds.
"""
        cleaned = clean_book_text(raw)
        self.assertNotIn("Page 42", cleaned)
        self.assertNotIn("- 43 -", cleaned)
        self.assertIn("The evening mist", cleaned)
        self.assertIn("A boat emerged", cleaned)

    def test_preserve_literary_quotes_flag(self):
        raw = "“Hello,” she said. ‘Yes,’ he replied — slowly…"
        straight = clean_book_text(raw, preserve_literary_quotes=False)
        self.assertIn('"', straight)
        self.assertIn("...", straight)

        curly = clean_book_text(raw, preserve_literary_quotes=True)
        self.assertIn("“", curly)
        self.assertIn("‘", curly)

    def test_normalize_block_text_warnings(self):
        raw = "Corrupt character \ufffd in text with many multi-\nline broken-\nwords here-\ntoo."
        norm, warnings = normalize_block_text(raw)
        self.assertGreaterEqual(len(warnings), 1)
        self.assertTrue(any("Unicode replacement" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
