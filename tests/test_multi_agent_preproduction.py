#!/usr/bin/env python3
"""
Test Suite: Room 1 - Pre-Production World & Lore Ingestion Studio.
Verifies the 3-agent pre-production architecture:
1. DramatisPersonaeAgent: Character profiling & Devanagari casting.
2. SonicWorldArchitect: Acoustic spaces & signature foley palettes in sonic_bible.json.
3. PhoneticLexiconDramaturge: World terminology & locations in book_bible.json.
4. PreProductionSupervisor: Novel master locking & caching invariant.
"""

import unittest
from unittest.mock import MagicMock, patch
import tempfile
import json
from pathlib import Path

from audiobook_factory.preproduction import (
    DramatisPersonaeAgent,
    SonicWorldArchitect,
    PhoneticLexiconDramaturge,
    PreProductionSupervisor,
    run_preproduction,
)


class TestMultiAgentPreproduction(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

        # Write metadata.json
        meta = {
            "title": "Test Chronicles",
            "author": "Test Author",
            "project_slug": "test_chronicles",
        }
        with open(self.project_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(meta, f)

        # Create dummy chapter
        ext_dir = self.project_dir / "extracted"
        ext_dir.mkdir(parents=True, exist_ok=True)
        with open(ext_dir / "chapter_001.md", "w", encoding="utf-8") as f:
            f.write("Geralt of Rivia entered the dark tavern of Blaviken. The innkeeper stared in silence.")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dramatis_personae_agent(self):
        """Verifies DramatisPersonaeAgent extracts character profiles with sociolects and pronouns."""
        agent = DramatisPersonaeAgent(model="mock-model")

        mock_characters = [
            {
                "english_name": "Geralt",
                "hindi_name": "गेराल्ट",
                "gender": "male",
                "aliases": ["White Wolf", "Witcher"],
                "prominence": "lead",
                "vocal_archetype": "deep gravelly baritone",
                "sociolect_trait": "COLD_CYNIC",
                "recommended_pronoun_level": "tu",
                "speech_quirks": "dry laconic grunts",
            }
        ]
        mock_llm = MagicMock(return_value=mock_characters)

        chars = agent.extract_dramatis_personae(
            novel_text_sample="Geralt of Rivia walked into the inn.",
            book_metadata={"title": "Test Novel", "author": "Author"},
            call_llm_fn=mock_llm,
        )

        self.assertEqual(len(chars), 1)
        self.assertEqual(chars[0]["english_name"], "Geralt")
        self.assertEqual(chars[0]["hindi_name"], "गेराल्ट")
        self.assertEqual(chars[0]["sociolect_trait"], "COLD_CYNIC")

    def test_sonic_world_architect(self):
        """Verifies SonicWorldArchitect outputs acoustic spaces and foley palettes in sonic_bible.json."""
        architect = SonicWorldArchitect(model="mock-model")

        mock_sonic_data = {
            "project_id": "proj-test",
            "book_title": "Test Chronicles",
            "primary_era": "medieval_fantasy",
            "acoustic_spaces": {
                "tavern_hearth": {
                    "reverb_type": "medium_wooden_hall",
                    "wet_mix": 0.18,
                    "predelay_ms": 25,
                    "decay_time_s": 1.4,
                    "dominant_materials": ["wood", "stone", "pewter"],
                }
            },
            "signature_foley_palettes": {
                "swordsman": ["steel_blade_scrape", "leather_scabbard"]
            },
            "world_ambience_motifs": [],
        }
        mock_llm = MagicMock(return_value=mock_sonic_data)

        sonic_bible = architect.design_sonic_bible(
            novel_text_sample="In the tavern, hearth crackled.",
            book_metadata={"title": "Test Chronicles", "project_slug": "test"},
            call_llm_fn=mock_llm,
        )

        self.assertIn("acoustic_spaces", sonic_bible)
        self.assertIn("tavern_hearth", sonic_bible["acoustic_spaces"])
        self.assertEqual(sonic_bible["acoustic_spaces"]["tavern_hearth"]["decay_time_s"], 1.4)

    def test_phonetic_lexicon_dramaturge(self):
        """Verifies PhoneticLexiconDramaturge extracts locations and lore terms."""
        dramaturge = PhoneticLexiconDramaturge(model="mock-model")

        mock_lex = {
            "locations": {"Blaviken": "ब्लाविकेन"},
            "organizations": {"Brotherhood of Sorcerers": "जादूगरों का संघ"},
            "creatures": {"Striga": "स्ट्रिगा"},
            "objects": {"Silver Sword": "चांदी की तलवार"},
            "terminology": {"Aard Sign": "आर्ड चिन्ह"},
        }
        mock_llm = MagicMock(return_value=mock_lex)

        lex = dramaturge.extract_lexicon_and_phonetics(
            novel_text_sample="The Striga screamed in Blaviken.",
            book_metadata={"title": "Test Chronicles"},
            call_llm_fn=mock_llm,
        )

        self.assertEqual(lex["locations"]["Blaviken"], "ब्लाविकेन")
        self.assertEqual(lex["creatures"]["Striga"], "स्ट्रिगा")

    def test_preproduction_supervisor_master_locking(self):
        """Verifies PreProductionSupervisor produces locked artifacts and respects caching."""
        supervisor = PreProductionSupervisor(model="mock-model")

        mock_chars = [{"english_name": "Geralt", "hindi_name": "गेराल्ट", "gender": "male"}]
        mock_sonic = {
            "acoustic_spaces": {"indoor": {"reverb_type": "room", "wet_mix": 0.15}},
            "signature_foley_palettes": {},
        }
        mock_lex = {"locations": {"Blaviken": "ब्लाविकेन"}}

        mock_dna = {
            "literary_tradition": "DARK_FANTASY_GRIT",
            "source_fidelity_tier": "RAW_UNRATED",
            "regional_dialect_cadence": "Hindustani",
        }

        with patch.object(supervisor.book_dna_agent, "analyze_book_dna", return_value=mock_dna), \
             patch.object(supervisor.dramatis_personae_agent, "extract_dramatis_personae", return_value=mock_chars), \
             patch.object(supervisor.sonic_architect, "design_sonic_bible", return_value=mock_sonic), \
             patch.object(supervisor.lexicon_dramaturge, "extract_lexicon_and_phonetics", return_value=mock_lex):

            res = supervisor.execute_preproduction(project_dir=self.project_dir, force=True)

            self.assertEqual(res["status"], "MASTER_LOCKED")
            self.assertTrue((self.project_dir / "book_bible.json").exists())
            self.assertTrue((self.project_dir / "sonic_bible.json").exists())
            self.assertTrue((self.project_dir / "cast_lock.json").exists())

            # Second run without force should return CACHED_LOCKED immediately
            cached_res = supervisor.execute_preproduction(project_dir=self.project_dir, force=False)
            self.assertEqual(cached_res["status"], "CACHED_LOCKED")


if __name__ == "__main__":
    unittest.main()
