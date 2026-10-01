#!/usr/bin/env python3
"""
Unit tests for Gate 2 Anti-Swallow Quality Gate Assertion.
Verifies:
1. Rejection of scripts where narration segments contain un-split dialogue quotes.
2. Acceptance of clean scripts where all dialogue is isolated into dedicated segments.
3. Enforcement of canonical speaker keys from character_roster.json.
"""

import json
import pytest
from pathlib import Path

from audiobook_factory.gate_auditor import audit_gate2_script, GateAuditError


@pytest.fixture
def temp_gate2_env(tmp_path):
    pdir = tmp_path / "test_proj"
    pdir.mkdir(parents=True, exist_ok=True)
    scripts_dir = pdir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    # Character roster with Mr. Dursley and Narrator
    roster = {
        "project_id": "proj-test",
        "characters": [
            {"english_name": "Mr. Dursley", "hindi_name": "मिस्टर डर्स्ली", "gender": "male", "aliases": ["Vernon"]},
        ]
    }
    with open(pdir / "character_roster.json", "w", encoding="utf-8") as rf:
        json.dump(roster, rf)

    return pdir, scripts_dir


def test_gate2_fails_on_swallowed_dialogue(temp_gate2_env):
    pdir, scripts_dir = temp_gate2_env
    bad_script_path = scripts_dir / "chapter_001_bad_script.json"

    # Segment 1 has narrator reading a direct quote ("शैतान कहीं का")
    bad_data = {
        "segments": [
            {
                "index": 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": "मिस्टर डर्स्ली ने गुस्से में बड़बड़ाया, \"शैतान कहीं का!\" और कार में बैठ गए।",
                "emotion": "tense"
            }
        ]
    }
    with open(bad_script_path, "w", encoding="utf-8") as f:
        json.dump(bad_data, f, ensure_ascii=False)

    with pytest.raises(GateAuditError) as exc_info:
        audit_gate2_script(bad_script_path, project_dir=pdir)

    assert "Direct dialogue quotes detected inside narration segments" in str(exc_info.value)


def test_gate2_passes_on_isolated_dialogue(temp_gate2_env):
    pdir, scripts_dir = temp_gate2_env
    clean_script_path = scripts_dir / "chapter_001_clean_script.json"

    # Properly split segments
    clean_data = {
        "segments": [
            {
                "index": 1,
                "type": "narration",
                "speaker": "Narrator",
                "text": "मिस्टर डर्स्ली ने गुस्से में बड़बड़ाया और कार में बैठ गए।",
                "emotion": "neutral"
            },
            {
                "index": 2,
                "type": "dialogue",
                "speaker": "Mr. Dursley",
                "text": "शैतान कहीं का!",
                "emotion": "angry"
            }
        ]
    }
    with open(clean_script_path, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, ensure_ascii=False)

    res = audit_gate2_script(clean_script_path, project_dir=pdir)
    assert res["status"] == "PASS"
    assert res["total_segments"] == 2
    assert res["speaker_breakdown"]["Mr. Dursley"] == 1
    assert res["speaker_breakdown"]["Narrator"] == 1


def test_gate2_fails_on_unauthorized_speaker(temp_gate2_env):
    pdir, scripts_dir = temp_gate2_env
    unauthorized_script_path = scripts_dir / "chapter_001_unauth_script.json"

    # Unknown character not in roster
    unauth_data = {
        "segments": [
            {
                "index": 1,
                "type": "dialogue",
                "speaker": "Random Alien",
                "text": "Hello Earth!",
                "emotion": "neutral"
            }
        ]
    }
    with open(unauthorized_script_path, "w", encoding="utf-8") as f:
        json.dump(unauth_data, f, ensure_ascii=False)

    with pytest.raises(GateAuditError) as exc_info:
        audit_gate2_script(unauthorized_script_path, project_dir=pdir)

    assert "Found non-canonical speakers" in str(exc_info.value)
