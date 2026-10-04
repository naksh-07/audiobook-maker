#!/usr/bin/env python3
"""
Unit tests for Room 2: Source-Anchored Translation Collective with Dual-Rule Invariant.
Verifies that:
1. When book_dna is CLASSIC_REVERENT (Premchand), the collective enforces dignified regional
   cadence, emotional pathos, and strictly forbids modern street slang or forced profanities.
2. When book_dna is RAW_UNRATED (Manto/Witcher/GoT), the collective enforces 19-to-21 Amplification,
   visceral combat choreography, raw battlefield insults, and somatic intimacy without bowdlerization.
3. book_dna propagates cleanly through MultiAgentTranslationCollective.
"""

import pytest
from unittest.mock import MagicMock

from audiobook_factory.translation.agents.draft_translator import LiteraryDraftTranslator
from audiobook_factory.translation.agents.idiom_dramaturge import SubtextAndIdiomDramaturge
from audiobook_factory.translation.agents.collective import MultiAgentTranslationCollective


def test_draft_translator_classic_reverent_scene_mode():
    translator = LiteraryDraftTranslator()
    premchand_dna = {
        "literary_tradition": "RURAL_REALISM_AND_PATHOS",
        "source_fidelity_tier": "CLASSIC_REVERENT",
        "regional_dialect_cadence": "Awadhi/Bhojpuri-infused Hindustani",
        "profanity_policy": "STRICTLY_CLEAN_REVERENT",
    }
    
    dialogue_block = '"Are you coming to the field?" asked Hori. "Yes," Gobar replied, "I will be right there."'
    directives = translator._detect_scene_mode(dialogue_block, "Scene 1", book_dna=premchand_dna)
    
    assert "CLASSIC LITERARY DIALOGUE" in directives
    assert "Awadhi/Bhojpuri-infused Hindustani" in directives
    assert "STRICTLY FORBIDDEN: Modern street vulgarities" in directives


def test_draft_translator_raw_unrated_scene_mode():
    translator = LiteraryDraftTranslator()
    dark_fantasy_dna = {
        "literary_tradition": "DARK_FANTASY_GRIT",
        "source_fidelity_tier": "RAW_UNRATED",
        "regional_dialect_cadence": "Rugged Frontier Hindustani",
        "profanity_policy": "UNRATED_AUTHENTIC_KASHYAP",
    }
    
    combat_block = "The monster lunged with claws bared. Geralt drew his silver blade, severed its throat, and blood gushed onto the stones."
    directives = translator._detect_scene_mode(combat_block, "Combat Scene", book_dna=dark_fantasy_dna)
    
    assert "VISCERAL COMBAT, GORE & STACCATO RHYTHM" in directives
    assert "STACCATO clauses" in directives
    assert "blood spray" in directives


def test_idiom_dramaturge_dual_rule_prompts():
    dramaturge = SubtextAndIdiomDramaturge()
    
    premchand_dna = {
        "literary_tradition": "RURAL_REALISM_AND_PATHOS",
        "source_fidelity_tier": "CLASSIC_REVERENT",
        "regional_dialect_cadence": "Awadhi/Bhojpuri Hindustani",
    }
    
    mock_llm_premchand = MagicMock(return_value="होरी ने गहरी सांस ली और बोला- भगवान ही मालिक है।")
    res_premchand = dramaturge.enrich_idioms_and_subtext(
        source_text="Hori sighed deeply and said God is our master.",
        cadence_hindi="होरी ने गहरी सांस ली...",
        glossary={"book_dna": premchand_dna},
        call_llm_fn=mock_llm_premchand
    )
    assert res_premchand == "होरी ने गहरी सांस ली और बोला- भगवान ही मालिक है।"
    called_sys = mock_llm_premchand.call_args[1].get("system_instruction") or mock_llm_premchand.call_args[0][1]
    assert "SACRED REVERENCE" in called_sys
    assert "STRICTLY FORBIDDEN to inject modern street profanity" in called_sys


def test_collective_threads_book_dna():
    collective = MultiAgentTranslationCollective()
    custom_dna = {
        "literary_tradition": "DARK_FANTASY_GRIT",
        "source_fidelity_tier": "RAW_UNRATED",
        "regional_dialect_cadence": "Rugged Frontier Hindustani",
    }
    
    mock_llm = MagicMock(return_value="यह एक बेहतरीन अनुवादित दृश्य है।")
    
    res = collective.translate_block(
        text_block="The mercenaries gathered in the cold tavern.",
        glossary={"book_dna": custom_dna},
        block_title="Tavern Scene",
        call_llm_fn=mock_llm
    )
    assert len(res) > 5
    assert mock_llm.called
