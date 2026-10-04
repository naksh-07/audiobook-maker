#!/usr/bin/env python3
"""
Test Suite: Room 2 - Multi-Agent Dramatic Translation Collective.
Verifies the 4-agent collaborative translation architecture:
1. LiteraryDraftTranslator: Sense-for-sense dramatic prose & scene modes.
2. HindustaniCadenceSpecialist: Spoken prosody, breath pauses & honorifics.
3. SubtextAndIdiomDramaturge: Earthy metaphors, rustic grit & 19-to-21 amplification.
4. TranslationQualityCritic: Canon verification, omission audit & reflection repair.
5. MultiAgentTranslationCollective: Full pipeline coordination & graceful fallbacks.
"""

import unittest
from unittest.mock import MagicMock, patch
import json

from audiobook_factory.translation.agents import (
    LiteraryDraftTranslator,
    HindustaniCadenceSpecialist,
    SubtextAndIdiomDramaturge,
    TranslationQualityCritic,
    MultiAgentTranslationCollective,
    get_translation_collective,
)
import audiobook_factory.translator as translator


class TestMultiAgentTranslation(unittest.TestCase):

    def setUp(self):
        self.sample_glossary = {
            "characters": [
                {
                    "english_name": "Geralt",
                    "hindi_name": "गेराल्ट",
                    "gender": "male",
                    "recommended_pronoun_level": "tu",
                    "hindustani_archetype": "COLD_CYNIC",
                    "speech_quirks": "dry laconic sarcasm",
                },
                {
                    "english_name": "Yennefer",
                    "hindi_name": "येनेफ़र",
                    "gender": "female",
                    "recommended_pronoun_level": "tum",
                    "hindustani_archetype": "CAUSTIC_ARISTOCRAT",
                },
            ],
            "relationships": [
                {"characters": ["Geralt", "Yennefer"], "level": "tum"},
            ],
            "locations_and_terms": {
                "Rivia": "रिविया",
                "Witcher": "विचर",
            },
            "general_tone": "dark fantasy, dramatic, contemporary Hindustani",
            "book_metadata": {
                "title": "Sword of Destiny",
                "author": "Andrzej Sapkowski",
            },
        }

    def test_draft_translator_scene_mode_routing(self):
        """Verifies scene mode detection properly triggers combat, intimacy, or dialogue directives."""
        draft_agent = LiteraryDraftTranslator(model="mock-model")

        # Combat text
        combat_mode = draft_agent._detect_scene_mode("He drew his blade with blood on the sword.", "Fight")
        self.assertIn("VISCERAL COMBAT", combat_mode)
        self.assertIn("STACCATO clauses", combat_mode)

        # Intimate text
        intimate_mode = draft_agent._detect_scene_mode("Her lips and gentle kiss on his skin.", "Night")
        self.assertIn("SOMATIC INTIMACY", intimate_mode)
        self.assertIn("MANTO STANDARD", intimate_mode)

        # Dialogue text
        dialogue_text = '"Who are you?" he said. "A traveler," she replied. "Prove it," he demanded.'
        dialogue_mode = draft_agent._detect_scene_mode(dialogue_text, "Tavern")
        self.assertIn("HIGH-STAKES DIALOGUE", dialogue_mode)
        self.assertIn("19-TO-21 AMPLIFICATION", dialogue_mode)

    def test_draft_translator_execution(self):
        """Verifies LiteraryDraftTranslator calls LLM and returns sanitized Devanagari text."""
        draft_agent = LiteraryDraftTranslator(model="mock-model")

        mock_hindi_response = "गेराल्ट ने अपनी तलवार खींची और आगे बढ़ा।"
        mock_llm = MagicMock(return_value=mock_hindi_response)

        res = draft_agent.translate_draft(
            text_block="Geralt drew his sword and stepped forward.",
            glossary=self.sample_glossary,
            block_title="Scene 1",
            call_llm_fn=mock_llm,
        )

        self.assertIn("गेराल्ट", res)
        self.assertIn("तलवार", res)
        self.assertTrue(mock_llm.called)

    def test_cadence_specialist_execution_and_fallback(self):
        """Verifies HindustaniCadenceSpecialist refines prosody and falls back gracefully if error occurs."""
        cadence_agent = HindustaniCadenceSpecialist(model="mock-model")

        draft = "गेराल्ट ने कहा, 'तुम यहां क्या कर रहे हो?'"
        mock_cadence_response = "गेराल्ट ने कहा—'तुम यहां क्या कर रहे हो...?'"
        mock_llm = MagicMock(return_value=mock_cadence_response)

        # Successful cadence pass
        refined = cadence_agent.refine_cadence(
            source_text="Geralt said, 'What are you doing here?'",
            draft_hindi=draft,
            glossary=self.sample_glossary,
            call_llm_fn=mock_llm,
        )
        self.assertIn("—", refined)
        self.assertIn("...", refined)

        # Error fallback
        mock_err_llm = MagicMock(side_effect=RuntimeError("API error"))
        fallback = cadence_agent.refine_cadence(
            source_text="Geralt said, 'What are you doing here?'",
            draft_hindi=draft,
            glossary=self.sample_glossary,
            call_llm_fn=mock_err_llm,
        )
        self.assertEqual(fallback, draft)

    def test_idiom_dramaturge_execution_and_fallback(self):
        """Verifies SubtextAndIdiomDramaturge enriches idioms and preserves text on error."""
        idiom_agent = SubtextAndIdiomDramaturge(model="mock-model")

        cadence_text = "उसने कहा, 'कमीने, पीछे हट जा।'"
        mock_enriched = "उसने गुर्राते हुए कहा, 'अबे ओ हरामी, पीछे हट जा, वरना यहीं गाड़ दूंगा!'"
        mock_llm = MagicMock(return_value=mock_enriched)

        enriched = idiom_agent.enrich_idioms_and_subtext(
            source_text="He said, 'Bastard, back off.'",
            cadence_hindi=cadence_text,
            glossary=self.sample_glossary,
            call_llm_fn=mock_llm,
        )
        self.assertIn("हरामी", enriched)

        # Fallback test
        mock_err_llm = MagicMock(side_effect=ValueError("Model choke"))
        fallback = idiom_agent.enrich_idioms_and_subtext(
            source_text="He said, 'Bastard, back off.'",
            cadence_hindi=cadence_text,
            glossary=self.sample_glossary,
            call_llm_fn=mock_err_llm,
        )
        self.assertEqual(fallback, cadence_text)

    def test_quality_critic_canon_replacement_and_certification(self):
        """Verifies TranslationQualityCritic replaces untranslated English character names with Devanagari."""
        critic = TranslationQualityCritic(model="mock-model")

        # Text with untranslated English name "Geralt"
        flawed_hindi = "Geralt ने कमरे में कदम रखा और चुपचाप खड़ा हो गया।"
        certified, report = critic.audit_and_certify(
            source_text="Geralt stepped into the room and stood silently.",
            hindi_text=flawed_hindi,
            glossary=self.sample_glossary,
            block_title="Scene 1",
        )

        # The critic must deterministically normalize "Geralt" -> "गेराल्ट"
        self.assertIn("गेराल्ट", certified)
        self.assertNotIn("Geralt", certified)
        self.assertEqual(report["status"], "CERTIFIED")

    def test_translation_collective_end_to_end(self):
        """Verifies the 4-agent collective runs in sequence and returns certified translation."""
        collective = MultiAgentTranslationCollective(model="mock-model")

        # Mock responses for each agent in sequence:
        # Pass 1 Draft -> Pass 2 Cadence -> Pass 3 Idiom -> Pass 4 (deterministic audit)
        mock_responses = [
            "गेराल्ट ने येनेफ़र को देखा।",  # Draft
            "गेराल्ट ने—येनेफ़र को देखा...",  # Cadence
            "गेराल्ट ने गहरी सांस लेकर—येनेफ़र को देखा...",  # Idiom
        ]
        call_count = 0

        def fake_llm(*args, **kwargs):
            nonlocal call_count
            resp = mock_responses[min(call_count, len(mock_responses) - 1)]
            call_count += 1
            return resp

        result = collective.translate_block(
            text_block="Geralt looked at Yennefer.",
            glossary=self.sample_glossary,
            block_title="Scene 1",
            call_llm_fn=fake_llm,
        )

        self.assertIn("गेराल्ट", result)
        self.assertIn("येनेफ़र", result)
        self.assertGreaterEqual(call_count, 3)

    def test_translator_single_block_integration(self):
        """Verifies translator._translate_single_block delegates to collective seamlessly."""
        mock_certified = "गेराल्ट ने शांत आवाज़ में कहा, 'यह अंत नहीं है।'"

        with patch.object(MultiAgentTranslationCollective, "translate_block", return_value=mock_certified) as mock_tb:
            res = translator._translate_single_block(
                text_block="Geralt said quietly, 'This is not the end.'",
                glossary=self.sample_glossary,
                block_title="Test Block",
                model="test-model",
            )
            self.assertEqual(res, mock_certified)
            mock_tb.assert_called_once()


if __name__ == "__main__":
    unittest.main()
