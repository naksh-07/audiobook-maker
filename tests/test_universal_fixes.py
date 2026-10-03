#!/usr/bin/env python3
"""
Test Suite: Universal Architecture & Permanent De-Biasing Verification.
"""

import pytest
from pathlib import Path
from audiobook_factory.project_classifier import ProjectClassifier, ProjectClassification
from audiobook_factory.sound_design.environment_profiles import get_environment_registry
from audiobook_factory.sound_bank import get_sound_bank
from audiobook_factory.sonic_bible_generator import SonicBibleGenerator
from audiobook_factory.safety import get_universal_safety_settings, get_dramatic_fiction_framing


def test_universal_safety_settings():
    settings = get_universal_safety_settings()
    assert len(settings) == 4
    for s in settings:
        assert s["threshold"] == "BLOCK_NONE"


def test_dramatic_fiction_framing():
    framing = get_dramatic_fiction_framing("Sword of Destiny", "Andrzej Sapkowski")
    assert "Sword of Destiny" in framing
    assert "Andrzej Sapkowski" in framing
    assert "DRAMATIC LITERARY CONTEXT" in framing


def test_project_classifier_witcher():
    pdir = Path("archive/witcher/sword_of_destiny")
    res = ProjectClassifier.classify(project_dir=pdir)
    assert res.era == "MEDIEVAL_FANTASY"
    assert res.genre == "fantasy"
    assert res.franchise_affinity == "the_witcher"
    assert res.primary_acoustic_env == "stone_ruins_exterior"


def test_project_classifier_synthetic_scifi():
    res = ProjectClassifier.classify(
        metadata={"title": "Starship Odyssey", "author": "Arthur C. Clarke"},
        sample_prose="The starship entered warp orbit around the alien planet. Consoles beeped on the bridge.",
    )
    assert res.era == "SPACE_OPERA_SCIFI"
    assert res.genre == "sci_fi"


def test_environment_profile_resolution_debiased():
    reg = get_environment_registry()

    # Stone ruins (previously missing)
    prof_ruins = reg.resolve_from_text("खंडहरों के बीच मलबे में सियाह सुराख़")
    assert prof_ruins.env_id == "stone_ruins_exterior"

    # Tavern
    prof_tavern = reg.resolve_from_text("They entered the noisy tavern and slammed tankards of ale.")
    assert prof_tavern.env_id == "tavern_interior"

    # Sci-Fi spaceship
    prof_ship = reg.resolve_from_text("Captain stepped onto the spaceship bridge as consoles hummed.")
    assert prof_ship.env_id == "spaceship_bridge"

    # Neutral fallback must NOT be suburban domestic room when no keywords match
    prof_neutral = reg.resolve_from_text("A mysterious silence lingered in the air.")
    assert prof_neutral.env_id == "room_tone"


def test_franchise_affinity_search():
    sb = get_sound_bank()
    results = sb.search("combat", category="foley", limit=3, franchise_affinity="the_witcher")
    assert len(results) > 0
    # Top result should have the_witcher franchise
    assert results[0].get("franchise_affinity") == "the_witcher"

    m_results = sb.search_music_catalog("wolf", limit=3, franchise_affinity="the_witcher")
    assert len(m_results) > 0
    assert m_results[0].get("franchise_affinity") == "the_witcher"


def test_sonic_bible_generation():
    pdir = Path("archive/witcher/sword_of_destiny")
    bible = SonicBibleGenerator.generate_for_project(pdir, force_rebuild=False)
    assert bible.book_title == "Sword of Destiny"
    assert len(bible.leitmotifs) > 0
    assert len(bible.acoustic_spaces) >= 5
    assert "geralt of rivia" in bible.leitmotifs or "lm_geralt_of_rivia" in bible.leitmotifs
