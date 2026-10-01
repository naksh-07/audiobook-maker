#!/usr/bin/env python3
"""
Unit tests for Autonomous Character Discovery & Casting Engine (CharacterCaster).
Verifies:
1. Dynamic character parsing and voice allocation without hardcoded lists.
2. Collision-free Gemini voice signatures.
3. Gender-appropriate persona selection.
4. Persistence of character_roster.json, voice_registry.json, and cast_lock.json.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.character_caster import (
    CharacterCaster,
    MALE_VOICE_PERSONAS,
    FEMALE_VOICE_PERSONAS,
)


@pytest.fixture
def temp_project(tmp_path):
    proj_dir = tmp_path / "test_book_project"
    proj_dir.mkdir(parents=True, exist_ok=True)
    ext_dir = proj_dir / "extracted"
    ext_dir.mkdir(parents=True, exist_ok=True)
    
    # Create sample chapter
    chap1 = ext_dir / "chapter_001.md"
    chap1.write_text(
        "# Chapter 1\n\n"
        "Mr. Dursley hummed as he picked out his most boring tie for work.\n"
        "Mrs. Dursley gossiped away happily as she wrestled a screaming Dudley into his high chair.\n"
        "\"Little tyke,\" chortled Mr. Dursley as he left the house.\n",
        encoding="utf-8"
    )
    return proj_dir


def test_build_cast_allocation_no_collision():
    raw_characters = [
        {"english_name": "Mr. Dursley", "hindi_name": "मिस्टर डर्स्ली", "gender": "male", "age": "middle-aged", "role": "antagonist", "aliases": ["Vernon"]},
        {"english_name": "Mrs. Dursley", "hindi_name": "मिसेज डर्स्ली", "gender": "female", "age": "middle-aged", "role": "supporting", "aliases": ["Petunia"]},
        {"english_name": "Dudley", "hindi_name": "डडली", "gender": "male", "age": "child", "role": "supporting", "aliases": ["Dudders"]},
        {"english_name": "Albus Dumbledore", "hindi_name": "डम्बलडोर", "gender": "male", "age": "elder", "role": "mentor", "aliases": ["Professor Dumbledore"]},
    ]

    roster, registry, cast_lock = CharacterCaster._build_cast_allocation(
        project_id="proj-test",
        raw_characters=raw_characters,
        default_narrator_voice="Aoede",
    )

    # 1. Narrator must be present in registry and roster
    assert "Narrator" in registry
    assert registry["Narrator"]["voice"] == "Aoede"

    # 2. Check all characters allocated (Narrator + 4 discovered)
    chars = roster["characters"]
    assert len(chars) == 5
    for name, c in chars.items():
        if name == "Narrator":
            continue
        eng = c["english_name"]
        assert eng in registry
        assigned_v = registry[eng]["voice"]
        # Character cannot steal lead narrator voice if options exist
        assert assigned_v != "Aoede"

    # 3. Check female character got female voice persona
    mrs_dursley_v = registry["Mrs. Dursley"]["voice"]
    assert mrs_dursley_v in FEMALE_VOICE_PERSONAS

    # 4. Check male characters got distinct male voice personas (no collisions)
    assigned_male_voices = [
        registry["Mr. Dursley"]["voice"],
        registry["Dudley"]["voice"],
        registry["Albus Dumbledore"]["voice"],
    ]
    assert len(set(assigned_male_voices)) == len(assigned_male_voices)

    # 5. Check cast lock created
    locks = cast_lock["locks"]
    assert "Mr. Dursley" in locks
    assert locks["Mr. Dursley"]["locked"] is True


def test_discover_and_cast_project_file_creation(temp_project):
    mock_chars = [
        {"english_name": "Mr. Dursley", "hindi_name": "मिस्टर डर्स्ली", "gender": "male", "age": "middle-aged", "role": "antagonist", "aliases": ["Vernon"]},
        {"english_name": "Mrs. Dursley", "hindi_name": "मिसेज डर्स्ली", "gender": "female", "age": "middle-aged", "role": "supporting", "aliases": ["Petunia"]},
    ]

    with patch.object(CharacterCaster, "_call_llm_casting", return_value=mock_chars):
        roster = CharacterCaster.discover_and_cast_project(
            project_dir=temp_project,
            use_hindi=False,
            default_narrator_voice="Aoede",
        )

    roster_file = temp_project / "character_roster.json"
    registry_file = temp_project / "voice_registry.json"
    lock_file = temp_project / "cast_lock.json"

    assert roster_file.exists()
    assert registry_file.exists()
    assert lock_file.exists()

    with open(roster_file, "r", encoding="utf-8") as f:
        saved_roster = json.load(f)
    assert len(saved_roster["characters"]) == 3  # Narrator + 2 characters
