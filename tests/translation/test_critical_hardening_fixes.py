#!/usr/bin/env python3
"""
Comprehensive Regression Test Suite for Translation Hardening Fixes (1 to 7).
Verifies:
- Fix 1: SourceSemanticMap WHO -> DID WHAT -> TO WHOM -> OBJECT -> NEGATION -> TIME/LOCATION
- Fix 2: TargetSemanticMap and SemanticAligner paragraph-level negation & actor alignment
- Fix 3: 4-Tier Certification State Machine (PASS, PASS_WITH_WARNINGS, REVIEW_REQUIRED, BLOCKED)
- Fix 4: Literary Intensity Vector Estimation & Gate T8 Calibrated Evaluation
- Fix 5: Multi-Paragraph & Scene Tiered Repair Planning with Bounded Retries
- Fix 6: Sanitizer Literary Register Preservation (नमस्ते, राम-राम, दारू, सोने की लड़की)
- Fix 7: Full 11-Component Provenance Fingerprint & Cache Invalidation
"""

import unittest
from pathlib import Path

from audiobook_factory.translation.source_semantic_map import (
    build_source_semantic_map,
    build_target_semantic_map,
    SemanticAligner,
    SEMANTIC_MAP_VERSION,
)
from audiobook_factory.translation.semantic_fidelity import (
    deterministic_negation_audit,
    evaluate_semantic_fidelity,
)
from audiobook_factory.translation.certification import (
    TranslationCertifier,
    GateStatus,
    GateAuditResult,
    EVALUATOR_VERSION,
)
from audiobook_factory.translation.intensity_model import (
    LiteraryIntensityVector,
    IntensityEvaluator,
)
from audiobook_factory.translation.repair_engine import (
    TieredRepairEngine,
    REPAIR_ENGINE_VERSION,
)
from audiobook_factory.translation.provenance import (
    TranslationProvenanceTracker,
)
from audiobook_factory.translation.book_bible import BookBible, BookEntity
from audiobook_factory.translation.scene_planner import ScenePlan
from audiobook_factory.sanitizer import audit_literary_register


class TestCriticalHardeningFixes(unittest.TestCase):

    def setUp(self):
        self.bible = BookBible(book_title="Test Chronicle", author="Master Writer")
        self.bible.characters["Valerius"] = BookEntity(
            canonical_id="valerius",
            english_name="Valerius",
            hindi_name="वलेरियस",
            role="the witcher",
        )
        self.bible.characters["Julian"] = BookEntity(
            canonical_id="julian",
            english_name="Julian",
            hindi_name="जूलियन",
            role="the poet",
        )
        self.bible.terminology["Silver Blade"] = "चाँदी की तलवार"
        self.bible.terminology_variants[r"\bविचरर\b"] = "विचर"

    def test_01_fix1_source_semantic_map_slot_extraction(self):
        """Fix 1: Verifies extraction of WHO, DID WHAT, TO WHOM, OBJECT, NEGATION, TIME, LOCATION."""
        passage = (
            'The next morning, Valerius sat in the courtyard, looking at the silver blade.\n\n'
            '"I did not enter the temple," agreed the poet.\n\n'
            'Valerius shouted at the guards in the hall.'
        )
        s_map = build_source_semantic_map(
            scene_text=passage,
            scene_id="scene_001",
            known_entities=["Valerius", "Julian"],
            known_objects=["silver blade"],
        )

        self.assertEqual(s_map.semantic_map_version, SEMANTIC_MAP_VERSION)
        self.assertEqual(len(s_map.propositions), 3)

        # Beat 1: Valerius sat in courtyard looking at silver blade
        b1 = s_map.propositions[0]
        self.assertIn("Valerius", b1.actors)
        self.assertTrue(len(b1.action) > 0, "Action must not be empty string")
        self.assertIn("the next morning", b1.time_marker.lower())
        self.assertIn("courtyard", b1.location_marker.lower())
        self.assertFalse(b1.has_negation)
        self.assertFalse(b1.is_dialogue)

        # Beat 2: Speech attribution with negation
        b2 = s_map.propositions[1]
        self.assertTrue(b2.has_negation)
        self.assertIn("not", b2.negation_keywords)
        self.assertTrue(b2.is_dialogue)
        self.assertIn("the poet", b2.actors)
        self.assertEqual(b2.action, "agreed")

        # Beat 3: Recipient extraction
        b3 = s_map.propositions[2]
        self.assertIn("Valerius", b3.actors)
        self.assertTrue(any("guard" in r.lower() for r in b3.recipients))

    def test_02_fix2_target_semantic_map_and_alignment(self):
        """Fix 2: Verifies TargetSemanticMap and paragraph-level negation audit on long scenes."""
        # 8-paragraph source text
        src_paras = [
            f"Paragraph {i}: The traveler walked along the stony road."
            for i in range(7)
        ]
        # Paragraph 7 contains negation
        src_paras.append("Paragraph 7: Valerius did not enter the ancient crypt.")
        full_src = "\n\n".join(src_paras)

        s_map = build_source_semantic_map(full_src, scene_id="scene_002", known_entities=["Valerius"])
        self.assertEqual(len(s_map.propositions), 8)

        # Target with 8 paragraphs where paragraph 7 omits negation
        tgt_paras_flawed = [
            f"अनुच्छेद {i}: मुसाफ़िर पथरीले रास्ते पर चलता रहा।"
            for i in range(7)
        ]
        # Inverted translation of paragraph 7 (missing 'नहीं')
        tgt_paras_flawed.append("अनुच्छेद 7: वलेरियस उस प्राचीन तहख़ाने में दाखिल हुआ।")
        full_tgt_flawed = "\n\n".join(tgt_paras_flawed)

        # Must be caught deterministically by paragraph-level audit even with len >= 8
        det_ok, inversions = deterministic_negation_audit(s_map, full_tgt_flawed)
        self.assertFalse(det_ok, "Must catch negation flip on paragraph 7 in multi-paragraph scene")
        self.assertTrue(any("Paragraph 7" in inv or "negation" in inv for inv in inversions))

        # Semantic aligner test
        t_map_flawed = build_target_semantic_map(full_tgt_flawed, scene_id="scene_002", book_bible=self.bible)
        align_res = SemanticAligner.align(s_map, t_map_flawed, book_bible=self.bible)
        self.assertIn(7, align_res.affected_paragraphs)

        # Faithful target with 'नहीं' in paragraph 7
        tgt_paras_faithful = list(tgt_paras_flawed)
        tgt_paras_faithful[7] = "अनुच्छेद 7: वलेरियस उस प्राचीन तहख़ाने में दाखिल नहीं हुआ।"
        full_tgt_faithful = "\n\n".join(tgt_paras_faithful)

        det_ok_f, _ = deterministic_negation_audit(s_map, full_tgt_faithful)
        self.assertTrue(det_ok_f, "Faithful translation must pass paragraph-level audit")

    def test_03_fix3_certification_status_differentiation(self):
        """Fix 3: Verifies that critical WARN cannot silently become PASS."""
        source_text = "Valerius sat in silence, looking at the silver blade."
        target_text = "वलेरियस चुपचाप बैठा रहा और उस चाँदी की तलवार को देखता रहा।"

        s_map = build_source_semantic_map(source_text, scene_id="scene_003", known_entities=["Valerius"])
        plan = ScenePlan(
            scene_id="scene_003",
            scene_title="Scene 3",
            start_paragraph_idx=0,
            end_paragraph_idx=0,
            text_block=source_text,
            active_characters=["Valerius"],
        )

        # 1. Clean translation -> PASS
        audit_pass = TranslationCertifier.certify_scene(
            source_text=source_text,
            target_text=target_text,
            source_map=s_map,
            scene_plan=plan,
            book_bible=self.bible,
        )
        self.assertTrue(audit_pass.certified)
        self.assertEqual(audit_pass.overall_status, "PASS")

        # 2. Blank translation -> BLOCKED
        audit_blocked = TranslationCertifier.certify_scene(
            source_text=source_text,
            target_text="",
            source_map=s_map,
            scene_plan=plan,
            book_bible=self.bible,
        )
        self.assertFalse(audit_blocked.certified)
        self.assertEqual(audit_blocked.overall_status, "BLOCKED")

        # 3. Flawed translation with semantic inversion -> REVIEW_REQUIRED
        inverted_target = "वलेरियस ने तलवार तोड़ दी और भाग गया।"
        audit_review = TranslationCertifier.certify_scene(
            source_text="Valerius did not break the blade.",
            target_text=inverted_target,
            source_map=build_source_semantic_map("Valerius did not break the blade.", scene_id="scene_003"),
            scene_plan=plan,
            book_bible=self.bible,
        )
        self.assertFalse(audit_review.certified)
        self.assertEqual(audit_review.overall_status, "REVIEW_REQUIRED")

    def test_04_fix4_intensity_model_calibrated_evaluation(self):
        """Fix 4: Verifies calibrated intensity estimation and Gate T8 evaluation."""
        src_text = "Blood splattered across the stone as the blade cut deep into flesh!"
        tgt_text = "पत्थर पर ख़ून बिखर गया और तलवार ने जिस्म को गहरा चीर दिया!"

        s_vec = IntensityEvaluator.estimate_source_intensity(src_text)
        t_vec = IntensityEvaluator.estimate_target_intensity(tgt_text, source_vector=s_vec)

        # Violence should be calibrated above baseline
        self.assertGreater(s_vec.violence, 0.5)
        self.assertGreater(t_vec.violence, 0.5)

        comp = IntensityEvaluator.compare_vectors(s_vec, t_vec)
        self.assertTrue(comp.is_valid)
        self.assertIn(comp.status, ("PASS", "WARN"))

    def test_05_fix5_repair_engine_orchestration_targeted_paragraphs(self):
        """Fix 5: Verifies TieredRepairEngine targets specific failing paragraphs (not hardcoded 0)."""
        # Create synthetic audit result where paragraph 2 failed
        audit = GateAuditResult(
            chapter_num=1,
            scene_id="scene_005",
            overall_status="REVIEW_REQUIRED",
            certified=False,
            affected_paragraphs=[2],
            summary="Paragraph 2 failed fidelity",
        )
        level, targets, reasons = TieredRepairEngine.plan_repair(audit, total_paragraphs=4)
        self.assertEqual(level, "PARAGRAPH_REWRITE")
        self.assertEqual(targets, [2], "Must target paragraph 2 specifically, not paragraph 0")

        # Test prompt construction
        p_prompt = TieredRepairEngine.build_paragraph_repair_prompt(
            source_paragraph="Source paragraph 2",
            current_target_paragraph="Target paragraph 2 with error",
            failure_reasons=["Missing negation"],
        )
        self.assertIn("Source paragraph 2", p_prompt)
        self.assertIn("Missing negation", p_prompt)

    def test_06_fix6_sanitizer_preserves_literary_choices(self):
        """Fix 6: Verifies legitimate literary choices are preserved in sanitizer and repair."""
        rustic_dialogue = "नमस्ते! सराय के कोने में बैठकर वह दारू पी रहा था और सोने की लड़की की बातें कर रहा था।"

        # Default audit must be non-destructive
        is_clean, cleaned, warnings = audit_literary_register(rustic_dialogue, apply_substitutions=False)
        self.assertEqual(cleaned, rustic_dialogue, "Default audit must be 100% non-destructive")
        self.assertIn("नमस्ते", cleaned)
        self.assertIn("दारू", cleaned)
        self.assertIn("सोने की लड़की", cleaned)

        # Level 1 repair must preserve literary greetings/beverages while fixing forbidden terms
        text_with_forbidden = "वह विचरर नमस्ते कहकर दारू माँगने लगा।"
        repaired, actions = TieredRepairEngine.apply_deterministic_repair(
            text_with_forbidden,
            terminology_variants=self.bible.terminology_variants,
        )
        self.assertIn("विचर", repaired)
        self.assertNotIn("विचरर", repaired)
        self.assertIn("नमस्ते", repaired, "नमस्ते must be preserved as legitimate character greeting")
        self.assertIn("दारू", repaired, "दारू must be preserved as authentic rustic beverage")

    def test_07_fix7_provenance_composite_key_invalidation(self):
        """Fix 7: Verifies that changing version components invalidates the cache key."""
        src = "The traveler arrived at dusk."
        b_hash = "bible_hash_abc"

        key_v1 = TranslationProvenanceTracker.generate_composite_key(
            source_text=src,
            bible_version_hash=b_hash,
            prompt_version="2.0.0",
            translator_version="2.0",
            evaluator_version="2.0",
            semantic_map_version="2.0",
            repair_version="2.0",
        )

        key_v2_prompt = TranslationProvenanceTracker.generate_composite_key(
            source_text=src,
            bible_version_hash=b_hash,
            prompt_version="2.1.0",  # Bumped
            translator_version="2.0",
            evaluator_version="2.0",
            semantic_map_version="2.0",
            repair_version="2.0",
        )

        key_v2_sem = TranslationProvenanceTracker.generate_composite_key(
            source_text=src,
            bible_version_hash=b_hash,
            prompt_version="2.0.0",
            translator_version="2.0",
            evaluator_version="2.0",
            semantic_map_version="2.1",  # Bumped
            repair_version="2.0",
        )

        self.assertNotEqual(key_v1, key_v2_prompt, "Prompt version change must invalidate cache key")
        self.assertNotEqual(key_v1, key_v2_sem, "Semantic map version change must invalidate cache key")

    def test_08_lexical_negation_and_zero_source_guard(self):
        """Auditor Finding Remediation: Verifies lexical negation parity & zero-source input guard."""
        # 1. Lexical negation: refused -> इनकार
        src = "He refused to enter the room."
        tgt = "उसने कमरे में जाने से इनकार कर दिया।"
        s_map = build_source_semantic_map(src)
        t_map = build_target_semantic_map(tgt)

        align = SemanticAligner.align(s_map, t_map, self.bible)
        self.assertTrue(align.overall_negation_parity, "Lexical negation 'refused' -> 'इनकार' must maintain parity")
        self.assertTrue(align.is_valid, "Alignment must be valid for accurate lexical refusal")

        fidelity = evaluate_semantic_fidelity(s_map, tgt)
        self.assertTrue(fidelity.is_valid, "Semantic fidelity must pass for lexical refusal")

        # 2. Zero-source input guard
        s_empty = build_source_semantic_map("")
        t_hallucinated = build_target_semantic_map("यह एक पूरी तरह से गढ़ा हुआ वाक्य है।")
        res_zero = SemanticAligner.align(s_empty, t_hallucinated, self.bible)
        self.assertFalse(res_zero.is_valid, "Empty source with hallucinated target must fail is_valid")
        self.assertEqual(res_zero.overall_coverage_ratio, 0.0)


if __name__ == "__main__":
    unittest.main()
