#!/usr/bin/env python3
"""
Unit tests for Room 1 Agent 0: Universal Literary DNA & Register Profiler.
Verifies novel-agnostic literary analysis across diverse authorial traditions:
- Munshi Premchand (dignified rural Awadhi/Hindustani, sacred reverence)
- Saadat Hasan Manto (somatic psychological realism, unvarnished human truth)
- Dark Fantasy / Sapkowski (visceral combat gore, tavern profanity, mercenary cynical banter)
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from audiobook_factory.preproduction.book_dna_agent import BookDNAAgent


def test_book_dna_agent_premchand_heuristic():
    agent = BookDNAAgent()
    sample = "होरी महतो ने दोनों बैलों को सानी-पानी दिया और अपनी लाठी संभालते हुए धनिया से बोला- गोबर को खेत पर भेज देना।"
    meta = {"title": "Godaan", "author": "Munshi Premchand", "project_slug": "godaan"}
    
    dna = agent._heuristic_fallback(sample, meta)
    assert dna["literary_tradition"] == "RURAL_REALISM_AND_PATHOS"
    assert dna["source_fidelity_tier"] == "CLASSIC_REVERENT"
    assert dna["profanity_policy"] == "STRICTLY_CLEAN_REVERENT"
    assert "Awadhi" in dna["regional_dialect_cadence"] or "Bhojpuri" in dna["regional_dialect_cadence"]


def test_book_dna_agent_manto_heuristic():
    agent = BookDNAAgent()
    sample = "ईशर सिंह ने अपनी ठंडी हथेली कुलवंत कौर के जिस्म पर रख दी। उसने गहरी सांस ली... ठंडा गोश्त।"
    meta = {"title": "Thanda Gosht", "author": "Saadat Hasan Manto", "project_slug": "thanda_gosht"}
    
    dna = agent._heuristic_fallback(sample, meta)
    assert dna["literary_tradition"] == "SOMATIC_PSYCHOLOGICAL_REALISM"
    assert dna["source_fidelity_tier"] == "RAW_UNRATED"
    assert dna["intimacy_intensity"] in ("SOMATIC_PASSION_RAW", "SOMATIC_PASSION_MANTO")


def test_book_dna_agent_dark_fantasy_heuristic():
    agent = BookDNAAgent()
    sample = "The witcher unsheathed his silver blade. The basilisk hissed in the crypt, blood dripping from its jaws."
    meta = {"title": "Sword of Destiny", "author": "Andrzej Sapkowski", "project_slug": "sword_of_destiny"}
    
    dna = agent._heuristic_fallback(sample, meta)
    assert dna["literary_tradition"] == "DARK_FANTASY_GRIT"
    assert dna["source_fidelity_tier"] == "RAW_UNRATED"
    assert dna["action_intensity"] == "VISCERAL_COMBAT_GORE"
    assert dna["profanity_policy"] == "UNRATED_AUTHENTIC_KASHYAP"


def test_book_dna_agent_mock_llm():
    agent = BookDNAAgent()
    mock_llm = MagicMock(return_value={
        "project_id": "proj-custom-epic",
        "book_title": "Custom Epic",
        "author": "Epic Author",
        "literary_tradition": "MEDIEVAL_WAR_CHRONICLE",
        "source_fidelity_tier": "RAW_UNRATED",
        "regional_dialect_cadence": "Archaic Courtly Hindustani",
        "profanity_policy": "MILD_COLLOQUIAL",
        "action_intensity": "VISCERAL_COMBAT_GORE",
        "intimacy_intensity": "NONE_OR_TENDER",
        "honorific_dynamics": "Strict feudal military hierarchy",
        "dialogue_delivery_tempo": "measured_deliberate",
        "world_atmosphere_summary": "Sieges, armor, and ruthless royal courts."
    })
    
    res = agent.analyze_book_dna(
        novel_text_sample="The fortress walls shook under cannon fire.",
        book_metadata={"title": "Custom Epic", "author": "Epic Author", "project_slug": "custom-epic"},
        call_llm_fn=mock_llm
    )
    
    assert res["literary_tradition"] == "MEDIEVAL_WAR_CHRONICLE"
    assert res["source_fidelity_tier"] == "RAW_UNRATED"
    assert res["action_intensity"] == "VISCERAL_COMBAT_GORE"
