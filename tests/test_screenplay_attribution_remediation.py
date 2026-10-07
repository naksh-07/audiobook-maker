#!/usr/bin/env python3
"""
Test Suite for Issue 2 Remediation: Screenplay Dialogue Attribution,
Split-Quote Unification, and Article-Stripped Alias Matching.
===================================================================
Verifies:
1. Deterministic Split-Quote Unification (Audible Flow Standard):
   - Merging character split thoughts around short author tags (< 35 words).
   - Pre-positioning narrative lead-in with em-dash ('—').
   - Preserving long narration (> 35 words) without merging.
2. Anti-Theft Protection:
   - Unknown/stranger lines are NEVER stolen by the preceding character speaker.
3. Bidirectional Article-Stripped Alias Resolution:
   - 'the stranger' <-> 'stranger' resolution against character roster.
4. Residual Speech Tag Scrubbing:
   - Hindi and English author dialogue tags cleanly scrubbed from spoken text.
5. Zero Hardcoding Invariants:
   - All script modules remain 100% novel-agnostic and franchise-neutral.
"""

import ast
import re
import unittest
from pathlib import Path
from typing import List, Dict, Any

from audiobook_factory.script.screenplay_cleaner import (
    clean_screenplay_pass2,
    stitch_split_dialogue_turns,
)
from audiobook_factory.script.agents.dialogue_attribution_auditor import (
    DialogueAttributionAuditor,
)


class TestScreenplayAttributionRemediation(unittest.TestCase):
    """Test suite validating all architectural fixes for Issue 2."""

    def test_01_split_quote_stitching_unification(self):
        """Validates that split quotes around narration tags are cleanly unified."""
        raw_segments = [
            {
                "index": 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": "The wind howled outside the tavern.",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Inquirer",
                "text": "Who are you,",
            },
            {
                "index": 3,
                "type": "narration",
                "speaker": "Narrator",
                "text": "asked the scarred traveler coldly,",
            },
            {
                "index": 4,
                "type": "dialogue",
                "speaker": "Inquirer",
                "text": "to question my presence here?",
            },
            {
                "index": 5,
                "type": "dialogue",
                "speaker": "Bystander",
                "text": "I am nobody, sir.",
            },
        ]

        stitched = stitch_split_dialogue_turns(raw_segments)

        # Expect 4 segments instead of 5:
        # 1. Narrator (intro)
        # 2. Narrator (lead-in with em-dash)
        # 3. Inquirer (unified dialogue)
        # 4. Bystander
        self.assertEqual(len(stitched), 4)

        # Check sequential 1-based indexing
        for idx, seg in enumerate(stitched, 1):
            self.assertEqual(seg["index"], idx)

        # Check Narrator lead-in
        self.assertEqual(stitched[1]["type"], "narration")
        self.assertEqual(stitched[1]["speaker"], "Narrator")
        self.assertTrue(stitched[1]["text"].endswith("—"), f"Lead-in should end with '—', got: {stitched[1]['text']}")
        self.assertIn("scarred traveler", stitched[1]["text"])

        # Check unified dialogue
        self.assertEqual(stitched[2]["type"], "dialogue")
        self.assertEqual(stitched[2]["speaker"], "Inquirer")
        self.assertEqual(stitched[2]["text"], "Who are you, to question my presence here?")

        # Check Bystander unchanged
        self.assertEqual(stitched[3]["speaker"], "Bystander")
        self.assertEqual(stitched[3]["text"], "I am nobody, sir.")

    def test_02_long_narration_not_merged(self):
        """Verifies that long descriptive narration (> 35 words) between same-speaker turns is NOT merged."""
        long_prose = " ".join(["word"] * 40)
        segments = [
            {"index": 1, "type": "dialogue", "speaker": "Speaker A", "text": "First thought."},
            {"index": 2, "type": "narration", "speaker": "Narrator", "text": long_prose},
            {"index": 3, "type": "dialogue", "speaker": "Speaker A", "text": "Second thought."},
        ]

        stitched = stitch_split_dialogue_turns(segments)
        self.assertEqual(len(stitched), 3, "Long narration should not be compressed into a tag lead-in")

    def test_03_different_speakers_not_merged(self):
        """Verifies that dialogue between DIFFERENT speakers is never merged."""
        segments = [
            {"index": 1, "type": "dialogue", "speaker": "Speaker A", "text": "Hello?"},
            {"index": 2, "type": "narration", "speaker": "Narrator", "text": "he waited."},
            {"index": 3, "type": "dialogue", "speaker": "Speaker B", "text": "Who is there?"},
        ]

        stitched = stitch_split_dialogue_turns(segments)
        self.assertEqual(len(stitched), 3)
        self.assertEqual(stitched[0]["speaker"], "Speaker A")
        self.assertEqual(stitched[2]["speaker"], "Speaker B")

    def test_04_stranger_lines_not_stolen_by_preceding_speaker(self):
        """
        Anti-Theft Test:
        Asserts that a 'stranger' or 'someone' speaking immediately after Character A
        is NOT overwritten with Character A.
        """
        raw_items = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Local Merchant",
                "text": "Leave this place at once!",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Stranger",
                "text": "I will leave when I choose.",
            },
        ]

        roster = {
            "characters": {
                "Local Merchant": {"gender": "male", "aliases": ["merchant"]},
                "Wandering Noble": {"gender": "male", "aliases": ["the stranger", "noble stranger"]},
            }
        }

        cleaned = clean_screenplay_pass2(raw_items, character_roster=roster)
        self.assertEqual(len(cleaned), 2)
        # Merchant must remain Merchant
        self.assertEqual(cleaned[0]["speaker"], "Local Merchant")
        # Stranger must resolve to Wandering Noble via alias, NOT be stolen by Local Merchant!
        self.assertEqual(cleaned[1]["speaker"], "Wandering Noble")
        self.assertNotEqual(cleaned[1]["speaker"], "Local Merchant")

    def test_05_bidirectional_article_alias_lookup(self):
        """Verifies bidirectional article-stripped and article-prefixed alias resolution."""
        roster = {
            "characters": {
                "Sir Galahad": {"gender": "male", "aliases": ["The Knight", "Gallant Rider"]},
                "Lady Guinevere": {"gender": "female", "aliases": ["Queen"]},
            }
        }

        auditor = DialogueAttributionAuditor()
        alias_map, _ = auditor._extract_roster_metadata(roster)

        # "The Knight" -> "knight" should resolve to "Sir Galahad"
        self.assertEqual(alias_map.get("knight"), "Sir Galahad")
        self.assertEqual(alias_map.get("the knight"), "Sir Galahad")
        self.assertEqual(alias_map.get("a knight"), "Sir Galahad")

        # "Queen" -> "the queen" should resolve to "Lady Guinevere"
        self.assertEqual(alias_map.get("queen"), "Lady Guinevere")
        self.assertEqual(alias_map.get("the queen"), "Lady Guinevere")

    def test_06_residual_speech_tag_scrubbing(self):
        """Verifies that authorial speech tags are cleanly removed from spoken lines."""
        # Hindi speech tags
        h_text_1 = "उसने कहा, मुझे तुम्हारी मदद की ज़रूरत नहीं है।"
        cleaned_1, modified_1 = DialogueAttributionAuditor._scrub_residual_speech_tags(h_text_1, is_hindi=True)
        self.assertTrue(modified_1)
        self.assertEqual(cleaned_1, "मुझे तुम्हारी मदद की ज़रूरत नहीं है।")

        h_text_2 = "चेचक के दागदार चेहरे वाले ने पूछा: तुम कौन हो?"
        cleaned_2, modified_2 = DialogueAttributionAuditor._scrub_residual_speech_tags(h_text_2, is_hindi=True)
        self.assertTrue(modified_2)
        self.assertEqual(cleaned_2, "तुम कौन हो?")

        # Spoken text ending with trailing tag
        h_text_3 = "यहाँ से चले जाओ, उसने गुर्राया।"
        cleaned_3, modified_3 = DialogueAttributionAuditor._scrub_residual_speech_tags(h_text_3, is_hindi=True)
        self.assertTrue(modified_3)
        self.assertEqual(cleaned_3, "यहाँ से चले जाओ")

        # English speech tags
        e_text_1 = 'The stranger said, "I have no quarrel with you."'
        cleaned_e1, modified_e1 = DialogueAttributionAuditor._scrub_residual_speech_tags(e_text_1, is_hindi=False)
        self.assertTrue(modified_e1)
        self.assertEqual(cleaned_e1, "I have no quarrel with you.")

        # Preserving vocal delivery tags
        tag_text = "[whispers] उसने कहा, खामोश रहो।"
        cleaned_tag, _ = DialogueAttributionAuditor._scrub_residual_speech_tags(tag_text, is_hindi=True)
        self.assertTrue(cleaned_tag.startswith("[whispers]"))
        self.assertIn("खामोश रहो।", cleaned_tag)
        self.assertNotIn("उसने कहा", cleaned_tag)

    def test_07_auditor_end_to_end_with_mock_llm(self):
        """Verifies DialogueAttributionAuditor with injected mock LLM callback."""
        turns = [
            {"index": 1, "type": "narration", "speaker": "Narrator", "text": "Two men stood face to face."},
            {"index": 2, "type": "dialogue", "speaker": "The Stranger", "text": 'उसने कहा, "हथियार नीचे रखो।"'},
            {"index": 3, "type": "dialogue", "speaker": "The Stranger", "text": '"वरना अंजाम बुरा होगा।"'},
        ]
        roster = {
            "characters": {
                "Lord Reginald": {"gender": "male", "aliases": ["The Stranger"]},
            }
        }

        # Mock LLM returning certified turns
        def mock_llm_fn(**kwargs):
            return [
                {"index": 1, "type": "narration", "speaker": "Narrator", "text": "Two men stood face to face."},
                {"index": 2, "type": "dialogue", "speaker": "Lord Reginald", "text": "हथियार नीचे रखो।"},
                {"index": 3, "type": "dialogue", "speaker": "Lord Reginald", "text": "वरना अंजाम बुरा होगा।"},
            ]

        auditor = DialogueAttributionAuditor()
        audited_turns, report = auditor.audit_and_correct(
            turns=turns,
            chunk_text="Source chunk...",
            is_hindi=True,
            character_roster=roster,
            call_llm_fn=mock_llm_fn,
        )

        self.assertEqual(report["status"], "AUDITED_AND_CERTIFIED")
        self.assertEqual(len(audited_turns), 3)
        self.assertEqual(audited_turns[1]["speaker"], "Lord Reginald")
        self.assertNotIn("उसने कहा", audited_turns[1]["text"])

    def test_08_zero_hardcoding_in_script_modules(self):
        """Scans all script modules to ensure zero novel titles or character tokens exist."""
        script_dir = Path(__file__).resolve().parent.parent / "audiobook_factory" / "script"
        py_files = list(script_dir.glob("**/*.py"))
        self.assertGreater(len(py_files), 3)

        forbidden_tokens = {"geralt", "dandelion", "borch", "three jackdaws", "sword of destiny"}
        violations = []

        for pf in py_files:
            tree = ast.parse(pf.read_text(encoding="utf-8"), filename=str(pf))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    val_lower = node.value.lower()
                    for tok in forbidden_tokens:
                        # Check as whole word token
                        words = set(re.findall(r"\b[a-z0-9_-]+\b", val_lower))
                        if tok in words:
                            violations.append(f"{pf.name}:{node.lineno} contains '{tok}'")

        self.assertEqual(
            len(violations),
            0,
            f"Found forbidden hardcoded tokens in script modules: {violations}",
        )


if __name__ == "__main__":
    unittest.main()
