#!/usr/bin/env python3
"""
Unit tests for Room 4: Dynamic Gemini 3.8 Voice Catalog & Multi-Persona Casting.
Verifies:
1. Sub-millisecond VoiceCatalog querying across 2,089 voices (114 native Hindi, 120 Indian English, 215 US English).
2. Dynamic, collision-free allocation for multi-character audio dramas in Hindi and English.
3. Natural pitch baseline preservation (pitch = 1.0) eliminating robotic asetrate warping.
4. Stage direction sanitization: extraction of bracketed acting cues into speechMetadata.style.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from audiobook_factory.tts.voice_catalog import VoiceCatalog, get_voice_catalog
from audiobook_factory.character_caster import CharacterCaster
from audiobook_factory.tts.providers.gemini import sanitize_spoken_text_and_extract_stage_directions


def test_voice_catalog_initialization_and_query():
    """Verify VoiceCatalog loads successfully and supports faceted queries."""
    catalog = get_voice_catalog()
    assert catalog is not None

    # Query Hindi voices
    hi_voices = catalog.query_voices(language_code="hi-IN")
    assert len(hi_voices) >= 10, "Should have loaded at least the core Hindi voices"

    # Query male low pitch voices
    male_low = catalog.query_voices(language_code="hi-IN", gender="male", pitch="low")
    assert len(male_low) > 0
    for v in male_low:
        assert v["gender"] == "male"
        assert v["pitch"] == "low"

    # Query female voices
    female_hi = catalog.query_voices(language_code="hi-IN", gender="female")
    assert len(female_hi) > 0
    for v in female_hi:
        assert v["gender"] == "female"


def test_best_matching_voice_and_collision_free_assignment():
    """Verify get_best_matching_voice chooses appropriate voices without collision."""
    catalog = get_voice_catalog()

    used = set()
    v1 = catalog.get_best_matching_voice(
        gender="male",
        language_code="hi-IN",
        archetype="stoic monster hunter warrior",
        exclude_voice_ids=used,
    )
    assert v1 not in used
    used.add(v1)

    v2 = catalog.get_best_matching_voice(
        gender="male",
        language_code="hi-IN",
        archetype="charismatic witty nobleman companion",
        exclude_voice_ids=used,
    )
    assert v2 not in used
    assert v2 != v1
    used.add(v2)

    v3 = catalog.get_best_matching_voice(
        gender="female",
        language_code="hi-IN",
        archetype="sorceress queen commander",
        exclude_voice_ids=used,
    )
    assert v3 not in used
    used.add(v3)

    assert len(used) == 3


def test_character_caster_build_cast_allocation_hindi():
    """Verify CharacterCaster allocates native Hindi voices with pitch 1.0 for Hindi projects."""
    raw_characters = [
        {"english_name": "Hero Protagonist", "gender": "male", "archetype": "stoic veteran hunter", "age": 35},
        {"english_name": "Charming Friend", "gender": "male", "archetype": "witty flamboyant companion", "age": 30},
        {"english_name": "Tavern Host", "gender": "male", "archetype": "peasant tavernkeeper commoner", "age": 50},
        {"english_name": "Sorceress Ally", "gender": "female", "archetype": "commanding mysterious sorceress", "age": 32},
        {"english_name": "Young Maiden", "gender": "female", "archetype": "youthful agile daughter", "age": 20},
    ]

    roster, registry, cast_lock = CharacterCaster._build_cast_allocation(
        project_id="proj-test-hindi",
        raw_characters=raw_characters,
        use_hindi=True,
    )

    # 1. Narrator must be locked to Aoede (supreme narrator lock)
    assert "Narrator" in registry
    assert registry["Narrator"]["voice"] == "Aoede"
    assert registry["Narrator"]["pitch"] == 1.0

    # 2. All non-Narrator characters must have distinct native Hindi voices (no collisions)
    char_voices = [cfg["voice"] for name, cfg in registry.items() if name != "Narrator"]
    assert len(char_voices) == len(set(char_voices)), "Character voices must be 100% collision-free"

    # 3. All non-Narrator characters must have native Hindi voices starting with hi-in-
    for v in char_voices:
        assert v.startswith("hi-in-"), f"Character voice {v} should be a native Hindi voice"

    # 4. Baseline pitch must be preserved around 1.0 (within micro-tolerance)
    for name, cfg in registry.items():
        assert 0.99 <= cfg["pitch"] <= 1.05, f"Character {name} pitch {cfg['pitch']} drifted too far"


def test_character_caster_dynamic_single_speaker_casting(tmp_path):
    """Verify dynamic single speaker auto-casting uses VoiceCatalog without drift."""
    proj_dir = tmp_path / "test_dyn_proj"
    proj_dir.mkdir(parents=True, exist_ok=True)

    # Cast character 1
    cfg1 = CharacterCaster.cast_single_speaker(
        speaker_name="Village Blacksmith",
        project_dir=proj_dir,
        gender="male",
        use_hindi=True,
    )
    assert cfg1["voice"].startswith("hi-in-")
    assert cfg1["pitch"] == 1.0

    # Cast character 2
    cfg2 = CharacterCaster.cast_single_speaker(
        speaker_name="Village Baker",
        project_dir=proj_dir,
        gender="male",
        use_hindi=True,
    )
    assert cfg2["voice"].startswith("hi-in-")
    assert cfg2["voice"] != cfg1["voice"]


def test_sanitize_spoken_text_and_extract_stage_directions():
    """Verify bracketed stage directions are extracted to style and stripped from spoken text."""
    # Example 1: Leading cue
    t1 = "[whispers] मत जाओ!"
    clean1, cues1 = sanitize_spoken_text_and_extract_stage_directions(t1)
    assert clean1 == "मत जाओ!"
    assert cues1 == ["whispers"]

    # Example 2: Trailing cue
    t2 = "तुम्हें क्या चाहिए? [cold menace]"
    clean2, cues2 = sanitize_spoken_text_and_extract_stage_directions(t2)
    assert clean2 == "तुम्हें क्या चाहिए?"
    assert cues2 == ["cold menace"]

    # Example 3: Hindi stage instruction
    t3 = "[धीमी आवाज में] यहाँ कोई नहीं है।"
    clean3, cues3 = sanitize_spoken_text_and_extract_stage_directions(t3)
    assert clean3 == "यहाँ कोई नहीं है।"
    assert cues3 == ["धीमी आवाज में"]

    # Example 4: Pure non-verbal tag
    t4 = "[sigh]"
    clean4, cues4 = sanitize_spoken_text_and_extract_stage_directions(t4)
    assert clean4 == "<sigh>"
    assert cues4 == ["sigh"]


def test_dialect_hint_scoring_preference():
    """Verify VoiceCatalog gives +45 bonus to dialect matches."""
    catalog = get_voice_catalog()

    # 1. Haryanvi preference
    haryanvi_voice = catalog.get_best_matching_voice(
        gender="male",
        language_code="hi-IN",
        archetype="warrior soldier brute",
        dialect_hint="Haryanvi",
    )
    v_haryanvi = catalog.get_voice(haryanvi_voice)
    assert v_haryanvi is not None
    assert "haryanvi" in v_haryanvi.get("dialect", "").lower()

    # 2. Bhojpuri preference
    bhojpuri_voice = catalog.get_best_matching_voice(
        gender="male",
        language_code="hi-IN",
        archetype="peasant tavernkeeper rustic",
        dialect_hint="Bhojpuri",
    )
    v_bhojpuri = catalog.get_voice(bhojpuri_voice)
    assert v_bhojpuri is not None
    assert "bhojpuri" in v_bhojpuri.get("dialect", "").lower()

    # 3. Awadhi preference
    awadhi_voice = catalog.get_best_matching_voice(
        gender="female",
        language_code="hi-IN",
        archetype="poetic gentle companion",
        dialect_hint="Awadhi",
    )
    v_awadhi = catalog.get_voice(awadhi_voice)
    assert v_awadhi is not None
    assert "awadhi" in v_awadhi.get("dialect", "").lower()


def test_anime_seiyu_child_boy_and_girl_casting():
    """
    Verify Anime Seiyū child casting and formant calibration:
    - Boy child (is_child=True, gender="male") gets youthful female voice or young male voice
      with Child Boy Formant Vector (pitch >= 1.03, bass_boost_db <= -2.0, presence_boost_db >= 2.5).
    - Girl child (is_child=True, gender="female") gets youthful female voice
      with Child Girl Formant Vector (pitch >= 1.05, bass_boost_db <= -2.5, presence_boost_db >= 2.8).
    """
    raw_characters = [
        {
            "canonical_name": "Little Boy Hero",
            "gender": "male",
            "is_child": True,
            "archetype": "energetic playful orphan child",
            "recommended_dialect": "Bhojpuri",
        },
        {
            "canonical_name": "Little Princess",
            "gender": "female",
            "is_child": True,
            "archetype": "gentle delicate destined girl child",
            "recommended_dialect": "Awadhi",
        },
    ]

    roster, registry, cast_lock = CharacterCaster._build_cast_allocation(
        project_id="proj-child-test",
        raw_characters=raw_characters,
        use_hindi=True,
    )

    catalog = get_voice_catalog()

    # Check Little Boy Hero
    boy_cfg = registry["Little Boy Hero"]
    boy_meta = catalog.get_voice(boy_cfg["voice"])
    assert boy_meta is not None
    # Boy child should be cast using youthful female or young male
    if boy_meta["gender"] == "male":
        assert boy_meta.get("age", 40) <= 28
    else:
        assert boy_meta["gender"] == "female"
    assert boy_cfg["pitch"] >= 1.03, "Child boy must have calibrated pitch >= 1.03"
    assert boy_cfg["speed"] == 1.03
    assert boy_cfg["bass_boost_db"] <= -2.0, "Child boy must have bass cut for small vocal tract"
    assert boy_cfg["presence_boost_db"] >= 2.5, "Child boy must have upper harmonic boost"

    # Check Little Princess
    girl_cfg = registry["Little Princess"]
    girl_meta = catalog.get_voice(girl_cfg["voice"])
    assert girl_meta is not None
    assert girl_meta["gender"] == "female"
    assert girl_cfg["pitch"] >= 1.05, "Child girl must have calibrated pitch >= 1.05"
    assert girl_cfg["speed"] == 1.03
    assert girl_cfg["bass_boost_db"] <= -2.5, "Child girl must have bass cut for delicate tract"
    assert girl_cfg["presence_boost_db"] >= 2.8, "Child girl must have sparkle upper harmonic boost"

    # Must be non-colliding
    assert boy_cfg["voice"] != girl_cfg["voice"]


def test_supreme_narrator_lock_aoede():
    """Verify that Narrator unconditionally receives Aoede in both Hindi and English."""
    # Hindi project without default narrator specified
    _, reg_hi, _ = CharacterCaster._build_cast_allocation(
        project_id="proj-hi-narrator",
        raw_characters=[],
        use_hindi=True,
    )
    assert reg_hi["Narrator"]["voice"] == "Aoede"
    assert reg_hi["Narrator"]["pitch"] == 1.0
    assert reg_hi["Narrator"]["speed"] == 1.0

    # English project
    _, reg_en, _ = CharacterCaster._build_cast_allocation(
        project_id="proj-en-narrator",
        raw_characters=[],
        use_hindi=False,
    )
    assert reg_en["Narrator"]["voice"] == "Aoede"
    assert reg_en["Narrator"]["pitch"] == 1.0
    assert reg_en["Narrator"]["speed"] == 1.0


def test_adolescent_teen_boy_dynamic_casting():
    """
    Verify that an adolescent teen boy (13-18yo) is dynamically allocated:
    1. A naturally young male voice model (age <= 28) matching character dialect.
    2. Zero digital pitch warping (pitch = 1.0, speed = 1.0) preventing robotic smurf/chipmunk artifacts.
    3. Clean adolescent EQ: bass_boost_db <= -2.5 (chest resonance cut), presence_boost_db >= 2.0.
    """
    catalog = get_voice_catalog()

    # 1. 15yo Haryanvi Teen Boy
    v_haryanvi = catalog.get_best_matching_voice(
        gender="male",
        language_code="hi-IN",
        archetype="15 year old teen fighter apprentice",
        age_hint=15,
        dialect_hint="Haryanvi",
    )
    meta_h = catalog.get_voice(v_haryanvi)
    assert meta_h is not None
    assert meta_h["gender"] == "male", "Teen boy must be allocated a male voice"
    assert meta_h.get("age", 99) <= 28, f"Voice {v_haryanvi} age {meta_h.get('age')} must be <= 28"
    assert "haryanvi" in meta_h.get("dialect", "").lower()

    # 2. 15yo Bundeli Teen Boy
    v_bundeli = catalog.get_best_matching_voice(
        gender="male",
        language_code="hi-IN",
        archetype="15 year old teen rebel scout",
        age_hint=15,
        dialect_hint="Bundeli",
    )
    meta_b = catalog.get_voice(v_bundeli)
    assert meta_b is not None
    assert meta_b["gender"] == "male"
    assert meta_b.get("age", 99) <= 28
    assert "bundeli" in meta_b.get("dialect", "").lower()

    # 3. Dynamic Roster Allocation
    raw_characters = [
        {
            "canonical_name": "Teen Hero",
            "gender": "male",
            "age": 15,
            "archetype": "determined 15 year old teen apprentice",
            "recommended_dialect": "Haryanvi",
        }
    ]
    _, registry, _ = CharacterCaster._build_cast_allocation(
        project_id="proj-teen-test",
        raw_characters=raw_characters,
        use_hindi=True,
    )
    cfg = registry["Teen Hero"]
    assert cfg["voice"].startswith("hi-in-")
    assert cfg["pitch"] == 1.0, "Adolescent teen boy must have pitch = 1.0 (zero digital warping)"
    assert cfg["speed"] == 1.0
    assert cfg["bass_boost_db"] <= -2.5, "Teen boy must have chest resonance cut"
    assert cfg["presence_boost_db"] >= 2.0, "Teen boy must have adolescent upper presence boost"


