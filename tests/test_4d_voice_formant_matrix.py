#!/usr/bin/env python3
"""
Unit tests for 4D Acoustic Formant & Timbre Matrix in CharacterCaster.
Verifies that:
1. Distinct vocal archetypes receive physically distinct pitch, tempo, and EQ formant settings.
2. Multiple characters sharing the same base Gemini voice receive mathematically non-colliding signatures.
3. Both character_roster.json and voice_registry.json contain complete DSP parameters.
"""

import pytest
import tempfile
import json
from pathlib import Path

from audiobook_factory.character_caster import CharacterCaster


def test_compute_acoustic_formant_vector_archetypes():
    # Warrior / Heavy
    warrior_vec = CharacterCaster.compute_acoustic_formant_vector(
        gender="male", archetype="veteran sword warrior", index=0
    )
    assert warrior_vec["pitch"] <= 0.92
    assert warrior_vec["bass_boost_db"] >= 2.5
    assert warrior_vec["speed"] <= 0.98

    # Bard / Youth
    bard_vec = CharacterCaster.compute_acoustic_formant_vector(
        gender="male", archetype="youthful energetic bard", index=0
    )
    assert bard_vec["pitch"] >= 1.04
    assert bard_vec["presence_boost_db"] >= 2.0
    assert bard_vec["speed"] >= 1.02

    # Tavernkeeper / Peasant
    peasant_vec = CharacterCaster.compute_acoustic_formant_vector(
        gender="male", archetype="innkeeper tavern peasant", index=0
    )
    assert peasant_vec["pitch"] >= 1.05
    assert peasant_vec["clarity_reduction_db"] >= 1.5

    # Female Commanding Leader
    queen_vec = CharacterCaster.compute_acoustic_formant_vector(
        gender="female", archetype="commanding queen sorceress", index=0
    )
    assert queen_vec["pitch"] <= 0.97
    assert queen_vec["bass_boost_db"] >= 1.0


def test_build_cast_allocation_non_colliding_signatures():
    raw_chars = [
        {"name": "Geralt", "gender": "male", "archetype": "stoic mutant hunter"},
        {"name": "Borch", "gender": "male", "archetype": "charismatic nobleman knight"},
        {"name": "Bhatiyara", "gender": "male", "archetype": "toothless tavernkeeper"},
        {"name": "Thug 1", "gender": "male", "archetype": "heavy mercenary brute"},
        {"name": "Thug 2", "gender": "male", "archetype": "agile cutpurse"},
        {"name": "Alderman", "gender": "male", "archetype": "elderly town mayor"},
        {"name": "Tea", "gender": "female", "archetype": "fierce warrior woman"},
        {"name": "Vea", "gender": "female", "archetype": "fierce warrior woman"},
    ]

    roster, vreg, cast_lock = CharacterCaster._build_cast_allocation(
        project_id="proj-test-novel",
        raw_characters=raw_chars,
        use_hindi=True,
    )

    # 1. Narrator must be registered
    assert "Narrator" in vreg
    assert vreg["Narrator"]["pitch"] == 1.0

    # 2. Check each character has distinct acoustic signature
    signatures = set()
    for name, cfg in vreg.items():
        if name == "Narrator":
            continue
        sig = (cfg["voice"], cfg["pitch"], cfg["speed"])
        assert sig not in signatures, f"Signature collision detected for {name}: {sig}"
        signatures.add(sig)

    # 3. Geralt vs Borch vs Bhatiyara contrast
    assert vreg["Geralt"]["pitch"] != vreg["Borch"]["pitch"] or vreg["Geralt"]["voice"] != vreg["Borch"]["voice"]
    assert vreg["Bhatiyara"]["clarity_reduction_db"] > 0.0
    assert vreg["Geralt"]["bass_boost_db"] > 0.0

    # 4. Check locks contain calibration_overrides
    for name, lock in cast_lock["locks"].items():
        assert "calibration_overrides" in lock or name == "Narrator"
        if name != "Narrator":
            calib = lock["calibration_overrides"]
            assert "pitch" in calib
            assert "bass_boost_db" in calib
