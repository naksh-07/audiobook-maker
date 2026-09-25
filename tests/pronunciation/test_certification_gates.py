#!/usr/bin/env python3
"""
Unit tests for Production Certification Gates T12, T13, T14, and T15.
"""

import unittest
import tempfile
import json
from pathlib import Path

from audiobook_factory.translation.book_bible import BookBible, BookEntity
from audiobook_factory.translation.source_semantic_map import build_source_semantic_map
from audiobook_factory.translation.scene_planner import ScenePlan
from audiobook_factory.translation.certification import TranslationCertifier, GateStatus
from audiobook_factory.pronunciation.contracts import PronunciationEntry, PronunciationStatus


class TestCertificationGates(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

        self.bible = BookBible(book_title="Test Novel", author="Test Author")
        self.bible.characters["Sherlock Holmes"] = BookEntity(
            canonical_id="sherlock_holmes",
            english_name="Sherlock Holmes",
            hindi_name="शरलॉक होम्स",
            pronunciation_hint="शरलॉक होम्स",
        )
        self.bible.characters["Geralt"] = BookEntity(
            canonical_id="geralt",
            english_name="Geralt",
            hindi_name="गेराल्ट",
            pronunciation_hint="गेराल्ट",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_gates_t12_and_t13_pass_on_clean_scene(self):
        source_text = "Sherlock Holmes sat in the room and looked around."
        target_text = "शरलॉक होम्स कमरे में बैठा रहा और चारों तरफ देखता रहा।"

        source_map = build_source_semantic_map(source_text, scene_id="scene_001", known_entities=["Sherlock Holmes"])
        scene_plan = ScenePlan(
            scene_id="scene_001",
            scene_title="Scene 1",
            start_paragraph_idx=0,
            end_paragraph_idx=0,
            text_block=source_text,
            active_characters=["Sherlock Holmes"],
        )

        audit_res = TranslationCertifier.certify_scene(
            source_text=source_text,
            target_text=target_text,
            source_map=source_map,
            scene_plan=scene_plan,
            book_bible=self.bible,
            chapter_num=1,
            call_llm_fn=None,
        )

        # Check Gate T12 (Spoken Language QA)
        self.assertIn("T12_spoken_language", audit_res.gates)
        self.assertEqual(audit_res.gates["T12_spoken_language"].status, GateStatus.PASS)

        # Check Gate T13 (Pronunciation Plan QA)
        self.assertIn("T13_pronunciation_plan", audit_res.gates)
        self.assertEqual(audit_res.gates["T13_pronunciation_plan"].status, GateStatus.PASS)

        # Check Gate T14 (Pronunciation Audio QA)
        self.assertIn("T14_pronunciation_audio", audit_res.gates)
        self.assertEqual(audit_res.gates["T14_pronunciation_audio"].status, GateStatus.PASS)

        # Check Gate T15 (Cross-Chapter Consistency)
        self.assertIn("T15_pronunciation_consistency", audit_res.gates)
        self.assertEqual(audit_res.gates["T15_pronunciation_consistency"].status, GateStatus.PASS)

        self.assertTrue(audit_res.certified)

    def test_02_gate_t13_critical_flags_unresolved_foreign_name(self):
        source_text = "Geralt said that Xylopharius was arriving tomorrow."
        target_text = "गेराल्ट ने कहा कि Xylopharius कल आ रहा है।"

        source_map = build_source_semantic_map(source_text, scene_id="scene_002", known_entities=["Geralt"])
        scene_plan = ScenePlan(
            scene_id="scene_002",
            scene_title="Scene 2",
            start_paragraph_idx=0,
            end_paragraph_idx=0,
            text_block=source_text,
            active_characters=["Geralt"],
        )

        audit_res = TranslationCertifier.certify_scene(
            source_text=source_text,
            target_text=target_text,
            source_map=source_map,
            scene_plan=scene_plan,
            book_bible=self.bible,
            chapter_num=1,
            call_llm_fn=None,
        )

        # Gate T13 should flag warning for unverified foreign name Xylopharius
        self.assertEqual(audit_res.gates["T13_pronunciation_plan"].status, GateStatus.WARN)
        # Because T13 is a CRITICAL_GATE, a critical warning causes overall status to be REVIEW_REQUIRED!
        self.assertEqual(audit_res.overall_status, "REVIEW_REQUIRED")
        self.assertFalse(audit_res.certified)


if __name__ == "__main__":
    unittest.main()
