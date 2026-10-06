#!/usr/bin/env python3
"""
Test Suite: Room 3 Agent 1.5 - Dialogue Attribution Auditor.
Verifies forensic dialogue attribution, speaker anti-swap audit,
deterministic residual speech tag scrubbing, alias resolution, and fallback safety.
"""

import unittest
from unittest.mock import MagicMock, patch

from audiobook_factory.script.agents.dialogue_attribution_auditor import DialogueAttributionAuditor
from audiobook_factory.script.dialogue_parser import parse_and_audit_dialogue_turns


class TestDialogueAttributionAuditor(unittest.TestCase):

    def setUp(self):
        self.auditor = DialogueAttributionAuditor(model="mock-auditor-model")
        self.sample_roster = {
            "characters": {
                "Geralt": {
                    "gender": "male",
                    "aliases": ["White Wolf", "Witcher", "Geralt of Rivia", "गेराल्ट"],
                },
                "Yennefer": {
                    "gender": "female",
                    "aliases": ["Sorceress", "Yen", "यूनिफ़र"],
                },
                "Dandelion": {
                    "gender": "male",
                    "aliases": ["Jaskier", "Bard", "डैंडेलियन"],
                },
            }
        }

    def test_strip_residual_speech_tags_hindi(self):
        """Verifies deterministic scrubbing of Hindi speech tags while preserving vocal tags."""
        cases = [
            # Leading tag
            ("उसने कहा, मुझे तुमसे बात करनी है।", "मुझे तुमसे बात करनी है।"),
            ("वह बोली: यहाँ कोई नहीं है।", "यहाँ कोई नहीं है।"),
            ("उसने फुसफुसाकर कहा, धीरे बोलो।", "धीरे बोलो।"),
            # Trailing tag
            ("मैं कल आऊँगा, उसने कहा।", "मैं कल आऊँगा"),
            ("तुम कौन हो? उसने पूछा।", "तुम कौन हो?"),
            # With bracketed vocal tag preserved
            ("[whispers] उसने फुसफुसाया, छिप जाओ।", "[whispers] छिप जाओ।"),
            ("[combat strain] उसने चिल्लाकर कहा, वार रोको!", "[combat strain] वार रोको!"),
        ]

        for input_text, expected in cases:
            cleaned, modified = self.auditor._scrub_residual_speech_tags(input_text, is_hindi=True)
            self.assertTrue(modified, f"Expected modification for: {input_text}")
            self.assertEqual(cleaned, expected)

    def test_strip_residual_speech_tags_english(self):
        """Verifies deterministic scrubbing of English speech tags."""
        cases = [
            ("he said, We have to leave immediately.", "We have to leave immediately."),
            ("she replied: There is no time.", "There is no time."),
            ("I cannot go on, he muttered.", "I cannot go on"),
            ("[whispers] he whispered, Be quiet.", "[whispers] Be quiet."),
        ]

        for input_text, expected in cases:
            cleaned, modified = self.auditor._scrub_residual_speech_tags(input_text, is_hindi=False)
            self.assertTrue(modified, f"Expected modification for: {input_text}")
            self.assertEqual(cleaned, expected)

    def test_speaker_inversion_correction(self):
        """Verifies detection and correction of speaker turn inversions (A <-> B flips)."""
        source_prose = (
            'Geralt drew his silver blade. "Step back, Yennefer," he warned. '
            '"I am not the one who needs protection," Yennefer snapped coldly.'
        )

        # Flawed input where turns were inverted
        inverted_turns = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Yennefer",  # FLIPPED: Actually Geralt
                "text": "Step back, Yennefer,",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Geralt",  # FLIPPED: Actually Yennefer
                "text": "I am not the one who needs protection,",
            },
        ]

        # Mock LLM Auditor returning corrected attribution
        mock_llm_corrections = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Geralt",
                "text": "Step back, Yennefer.",
                "correction_made": "Corrected speaker inversion from Yennefer to Geralt based on prose context",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Yennefer",
                "text": "I am not the one who needs protection.",
                "correction_made": "Corrected speaker inversion from Geralt to Yennefer based on prose context",
            },
        ]
        mock_llm = MagicMock(return_value=mock_llm_corrections)

        audited, report = self.auditor.audit_and_correct(
            turns=inverted_turns,
            chunk_text=source_prose,
            character_roster=self.sample_roster,
            call_llm_fn=mock_llm,
        )

        self.assertEqual(audited[0]["speaker"], "Geralt")
        self.assertEqual(audited[1]["speaker"], "Yennefer")
        self.assertEqual(report["inversions_fixed"], 2)
        self.assertEqual(report["status"], "AUDITED_AND_CERTIFIED")

    def test_misattribution_to_narrator_and_pronouns_fixed(self):
        """Verifies that dialogue mistakenly attributed to Narrator or pronouns is corrected."""
        source_prose = 'Dandelion strummed his lute. "Listen to this tale!" he cried.'

        flawed_turns = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Narrator",  # Flawed: Spoken dialogue attributed to Narrator
                "text": "Listen to this tale!",
            }
        ]

        mock_llm_corrections = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Dandelion",
                "text": "Listen to this tale!",
                "correction_made": "Re-attributed spoken quote from Narrator to Dandelion",
            }
        ]
        mock_llm = MagicMock(return_value=mock_llm_corrections)

        audited, report = self.auditor.audit_and_correct(
            turns=flawed_turns,
            chunk_text=source_prose,
            character_roster=self.sample_roster,
            call_llm_fn=mock_llm,
        )

        self.assertEqual(audited[0]["speaker"], "Dandelion")
        self.assertEqual(report["misattributions_fixed"], 1)

    def test_canonical_alias_resolution(self):
        """Verifies deterministic alias resolution to canonical roster name."""
        turns = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "White Wolf",  # Alias for Geralt
                "text": "I will handle this.",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "यूनिफ़र",  # Hindi alias for Yennefer
                "text": "सावधान रहना।",
            },
        ]

        # No LLM corrections; relying on deterministic alias mapping
        audited, _ = self.auditor.audit_and_correct(
            turns=turns,
            chunk_text="Dialogue chunk",
            is_hindi=True,
            character_roster=self.sample_roster,
            call_llm_fn=lambda **kw: [],
        )

        self.assertEqual(audited[0]["speaker"], "Geralt")
        self.assertEqual(audited[1]["speaker"], "Yennefer")

    def test_universal_novel_agnostic_premchand(self):
        """Verifies auditor works seamlessly on classic literature (Premchand) with zero hardcoding."""
        premchand_roster = {
            "characters": {
                "Hori": {"gender": "male", "aliases": ["होरी", "महतो"]},
                "Dhania": {"gender": "female", "aliases": ["धनिया"]},
            }
        }
        source_prose = 'होरी ने सिर झुकाकर कहा, "भगवान की यही मर्जी है।" धनिया बिगड़कर बोली, "भगवान का नाम लेकर क्यों डरते हो?"'

        candidate_turns = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "होरी",
                "text": "होरी ने सिर झुकाकर कहा, भगवान की यही मर्जी है।",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "धनिया",
                "text": "धनिया बिगड़कर बोली, भगवान का नाम लेकर क्यों डरते हो?",
            },
        ]

        # Auditor without LLM (pure deterministic fallback)
        audited, report = self.auditor.audit_and_correct(
            turns=candidate_turns,
            chunk_text=source_prose,
            is_hindi=True,
            character_roster=premchand_roster,
            call_llm_fn=lambda **kw: [],
        )

        # Speakers resolved to canonical English names
        self.assertEqual(audited[0]["speaker"], "Hori")
        self.assertEqual(audited[1]["speaker"], "Dhania")
        # Tags stripped
        self.assertNotIn("कहा", audited[0]["text"])
        self.assertNotIn("बोली", audited[1]["text"])
        self.assertEqual(report["tags_stripped"], 2)

    def test_graceful_fallback_when_llm_fails(self):
        """Verifies auditor falls back safely to deterministic rules when LLM raises an error."""
        turns = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Witcher",
                "text": "he said, The path is clear.",
            }
        ]

        def crashing_llm(**kw):
            raise RuntimeError("API timeout")

        audited, report = self.auditor.audit_and_correct(
            turns=turns,
            chunk_text="The path is clear.",
            character_roster=self.sample_roster,
            call_llm_fn=crashing_llm,
        )

        self.assertEqual(len(audited), 1)
        self.assertEqual(audited[0]["speaker"], "Geralt")
        self.assertEqual(audited[0]["text"], "The path is clear.")
        self.assertEqual(report["tags_stripped"], 1)


if __name__ == "__main__":
    unittest.main()
