"""
Comprehensive Test Suite for Audit Remediation (Zero-Hardcoding, Creative Autonomy, & Bug Fixes).
Validates all 10 fixes identified by independent expert auditors.
"""

import json
import pytest
from pathlib import Path

from audiobook_factory.acoustic_bus_matrix import derive_ucs_category, UCS_RULES
from audiobook_factory.character_caster import CharacterCaster
from audiobook_factory.tts.voice_catalog import get_voice_catalog
from audiobook_factory.gates.literary import audit_gate1_roster
from audiobook_factory.sanitizer import filter_bracketed_tags
from audiobook_factory.script.screenplay_cleaner import stitch_split_dialogue_turns, clean_screenplay_pass2


def test_acoustic_bus_matrix_zero_witcher_lore_and_universal():
    """Verify that Witcher signs and monsters are purged, and modern/sci-fi categories exist."""
    # 1. Assert zero Witcher signs or striga in UCS_RULES keywords
    for keywords, ucs_code in UCS_RULES:
        for kw in keywords:
            assert kw not in ("igni", "aard", "quen", "axii", "yrden", "striga"), f"Forbidden token {kw} found in UCS_RULES"

    # 2. Assert universal modern and sci-fi categories work
    assert derive_ucs_category("fired a pistol") == "GUNPist"
    assert derive_ucs_category("engine revved") == "VEHCar"
    assert derive_ucs_category("terminal beeped") == "ELECGen"
    assert derive_ucs_category("spell burst") == "MAGCSpell"
    assert derive_ucs_category("beast roar") == "CREAVoc"


def test_voice_casting_catalog_zero_franchise_names():
    """Verify that voice_casting_catalog.json does not hardcode Geralt, Ciri, Yennefer, Dandelion."""
    catalog_path = Path("audiobooks/voice_casting_catalog.json")
    assert catalog_path.exists()
    content = catalog_path.read_text(encoding="utf-8").lower()
    for forbidden in ("geralt", "ciri", "yennefer", "dandelion", "jaskier", "blaviken"):
        assert forbidden not in content, f"Forbidden franchise token '{forbidden}' found in voice_casting_catalog.json"


def test_null_gender_handling_does_not_crash():
    """Verify that JSON null gender values do not throw AttributeError in character_caster or voice_catalog."""
    raw_characters = [
        {
            "canonical_name": "Mysterious Entity",
            "gender": None,  # Simulates LLM outputting {"gender": null}
            "archetype": "shadowy figure",
        }
    ]
    # Should not raise AttributeError: 'NoneType' object has no attribute 'lower'
    roster, registry, _ = CharacterCaster._build_cast_allocation(
        project_id="proj-null-test",
        raw_characters=raw_characters,
        use_hindi=False,
    )
    assert "Mysterious Entity" in registry
    assert registry["Mysterious Entity"]["voice"] is not None

    # Test voice_catalog directly with None gender and None archetype
    catalog = get_voice_catalog()
    v = catalog.get_best_matching_voice(gender=None, archetype=None, language_code="hi-IN")
    assert v is not None


def test_gate1_dynamic_voice_catalog_integration():
    """Verify Gate 1 audits acoustic gender alignment dynamically via VoiceCatalog."""
    roster = {
        "characters": {
            "Hero": {"gender": "male", "archetype": "noble knight"},
            "Heroine": {"gender": "female", "archetype": "wise scholar"},
            "Child": {"gender": "male", "archetype": "little boy", "is_child": True},
        }
    }
    # Allocate authentic native Hindi voices from VoiceCatalog
    registry = {
        "Narrator": {"voice": "Aoede", "pitch": 1.0, "speed": 1.0},
        "Hero": {"voice": "hi-in-podcaster-12", "pitch": 1.0, "speed": 1.0},  # Male
        "Heroine": {"voice": "hi-in-advisor-1", "pitch": 1.0, "speed": 1.0},   # Female
        "Child": {"voice": "hi-in-tutor-7", "pitch": 1.03, "speed": 1.03},     # Female Seiyū for boy child
    }
    active = ["Hero", "Heroine", "Child"]

    # Must pass without GateAuditError
    result = audit_gate1_roster(roster, registry, active)
    assert result["status"] == "PASS"


def test_split_quote_stitching_speech_verbs_only():
    """Verify split quotes are unified only for short speech tags, preserving physical action blocking."""
    # Case 1: Short speech tag with speech verb -> should unify
    turns_with_tag = [
        {"type": "dialogue", "speaker": "Geralt", "text": "We leave at dawn."},
        {"type": "narration", "speaker": "Narrator", "text": "उसने धीमे से कहा,"},
        {"type": "dialogue", "speaker": "Geralt", "text": "Be ready.", "acting": {"delivery_style": "quiet warning"}},
    ]
    stitched1 = stitch_split_dialogue_turns(turns_with_tag)
    assert len(stitched1) == 2
    assert stitched1[0]["type"] == "narration"
    assert "—" in stitched1[0]["text"]
    assert stitched1[1]["type"] == "dialogue"
    assert stitched1[1]["text"] == "We leave at dawn. Be ready."
    assert "quiet warning" in stitched1[1].get("acting", {}).get("delivery_style", "")

    # Case 2: Physical action sequence -> must NOT reorder chronology
    turns_with_action = [
        {"type": "dialogue", "speaker": "Geralt", "text": "Stop right there."},
        {"type": "narration", "speaker": "Narrator", "text": "He stepped across the threshold, unsheathed his steel blade, and kicked the heavy iron door shut behind him."},
        {"type": "dialogue", "speaker": "Geralt", "text": "Drop your weapons."},
    ]
    stitched2 = stitch_split_dialogue_turns(turns_with_action)
    assert len(stitched2) == 3, "Physical action blocking must preserve authentic narrative chronology!"
    assert stitched2[0]["text"] == "Stop right there."
    assert stitched2[1]["type"] == "narration"
    assert stitched2[2]["text"] == "Drop your weapons."


def test_acting_tags_preservation_in_sanitizer():
    """Verify that nuanced acting cues are preserved for downstream TTS style extraction."""
    import re

    # Direct filter_bracketed_tags test
    m1 = re.search(r"\[[^\]]+\]", "[hesitates, catches breath]")
    assert filter_bracketed_tags(m1) == "[hesitates, catches breath]"

    m2 = re.search(r"\[[^\]]+\]", "[ironic smirk]")
    assert filter_bracketed_tags(m2) == "[ironic smirk]"

    m3 = re.search(r"\[[^\]]+\]", "[trembling with fury]")
    assert filter_bracketed_tags(m3) == "[trembling with fury]"

    # Verify clean_screenplay_pass2 preserves them in dialogue text
    raw_segments = [
        {
            "index": 1,
            "type": "dialogue",
            "speaker": "Rogue",
            "text": "[ironic smirk] Did you really think you could deceive me?",
        }
    ]
    cleaned = clean_screenplay_pass2(raw_segments, is_hindi=False)
    assert len(cleaned) == 1
    assert "[ironic smirk]" in cleaned[0]["text"]


def test_bilingual_dialogue_preserved_in_hindi():
    """Verify that valid English dialogue in a Hindi screenplay is not deleted."""
    segments = [
        {
            "index": 1,
            "type": "dialogue",
            "speaker": "Wizard",
            "text": "Ignis potentia magnus est semper.",  # Latin/English incantation (6 words, 0 devanagari)
        },
        {
            "index": 2,
            "type": "dialogue",
            "speaker": "AI",
            "text": "Here is the translation of the chapter below:",  # Refusal / preamble leak
        }
    ]
    cleaned = clean_screenplay_pass2(segments, is_hindi=True)
    # The valid dialogue must be preserved; the refusal preamble must be dropped
    assert len(cleaned) == 1
    assert cleaned[0]["speaker"] == "Wizard"
    assert cleaned[0]["text"] == "Ignis potentia magnus est semper."
