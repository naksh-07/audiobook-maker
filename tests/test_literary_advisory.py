#!/usr/bin/env python3
"""
Unit tests for Literary Advisory Lexicon DB and Register Auditor.
Verifies:
1. SQLite dynamic DB initialization and schema verification.
2. Prompt injection formatting for translation guidelines.
3. Meso-tier audit of literary register and anti-robotic phrase correction.
4. Model hierarchy in translator.
"""

import sys
import unittest
import tempfile
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent.parent
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from audiobook_factory.advisory_lexicon import LiteraryAdvisoryDB, get_advisory_db
from audiobook_factory.sanitizer import audit_literary_register
from audiobook_factory.translator import DEFAULT_MODEL, MODEL_CANDIDATES


class TestLiteraryAdvisory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_advisory.db"
        self.db = LiteraryAdvisoryDB(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_db_initialization_and_seeding(self):
        rules = self.db.list_rules()
        self.assertGreaterEqual(len(rules), 7, "Default seed should contain at least 7 literary rules")
        categories = {r["category"] for r in rules}
        self.assertIn("appearance", categories)
        self.assertIn("youth_sensual", categories)
        self.assertIn("salutations", categories)
        self.assertIn("beverages", categories)

    def test_02_format_guidelines_for_prompt(self):
        guidance = self.db.get_formatted_prompt_guidelines()
        self.assertIn("DYNAMIC LITERARY ADVISORY", guidance)
        self.assertIn("गोरी-चिट्टी", guidance)
        self.assertIn("Banned Robotic Antipatterns", guidance)

    def test_03_audit_literary_register_cleans_antipatterns(self):
        raw_robotic_text = (
            "नमस्ते, गेराल्ट! वह सुनहरी लड़की अपनी कुंवारी चोटी हिला रही थी "
            "और सराय में सब दारू पी रहे थे।"
        )
        is_clean, cleaned, warnings = audit_literary_register(raw_robotic_text)
        self.assertFalse(is_clean, "Expected is_clean=False for robotic antipatterns")
        self.assertGreater(len(warnings), 0, "Expected warnings for robotic antipatterns")
        self.assertNotIn("सुनहरी लड़की", cleaned)
        self.assertNotIn("कुंवारी चोटी", cleaned)
        self.assertNotIn("नमस्ते, गेराल्ट", cleaned)
        self.assertNotIn("दारू", cleaned)

    def test_04_audit_literary_register_passes_calibrated_text(self):
        calibrated_text = (
            "सलाम, गेराल्ट! वह गोरी-चिट्टी कमसिन लड़की अपनी लंबी चोटी हिला रही थी "
            "और सराय में सब मदिरा और शराब पी रहे थे।"
        )
        is_clean, cleaned, warnings = audit_literary_register(calibrated_text)
        self.assertTrue(is_clean, f"Expected is_clean=True, got warnings: {warnings}")
        self.assertEqual(len(warnings), 0, f"Expected 0 warnings for calibrated text, got: {warnings}")
        self.assertEqual(cleaned, calibrated_text)

    def test_05_translator_model_hierarchy(self):
        self.assertEqual(DEFAULT_MODEL, "gemini-3.8-flash")
        self.assertIn("gemini-3.8-flash", MODEL_CANDIDATES)
        self.assertIn("gemini-3.7-flash", MODEL_CANDIDATES)


if __name__ == "__main__":
    unittest.main()
