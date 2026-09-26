#!/usr/bin/env python3
"""
Audiobook Factory - Golden Sound Design Regression Test Suite.
==============================================================
Validates the upgraded Sound Design Subsystem against all 15 Canonical Golden Benchmarks.
Tests acoustic world building, leitmotif continuity, character physics, tableware isolation,
magical language, crowd walla restraint, and independent multi-signal QC audit compliance.
"""

import pytest
from audiobook_factory.sound_design.golden_benchmarks import GOLDEN_BENCHMARK_SCENARIOS
from audiobook_factory.sound_design.sound_director import get_sound_design_director
from audiobook_factory.sound_design.qc import get_sound_design_qc_auditor


@pytest.mark.parametrize("scenario", GOLDEN_BENCHMARK_SCENARIOS, ids=[s["benchmark_id"] for s in GOLDEN_BENCHMARK_SCENARIOS])
def test_golden_benchmark_scenario(scenario):
    director = get_sound_design_director()
    qc_auditor = get_sound_design_qc_auditor()

    scene_id = scenario["benchmark_id"]
    chapter_id = "golden_chapter"
    segments = scenario["segments"]
    duration_ms = 30000

    # Execute director
    blueprint, timeline = director.direct_scene(
        scene_id=scene_id,
        chapter_id=chapter_id,
        segments=segments,
        start_ms=0,
        end_ms=duration_ms,
        environment_override=scenario.get("environment_id"),
        characters_override=scenario.get("characters"),
        tension_override=scenario.get("tension_level"),
        emotion_override=scenario.get("dominant_emotion"),
    )


    # 1. Timeline integrity
    assert timeline.scene_id == scene_id
    assert timeline.total_duration_ms == duration_ms
    assert len(timeline.events) > 0

    # 2. Run Multi-Signal QC Audit
    qc_report = qc_auditor.audit_scene_sound_design(blueprint, timeline)
    assert qc_report.status in ("PASS", "WARN"), f"QC Failed for {scene_id}: {qc_report.errors}"
    assert len(qc_report.errors) == 0, f"QC Errors in {scene_id}: {qc_report.errors}"
    assert qc_report.spatial_stage_valid is True
    assert qc_report.ambience_continuity_verified is True

    # 3. Scenario-specific checks
    checks = scenario.get("expected_checks", {})

    if checks.get("tableware_isolation"):
        # Confirms no tableware asset was mistakenly branded as sword clash
        for evt in timeline.events:
            if evt.category in ("FOLEY", "HARD_SFX"):
                assert not ("plate" in evt.asset_path and "weap" in evt.asset_path.lower())

    if checks.get("walla_suppressed"):
        walla_events = [e for e in timeline.events if e.category == "WALLA"]
        assert len(walla_events) == 0, f"Expected walla suppressed in {scene_id}, but found {len(walla_events)}"

    if checks.get("walla_present"):
        walla_events = [e for e in timeline.events if e.category == "WALLA"]
        assert len(walla_events) >= 1, f"Expected walla present in {scene_id}"

    if checks.get("creature_event_present"):
        creature_events = [e for e in timeline.events if e.category == "CREATURE"]
        assert len(creature_events) >= 1, f"Expected creature event in {scene_id}"

    if checks.get("hard_sfx_present"):
        sfx_events = [e for e in timeline.events if e.category == "HARD_SFX"]
        assert len(sfx_events) >= 1, f"Expected hard SFX in {scene_id}"

    if checks.get("magic_event_present"):
        magic_events = [e for e in timeline.events if e.category == "MAGIC"]
        assert len(magic_events) >= 1, f"Expected magic event in {scene_id}"

    if checks.get("silence_present"):
        silence_events = [e for e in timeline.events if e.category == "SILENCE"]
        assert len(silence_events) >= 1, f"Expected intentional silence in {scene_id}"

    if checks.get("no_music"):
        music_events = [e for e in timeline.events if e.category == "MUSIC"]
        assert len(music_events) == 0, f"Expected no music in {scene_id}, but found {len(music_events)}"

    if checks.get("music_present"):
        music_events = [e for e in timeline.events if e.category == "MUSIC"]
        assert len(music_events) >= 1, f"Expected music cue in {scene_id}"

    if checks.get("beat_aware_timing"):
        music_events = [e for e in timeline.events if e.category == "MUSIC"]
        assert any(e.timing_rationale for e in music_events), f"Expected beat-aware timing rationale in {scene_id}"

    if checks.get("ambience_layers_min"):
        amb_events = [e for e in timeline.events if e.category == "AMBIENCE"]
        assert len(amb_events) >= checks["ambience_layers_min"], f"Expected >= {checks['ambience_layers_min']} ambience layers in {scene_id}, got {len(amb_events)}"

    if checks.get("foley_present"):
        foley_events = [e for e in timeline.events if e.category == "FOLEY"]
        assert len(foley_events) >= 1, f"Expected foley events in {scene_id}"

    if checks.get("spatial_diversity"):
        pans = {e.spatial.azimuth_pan for e in timeline.events if e.spatial}
        assert len(pans) >= 2, f"Expected spatial panning diversity, got {pans}"

    if checks.get("walla_attenuated_or_suppressed"):
        walla_events = [e for e in timeline.events if e.category == "WALLA"]
        for w in walla_events:
            assert w.mix_intent.duck_under_dialogue or w.relative_intensity in ("whisper_quiet", "subtle_bed"), f"Walla not properly subordinated or attenuated in {scene_id}"
