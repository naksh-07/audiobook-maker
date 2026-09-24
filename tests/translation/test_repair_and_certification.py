#!/usr/bin/env python3
"""
Unit tests for Tiered Self-Healing Repair and Multi-Gate Translation Certification.
"""

import unittest
import tempfile
from pathlib import Path

from audiobook_factory.translation.repair_engine import TieredRepairEngine
from audiobook_factory.translation.certification import TranslationCertifier, GateStatus
from audiobook_factory.translation.book_bible import BookBible, BookEntity
from audiobook_factory.translation.source_semantic_map import build_source_semantic_map
from audiobook_factory.translation.scene_planner import ScenePlan


class TestRepairAndCertification(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_deterministic_repair_fixes_forbidden_variants_and_antipatterns(self):
        raw_text = "वह विचरर उस सुनहरी लड़की को देखकर नमस्ते कहने लगा।"
        repaired, actions = TieredRepairEngine.apply_deterministic_repair(
            raw_text,
            terminology_variants={r"\bविचरर\b": "विचर"},
        )

        self.assertNotIn("विचरर", repaired)
        self.assertIn("विचर", repaired)
        self.assertNotIn("सुनहरी लड़की", repaired)
        self.assertIn("गोरी-चिट्टी", repaired)
        self.assertGreaterEqual(len(actions), 2)
        self.assertTrue(all(a.repaired_successfully for a in actions))

    def test_02_certify_scene_end_to_end_and_save_artifacts(self):
        bible = BookBible(book_title="The Last Wish", author="Andrzej Sapkowski")
        bible.characters["Geralt"] = BookEntity(
            canonical_id="geralt",
            english_name="Geralt",
            hindi_name="गेराल्ट",
        )
        bible.terminology["Witcher"] = "विचर"

        source_text = "Geralt sat in silence, looking at the silver blade."
        target_text = "गेराल्ट चुपचाप बैठा रहा और उस चाँदी की तलवार को देखता रहा।"

        source_map = build_source_semantic_map(source_text, scene_id="scene_001", known_entities=["Geralt"])
        scene_plan = ScenePlan(
            scene_id="scene_001",
            scene_title="Scene 1: Library Silence",
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
            book_bible=bible,
            chapter_num=1,
            call_llm_fn=None,  # deterministic fast check
        )

        self.assertTrue(audit_res.certified)
        self.assertIn(audit_res.overall_status, ("PASS", "AUTO_REPAIR"))
        self.assertEqual(audit_res.gates["T0_source_integrity"].status, GateStatus.PASS)
        self.assertEqual(audit_res.gates["T5_terminology"].status, GateStatus.PASS)

        # Save artifact bundle
        prov_dict = {"composite_cache_key": "test_key_123", "model": "gemini-3.8-flash"}
        TranslationCertifier.save_artifact_bundle(
            output_dir=self.output_dir,
            source_text=source_text,
            target_text=target_text,
            source_map=source_map,
            scene_plan=scene_plan,
            audit_result=audit_res,
            provenance_dict=prov_dict,
        )

        self.assertTrue((self.output_dir / "source.md").exists())
        self.assertTrue((self.output_dir / "translation.md").exists())
        self.assertTrue((self.output_dir / "semantic_map.json").exists())
        self.assertTrue((self.output_dir / "scene_plan.json").exists())
        self.assertTrue((self.output_dir / "certification.json").exists())
        self.assertTrue((self.output_dir / "provenance.json").exists())


if __name__ == "__main__":
    unittest.main()
