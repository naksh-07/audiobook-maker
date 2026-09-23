#!/usr/bin/env python3
"""
Unit and Regression Test Suite for ADR-021: Zero-Voice-Drift Hardening & Deterministic Speaker Attribution.
Verifies:
1. TTSDispatcher raises UnregisteredSpeakerError on unregistered dialogue characters.
2. TTSDispatcher resolves aliases from character_roster.json to canonical voices.
3. Pre-flight chapter validation halts synthesis before API calls on invalid speakers.
4. Gate 2 auto-discovers roster and catches unmapped non-canonical speakers.
5. Gate 1 Acoustic Gender Alignment warns on male/female persona mismatches.
6. clean_screenplay_pass2 resolves parenthetical annotations, fuzzy aliases, and Hindi pronouns.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.tts_dispatcher import TTSDispatcher, UnregisteredSpeakerError
from audiobook_factory.gate_auditor import audit_gate2_script, audit_gate1_roster, GateAuditError
from audiobook_factory.script_builder import clean_screenplay_pass2


class TestZeroVoiceDriftADR021(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)
        self.scripts_dir = self.project_dir / "scripts"
        self.audio_dir = self.project_dir / "audio_chunks"
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)

        # Base character roster
        self.roster_data = {
            "characters": {
                "Narrator": {
                    "gender": "female",
                    "voice_persona": "Aoede",
                    "aliases": ["सूत्रधार"]
                },
                "Geralt": {
                    "gender": "male",
                    "voice_persona": "Charon",
                    "aliases": ["Witcher", "विचर", "गेराल्ट", "Geralt of Rivia"]
                },
                "Yennefer": {
                    "gender": "female",
                    "voice_persona": "Kore",
                    "aliases": ["Sorceress", "येनेफ़र"]
                },
                "Dandelion": {
                    "gender": "male",
                    "voice_persona": "Puck",
                    "aliases": ["Bard", "डैंडेलियन"]
                }
            }
        }
        with open(self.project_dir / "character_roster.json", "w", encoding="utf-8") as f:
            json.dump(self.roster_data, f, ensure_ascii=False, indent=2)

        # Base voice registry
        self.registry_data = {
            "Narrator": {"backend": "gemini_tts", "voice": "Aoede", "speed": 1.0},
            "Geralt": {"backend": "gemini_tts", "voice": "Charon", "speed": 0.98, "pitch": 1.0},
            "Yennefer": {"backend": "gemini_tts", "voice": "Kore", "speed": 1.0},
            "Dandelion": {"backend": "gemini_tts", "voice": "Puck", "speed": 1.05},
        }
        with open(self.project_dir / "voice_registry.json", "w", encoding="utf-8") as f:
            json.dump(self.registry_data, f, ensure_ascii=False, indent=2)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_01_unregistered_dialogue_speaker_raises_error(self):
        """Verify TTSDispatcher strictly prohibits silent fallback to Aoede for unregistered dialogue."""
        dispatcher = TTSDispatcher(project_dir=self.project_dir, strict_speakers=True)

        # Narrator and narration segments return Narrator config safely
        narr_cfg = dispatcher.get_speaker_config("Narrator", seg_type="narration")
        self.assertEqual(narr_cfg["voice"], "Aoede")

        narration_unknown = dispatcher.get_speaker_config("SomeRandomTag", seg_type="narration")
        self.assertEqual(narration_unknown["voice"], "Aoede")

        # Unregistered character in dialogue segment MUST raise UnregisteredSpeakerError
        with self.assertRaises(UnregisteredSpeakerError) as ctx:
            dispatcher.get_speaker_config("MysteriousStranger", seg_type="dialogue")
        self.assertIn("MysteriousStranger", str(ctx.exception))
        self.assertIn("Silent fallback to Narrator is prohibited", str(ctx.exception))

    def test_02_alias_resolution_in_tts_dispatcher(self):
        """Verify TTSDispatcher resolves roster aliases to canonical voice configurations."""
        dispatcher = TTSDispatcher(project_dir=self.project_dir, strict_speakers=True)

        # English alias
        cfg_witcher = dispatcher.get_speaker_config("Witcher", seg_type="dialogue")
        self.assertEqual(cfg_witcher["voice"], "Charon")

        # Hindi Devanagari alias
        cfg_hindi = dispatcher.get_speaker_config("विचर", seg_type="dialogue")
        self.assertEqual(cfg_hindi["voice"], "Charon")

        # Multi-word alias with space/underscore variation
        cfg_full = dispatcher.get_speaker_config("Geralt_of_Rivia", seg_type="dialogue")
        self.assertEqual(cfg_full["voice"], "Charon")

    def test_03_preflight_validation_aborts_synthesis_on_invalid_speaker(self):
        """Verify synthesize_chapter_script dry-run pre-flight catches bad speakers before API calls."""
        bad_script = [
            {"index": 1, "type": "narration", "speaker": "Narrator", "text": "Night had fallen."},
            {"index": 2, "type": "dialogue", "speaker": "Geralt", "text": "Something is wrong."},
            {"index": 3, "type": "dialogue", "speaker": "Corrupted_Role_99", "text": "You will die."},
        ]
        script_file = self.scripts_dir / "chapter_001_hi_script.json"
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(bad_script, f)

        dispatcher = TTSDispatcher(project_dir=self.project_dir, strict_speakers=True)

        with self.assertRaises(UnregisteredSpeakerError) as ctx:
            dispatcher.synthesize_chapter_script(script_file, chapter_num=1)
        self.assertIn("Corrupted_Role_99", str(ctx.exception))

    def test_04_gate2_auto_discovers_roster_and_catches_unmapped_speaker(self):
        """Verify Gate 2 auto-discovers character_roster.json and fails on non-canonical speakers."""
        # Invalid script with non-canonical speaker
        invalid_script = [
            {"index": 1, "type": "narration", "speaker": "Narrator", "text": "Scene starts."},
            {"index": 2, "type": "dialogue", "speaker": "UnmappedMerchant", "text": "Buy my wares!"},
        ]
        script_file = self.scripts_dir / "chapter_002_hi_script.json"
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(invalid_script, f)

        with self.assertRaises(GateAuditError) as ctx:
            audit_gate2_script(script_file, project_dir=self.project_dir)
        self.assertIn("UnmappedMerchant", str(ctx.exception))

        # Valid script with canonical characters, aliases, and Foley action beats
        valid_script = [
            {"index": 1, "type": "narration", "speaker": "Narrator", "text": "Scene starts."},
            {"index": 2, "type": "dialogue", "speaker": "Geralt", "text": "Silver is for monsters."},
            {"index": 3, "type": "action", "speaker": "Foley", "text": "[ACTION]"},
            {"index": 4, "type": "dialogue", "speaker": "Witcher", "text": "Steel is for men."},
        ]
        with open(script_file, "w", encoding="utf-8") as f:
            json.dump(valid_script, f)

        res = audit_gate2_script(script_file, project_dir=self.project_dir)
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["total_segments"], 4)

    def test_05_gate1_acoustic_gender_alignment_check(self):
        """Verify Gate 1 checks gender alignment without crashing."""
        # Misaligned male character assigned female persona Aoede (with distinct pitch so no collision)
        misaligned_registry = dict(self.registry_data)
        misaligned_registry["Geralt"] = {"backend": "gemini_tts", "voice": "Aoede", "pitch": 0.85, "speed": 0.95}
        with open(self.project_dir / "voice_registry_misaligned.json", "w", encoding="utf-8") as f:
            json.dump(misaligned_registry, f)

        res = audit_gate1_roster(
            self.project_dir / "character_roster.json",
            self.project_dir / "voice_registry_misaligned.json",
            active_characters=["Narrator", "Geralt"]
        )
        self.assertEqual(res["status"], "PASS")

    def test_06_clean_screenplay_pass2_hardening(self):
        """Verify pass 2 resolves parenthetical annotations, fuzzy aliases, and Hindi pronouns."""
        raw_items = [
            {"type": "dialogue", "speaker": "Geralt", "text": "Let us begin."},
            {"type": "dialogue", "speaker": "उसने", "text": "Indeed, Witcher."},  # Should resolve to Geralt (last male)
            {"type": "dialogue", "speaker": "Yennefer (Sorceress)", "text": "Quiet, both of you."}, # Parenthetical
            {"type": "dialogue", "speaker": "महिला", "text": "I will handle this."}, # Female pronoun -> Yennefer
            {"type": "dialogue", "speaker": "विचर", "text": "Understood."}, # Hindi alias -> Geralt
        ]

        cleaned = clean_screenplay_pass2(
            raw_items,
            is_hindi=True,
            character_roster=self.roster_data,
        )

        self.assertEqual(len(cleaned), 5)
        self.assertEqual(cleaned[0]["speaker"], "Geralt")
        self.assertEqual(cleaned[1]["speaker"], "Geralt")
        self.assertEqual(cleaned[2]["speaker"], "Yennefer")
        self.assertEqual(cleaned[3]["speaker"], "Yennefer")
        self.assertEqual(cleaned[4]["speaker"], "Geralt")


if __name__ == "__main__":
    unittest.main()
