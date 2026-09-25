#!/usr/bin/env python3
"""
Unit tests for Spoken Text Engine and Immutability Safeguards.
"""

import unittest
from audiobook_factory.contracts import ScreenplaySegment, ActingInstructions
from audiobook_factory.pronunciation.lexicon import PronunciationLexicon
from audiobook_factory.pronunciation.resolver import PronunciationResolver
from audiobook_factory.pronunciation.spoken_text import SpokenTextEngine
from audiobook_factory.pronunciation.contracts import PronunciationEntry, PronunciationStatus


class TestSpokenTextEngine(unittest.TestCase):

    def setUp(self):
        self.lexicon = PronunciationLexicon()
        self.lexicon.seed_default_lexicon()
        self.resolver = PronunciationResolver(self.lexicon)
        self.engine = SpokenTextEngine(self.resolver)

    def test_01_literary_text_immutability(self):
        original_literary = "Sherlock Holmes ने ₹500 निकाले और कहा, “यह काफी है।”"
        seg = ScreenplaySegment(
            index=1,
            type="dialogue",
            speaker="Sherlock Holmes",
            text=original_literary,
        )

        result = self.engine.resolve_screenplay_segment(seg)

        # Literary text must NOT be mutated
        self.assertEqual(seg.text, original_literary)
        self.assertEqual(result.literary_text, original_literary)

        # Spoken text must have resolved entity and currency
        self.assertIn("शरलॉक होम्स", result.spoken_text)
        self.assertIn("पाँच सौ रुपये", result.spoken_text)

    def test_02_acting_tag_protection(self):
        literary = "[whispers] उसने धीरे से कहा, [gasp] “FBI यहाँ है!”"
        result = self.engine.resolve_text(literary)

        # Tags must be preserved exactly
        self.assertTrue(result.spoken_text.startswith("[whispers]"))
        self.assertIn("[gasp]", result.spoken_text)
        # Acronym should be expanded
        self.assertIn("एफ़.बी.आई.", result.spoken_text)
        # Display text should have tags stripped
        self.assertNotIn("[whispers]", result.display_text)
        self.assertNotIn("[gasp]", result.display_text)

    def test_03_multi_word_entity_replacement(self):
        self.lexicon.add_entry(PronunciationEntry(
            canonical_id="kaer_morhen",
            canonical_text="Kaer Morhen",
            spoken_form="केर मॉरहेन",
            status=PronunciationStatus.VERIFIED,
        ))
        text = "हम कल सुबह Kaer Morhen के लिए निकलेंगे।"
        result = self.engine.resolve_text(text)
        self.assertEqual(result.spoken_text, "हम कल सुबह केर मॉरहेन के लिए निकलेंगे।")
        self.assertEqual(result.literary_text, text)


if __name__ == "__main__":
    unittest.main()
