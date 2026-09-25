#!/usr/bin/env python3
"""
Tests for Performance Bible Generator in audiobook_factory.dramaturgy.performance_bible
========================================================================================
Verifies projection from BookBible and Roster data into CharacterPerformanceProfiles,
delivery archetypes, emotional behaviors, speech quirks, and serialization.
"""

import json
import pytest
from pathlib import Path
from audiobook_factory.dramaturgy.performance_bible import PerformanceBibleGenerator
from audiobook_factory.dramaturgy.contracts import PerformanceBible, CharacterPerformanceProfile


def test_performance_bible_from_roster_dict(tmp_path):
    """Verifies synthesis of performance profiles from dictionary-style character roster."""
    roster_data = {
        "characters": {
            "Commander_Vance": {
                "display_name": "Commander Vance",
                "gender": "male",
                "sociolect_trait": "RUSTIC_WARRIOR",
            },
            "Lady_Aurelia": {
                "display_name": "Lady Aurelia",
                "gender": "female",
                "sociolect_trait": "CAUSTIC_ARISTOCRAT",
            },
            "Narrator": {
                "display_name": "Narrator",
            },
            "Foley": {
                "display_name": "Foley",
            },
        }
    }

    bible = PerformanceBibleGenerator.generate_bible_for_project(
        project_dir=tmp_path,
        roster_data=roster_data,
    )

    assert isinstance(bible, PerformanceBible)
    assert "Commander_Vance" in bible.characters
    assert "Lady_Aurelia" in bible.characters
    # Narrator and Foley should not be in characters dict, Narrator has its own narrator_style
    assert "Narrator" not in bible.characters
    assert "Foley" not in bible.characters

    vance = bible.characters["Commander_Vance"]
    assert isinstance(vance, CharacterPerformanceProfile)
    assert vance.baseline_pace == 0.96
    assert vance.articulation == "guttural_blunt"
    assert "bellowing_rage" in vance.emotional_behaviors.get("anger", "")
    assert len(vance.performance_rules) >= 1

    aurelia = bible.characters["Lady_Aurelia"]
    assert aurelia.baseline_pace == 1.04
    assert aurelia.articulation == "sharp_high_status"
    assert "cutting_condescension" in aurelia.emotional_behaviors.get("anger", "")


def test_performance_bible_from_roster_list(tmp_path):
    """Verifies synthesis of performance profiles from list-style character roster."""
    roster_data = {
        "characters": [
            {
                "english_name": "Silas",
                "sociolect_trait": "COLD_CYNIC",
            },
            {
                "english_name": "Milo",
                "sociolect_trait": "VULNERABLE_SCHOLAR",
            },
        ]
    }

    bible = PerformanceBibleGenerator.generate_bible_for_project(
        project_dir=tmp_path,
        roster_data=roster_data,
    )

    assert "Silas" in bible.characters
    assert "Milo" in bible.characters

    silas = bible.characters["Silas"]
    assert silas.restraint_level == 0.85
    assert "cold_menace" in silas.emotional_behaviors.get("anger", "")

    milo = bible.characters["Milo"]
    assert milo.baseline_energy == 0.65
    assert "hesitant" in milo.articulation


def test_performance_bible_narrator_style(tmp_path):
    """Verifies canonical narrator style defaults."""
    bible = PerformanceBibleGenerator.generate_bible_for_project(project_dir=tmp_path)
    assert bible.narrator_style is not None
    assert bible.narrator_style.get("baseline_pace") == 1.0
    assert "objective" in bible.narrator_style.get("tone", "")


def test_performance_bible_serialization(tmp_path):
    """Verifies clean roundtrip JSON serialization."""
    roster_data = {
        "characters": {
            "Master_Corvo": {
                "sociolect_trait": "COLD_CYNIC",
            }
        }
    }
    bible = PerformanceBibleGenerator.generate_bible_for_project(
        project_dir=tmp_path,
        roster_data=roster_data,
    )

    out_file = tmp_path / "performance_bible.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(bible.model_dump(), f, indent=2)

    assert out_file.exists()
    with open(out_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["version"] == "1.0"
    assert "Master_Corvo" in loaded["characters"]
    assert loaded["characters"]["Master_Corvo"]["baseline_pace"] == 0.92
