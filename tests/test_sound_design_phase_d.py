#!/usr/bin/env python3
"""
Unit and Integration Tests for Sound Design Phase D:
Supernatural & Magical Sound Language (Capability 11).
"""

import pytest
from audiobook_factory.sound_design.magical_sound import MagicalSoundEngine, get_magical_sound_engine
from audiobook_factory.sound_design.contracts import MagicalSoundSpec


def test_magical_sound_detection():
    engine = get_magical_sound_engine()

    segments = [
        {
            "segment_index": 1,
            "text": "Geralt formed the sign of Quen, and an amber shield flared around him.",
            "sfx_cues": [],
        },
        {
            "segment_index": 2,
            "text": "Harry whispered 'Lumos' as a gentle illumination sprang from his wand tip.",
            "sfx_cues": [],
        },
        {
            "segment_index": 3,
            "text": "With a loud crack, the wizard apparated into the empty hall.",
            "sfx_cues": [],
        },
    ]

    events = engine.detect_magic_events(segments, tension_level=0.7)
    assert len(events) >= 3

    quen_ev = [e for e in events if "Quen" in e.spell_or_artifact_name][0]
    assert quen_ev.stage == "shield_barrier"
    assert quen_ev.sonic_identity_family == "shield_barrier"

    lumos_ev = [e for e in events if "Lumos" in e.spell_or_artifact_name][0]
    assert lumos_ev.stage == "charge_hum"
    assert lumos_ev.sonic_identity_family == "celestial_illumination"

    teleport_ev = [e for e in events if e.stage == "teleport_displacement"][0]
    assert teleport_ev.stage == "teleport_displacement"


def test_magical_sound_sequence_synthesis():
    engine = get_magical_sound_engine()

    # Synthesize full 3-stage spell sequence for Aard
    seq = engine.synthesize_spell_sequence("Aard", power_level="high_potency")
    assert len(seq) == 3
    stages = [s.stage for s in seq]
    assert stages == ["charge_hum", "release_burst", "impact_strike"]
    assert all(s.sonic_identity_family == "kinetic_telekinetic" for s in seq)
    assert any(s.relative_intensity == "explosive_impact" for s in seq)
