#!/usr/bin/env python3
"""
Unit tests for Pronunciation Lexicon, Language Detection, Code Switching, and 7-Tier Resolver.
"""

import unittest
import tempfile
from pathlib import Path

from audiobook_factory.pronunciation.contracts import (
    PronunciationEntry,
    PronunciationStatus,
    PronunciationSource,
    SpokenLanguage,
)
from audiobook_factory.pronunciation.lexicon import PronunciationLexicon
from audiobook_factory.pronunciation.language_detector import (
    detect_token_language,
    classify_sentence_language,
)
from audiobook_factory.pronunciation.code_switch import CodeSwitchEngine
from audiobook_factory.pronunciation.resolver import (
    PronunciationResolver,
    number_to_hindi_words,
)
from audiobook_factory.translation.book_bible import BookBible, BookEntity


class TestPronunciationResolver(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        self.lexicon = PronunciationLexicon.load_or_create(self.project_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_language_detection(self):
        self.assertEqual(detect_token_language("नमस्ते"), SpokenLanguage.HINDI)
        self.assertEqual(detect_token_language("Geralt"), SpokenLanguage.ENGLISH)
        self.assertEqual(detect_token_language("ज़िंदगी"), SpokenLanguage.URDU)
        self.assertEqual(detect_token_language("प्रतीक्षा"), SpokenLanguage.SANSKRIT)

        sent_info = classify_sentence_language("Geralt ने अपनी तलवार उठाई।")
        self.assertTrue(sent_info["is_code_switched"])
        self.assertEqual(sent_info["primary_language"], SpokenLanguage.HINDI)

    def test_02_tier_1_manual_override_priority(self):
        self.lexicon.add_override(
            token="Ostrit",
            spoken_form="ओस्ट्रिट_मैनुअल",
            expected_language=SpokenLanguage.FOREIGN,
        )
        resolver = PronunciationResolver(self.lexicon)
        res = resolver.resolve_token("Ostrit")
        self.assertEqual(res.resolved_spoken, "ओस्ट्रिट_मैनुअल")
        self.assertEqual(res.source, PronunciationSource.MANUAL_OVERRIDE)
        self.assertEqual(res.status, PronunciationStatus.VERIFIED)

    def test_03_tier_2_book_bible_synchronization(self):
        bible = BookBible(book_title="Test")
        bible.characters["Yennefer"] = BookEntity(
            canonical_id="yennefer",
            english_name="Yennefer",
            hindi_name="येनेफ़र",
            pronunciation_hint="येनेफ़र",
        )
        resolver = PronunciationResolver(self.lexicon, book_bible=bible)
        res = resolver.resolve_token("Yennefer")
        self.assertEqual(res.resolved_spoken, "येनेफ़र")
        self.assertEqual(res.source, PronunciationSource.BOOK_BIBLE)

    def test_04_tier_3_verified_project_history(self):
        resolver = PronunciationResolver(self.lexicon)
        resolver.register_verified_pronunciation("Kaer Morhen", "केर मॉरहेन")
        res = resolver.resolve_token("Kaer Morhen")
        self.assertEqual(res.resolved_spoken, "केर मॉरहेन")
        self.assertEqual(res.source, PronunciationSource.PREVIOUS_VERIFIED)

    def test_05_tier_4_canonical_lexicon(self):
        resolver = PronunciationResolver(self.lexicon)
        # "Sherlock Holmes" is seeded in default lexicon
        res = resolver.resolve_token("Sherlock Holmes")
        self.assertEqual(res.resolved_spoken, "शरलॉक होम्स")
        self.assertEqual(res.source, PronunciationSource.CANONICAL_LEXICON)

    def test_06_tier_5_deterministic_numeral_and_currency_rules(self):
        resolver = PronunciationResolver(self.lexicon)

        # Latin numerals
        res_num = resolver.resolve_token("25")
        self.assertEqual(res_num.resolved_spoken, "पच्चीस")
        self.assertEqual(res_num.source, PronunciationSource.DETERMINISTIC_RULE)

        # Devanagari numerals
        res_deva = resolver.resolve_token("५००")
        self.assertEqual(res_deva.resolved_spoken, "पाँच सौ")

        # Currency
        res_curr = resolver.resolve_token("₹100")
        self.assertEqual(res_curr.resolved_spoken, "सौ रुपये")

        # Acronym
        res_acro = resolver.resolve_token("RAW")
        self.assertEqual(res_acro.resolved_spoken, "आर.ए.डब्ल्यू.")

    def test_07_tier_7_unresolved_foreign_name_requires_review(self):
        resolver = PronunciationResolver(self.lexicon)
        # Unknown foreign name not in any lexicon or bible
        res = resolver.resolve_token("Xylopharius")
        self.assertEqual(res.status, PronunciationStatus.REVIEW_REQUIRED)
        self.assertTrue(res.requires_review)
        self.assertEqual(res.source, PronunciationSource.UNRESOLVED)
        # Keeps token as fallback
        self.assertEqual(res.resolved_spoken, "Xylopharius")

    def test_08_number_to_hindi_words_converter(self):
        self.assertEqual(number_to_hindi_words(0), "शून्य")
        self.assertEqual(number_to_hindi_words(7), "सात")
        self.assertEqual(number_to_hindi_words(15), "पंद्रह")
        self.assertEqual(number_to_hindi_words(100), "सौ")
        self.assertEqual(number_to_hindi_words(1500), "एक हज़ार पाँच सौ")
        self.assertEqual(number_to_hindi_words(200000), "दो लाख")


if __name__ == "__main__":
    unittest.main()
