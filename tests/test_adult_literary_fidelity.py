#!/usr/bin/env python3
"""
Test Suite: Adult Literary Fidelity & HBO-Grade Intimacy Standardization.
Verifies the 11 locked Gangs of Wasseypur / Manto fidelity pillars,
the 70/30 Anti-Parody Invariant, ASMR intimacy staging, and 100% profanity retention.
"""

import unittest
import os
import inspect
from pathlib import Path

from audiobook_factory.contracts import ProjectConfig, CharacterProfile, ScreenplaySegment, ActingInstructions, SpatialCoordinates, SegmentMusicParams
from audiobook_factory.sanitizer import (
    validate_and_sanitize_translation,
    sanitize_screenplay_segment,
    COMPILED_TTS_TAG_RE,
)
from audiobook_factory.script_builder import normalize_speech_text, clean_screenplay_pass2
import audiobook_factory.translator as translator


class TestAdultLiteraryFidelity(unittest.TestCase):

    def test_project_config_adult_literary_mode_default(self):
        """Verifies that ProjectConfig defaults adult_literary_mode to True."""
        cfg = ProjectConfig(
            project_id="test_witcher",
            title="The Last Wish",
            author="Andrzej Sapkowski",
            source_language="en",
            assets_dir="audiobooks/test_witcher",
        )
        self.assertTrue(cfg.adult_literary_mode)

    def test_character_profile_sociolect_trait(self):
        """Verifies CharacterProfile supports Desi sociolect traits without breaking schema."""
        profile = CharacterProfile(
            character_uuid="char-geralt-001",
            display_name="Geralt",
            gender="male",
            assigned_voice_id="Charon",
            sociolect_trait="COLD_CYNIC",
        )
        self.assertEqual(profile.sociolect_trait, "COLD_CYNIC")

        # Fallback profile without sociolect
        profile_vanilla = CharacterProfile(
            character_uuid="char-dandelion-002",
            display_name="Dandelion",
            gender="male",
            assigned_voice_id="Puck",
        )
        self.assertIsNone(profile_vanilla.sociolect_trait)

    def test_sanitizer_raw_adult_profanity_and_intimacy_retention(self):
        """
        Verifies that sanitizer.py NEVER strips, drops, or bowdlerizes raw Hindustani cuss words
        and somatic intimacy vocabulary. 100% retention guarantee.
        """
        sample_passages = [
            "पीछे हट, रंडी के पिल्ले! अगर एक कदम और बढ़ाया तो तेरी गांड में इतनी तलवारें घोंपेंगे कि बैठना भूल जाएगा।",
            "उसने बकचोदी बंद की और लंड के टोपे को ज़मीन पर पटक दिया। मादरचोद वहीं तड़पने लगा।",
            "कमरे में उसकी तपती कमर और बेकाबू सांसों की महक थी... कांपती उंगलियां उसकी पीठ पर धंस गईं।",
            "[spits] थू! सूअर का पेशाब पी के आया है क्या भोसड़ीके? निकल यहां से!",
            "[growl] हूँ... काम बोलो और सिक्के दिखाओ, फ़ालतू का प्रपंच नहीं।",
            "[whispers] (मन में: साला खुद तो महलों में मलाई चाप रहा है...)",
            "[intimate, breathy] रुकना मत... मेरी जान... और पास आओ...",
        ]

        for text in sample_passages:
            is_valid, cleaned, reason = validate_and_sanitize_translation(text, is_hindi=True)
            self.assertTrue(is_valid, f"Sanitizer rejected valid raw adult text: '{text}' (Reason: {reason})")
            # Verify explicit core words survived untouched
            for core_word in ["रंडी", "गांड", "बकचोदी", "मादरचोद", "तपती कमर", "भोसड़ीके", "हूँ", "मन में", "मेरी जान"]:
                if core_word in text:
                    self.assertIn(core_word, cleaned)

    def test_screenplay_intimacy_asmr_staging(self):
        """Verifies that ScreenplaySegment correctly captures ASMR proximity, deep ducking, and breath pre-roll."""
        raw_items = [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Yennefer",
                "text": "[whispers] ठहरो... तुम्हारे हाथ... बर्फ़ की तरह ठंडे हैं गेराल्ट...",
                "emotion": "whispering",
                "pause_after_ms": 700,
                "acting": {"delivery_style": "whispering_fear", "pacing": 0.88},
                "spatial": {"pan": 0.0, "proximity": "intimate_close"},
                "acoustic_env": "quiet_chamber",
                "intensity_level": "low",
                "pre_roll_breath_ms": 250,
                "music": {"mood": "mysterious", "ducking_db": -22.0},
            }
        ]

        cleaned = clean_screenplay_pass2(raw_items, is_hindi=True)
        self.assertEqual(len(cleaned), 1)
        seg = cleaned[0]

        self.assertEqual(seg["speaker"], "Yennefer")
        self.assertIn("[whispers]", seg["text"])
        self.assertEqual(seg["spatial"]["proximity"], "intimate_close")
        self.assertEqual(seg["spatial"]["pan"], 0.0)
        self.assertEqual(seg["pre_roll_breath_ms"], 250)
        self.assertEqual(seg["intensity_level"], "low")
        self.assertEqual(seg["music"]["ducking_db"], -22.0)

    def test_translator_system_prompt_has_70_30_and_manto_mandate(self):
        """Verifies that translator.py incorporates the Anti-Bowdlerization and 70/30 Anti-Parody Invariant."""
        func_source = inspect.getsource(translator._translate_single_block)
        self.assertIn("LITERARY ANTI-BOWDLERIZATION MANDATE", func_source)
        self.assertIn("70/30 ANTI-PARODY INVARIANT", func_source)
        self.assertIn("Anurag Kashyap", func_source)
        self.assertIn("Saadat Hasan Manto", func_source)
        self.assertIn("गांड", func_source)
        self.assertIn("चूतड़", func_source)
        self.assertIn("19-TO-21 AMPLIFICATION", func_source)
        self.assertIn("TU <-> MAAI-BAAP", func_source)
        self.assertIn("SOMATIC INTIMACY", func_source)
        self.assertIn("NOTHING ABOVE SOURCE", func_source)

    def test_normalize_speech_text_preserves_adult_slang_and_prosody(self):
        """Verifies that normalize_speech_text preserves Hindi cuss words, slurs, and dramatic ellipses."""
        text = "रुक, भोसड़ीके... एक कदम और मत बढ़ाना—समझा?!"
        normalized = normalize_speech_text(text, is_hindi=True)
        self.assertIn("भोसड़ीके", normalized)
        self.assertIn("...", normalized)

    def test_tts_dispatcher_safety_settings_block_none(self):
        """Verifies that tts_dispatcher passes BLOCK_NONE across all 4 harm categories to prevent false-positive censorship."""
        import audiobook_factory.tts_dispatcher as tts_dispatcher
        func_source = inspect.getsource(tts_dispatcher.synthesize_gemini_tts)
        self.assertIn('"safetySettings"', func_source)
        self.assertIn('"HARM_CATEGORY_HARASSMENT"', func_source)
        self.assertIn('"HARM_CATEGORY_HATE_SPEECH"', func_source)
        self.assertIn('"HARM_CATEGORY_SEXUALLY_EXPLICIT"', func_source)
        self.assertIn('"HARM_CATEGORY_DANGEROUS_CONTENT"', func_source)
        self.assertIn('"BLOCK_NONE"', func_source)


if __name__ == "__main__":
    unittest.main()

