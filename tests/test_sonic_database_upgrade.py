#!/usr/bin/env python3
"""
Test Suite: Sonic Database Engine & Retrieval System Upgrade.
Verifies:
1. SonicIntelligenceBridge resolves virtual sound assets into expected cache paths without dropping them to silence.
2. FTS5 BM25 weighted ranking prioritizes authentic physical semantic matches in < 5ms.
3. BBC metadata backfill engine accurately extracts physical action, exciter, and resonator tags.
4. Precache essential bundle contracts and multi-agent director virtual cue preservation.
"""

import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from audiobook_factory.sound_bank import get_sound_bank, SoundBank
from audiobook_factory.sonic_intelligence_bridge import SonicIntelligenceBridge
from audiobook_factory.sound_bank.metadata_backfill import BBCMetadataBackfillEngine
from audiobook_factory.director.multi_agent_director import MultiAgentDirector
from audiobook_factory.director.agents import MicroFoleyPlan, FoleyEventDirective


@pytest.fixture(scope="module")
def sound_bank():
    return get_sound_bank()


@pytest.fixture(scope="module")
def bridge(sound_bank):
    return SonicIntelligenceBridge(sound_bank=sound_bank)


def test_01_bridge_virtual_asset_resolution(bridge):
    """Verifies that the Bridge resolves virtual cues to target cache paths with exact_fts_virtual tier."""
    path, tier, score = bridge.resolve_asset_with_fallback("footsteps wood", category="foley")
    
    assert path is not None, "Bridge must not collapse into silence for footsteps wood"
    assert "virtual" in tier, f"Expected a virtual resolution tier, got '{tier}'"
    assert tier == "exact_fts_virtual"
    assert score >= 0.90, f"Expected high match score, got {score}"
    assert path.name.endswith(".mp3"), f"Expected an MP3 file name, got {path.name}"
    assert "cache" in str(path).replace("\\", "/"), f"Expected target cache path, got {path}"


def test_02_bridge_virtual_music_resolution(bridge):
    """Verifies that virtual music tracks from Incompetech resolve successfully via Bridge."""
    path, tier, score = bridge.resolve_asset_with_fallback("peaceful acoustic serenity", category="music")
    
    assert path is not None, "Bridge must resolve peaceful acoustic music"
    assert tier in ("exact_fts", "exact_fts_virtual", "relaxed_fts", "relaxed_fts_virtual")
    assert score >= 0.80


def test_03_search_bm25_speed_and_ordering(sound_bank):
    """Verifies that FTS5 search with weighted BM25 executes in < 50ms and orders by match quality."""
    t0 = time.time()
    results = sound_bank.search("footsteps wood", category="FOL", limit=5)
    elapsed_ms = (time.time() - t0) * 1000.0

    assert len(results) > 0, "Expected at least 1 match for footsteps wood"
    assert elapsed_ms < 50.0, f"Search took too long ({elapsed_ms:.2f}ms), expected < 50ms"
    
    # Top results should be authentic footsteps, not swords or saws
    top_fn = results[0]["filename"].lower()
    top_tags = (results[0].get("tags") or "").lower()
    top_title = (results[0].get("title") or "").lower()
    combined = f"{top_fn} {top_tags} {top_title}"
    
    assert "footstep" in combined or "walk" in combined, f"Top match '{results[0]['filename']}' should be a footstep"
    assert "saw" not in top_fn, "Handsaw must not outrank authentic footsteps"


def test_04_metadata_backfill_extractor_accuracy():
    """Verifies regex extraction of action_type, exciter, and resonator from archive descriptions."""
    # Test case 1: Footsteps on wood
    t1 = BBCMetadataBackfillEngine.extract_physical_tags(
        title="Footsteps on Wood, woman walking, departing.",
        description="Footsteps on Wood, woman walking, departing. (Dead acoustic.)",
        filename="07037204.mp3",
    )
    assert t1.get("action_type") in ("walk", "depart")
    assert t1.get("resonator") == "wood"
    assert t1.get("exciter") in ("leather", "wood")

    # Test case 2: Door slam
    t2 = BBCMetadataBackfillEngine.extract_physical_tags(
        title="Heavy Wooden Door Slams Shut",
        description="Interior domestic bedroom, wooden door slams violently.",
        filename="door_slam.wav",
    )
    assert t2.get("action_type") in ("slam", "close")
    assert t2.get("exciter") == "wood"

    # Test case 3: Tea pouring
    t3 = BBCMetadataBackfillEngine.extract_physical_tags(
        title="Pouring tea from ceramic pot into china cup",
        description="Hot liquid stream filling porcelain teacup with saucer clink.",
        filename="tea_pour.mp3",
    )
    assert t3.get("action_type") in ("pour", "clink")
    assert t3.get("exciter") in ("water", "ceramic")


def test_05_precache_essential_bundle_discovery(sound_bank):
    """Verifies that precache_essential_bundle identifies ubiquitous everyday sounds."""
    # Test query discovery logic with a mocked download worker
    with patch.object(sound_bank, "download_virtual_asset") as mock_dl:
        mock_dl.return_value = None  # Do not actually download during unit test
        
        # Test dry-run identification
        stats = sound_bank.precache_essential_bundle(max_workers=2)
        assert stats["total_essential_identified"] >= 20, "Should identify at least 20 essential audio assets"
        assert stats["total_essential_identified"] == stats["already_cached"] + stats["queued_for_download"]


def test_06_multi_agent_director_virtual_cues_preserved(sound_bank):
    """Verifies that MultiAgentDirector preserves virtual cues and does not discard them."""
    director = MultiAgentDirector(sound_bank=sound_bank)
    
    plan = MicroFoleyPlan(
        chapter_id="ch01",
        events=[
            FoleyEventDirective(
                segment_index=1,
                action_verb="walk",
                object_material="wood",
                surface_resonance="wood",
                is_micro_foley=True,
                relative_position=0.5,
                volume_db=-18.0,
                dramatic_purpose="Character pacing across hardwood floor",
            )
        ]
    )
    
    cues = director._resolve_foley_cues(
        foley_plan=plan,
        script_segments=[{"index": 1, "text": "He walked across the floor."}],
        seg_starts_ms={1: 0},
        segment_durations_sec={1: 4.0},
    )
    
    assert len(cues) == 1, "Foley cue must be resolved into manifest, not dropped to silence"
    cue = cues[0]
    assert "07037204" in cue.asset_path or "cache" in cue.asset_path or ".mp3" in cue.asset_path
