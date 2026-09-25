#!/usr/bin/env python3
"""
Tests for Dramatic Validator & Gate 2.5 in audiobook_factory.dramaturgy.dramatic_validator
========================================================================================
Verifies fail-closed structural validation, anti-emotional teleportation detection,
epistemic isolation constraints, creative overreach detection, and Gate 2.5 audit.
"""

import json
import pytest
from pathlib import Path
from audiobook_factory.dramaturgy.dramatic_validator import DramaticValidator
from audiobook_factory.dramaturgy.contracts import (
    DramaticPlan,
    SceneDramaticPlan,
    DramaticBeat,
    CharacterDramaticObjective,
)
from audiobook_factory.gate_auditor import audit_gate2_5_dramatic_fidelity, GateAuditError


def test_validator_empty_screenplay():
    """Empty screenplay should fail immediately with EMPTY_SCREENPLAY error."""
    res = DramaticValidator.validate_screenplay_and_plan(segments=[])
    assert res.status == "FAIL"
    assert res.passed is False
    assert any(i.code == "EMPTY_SCREENPLAY" for i in res.issues)


def test_validator_non_monotonic_indexes():
    """Non-monotonic segment indices must be flagged as ERROR."""
    segments = [
        {"uid": "s1", "index": 1, "speaker": "Narrator", "type": "narration", "text": "Intro text."},
        {"uid": "s2", "index": 3, "speaker": "Marcus", "type": "dialogue", "text": "Skipped index!"},
    ]
    res = DramaticValidator.validate_screenplay_and_plan(segments=segments)
    assert res.status == "FAIL"
    assert any(i.code == "NON_MONOTONIC_INDEX" for i in res.issues)


def test_validator_orphan_scene_and_beat_refs():
    """Segments referencing non-existent scenes or beats must be flagged."""
    d_plan = DramaticPlan(
        chapter_id="ch_001",
        chapter_num=1,
        scenes=[
            SceneDramaticPlan(
                scene_id="scene_001",
                chapter_num=1,
                beats=[
                    DramaticBeat(
                        beat_id="scene_001_b001",
                        scene_id="scene_001",
                        index=1,
                    )
                ],
            )
        ],
    )

    segments = [
        {
            "uid": "s1",
            "index": 1,
            "speaker": "Marcus",
            "type": "dialogue",
            "text": "Hello there.",
            "scene_id": "scene_999",  # Non-existent
            "beat_id": "scene_001_b001",
            "actioning": "probe",
        },
        {
            "uid": "s2",
            "index": 2,
            "speaker": "Marcus",
            "type": "dialogue",
            "text": "Another line.",
            "scene_id": "scene_001",
            "beat_id": "beat_phantom_999",  # Non-existent beat
            "actioning": "probe",
        },
    ]

    res = DramaticValidator.validate_screenplay_and_plan(segments=segments, dramatic_plan=d_plan)
    assert any(i.code == "ORPHAN_SCENE_REF" for i in res.issues)
    assert any(i.code == "ORPHAN_BEAT_REF" for i in res.issues)


def test_validator_epistemic_isolation_breach():
    """Character uttering a fact marked UNKNOWN in epistemic constraints must fail with ERROR."""
    class MockEpistemicMemory:
        epistemic_constraints = {
            "Julian": {
                "UNKNOWN": ["forbidden poisoned well"],
                "KNOWN": ["village map"],
            }
        }

    segments = [
        {
            "uid": "s1",
            "index": 1,
            "speaker": "Julian",
            "type": "dialogue",
            "text": "Beware, they poured arsenic into the forbidden poisoned well!",
            "actioning": "warn",
        }
    ]

    res = DramaticValidator.validate_screenplay_and_plan(
        segments=segments,
        memory_context=MockEpistemicMemory(),
    )
    assert res.status == "FAIL"
    assert any(i.code == "EPISTEMIC_ISOLATION_BREACH" for i in res.issues)


def test_validator_emotional_teleportation():
    """Volatile emotional leaps without dramatic bridges trigger EMOTIONAL_TELEPORTATION warning."""
    segments = [
        {
            "uid": "s1",
            "index": 1,
            "speaker": "Elena",
            "type": "dialogue",
            "text": "Everything is serene and calm.",
            "surface_emotion": "calm",
            "actioning": "comfort",
        },
        {
            "uid": "s2",
            "index": 2,
            "speaker": "Elena",
            "type": "dialogue",
            "text": "I WILL DESTROY EVERYTHING YOU LOVE!",
            "surface_emotion": "bellowing_rage",
            "actioning": "threaten",
        },
    ]

    res = DramaticValidator.validate_screenplay_and_plan(segments=segments)
    assert any(i.code == "EMOTIONAL_TELEPORTATION" for i in res.issues)


def test_validator_creative_overreach():
    """Unsupported high-confidence subtext or invented SFX actions trigger overreach warnings."""
    source_text = "The room was quiet. A single candle flickered on the desk."
    segments = [
        {
            "uid": "s1",
            "index": 1,
            "speaker": "Julian",
            "type": "dialogue",
            "text": "Good evening.",
            "actioning": "probe",
            "subtext": "I am secretly an immortal dragon king from the astral plane.",
            "subtext_classification": "UNSUPPORTED",
            "subtext_confidence": 0.95,
        },
        {
            "uid": "s2",
            "index": 2,
            "speaker": "Foley",
            "type": "action",
            "text": "[SFX]",
            "sfx_cues": ["explosion"],
        },
    ]

    res = DramaticValidator.validate_screenplay_and_plan(
        segments=segments,
        source_text=source_text,
    )
    assert any(i.code == "CREATIVE_OVERREACH_SUBTEXT" for i in res.issues)
    assert any(i.code == "CREATIVE_OVERREACH_ACTION" for i in res.issues)


def test_audit_gate2_5_dramatic_fidelity(tmp_path):
    """Verifies that audit_gate2_5_dramatic_fidelity passes on valid screenplay and raises on invalid."""
    # 1. Create a valid script file
    script_data = {
        "chapter_num": 1,
        "title": "Chapter 1",
        "segments": [
            {
                "index": 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": "The wind howled through the ruined stone towers.",
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Marcus",
                "text": "Stay close, Julian.",
                "actioning": "reassure",
                "surface_emotion": "guarded",
            },
        ],
    }
    script_file = tmp_path / "chapter_001_script.json"
    with open(script_file, "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2)

    gate_result = audit_gate2_5_dramatic_fidelity(script_file=script_file)
    assert gate_result["status"] in ("PASS", "WARNING")
    assert gate_result["total_segments"] == 2

    # 2. Corrupt index to non-monotonic -> should raise GateAuditError
    script_data["segments"][1]["index"] = 5
    with open(script_file, "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2)

    with pytest.raises(GateAuditError) as exc_info:
        audit_gate2_5_dramatic_fidelity(script_file=script_file)
    assert "Gate 2.5 Dramatic Fidelity Failed" in str(exc_info.value)
