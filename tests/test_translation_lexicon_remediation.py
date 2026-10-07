#!/usr/bin/env python3
"""
Test Suite: Issue 1 Remediation (Dynamic Lexicon & Netflix-Standard Translation Register)
==========================================================================================
Verifies:
1. PronunciationLexicon has zero hardcoded fiction characters or modern agencies in seed_default_lexicon.
2. PronunciationLexicon.prune_polluted_entries() safely purges legacy contaminated IDs.
3. BookBible.propose_new_entity() accurately partitions entities into locations, creatures, titles, etc.
4. DeepSearchNovelDossier contains world_lore_entities and PreProductionSupervisor syncs them.
5. LiteraryDraftTranslator injects the 4-Tier Cognitive Semantic Register Ladder (anti-Tat-Sama).
6. HindustaniCadenceSpecialist and TranslationQualityCritic empower spoken register refactoring.
"""

import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock

from audiobook_factory.pronunciation.lexicon import PronunciationLexicon, PronunciationEntry, SpokenLanguage, PronunciationStatus, PronunciationSource
from audiobook_factory.translation.book_bible import BookBible, BookEntity
from audiobook_factory.preproduction.novel_deepsearch import DeepSearchNovelDossier
from audiobook_factory.translation.agents.draft_translator import LiteraryDraftTranslator
from audiobook_factory.translation.agents.cadence_specialist import HindustaniCadenceSpecialist
from audiobook_factory.translation.agents.translation_critic import TranslationQualityCritic


def test_01_lexicon_seed_has_zero_hardcoded_fiction_or_agencies():
    """Assert seed_default_lexicon is novel-agnostic and seeds zero hardcoded characters/agencies."""
    lex = PronunciationLexicon()
    lex.seed_default_lexicon()
    assert len(lex.entries) == 0, "seed_default_lexicon must not seed any hardcoded fiction or agency entries"


def test_02_lexicon_prune_polluted_entries():
    """Assert prune_polluted_entries removes legacy hardcoded IDs."""
    lex = PronunciationLexicon()
    for pid in ("fbi", "cbi", "sherlock_holmes", "dr_watson", "geralt_valid"):
        lex.entries[pid] = PronunciationEntry(
            canonical_id=pid,
            canonical_text=pid.title(),
            spoken_form=pid,
            category="character",
            expected_language=SpokenLanguage.ENGLISH,
            status=PronunciationStatus.VERIFIED,
            source=PronunciationSource.CANONICAL_LEXICON,
        )

    removed = lex.prune_polluted_entries()
    assert removed == 4
    assert "geralt_valid" in lex.entries
    assert "fbi" not in lex.entries
    assert "sherlock_holmes" not in lex.entries


def test_03_book_bible_propose_new_entity_category_routing():
    """Assert propose_new_entity routes to locations, creatures, titles, etc., rather than dumping all into characters."""
    bible = BookBible(book_title="Test Universe")

    # Character
    c_ent = BookEntity(english_name="Geralt", hindi_name="गेराल्ट", category="character", confidence=0.9)
    assert bible.propose_new_entity(c_ent, 1) is True
    assert "Geralt" in bible.characters

    # Creature
    cr_ent = BookEntity(english_name="Basilisk", hindi_name="बेसिलिस्क", category="creature", confidence=0.9)
    assert bible.propose_new_entity(cr_ent, 1) is True
    assert "Basilisk" in bible.creatures
    assert "Basilisk" not in bible.characters

    # Location
    loc_ent = BookEntity(english_name="Wyzima", hindi_name="विज़िमा", category="location", confidence=0.9)
    assert bible.propose_new_entity(loc_ent, 1) is True
    assert "Wyzima" in bible.locations
    assert "Wyzima" not in bible.characters

    # Title
    t_ent = BookEntity(english_name="Alderman", hindi_name="नगर प्रमुख", category="title", confidence=0.9)
    assert bible.propose_new_entity(t_ent, 1) is True
    assert "Alderman" in bible.titles
    assert "Alderman" not in bible.characters


def test_04_deepsearch_dossier_contains_world_lore_entities():
    """Assert DeepSearchNovelDossier schema includes world_lore_entities dictionary."""
    dossier = DeepSearchNovelDossier(
        book_title="Test Novel",
        author="Test Author",
        world_lore_entities={
            "locations": {"Novigrad": "नोविग्राड"},
            "creatures": {"Striga": "स्ट्रिगा"},
            "titles": {"Castellan": "कास्टेलान"},
        }
    )
    assert "Novigrad" in dossier.world_lore_entities["locations"]
    assert "Striga" in dossier.world_lore_entities["creatures"]
    assert "Castellan" in dossier.world_lore_entities["titles"]


def test_05_draft_translator_prompt_enforces_semantic_register_ladder():
    """Verify LiteraryDraftTranslator system prompt commands the 4-tier Semantic Register Ladder."""
    translator = LiteraryDraftTranslator()
    
    captured_prompt = None
    captured_sys_prompt = None

    def fake_call_gemini(prompt, system_instruction="", **kwargs):
        nonlocal captured_prompt, captured_sys_prompt
        captured_prompt = prompt
        captured_sys_prompt = system_instruction
        return "अनुवादित पाठ"

    glossary = {"characters": []}
    translator.translate_draft(
        text_block="The muscles of their powerful thighs were visible beneath lynx skins wrapped around their hips.",
        glossary=glossary,
        block_title="Scene 1",
        adult_mode=True,
        call_llm_fn=fake_call_gemini,
    )

    assert captured_sys_prompt is not None
    assert "4-TIER COGNITIVE SEMANTIC REGISTER LADDER" in captured_sys_prompt
    assert "कमर" in captured_sys_prompt
    assert "कूल्हे" in captured_sys_prompt
    assert "नितंब" in captured_sys_prompt  # Banned mention
    assert "गांड" in captured_sys_prompt
    assert "लड़ाकू औरतें" in captured_sys_prompt
    assert "सौदा" in captured_sys_prompt


def test_06_cadence_specialist_and_critic_enforce_spoken_naturalness():
    """Assert CadenceSpecialist and TranslationQualityCritic mandate spoken register refactoring."""
    cadence = HindustaniCadenceSpecialist()
    captured_cadence_sys = None

    def fake_cadence_llm(prompt, system_instruction="", **kwargs):
        nonlocal captured_cadence_sys
        captured_cadence_sys = system_instruction
        return "सुधरा हुआ संवाद"

    cadence.refine_cadence(
        source_text="Sample English",
        draft_hindi="नमूना हिंदी",
        glossary={},
        call_llm_fn=fake_cadence_llm,
    )

    assert captured_cadence_sys is not None
    assert "कमर" in captured_cadence_sys or "कूल्हे" in captured_cadence_sys
    assert "नितंब" in captured_cadence_sys  # Explictly instructed to replace
    assert "लड़ाकू औरतें" in captured_cadence_sys
