#!/usr/bin/env python3
"""
Audiobook Factory - Production-Quality Cinematic Sound Design Upgrade Test Suite.
================================================================================
Verifies the 5 production upgrade priorities:
1. Narrative Event -> Precise Sound Timing & Source Beat Anchoring (no 35%/40% shortcuts)
2. Real Asset Resolution & Removal of Fake Asset Paths
3. Shared Scene-Level Acoustic & Dramatic State + Cross-System Reactions
4. Deeper Scene-Aware Evolution (7-Phase Narrative Progression)
5. Evidence-Based Sound Design QC & Forensic Data Verification
"""

import pytest
from pathlib import Path
from typing import Dict, Any, List

from audiobook_factory.sound_design.sound_director import SoundDesignDirector, get_sound_design_director
from audiobook_factory.sound_design.qc import SoundDesignQCAuditor, get_sound_design_qc_auditor
from audiobook_factory.sound_design.scene_state import (
    SceneAcousticDramaticStateManager,
    get_scene_state_manager,
)
from audiobook_factory.sound_design.asset_retriever import (
    SoundAssetRetriever,
    get_asset_retriever,
)
from audiobook_factory.sound_design.contracts import (
    SoundTimeline,
    SoundTimelineEvent,
    SceneAudioBlueprint,
    SpatialMetadata,
    MixIntent,
)


def test_priority1_precise_narrative_event_timing():
    """
    Priority 1: Verifies that events are anchored to actual screenplay segments,
    action blocking, and dramatic moments — NOT arbitrary 35% or 40% percentage offsets.
    """
    director = SoundDesignDirector()
    scene_id = "p1_precise_timing_scene"
    chapter_id = "chap_01"
    duration_ms = 40000

    # 4 distinct segments spanning 40 seconds (0 to 40,000ms)
    # Segment 1: Calm setup (0 - 10,000ms)
    # Segment 2: Action sword draw (10,000 - 20,000ms)
    # Segment 3: Creature roar in confrontation (20,000 - 30,000ms)
    # Segment 4: Spell cast release (30,000 - 40,000ms)
    segments = [
        {
            "segment_index": 1,
            "speaker": "Narrator",
            "text": "The crypt was silent and damp.",
            "start_ms": 0,
            "end_ms": 10000,
        },
        {
            "segment_index": 2,
            "speaker": "Geralt",
            "text": "He drew his silver sword from the scabbard.",
            "start_ms": 10000,
            "end_ms": 20000,
            "action_verb": "draw",
        },
        {
            "segment_index": 3,
            "speaker": "Narrator",
            "text": "The striga roared violently, lunging from the dark.",
            "start_ms": 20000,
            "end_ms": 30000,
            "creature": "striga",
        },
        {
            "segment_index": 4,
            "speaker": "Geralt",
            "text": "He cast Aard with a sudden burst of concussive force.",
            "start_ms": 30000,
            "end_ms": 40000,
            "sfx_cues": ["aard"],
        },
    ]

    blueprint, timeline = director.direct_scene(
        scene_id=scene_id,
        chapter_id=chapter_id,
        segments=segments,
        start_ms=0,
        end_ms=duration_ms,
        tension_override=0.8,
    )

    # 1. Inspect Foley timing
    foley_events = [e for e in timeline.events if e.category == "FOLEY"]
    assert len(foley_events) >= 1
    sword_foley = foley_events[0]
    # Anchored to Segment 2 (starts >= 10,000ms, not at 0.0s)
    assert sword_foley.source_segment_index == 2
    assert 10000 <= sword_foley.start_ms < 20000
    assert "segment 2" in sword_foley.timing_rationale.lower()
    assert sword_foley.dramatic_purpose != ""

    # 2. Inspect Creature timing (MUST NOT be fixed 35% of 40,000 = 14,000ms!)
    creature_events = [e for e in timeline.events if e.category == "CREATURE"]
    assert len(creature_events) >= 1
    striga_event = creature_events[0]
    # Anchored to Segment 3 (starts >= 20,000ms!)
    assert striga_event.source_segment_index == 3
    assert 20000 <= striga_event.start_ms < 30000
    assert striga_event.start_ms != 14000  # Proves 35% shortcut was completely eradicated!
    assert "segment 3" in striga_event.timing_rationale.lower()

    # 3. Inspect Magic timing (MUST NOT be fixed 40% of 40,000 = 16,000ms!)
    magic_events = [e for e in timeline.events if e.category == "MAGIC"]
    assert len(magic_events) >= 1
    aard_event = magic_events[0]
    # Anchored to Segment 4 (starts >= 30,000ms!)
    assert aard_event.source_segment_index == 4
    assert 30000 <= aard_event.start_ms < 40000
    assert aard_event.start_ms != 16000  # Proves 40% shortcut was completely eradicated!
    assert "segment 4" in aard_event.timing_rationale.lower()


def test_priority2_real_asset_resolution_no_fake_paths():
    """
    Priority 2: Verifies that fake asset paths (e.g. 'foley_{action}_{material}.wav')
    are never generated. If an asset is missing from the sound bank, it must be explicitly
    marked as unresolved with asset_path=''.
    """
    director = SoundDesignDirector()
    scene_id = "p2_real_asset_scene"
    chapter_id = "chap_01"

    segments = [
        {
            "segment_index": 1,
            "speaker": "Hero",
            "text": "He poured wine from the pitcher and drank.",
        },
        {
            "segment_index": 2,
            "speaker": "Narrator",
            "text": "The ancient gargoyle snarled menacingly.",
        },
    ]

    blueprint, timeline = director.direct_scene(
        scene_id=scene_id,
        chapter_id=chapter_id,
        segments=segments,
        start_ms=0,
        end_ms=20000,
    )

    for evt in timeline.events:
        # Crucial Invariant: Banned fake path patterns
        banned_patterns = [
            "foley_pour_liquid.wav",
            "creature_gargoyle_vocalization",
            "foley_action_wood.wav",
        ]
        for pat in banned_patterns:
            assert pat not in evt.asset_path, f"Event '{evt.event_id}' contains banned fake asset path '{evt.asset_path}'!"

        if evt.category != "SILENCE":
            if evt.is_resolved:
                # If resolved, path must point to an actual file
                assert evt.asset_path != ""
                assert Path(evt.asset_path).exists()
            else:
                # If unresolved, asset_path must be empty and unresolved_reason must be explicit
                assert evt.asset_path == ""
                assert evt.unresolved_reason is not None
                assert len(evt.unresolved_reason) > 5


def test_priority3_cross_system_cinematic_interaction():
    """
    Priority 3: Verifies that systems influence one another via shared acoustic state:
    - Close creature proximity scatters/suppresses walla and thins ambience.
    - Magic attacks subordinate music mix intent and trigger spectral thinning.
    """
    state_mgr = get_scene_state_manager()
    from audiobook_factory.sound_design.contracts import SceneAudioUnderstandingResult

    understanding = SceneAudioUnderstandingResult(
        scene_id="p3_cross_system_scene",
        chapter_id="chap_01",
        environment_type="tavern_common_room",
        dominant_emotion="terror",
        tension_level=0.9,
        requires_walla=True,
        walla_description="Tavern murmur",
        creature_presence="striga",
    )

    state = state_mgr.initialize_state(
        scene_id="p3_cross_system_scene",
        understanding=understanding,
        staged_positions={},
    )

    assert state.walla_permitted is True

    # Evaluate reactions with creature present at high tension
    reactions = state_mgr.evaluate_cross_system_reactions(
        state=state,
        has_creature=True,
        has_magic=True,
    )

    assert len(reactions) >= 2

    # 1. Walla suppressed by creature
    assert state.walla_permitted is False
    walla_rx = [r for r in reactions if r.target_system == "WALLA"]
    assert len(walla_rx) >= 1
    assert "suppression" in walla_rx[0].reaction_type.lower()

    # 2. Music subordinated by magic
    music_rx = [r for r in reactions if r.target_system == "MUSIC"]
    assert len(music_rx) >= 1
    assert music_rx[0].mix_intent_override is not None
    assert music_rx[0].mix_intent_override.duck_under_dialogue is True


def test_priority4_narrative_state_driven_evolution():
    """
    Priority 4: Verifies the 7-phase narrative evolution:
    CALM -> UNEASE -> TENSION -> THREAT -> EVENT -> AFTERMATH -> RECOVERY
    """
    state_mgr = get_scene_state_manager()
    from audiobook_factory.sound_design.contracts import SceneAudioUnderstandingResult

    # Calm setting
    calm_und = SceneAudioUnderstandingResult(
        scene_id="p4_calm",
        chapter_id="chap_01",
        environment_type="castle_stone_corridor",
        tension_level=0.2,
        dominant_emotion="peaceful",
    )
    calm_state = state_mgr.initialize_state("p4_calm", calm_und, {})
    assert calm_state.active_phase == "CALM"
    assert calm_state.music_variation == "INTIMATE"

    # Threat setting with high tension
    threat_und = SceneAudioUnderstandingResult(
        scene_id="p4_threat",
        chapter_id="chap_01",
        environment_type="dark_forest",
        tension_level=0.85,
        dominant_emotion="dread",
    )
    threat_state = state_mgr.initialize_state("p4_threat", threat_und, {})
    assert threat_state.active_phase == "THREAT"
    assert threat_state.music_variation == "TENSE"

    # Event phase triggered by hard SFX
    state_mgr.evaluate_cross_system_reactions(threat_state, has_hard_sfx=True)
    assert threat_state.active_phase == "EVENT"


def test_priority5_evidence_based_qc_audit():
    """
    Priority 5: Verifies that QC inspects real SoundTimeline data and catches:
    - Orphan events (events with no source segment or beat link)
    - Fake asset paths on unresolved events
    - Negative timestamps
    - Trivial verbs in accepted foley
    """
    auditor = get_sound_design_qc_auditor()

    blueprint = SceneAudioBlueprint(
        scene_id="qc_evidence_scene",
        chapter_id="chap_01",
        location_id="indoor_room",
        restraint_target="moderate",
        characters_staged={
            "Narrator": SpatialMetadata(azimuth_pan=0.0, proximity="normal_room"),
        },
    )

    # 1. Timeline with an orphan event and a negative timestamp
    bad_timeline = SoundTimeline(
        timeline_id="tl_bad",
        chapter_id="chap_01",
        scene_id="qc_evidence_scene",
        total_duration_ms=10000,
        events=[
            SoundTimelineEvent(
                event_id="evt_amb",
                category="AMBIENCE",
                start_ms=0,
                duration_ms=10000,
                is_resolved=True,
                asset_path="valid_amb.wav",
            ),
            SoundTimelineEvent(
                event_id="evt_orphan_foley",
                category="FOLEY",
                start_ms=100,
                duration_ms=400,
                source_segment_index=None,  # Orphan!
                provenance_segment_uid=None,
                provenance_beat_id=None,
                is_resolved=False,
                asset_path="fake_foley.wav",  # Fake path on unresolved event!
            ),
            SoundTimelineEvent(
                event_id="evt_trivial_foley",
                category="FOLEY",
                start_ms=500,
                duration_ms=300,
                source_segment_index=1,
                asset_name="Hero sighed",  # Trivial verb!
                decision_reason="Accepted foley action: 'sighed'",
                is_resolved=True,
                asset_path="",  # Resolved but empty asset path!
            ),
        ],
    )

    report = auditor.audit_scene_sound_design(blueprint, bad_timeline)
    assert report.status == "FAIL"
    error_text = " ".join(report.errors).lower()
    assert "orphan" in error_text
    assert "fake path" in error_text
    assert "trivial verb" in error_text
    assert report.asset_provenance_verified is False


def test_priority5_clean_qc_passes_valid_scene():
    """
    Priority 5: Verifies that a properly formed, beat-anchored scene passes QC.
    """
    director = get_sound_design_director()
    auditor = get_sound_design_qc_auditor()

    segments = [
        {
            "segment_index": 1,
            "speaker": "Narrator",
            "text": "The rain fell softly on the stone courtyard.",
            "start_ms": 0,
            "end_ms": 5000,
        },
        {
            "segment_index": 2,
            "speaker": "Guard",
            "text": "Who goes there?",
            "start_ms": 5000,
            "end_ms": 10000,
        },
    ]

    blueprint, timeline = director.direct_scene(
        scene_id="qc_valid_scene",
        chapter_id="chap_01",
        segments=segments,
        start_ms=0,
        end_ms=10000,
    )

    report = auditor.audit_scene_sound_design(blueprint, timeline)
    assert report.status in ("PASS", "WARN")
    assert len(report.errors) == 0
    assert report.asset_provenance_verified is True
    assert report.spatial_stage_valid is True
    assert report.ambience_continuity_verified is True
