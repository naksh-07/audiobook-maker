#!/usr/bin/env python3
"""
Audiobook Factory - Adversarial Audit Remediation Test Suite.
============================================================
Exhaustively tests the remediation of all P0, P1, and P2 flaws identified
by the adversarial sound design expert panel:
- P0-1: Absolute chapter timestamp coordinate normalization in SilenceEngine & QC.
- P0-2: Music cue duration boundary overflow clamping past scene end.
- P0-3: SpatialTrajectory literal matching ("left_to_right", "right_to_left").
- P1-1: Adapter ambience reuse without duplicate state tracking / duration inflation.
- P1-2: Hard SFX proportional start timing (zero clumping at 0.0s).
- P1-3: Case-insensitive Narrator center-lock QC check ("Narrator", "NARRATOR").
- P1-4: Trivial physical motion rejection under elevated tension.
- P1-5: False-positive token substring avoidance ("drawer", "radish") & segment deduplication.
- P2-1: Engine reset hooks for multi-book batch execution.
"""

import pytest
from pathlib import Path
from audiobook_factory.sound_design.contracts import (
    ActionCandidate,
    SceneAudioUnderstandingResult,
    SceneAudioBlueprint,
    SoundTimeline,
    SoundTimelineEvent,
    SpatialMetadata,
    MixIntent,
)
from audiobook_factory.sound_design.silence_engine import SilenceEngine, get_silence_engine
from audiobook_factory.sound_design.music_motif_director import MusicCueDirector
from audiobook_factory.sound_design.spatial_acoustics import SpatialGeographyEngine
from audiobook_factory.sound_design.ambience_engine import AmbienceEngine, get_ambience_engine
from audiobook_factory.sound_design.sound_director import SoundDesignDirector
from audiobook_factory.sound_design.adapter import SoundDesignAdapter
from audiobook_factory.sound_design.qc import SoundDesignQCAuditor
from audiobook_factory.sound_design.foley_engine import FoleyEngine
from audiobook_factory.sound_design.scene_understanding import SceneAudioAnalyzer
from audiobook_factory.sonic_bible import SonicBible, LeitmotifDefinition


def test_p0_silence_density_with_absolute_chapter_offsets():
    """P0-1: Ensure density is not collapsed to 0.0% when scene starts at chapter offset (e.g. 45000ms)."""
    engine = SilenceEngine()
    total_duration_ms = 30000
    scene_start_ms = 45000

    # Events at absolute chapter timestamps: 50,000ms - 58,000ms (8,000ms active sound)
    active_spans = [
        (50000, 54000),  # 4000ms
        (56000, 60000),  # 4000ms
    ]

    # Test with explicit scene_start_ms
    res_explicit = engine.evaluate_scene_density(
        total_duration_ms=total_duration_ms,
        active_sound_spans=active_spans,
        restraint_target="moderate",
        scene_start_ms=scene_start_ms,
    )
    assert res_explicit["density"] > 0.0
    assert pytest.approx(res_explicit["density"], 0.01) == round(8000 / 30000, 3)

    # Test with auto-detected offset (scene_start_ms=None)
    res_auto = engine.evaluate_scene_density(
        total_duration_ms=total_duration_ms,
        active_sound_spans=active_spans,
        restraint_target="moderate",
        scene_start_ms=None,
    )
    assert res_auto["density"] > 0.0


def test_p0_music_cue_duration_boundary_overflow_clamping():
    """P0-2: Ensure music cue duration is strictly clamped within scene bounds."""
    director = MusicCueDirector()
    start_ms = 10000
    end_ms = 16000  # 6-second short scene

    cues = director.direct_scene_cues(
        scene_id="short_scene_overflow_test",
        start_ms=start_ms,
        end_ms=end_ms,
        tension_level=0.5,
        dominant_emotion="neutral",
        restraint_target="moderate",
    )
    assert len(cues) == 1
    cue = cues[0]
    # Cue start + duration must NEVER exceed scene end_ms
    assert cue.start_ms + cue.duration_ms <= end_ms
    assert cue.start_ms >= start_ms


def test_p0_spatial_trajectory_literal_matching():
    """P0-3: Ensure standard contracts SpatialTrajectory literals update pan correctly without crash."""
    geography = SpatialGeographyEngine()
    scene_id = "trajectory_test_scene"
    geography.stage_scene_characters(scene_id, ["Protagonist"])

    # left_to_right should update pan to +0.50
    updated_lr = geography.apply_trajectory(scene_id, "Protagonist", "left_to_right")
    assert updated_lr.azimuth_pan == 0.50
    assert updated_lr.trajectory == "left_to_right"

    # right_to_left should update pan to -0.50
    updated_rl = geography.apply_trajectory(scene_id, "Protagonist", "right_to_left")
    assert updated_rl.azimuth_pan == -0.50
    assert updated_rl.trajectory == "right_to_left"


def test_p1_adapter_no_duplicate_ambience_state_mutation():
    """P1-1: Ensure adapter reuses timeline ambience without double-calling build_scene_ambience."""
    adapter = SoundDesignAdapter()
    engine = adapter.ambience_engine
    engine.reset()

    chapter_id = "ch_audit_test"
    segments = [
        {"index": 1, "speaker": "Narrator", "text": "The wind howled.", "acoustic_env": "castle_stone_corridor"}
    ]

    out = adapter.direct_and_adapt_scene(
        scene_id="sc_01",
        chapter_id=chapter_id,
        segments=segments,
        start_ms=0,
        end_ms=20000,
    )

    state = engine._state_tracker.get(chapter_id)
    assert state is not None
    # Accumulated duration should be exactly 20000ms, NOT 40000ms
    assert state.accumulated_duration_ms == 20000
    assert out["scene_acoustic_profile"] is not None


def test_p1_hard_sfx_segment_proportional_timing_no_zero_clumping():
    """P1-2: Ensure multiple Hard SFX without start_ms are proportionally timed and do not clump at 0.0s."""
    director = SoundDesignDirector()
    scene_id = "sc_hardsfx_clumping_test"
    chapter_id = "ch_01"

    # 3 segments with distinct physical impacts and NO start_ms
    segments = [
        {"index": 1, "speaker": "Narrator", "text": "The iron gate slammed shut with a deafening boom."},
        {"index": 2, "speaker": "Hero", "text": "Hold the line!"},
        {"index": 3, "speaker": "Narrator", "text": "Their blades struck with violent force."},
        {"index": 4, "speaker": "Narrator", "text": "A sudden explosion rocked the foundation."},
    ]

    blueprint, timeline = director.direct_scene(
        scene_id=scene_id,
        chapter_id=chapter_id,
        segments=segments,
        start_ms=10000,
        end_ms=40000,
    )

    sfx_events = [e for e in timeline.events if e.category == "HARD_SFX"]
    assert len(sfx_events) >= 2

    # Verify that start times are distinct and not all pinned to start_ms (10000)
    timestamps = [e.start_ms for e in sfx_events]
    assert len(set(timestamps)) == len(timestamps), "Hard SFX should not collide at the exact same timestamp"


def test_p1_narrator_center_lock_case_insensitive_qc():
    """P1-3: Ensure QC auditor detects off-center narrator pan even with Title Case 'Narrator'."""
    auditor = SoundDesignQCAuditor()
    blueprint = SceneAudioBlueprint(
        scene_id="sc_narrator_qc_test",
        chapter_id="ch_01",
        characters_staged={
            "Narrator": SpatialMetadata(azimuth_pan=0.45, proximity="normal_room"),  # Off-center!
        },
    )
    timeline = SoundTimeline(
        timeline_id="tl_test",
        chapter_id="ch_01",
        scene_id="sc_narrator_qc_test",
        total_duration_ms=10000,
        events=[
            SoundTimelineEvent(
                event_id="evt_01",
                category="AMBIENCE",
                start_ms=0,
                duration_ms=10000,
                spatial=SpatialMetadata(azimuth_pan=0.0),
            )
        ],
    )

    report = auditor.audit_scene_sound_design(blueprint, timeline)
    assert not report.spatial_stage_valid
    assert any("Narrator azimuth pan" in err for err in report.errors)


def test_p1_trivial_verbs_rejected_even_under_high_tension():
    """P1-4: Ensure trivial actions (blink, sigh, fidget) are REJECTED_TRIVIAL even under tension=1.0."""
    engine = FoleyEngine()
    cand = ActionCandidate(
        segment_index=1,
        subject="Hero",  # Named character elevates score
        action_verb="blink",
        object_material="wood",
        is_explicit_blocking=False,
    )

    result = engine.evaluate_candidate(
        action=cand,
        tension_level=1.0,  # Peak tension
        restraint_target="dense",
    )
    assert result.status == "REJECTED_TRIVIAL"
    assert "Trivial physical motion" in result.rejection_reason


def test_p1_false_positive_substring_tokens_avoided():
    """P1-5: Ensure 'drawer' is not parsed as 'draw' steel and actions are deduplicated per segment."""
    analyzer = SceneAudioAnalyzer()
    segments = [
        {
            "index": 1,
            "speaker": "Hero",
            "text": "He pulled open the wooden drawer and ate a crisp radish.",
        },
        {
            "index": 2,
            "speaker": "Hero",
            "text": "He stepped forward, stepped again, and stepped into the darkness.",
        },
    ]

    result = analyzer.analyze_scene(
        scene_id="sc_token_test",
        chapter_id="ch_01",
        segments=segments,
    )

    # Segment 1 should NOT have "draw" steel or "dish" foley actions from "drawer" or "radish"
    seg1_actions = [a for a in result.action_candidates if a.segment_index == 1]
    assert not any(a.action_verb == "draw" for a in seg1_actions)
    assert not any(a.object_material == "plate" for a in seg1_actions)

    # Segment 2 should have exactly 1 deduplicated "step" action, NOT 3
    seg2_steps = [a for a in result.action_candidates if a.segment_index == 2 and a.action_verb == "step"]
    assert len(seg2_steps) == 1


def test_p2_engine_reset_hooks():
    """P2-1: Ensure reset hooks properly clear internal state across batch execution."""
    amb_engine = AmbienceEngine()
    amb_engine._state_tracker["ch_prev"] = None  # type: ignore
    assert "ch_prev" in amb_engine._state_tracker
    amb_engine.reset()
    assert len(amb_engine._state_tracker) == 0

    spatial_engine = SpatialGeographyEngine()
    spatial_engine._scene_staging["sc_prev"] = {}
    assert "sc_prev" in spatial_engine._scene_staging
    spatial_engine.reset()
    assert len(spatial_engine._scene_staging) == 0
