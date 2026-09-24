#!/usr/bin/env python3
"""
Unit tests for Literary Intensity Model (Soft ±0.75 Heuristic)
and Deterministic Semantic Pre-Validation & Terminology Auditing.
"""

import unittest
from audiobook_factory.translation.intensity_model import (
    LiteraryIntensityVector,
    IntensityEvaluator,
)
from audiobook_factory.translation.source_semantic_map import build_source_semantic_map
from audiobook_factory.translation.semantic_fidelity import deterministic_negation_audit
from audiobook_factory.translation.terminology_auditor import audit_terminology
from audiobook_factory.translation.book_bible import BookBible, BookEntity


class TestIntensityAndFidelity(unittest.TestCase):

    def test_01_soft_intensity_heuristic_warns_on_mild_shift(self):
        # Shift between 0.75 and 2.0 must emit WARN, is_valid=True (not a hard FAIL)
        source_vec = LiteraryIntensityVector(profanity=2.0, violence=2.0, sexual_intimacy=3.0)
        target_vec = LiteraryIntensityVector(profanity=3.0, violence=2.5, sexual_intimacy=2.0)  # delta 1.0

        res = IntensityEvaluator.compare_vectors(source_vec, target_vec)
        self.assertTrue(res.is_valid, "Mild intensity delta <= 2.0 must remain valid")
        self.assertEqual(res.status, "WARN", "Divergence > 0.75 must trigger soft WARN heuristic")
        self.assertGreater(len(res.warnings), 0)

    def test_02_extreme_divergence_triggers_hard_fail(self):
        # Extreme sanitization: source intimacy 4.5 -> target 0.5 (delta 4.0)
        source_vec = LiteraryIntensityVector(sexual_intimacy=4.5)
        target_vec = LiteraryIntensityVector(sexual_intimacy=0.5)

        res = IntensityEvaluator.compare_vectors(source_vec, target_vec)
        self.assertFalse(res.is_valid, "Extreme sanitization (> 2.0) must FAIL")
        self.assertEqual(res.status, "FAIL")
        self.assertIn("CRITICAL SANITIZATION", res.failure_reasons[0])

    def test_03_deterministic_negation_flip_detected(self):
        source_text = "Geralt did not enter the cursed chamber."
        source_map = build_source_semantic_map(source_text, scene_id="scene_001")

        # Inverted target without negation
        target_inverted = "गेराल्ट उस शापित कमरे में दाखिल हुआ।"
        ok, inversions = deterministic_negation_audit(source_map, target_inverted)
        self.assertFalse(ok, "Inversion without Hindi negation must be caught deterministically")
        self.assertEqual(len(inversions), 1)

        # Faithful target with negation
        target_faithful = "गेराल्ट उस शापित कमरे में दाखिल नहीं हुआ।"
        ok_faithful, _ = deterministic_negation_audit(source_map, target_faithful)
        self.assertTrue(ok_faithful, "Faithful translation with 'नहीं' must pass")

    def test_04_deterministic_terminology_auditor_flags_forbidden_variant(self):
        bible = BookBible(book_title="Test Book")
        bible.terminology["Witcher"] = "विचर"
        bible.terminology_variants[r"\bविचरर\b"] = "विचर"

        # Text containing forbidden variant 'विचरर'
        bad_text = "वह विचरर अपनी तलवार लेकर खड़ा था।"
        res = audit_terminology(bad_text, bible, source_text="The witcher stood with sword.")
        self.assertFalse(res.is_valid)
        self.assertIn("Forbidden variant 'विचरर'", res.forbidden_variants_found[0])

        # Text with canonical 'विचर'
        good_text = "वह विचर अपनी तलवार लेकर खड़ा था।"
        res_good = audit_terminology(good_text, bible, source_text="The witcher stood with sword.")
        self.assertTrue(res_good.is_valid)


if __name__ == "__main__":
    unittest.main()
