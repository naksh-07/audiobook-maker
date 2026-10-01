#!/usr/bin/env python3
"""
Test Suite: Architecture Auditor & LLM-Script Coordination Protocols.
Verifies:
1. Read-only audit guarantees (zero files created or modified).
2. Coordination contracts & schema shields (Pydantic v2 validation and repair).
3. Sonic Intelligence Bridge (bilingual normalization, tiered FTS5 expansion, and hit rate calculation).
4. Subsystem audit integrity across the 10 architecture domains.
"""

import os
import json
import pytest
from pathlib import Path

from audiobook_factory.coordination_contracts import (
    strip_markdown_fences,
    RawScreenplaySegmentContract,
    ScreenplayScriptPayload,
    RawMusicCueContract,
    RawFoleyEventContract,
    CoordinationValidationError,
)
from audiobook_factory.sonic_intelligence_bridge import SonicIntelligenceBridge
from audiobook_factory.architecture_auditor import ArchitectureAuditor
from audiobook_factory.sound_bank import get_sound_bank


# -----------------------------------------------------------------------------
# Test 1: Markdown Fence Stripping & JSON Extraction
# -----------------------------------------------------------------------------
def test_strip_markdown_fences():
    raw_with_fence = "```json\n[{\"index\": 1, \"speaker\": \"Narrator\", \"text\": \"Hello\"}]\n```"
    cleaned = strip_markdown_fences(raw_with_fence)
    assert cleaned.startswith("[")
    assert cleaned.endswith("]")

    raw_with_text_fence = "```\n{\"segments\": []}\n```"
    cleaned_text = strip_markdown_fences(raw_with_text_fence)
    assert cleaned_text == "{\"segments\": []}"

    plain = "{\"test\": 123}"
    assert strip_markdown_fences(plain) == plain


# -----------------------------------------------------------------------------
# Test 2: Screenplay Segment Schema & Speaker Sanitization
# -----------------------------------------------------------------------------
def test_screenplay_segment_speaker_sanitization():
    # Pronoun leak should be coerced to Narrator
    seg1 = RawScreenplaySegmentContract(
        index=1,
        type="dialogue",
        speaker="उसने",
        text="\"हम कल मिलेंगे।\"",
    )
    assert seg1.speaker == "Narrator"
    assert seg1.text == "हम कल मिलेंगे।"

    # Punctuation wrapping should be cleanly stripped
    seg2 = RawScreenplaySegmentContract(
        index=2,
        type="dialogue",
        speaker="[Vernon Dursley]:",
        text="Get inside now!",
    )
    assert seg2.speaker == "Vernon Dursley"
    assert seg2.text == "Get inside now!"


# -----------------------------------------------------------------------------
# Test 3: Screenplay Segment Markdown Leaks Cleanup
# -----------------------------------------------------------------------------
def test_screenplay_segment_text_cleanup():
    dirty_text = (
        "### Scene 1\n"
        "Note: Character is nervous.\n"
        "This is the real spoken line.\n"
        "```commentary```"
    )
    seg = RawScreenplaySegmentContract(
        index=1,
        type="narration",
        speaker="Narrator",
        text=dirty_text,
    )
    assert "###" not in seg.text
    assert "Note:" not in seg.text
    assert "This is the real spoken line." in seg.text


# -----------------------------------------------------------------------------
# Test 4: Screenplay Payload JSON Auto-Repair
# -----------------------------------------------------------------------------
def test_screenplay_payload_parsing_and_repair():
    raw_response = (
        "Here is the dramatized screenplay you requested:\n\n"
        "```json\n"
        "[\n"
        "  {\n"
        "    \"index\": 1,\n"
        "    \"type\": \"narration\",\n"
        "    \"speaker\": \"Narrator\",\n"
        "    \"text\": \"सूरज डूब रहा था।\"\n"
        "  },\n"
        "  {\n"
        "    \"index\": 2,\n"
        "    \"type\": \"action\",\n"
        "    \"speaker\": \"Foley\",\n"
        "    \"text\": \"[ACTION]\"\n"
        "  }\n"
        "]\n"
        "```\n"
        "Hope this helps!"
    )
    payload = ScreenplayScriptPayload.from_raw_json(raw_response)
    assert len(payload.segments) == 2
    assert payload.segments[0].speaker == "Narrator"
    assert payload.segments[1].type == "action"
    assert payload.segments[1].speaker == "Foley"


# -----------------------------------------------------------------------------
# Test 5: Sonic Intelligence Bilingual Normalization & Expansion
# -----------------------------------------------------------------------------
def test_sonic_intelligence_query_expansion():
    bridge = SonicIntelligenceBridge(sound_bank=get_sound_bank())

    # Hindi anchor query for door
    candidates = bridge.normalize_and_expand_query("दरवाजा चूं", category="foley")
    joined = " ".join(candidates).lower()
    assert "door" in joined or "creak" in joined

    # Hindi anchor query for car
    car_cands = bridge.normalize_and_expand_query("कार का दरवाजा", category="foley")
    car_joined = " ".join(car_cands).lower()
    assert "car" in car_joined or "door" in car_joined

    # Flowery music query with stop words
    music_cands = bridge.normalize_and_expand_query(
        "very subtle and deep emotional solo cello in the background",
        category="music"
    )
    assert len(music_cands) >= 2
    # Stop words like "very", "and", "the", "in" should be filtered from primary tokens
    assert "very" not in music_cands[0].split()


# -----------------------------------------------------------------------------
# Test 6: Sonic Intelligence Combat Asset Guard
# -----------------------------------------------------------------------------
def test_sonic_intelligence_combat_guard():
    bridge = SonicIntelligenceBridge(sound_bank=get_sound_bank())

    # In a non-combat domestic scene, combat terms like swords should be blocked
    cand_path, tier, _ = bridge.resolve_asset_with_fallback(
        query="tea cup tableware",
        category="foley",
        is_combat_scene=False,
    )
    if cand_path:
        fname = cand_path.name.lower()
        assert "sword" not in fname
        assert "blade" not in fname
        assert "axe" not in fname


# -----------------------------------------------------------------------------
# Test 7: Architecture Auditor Read-Only Guarantee
# -----------------------------------------------------------------------------
def test_architecture_auditor_read_only(tmp_path):
    # Create a dummy project structure
    proj_dir = tmp_path / "test_project"
    proj_dir.mkdir()
    (proj_dir / "extracted").mkdir()
    (proj_dir / "extracted" / "chapter_001.md").write_text("# Chapter 1\n" + ("A" * 500), encoding="utf-8")

    # Record directory state before audit
    files_before = {str(p): p.stat().st_mtime for p in proj_dir.rglob("*")}

    # Run audit
    auditor = ArchitectureAuditor(project_dir=proj_dir)
    report = auditor.audit_all()

    # Verify no files were created or modified
    files_after = {str(p): p.stat().st_mtime for p in proj_dir.rglob("*")}
    assert files_before == files_after, "Read-only audit must not create or modify any project files!"
    assert report["read_only"] is True
    assert "subsystems" in report
    assert report["subsystems"]["system1_ingestion"]["status"] == "PASS"


# -----------------------------------------------------------------------------
# Test 8: Live Project Chapter 1 Architecture Audit (Read-Only)
# -----------------------------------------------------------------------------
def test_live_project_read_only_audit():
    live_proj = Path("audiobooks/projects/harry_potter_or_paras_patthar").resolve()
    if not live_proj.exists():
        pytest.skip("Live project harry_potter_or_paras_patthar not found")

    auditor = ArchitectureAuditor(project_dir=live_proj)
    report = auditor.audit_all(chapter_num=1)

    assert report["read_only"] is True
    summary = report["summary"]
    assert summary["overall_score"] >= 70.0
    assert summary["failed"] == 0, f"No subsystem should FAIL on certified Chapter 1: {report['subsystems']}"
    assert "sonic_intelligence_hit_rate" in summary
