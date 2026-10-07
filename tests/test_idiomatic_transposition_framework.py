#!/usr/bin/env python3
"""
Unit tests for the Universal Idiomatic Transposition Framework ("Pinch of Salt").
Verifies Category A vs Category B taxonomy, anti-calque defense, prompt directives,
and advisory lexicon integration.
"""

import pytest
from audiobook_factory.translation.agents.idiom_dramaturge import SubtextAndIdiomDramaturge
from audiobook_factory.translation.agents.draft_translator import LiteraryDraftTranslator as DraftTranslator
from audiobook_factory.translation.agents.cadence_specialist import HindustaniCadenceSpecialist as CadenceSpecialist
from audiobook_factory.advisory_lexicon import get_advisory_db
from audiobook_factory.translation.hindustani_register import HindustaniRegisterEngine, HindustaniRegisterSpec


def test_01_idiom_dramaturge_commands_category_a():
    """Verify that SubtextAndIdiomDramaturge mandates Category A Universal Spoken Idioms."""
    agent = SubtextAndIdiomDramaturge()
    captured_instruction = ""

    def mock_llm_fn(prompt: str, system_instruction: str, **kwargs):
        nonlocal captured_instruction
        captured_instruction = system_instruction
        return "सत्यापित अनुवाद।"

    glossary = {"book_dna": {"source_fidelity_tier": "RAW_UNRATED"}}
    agent.enrich_idioms_and_subtext(
        source_text="Test source",
        cadence_hindi="परीक्षण पाठ",
        glossary=glossary,
        call_llm_fn=mock_llm_fn,
    )

    assert "CATEGORY A: UNIVERSAL SPOKEN IDIOMS" in captured_instruction
    assert "लिख के ले लो" in captured_instruction
    assert "मौत को दावत देना" in captured_instruction
    assert "खाल उधेड़ना" in captured_instruction


def test_02_idiom_dramaturge_bans_category_b_parody():
    """Verify that SubtextAndIdiomDramaturge strictly bans Category B Indian village tropes."""
    agent = SubtextAndIdiomDramaturge()
    captured_instruction = ""

    def mock_llm_fn(prompt: str, system_instruction: str, **kwargs):
        nonlocal captured_instruction
        captured_instruction = system_instruction
        return "सत्यापित अनुवाद।"

    glossary = {"book_dna": {"source_fidelity_tier": "RAW_UNRATED"}}
    agent.enrich_idioms_and_subtext(
        source_text="Test source",
        cadence_hindi="परीक्षण पाठ",
        glossary=glossary,
        call_llm_fn=mock_llm_fn,
    )

    assert "CATEGORY B: CULTURALLY BOUND LOCAL TROPES" in captured_instruction
    assert "गंगा नहाना" in captured_instruction
    assert "पंचों का फैसला" in captured_instruction
    assert "नाच न जाने आँगन टेढ़ा" in captured_instruction


def test_03_draft_translator_sense_for_sense_idiom_instruction():
    """Verify that DraftTranslator mandates sense-for-sense idiomatic transposition."""
    translator = DraftTranslator()
    captured_prompt = ""

    def mock_llm_fn(prompt: str, system_instruction: str, **kwargs):
        nonlocal captured_prompt
        captured_prompt = system_instruction
        return "सत्यापित अनुवाद।"

    glossary = {"book_dna": {"source_fidelity_tier": "RAW_UNRATED"}}
    translator.translate_draft(
        text_block="He was heading to his doom, sure as eggs is eggs.",
        glossary=glossary,
        adult_mode=True,
        call_llm_fn=mock_llm_fn,
    )

    assert "UNIVERSAL IDIOMATIC TRANSPOSITION" in captured_prompt
    assert "anti-calque" in captured_prompt
    assert "अंडे अंडे हैं" in captured_prompt
    assert "बाल्टी को लात मारना" in captured_prompt


def test_04_cadence_specialist_idiomatic_timing_directive():
    """Verify that CadenceSpecialist includes actor timing for idiomatic punchlines."""
    specialist = CadenceSpecialist()
    captured_instruction = ""

    def mock_llm_fn(prompt: str, system_instruction: str, **kwargs):
        nonlocal captured_instruction
        captured_instruction = system_instruction
        return "सत्यापित पाठ।"

    specialist.refine_cadence(
        source_text="Test source",
        draft_hindi="परीक्षण पाठ",
        glossary={},
        call_llm_fn=mock_llm_fn,
    )

    assert "IDIOMATIC PUNCHLINES & ACTOR TIMING" in captured_instruction
    assert "लिख के ले लो" in captured_instruction


def test_05_advisory_db_seeds_universal_idiom_rules():
    """Verify that AdvisoryLexiconDB contains active rules for universal idioms and anti-calque."""
    db = get_advisory_db()
    rules = db.list_rules()
    categories = {r["category"] for r in rules}

    assert "universal_idioms" in categories
    assert "anti_calque_defense" in categories

    prompt_guidance = db.get_formatted_prompt_guidelines()
    assert "UNIVERSAL_IDIOMS" in prompt_guidance
    assert "ANTI_CALQUE_DEFENSE" in prompt_guidance


def test_06_hindustani_register_recognizes_universal_idioms():
    """Verify that HindustaniRegisterEngine recognizes universal idioms as organic seasoning."""
    engine = HindustaniRegisterEngine()
    sample_dialogue = "उसने कहा, 'लिख के ले लो, वो अपनी मौत को दावत दे रहा है और उसकी खाल उधेड़ दी जाएगी।'"
    result = engine.audit_text(sample_dialogue)

    assert result.is_balanced is True
    assert any(term in result.detected_seasoning_words for term in ["लिख के ले लो", "मौत को दावत", "खाल उधेड़ना"])
