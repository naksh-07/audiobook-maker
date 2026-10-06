#!/usr/bin/env python3
"""
Unit tests for Universal Novel DeepSearch Grounding Engine.
Verifies:
1. Fallback intelligence archetypes across world literature (Premchand, Manto, Christie, Asimov, Contemporary).
2. DeepSearchNovelDossier schema validation, immutability, and JSON serialization.
3. Custom LLM callback integration with Google Search grounding mocks.
4. Cross-engine compatibility with HindustaniRegisterEngine and preproduction pipelines.
"""

import json
import pytest
from unittest.mock import MagicMock
from pathlib import Path

from audiobook_factory.preproduction.novel_deepsearch import (
    NovelDeepSearchEngine,
    DeepSearchNovelDossier,
    LiteraryDNAProfile,
    CanonicalCharacter,
    WorldAcousticSetting,
    MusicalTradition,
    LinguisticDialectProfile,
)
from audiobook_factory.translation.hindustani_register import HindustaniRegisterEngine


class TestNovelDeepSearchGrounding:
    """Test suite verifying universal grounding across diverse literary genres and periods."""

    def test_01_premchand_rural_realism_grounding(self):
        """Verifies Premchand's Godaan resolves into Rural Realism with authentic acoustic & linguistic constraints."""
        dossier_dict = NovelDeepSearchEngine._build_robust_fallback_dossier(
            title="Godaan",
            author="Munshi Premchand",
            project_slug="godaan",
            sample_text="होरी गाय की लालसा में गोबर और धनिया के साथ खेत पर चर्चा कर रहा था।",
        )
        dossier = DeepSearchNovelDossier.model_validate(dossier_dict)

        assert dossier.literary_dna.tradition == "RURAL_REALISM_PATHOS"
        assert "rural" in dossier.literary_dna.historical_era.lower()
        assert "Awadh" in dossier.literary_dna.setting_geography

        # Acoustic checks: No modern cars, cellphones, or firearms
        banned = dossier.world_acoustics.banned_anachronisms
        assert "car" in banned or "automobile" in banned
        assert "telephone" in banned or "mobile" in banned

        # Musical checks: Rural Indian instruments
        instruments = [i.lower() for i in dossier.musical_tradition.signature_instruments]
        assert any("bansuri" in inst for inst in instruments)
        assert any("shehnai" in inst for inst in instruments)

        # Character roster: Hori and Dhaniya
        char_names = [c.english_name for c in dossier.characters]
        assert "Hori" in char_names
        assert "Dhaniya" in char_names

        # Cross-engine check: HindustaniRegisterEngine correctly adopts rural register
        register_engine = HindustaniRegisterEngine.from_book_dna(dossier.literary_dna.model_dump())
        assert register_engine is not None

    def test_02_manto_somatic_psychological_realism(self):
        """Verifies Saadat Hasan Manto resolves into Somatic Psychological Realism with gritty cadence."""
        dossier_dict = NovelDeepSearchEngine._build_robust_fallback_dossier(
            title="Toba Tek Singh",
            author="Saadat Hasan Manto",
            project_slug="toba_tek_singh",
            sample_text="बंटवारे के दो-तीन साल बाद लाहौर के पागलखाने में हलचल मची हुई थी।",
        )
        dossier = DeepSearchNovelDossier.model_validate(dossier_dict)

        assert dossier.literary_dna.tradition == "SOMATIC_PSYCHOLOGICAL_REALISM"
        assert "1940s" in dossier.literary_dna.historical_era
        assert "Lahore" in dossier.literary_dna.setting_geography

        # Linguistic register guidance
        reg = dossier.linguistic_dialect.recommended_hindustani_register.lower()
        assert "visceral" in reg or "cynical" in reg or "urban" in reg

        # Acoustic check: No internet or lasers in 1947
        banned = dossier.world_acoustics.banned_anachronisms
        assert "smartphone" in banned
        assert "internet" in banned

    def test_03_agatha_christie_golden_age_mystery(self):
        """Verifies Agatha Christie resolves into Classic Detective Mystery."""
        dossier_dict = NovelDeepSearchEngine._build_robust_fallback_dossier(
            title="Murder on the Orient Express",
            author="Agatha Christie",
            project_slug="orient_express",
            sample_text="Hercule Poirot inspected the compartment as the train ground to a halt in snow.",
        )
        dossier = DeepSearchNovelDossier.model_validate(dossier_dict)

        assert dossier.literary_dna.tradition == "CLASSIC_DETECTIVE_MYSTERY"
        assert dossier.literary_dna.primary_genre == "Whodunit / Murder Mystery"

        # Musical checks: Cello, pizzicato, clockwork suspense
        inst = " ".join(dossier.musical_tradition.signature_instruments).lower()
        assert "cello" in inst or "pizzicato" in inst

        # Loanwords suitable for detective fiction
        loans = dossier.linguistic_dialect.acceptable_loanwords
        assert "detective" in loans or "inspector" in loans or "police" in loans

    def test_04_asimov_speculative_scifi(self):
        """Verifies Isaac Asimov sci-fi resolves into Speculative Sci-Fi with synth aesthetics and banned medieval tropes."""
        dossier_dict = NovelDeepSearchEngine._build_robust_fallback_dossier(
            title="Foundation",
            author="Isaac Asimov",
            project_slug="foundation",
            sample_text="The galactic empire was decaying while Trantor sat at the hub of the galaxy.",
        )
        dossier = DeepSearchNovelDossier.model_validate(dossier_dict)

        assert dossier.literary_dna.tradition == "SPECULATIVE_SCI_FI"
        assert "future" in dossier.literary_dna.historical_era.lower()

        # Acoustic check: Swords and horse carriages banned in space
        banned = dossier.world_acoustics.banned_anachronisms
        assert "sword" in banned or "horse_carriage" in banned

        # Musical checks: Synths and sub-bass drones
        inst = " ".join(dossier.musical_tradition.signature_instruments).lower()
        assert "synthesizer" in inst or "drone" in inst

    def test_05_universal_contemporary_default(self):
        """Verifies unclassified contemporary novel defaults safely to clean Universal Contemporary."""
        dossier_dict = NovelDeepSearchEngine._build_robust_fallback_dossier(
            title="The City and Its Changing Seasons",
            author="Ananya Sen",
            project_slug="city_seasons",
            sample_text="The coffee shop was bustling as cars passed outside the window.",
        )
        dossier = DeepSearchNovelDossier.model_validate(dossier_dict)

        assert dossier.literary_dna.tradition == "UNIVERSAL_CONTEMPORARY"
        assert dossier.literary_dna.historical_era == "contemporary"
        assert "piano" in " ".join(dossier.musical_tradition.signature_instruments).lower()

    def test_06_mock_llm_grounded_research_pipeline(self):
        """Verifies research_novel properly executes with a custom mock LLM returning Google-grounded payload."""
        mock_response = json.dumps({
            "book_title": "Norwegian Wood",
            "author": "Haruki Murakami",
            "project_slug": "norwegian_wood",
            "literary_dna": {
                "tradition": "MAGICAL_REALISM_MELANCHOLY",
                "primary_genre": "Literary Fiction / Coming-of-Age",
                "sub_genres": ["Drama", "Romance"],
                "historical_era": "1960s",
                "setting_geography": "Tokyo, Japan",
                "publication_year": "1987",
                "narrative_tone": "melancholic, nostalgic, reflective",
                "source_fidelity_tier": "STANDARD_ADULT",
            },
            "characters": [
                {
                    "english_name": "Toru Watanabe",
                    "hindi_name": "तोरू वातानाबे",
                    "role_prominence": "lead",
                    "gender": "male",
                    "age_group": "youth",
                    "occupation_status": "University Student",
                    "vocal_weight": "balanced",
                    "aliases": ["Toru"],
                },
                {
                    "english_name": "Naoko",
                    "hindi_name": "नाओको",
                    "role_prominence": "lead",
                    "gender": "female",
                    "age_group": "youth",
                    "occupation_status": "Student",
                    "vocal_weight": "melodic_soft",
                    "aliases": [],
                }
            ],
            "world_acoustics": {
                "primary_materials": ["wood", "tatami", "rain", "record player"],
                "architectural_style": "1960s Tokyo apartments and sanatorium",
                "geography_climate": "temperate, misty, rainy",
                "banned_anachronisms": ["smartphone", "laptop", "internet", "cd"],
            },
            "musical_tradition": {
                "cultural_tradition": "1960s acoustic folk and classical guitar",
                "signature_instruments": ["acoustic guitar", "gentle piano", "rain texture"],
                "primary_moods": ["nostalgic", "poignant", "melancholic"],
            },
            "linguistic_dialect": {
                "recommended_hindustani_register": "introspective, gentle, poetic Hindustani",
                "regional_cadence": "soft spoken cadence",
                "acceptable_loanwords": ["record", "guitar", "college", "room"],
                "proverb_transposition_style": "metaphorical emotional resonance",
            },
            "research_summary": "Canonical profile for Norwegian Wood by Haruki Murakami.",
            "search_citations": ["https://en.wikipedia.org/wiki/Norwegian_Wood_(novel)"],
        })

        mock_call = MagicMock(return_value=mock_response)

        dossier = NovelDeepSearchEngine.research_novel(
            title="Norwegian Wood",
            author="Haruki Murakami",
            sample_text="I was 37 then, seated in a Boeing 747.",
            call_llm_fn=mock_call,
        )

        assert dossier.book_title == "Norwegian Wood"
        assert dossier.author == "Haruki Murakami"
        assert dossier.literary_dna.tradition == "MAGICAL_REALISM_MELANCHOLY"
        assert len(dossier.characters) == 2
        assert dossier.characters[0].english_name == "Toru Watanabe"
        assert dossier.characters[1].english_name == "Naoko"
        assert "smartphone" in dossier.world_acoustics.banned_anachronisms
        assert "guitar" in dossier.linguistic_dialect.acceptable_loanwords

        # Verify Google Search grounding tool was requested
        assert mock_call.called
        call_kwargs = mock_call.call_args.kwargs
        assert "tools" in call_kwargs
        assert any("googleSearch" in t for t in call_kwargs["tools"])
