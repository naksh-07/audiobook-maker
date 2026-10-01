#!/usr/bin/env python3
"""
Audiobook Factory - Golden Performance Suite Tests (Prompt 5).
Validates the permanent Golden Performance Suite v1.0:
1. Contract completeness across all 18 golden scenes
2. Full suite execution on baseline takes (100% acceptable, 0 hard regressions)
3. Failure injection testing across 8 distinct failure classes
4. Distinction between HARD_REGRESSION, SOFT_REGRESSION, and REVIEW
5. End-to-end regression safety cycle: Break -> Catch -> Restore -> Pass
"""

from __future__ import annotations
import math
import struct
import wave
from pathlib import Path
import pytest

from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    TakeVariant,
)
from audiobook_factory.performance.golden_suite import (
    GoldenPerformanceSuite,
    GoldenSceneDefinition,
    GoldenSceneEvaluationResult,
    GoldenSuiteReport,
    generate_golden_audio_wave,
)


@pytest.fixture
def golden_suite():
    return GoldenPerformanceSuite()


# =========================================================================
# Test 1: Contract Completeness Across All 18 Golden Scenes
# =========================================================================
def test_all_18_golden_scenes_contract_completeness(golden_suite):
    """Verify all 18 scenes possess comprehensive metadata and human baselines."""
    scenes = golden_suite.SCENES
    assert len(scenes) == 18, f"Expected 18 golden scenes, found {len(scenes)}"

    expected_categories = {"narration", "performance", "dialogue", "pronunciation", "transition"}
    actual_categories = {s.category for s in scenes}
    assert expected_categories.issubset(actual_categories)

    for s in scenes:
        assert s.scene_id.startswith("GS-")
        assert len(s.title) > 5
        assert len(s.text) > 5
        assert s.speaker != ""
        assert s.expected_emotional_state != ""
        assert "pause_after_ms" in s.expected_timing
        assert "rms_range" in s.expected_acoustic
        assert s.human_baseline.get("approval_status") == "APPROVED"
        rubric = s.human_baseline.get("rubric", {})
        assert "overall" in rubric
        assert rubric["overall"] >= 4.0


# =========================================================================
# Test 2: Full Suite Execution Baseline (All 18 Scenes Pass)
# =========================================================================
def test_golden_suite_execution_baseline_all_pass(golden_suite, tmp_path):
    """Verify that known-good baseline takes pass with zero hard regressions."""
    report = golden_suite.run_suite(audio_dir=tmp_path)

    assert report.total_scenes == 18
    assert report.hard_regression_count == 0
    assert report.is_acceptable is True
    assert report.passed_count >= 15  # At least 15 clean passes, remainder at most soft/review
    assert report.mean_dimension_scores["performance"] >= 0.70
    assert report.mean_dimension_scores["pronunciation"] >= 0.90
    assert report.mean_dimension_scores["technical_audio"] >= 0.90


# =========================================================================
# Test 3: Failure Injection - Wrong Speaker Detected
# =========================================================================
def test_failure_injection_wrong_speaker_caught(golden_suite, tmp_path):
    """Verify that an unexpected speaker change triggers an immediate HARD_REGRESSION."""
    scene = golden_suite.SCENES[0]  # GS-01: Narrator
    wav = tmp_path / "take_wrong_spk.wav"
    generate_golden_audio_wave(wav, duration_sec=3.8)

    take = TakeVariant(
        take_id="t_wrong_spk",
        segment_uid="s_01",
        segment_index=1,
        variant_type="standard",
        audio_path=str(wav),
        direction=PerformanceDirection(
            direction_id="pd_01", index=1, speaker="Narrator", surface_emotion="neutral"
        ),
        is_selected=True,
    )

    # Inject wrong speaker
    mutated = GoldenPerformanceSuite.inject_failure(scene, take, "wrong_speaker", tmp_path)
    res = golden_suite.evaluate_scene(scene, mutated)

    assert res.status == "HARD_REGRESSION"
    assert not res.structural_pass
    assert any("Speaker mismatch" in h for h in res.hard_regressions)


# =========================================================================
# Test 4: Failure Injection - Dropped / Swallowed Word Detected
# =========================================================================
def test_failure_injection_dropped_word_caught(golden_suite, tmp_path):
    """Verify that truncated or swallowed audio fails acoustic pronunciation QA."""
    scene = golden_suite.SCENES[13]  # GS-14: Hindi dialogue with nuktas
    wav = tmp_path / "take_swallowed.wav"
    generate_golden_audio_wave(wav, duration_sec=3.6)

    take = TakeVariant(
        take_id="t_swallowed",
        segment_uid="s_14",
        segment_index=14,
        variant_type="standard",
        audio_path=str(wav),
        direction=PerformanceDirection(
            direction_id="pd_14", index=14, speaker=scene.speaker, surface_emotion="command"
        ),
        is_selected=True,
    )

    # Inject dropped word (abnormally short 40ms audio)
    mutated = GoldenPerformanceSuite.inject_failure(scene, take, "dropped_word", tmp_path)
    res = golden_suite.evaluate_scene(scene, mutated)

    assert res.status == "HARD_REGRESSION"
    assert not res.pronunciation_pass
    assert any("pronunciation QA failure" in h for h in res.hard_regressions)


# =========================================================================
# Test 5: Failure Injection - Missing Performance Direction Detected
# =========================================================================
def test_failure_injection_missing_direction_caught(golden_suite, tmp_path):
    """Verify that a take lacking PerformanceDirection triggers a structural HARD_REGRESSION."""
    scene = golden_suite.SCENES[3]  # GS-04: Baron anger
    wav = tmp_path / "take_no_dir.wav"
    generate_golden_audio_wave(wav, duration_sec=2.8)

    take = TakeVariant(
        take_id="t_no_dir",
        segment_uid="s_04",
        segment_index=4,
        variant_type="standard",
        audio_path=str(wav),
        direction=PerformanceDirection(
            direction_id="pd_04", index=4, speaker=scene.speaker, surface_emotion="anger"
        ),
        is_selected=True,
    )

    mutated = GoldenPerformanceSuite.inject_failure(scene, take, "missing_direction", tmp_path)
    res = golden_suite.evaluate_scene(scene, mutated)

    assert res.status == "HARD_REGRESSION"
    assert not res.structural_pass
    assert any("Missing PerformanceDirection" in h for h in res.hard_regressions)


# =========================================================================
# Test 6: Failure Injection - Severe Digital Rail Clipping Detected
# =========================================================================
def test_failure_injection_clipping_caught(golden_suite, tmp_path):
    """Verify that audio with excessive rail-pinned clipping triggers a technical HARD_REGRESSION."""
    scene = golden_suite.SCENES[0]  # GS-01: Max clipping allowed = 0
    wav = tmp_path / "take_clean.wav"
    generate_golden_audio_wave(wav, duration_sec=3.8)

    take = TakeVariant(
        take_id="t_clipped",
        segment_uid="s_01",
        segment_index=1,
        variant_type="standard",
        audio_path=str(wav),
        direction=PerformanceDirection(
            direction_id="pd_01", index=1, speaker=scene.speaker, surface_emotion="neutral"
        ),
        is_selected=True,
    )

    mutated = GoldenPerformanceSuite.inject_failure(scene, take, "clipping", tmp_path)
    res = golden_suite.evaluate_scene(scene, mutated)

    assert res.status == "HARD_REGRESSION"
    assert not res.technical_pass
    assert any("Severe digital rail clipping" in h for h in res.hard_regressions)


# =========================================================================
# Test 7: Failure Injection - Severe DC Offset Detected
# =========================================================================
def test_failure_injection_dc_offset_caught(golden_suite, tmp_path):
    """Verify that hardware or algorithmic DC offset bias is detected."""
    scene = golden_suite.SCENES[0]
    wav = tmp_path / "take_dc.wav"
    generate_golden_audio_wave(wav, duration_sec=3.8)

    take = TakeVariant(
        take_id="t_dc",
        segment_uid="s_01",
        segment_index=1,
        variant_type="standard",
        audio_path=str(wav),
        direction=PerformanceDirection(
            direction_id="pd_01", index=1, speaker=scene.speaker, surface_emotion="neutral"
        ),
        is_selected=True,
    )

    mutated = GoldenPerformanceSuite.inject_failure(scene, take, "dc_offset", tmp_path)
    res = golden_suite.evaluate_scene(scene, mutated)

    assert res.status == "HARD_REGRESSION"
    assert not res.technical_pass
    assert any("DC offset bias" in h for h in res.hard_regressions)


# =========================================================================
# Test 8: Failure Injection - Dead Air Timing Violation Detected
# =========================================================================
def test_failure_injection_dead_air_caught(golden_suite, tmp_path):
    """Verify that excessive pause (1800ms) on rapid retort line triggers dead air violation."""
    scene = golden_suite.SCENES[10]  # GS-11: Rapid retort (max gap 150ms)
    wav = tmp_path / "take_dead_air.wav"
    generate_golden_audio_wave(wav, duration_sec=1.6)

    take = TakeVariant(
        take_id="t_dead_air",
        segment_uid="s_11",
        segment_index=11,
        variant_type="standard",
        audio_path=str(wav),
        direction=PerformanceDirection(
            direction_id="pd_11", index=11, speaker=scene.speaker, surface_emotion="defiance",
            turn_taking_behavior="eager_counter", pause_after_ms=120
        ),
        is_selected=True,
    )

    mutated = GoldenPerformanceSuite.inject_failure(scene, take, "dead_air", tmp_path)
    res = golden_suite.evaluate_scene(scene, mutated)

    assert res.status == "HARD_REGRESSION"
    assert not res.dialogue_pass
    assert any("Dead air violation" in h for h in res.hard_regressions)


# =========================================================================
# Test 9: Failure Injection - Truncated Emotional Pause Detected
# =========================================================================
def test_failure_injection_truncated_pause_caught(golden_suite, tmp_path):
    """Verify that truncating a dramatic aposiopesis pause (50ms vs 1250ms) triggers regression."""
    scene = golden_suite.SCENES[2]  # GS-03: Grief aposiopesis (min 1100ms)
    wav = tmp_path / "take_trunc.wav"
    generate_golden_audio_wave(wav, duration_sec=3.5)

    take = TakeVariant(
        take_id="t_trunc",
        segment_uid="s_03",
        segment_index=3,
        variant_type="standard",
        audio_path=str(wav),
        direction=PerformanceDirection(
            direction_id="pd_03", index=3, speaker=scene.speaker, surface_emotion="grief",
            silence_type="emotional_freeze", pause_after_ms=1250
        ),
        is_selected=True,
    )

    mutated = GoldenPerformanceSuite.inject_failure(scene, take, "truncated_pause", tmp_path)
    res = golden_suite.evaluate_scene(scene, mutated)

    assert res.status == "HARD_REGRESSION"
    assert not res.dialogue_pass
    assert any("Emotional pause truncated" in h for h in res.hard_regressions)


# =========================================================================
# Test 10: Soft Regression vs Hard Regression Distinction
# =========================================================================
def test_soft_regression_vs_hard_regression_distinction(golden_suite, tmp_path):
    """Verify that non-fatal variance (e.g. minor timing drift) results in SOFT_REGRESSION, not HARD_REGRESSION."""
    scene = golden_suite.SCENES[0]  # GS-01: max turn gap 600ms
    wav = tmp_path / "take_soft.wav"
    generate_golden_audio_wave(wav, duration_sec=3.8)

    # 700ms pause is slightly above 600ms target, but well below 600+300=900ms dead air hard threshold
    p_dir = PerformanceDirection(
        direction_id="pd_01_soft", index=1, speaker=scene.speaker, surface_emotion="neutral",
        pause_after_ms=700
    )
    take = TakeVariant(
        take_id="t_soft",
        segment_uid="s_01",
        segment_index=1,
        variant_type="standard",
        audio_path=str(wav),
        direction=p_dir,
        is_selected=True,
    )

    res = golden_suite.evaluate_scene(scene, take)
    assert res.status == "SOFT_REGRESSION"
    assert len(res.hard_regressions) == 0
    assert len(res.soft_regressions) > 0
    assert any("Timing latency drift" in s for s in res.soft_regressions)


# =========================================================================
# Test 11: Regression Safety Cycle (Break -> Catch -> Restore -> Pass)
# =========================================================================
def test_regression_safety_cycle_break_catch_restore_pass(golden_suite, tmp_path):
    """
    Mandatory Phase 18 Safety Test:
    1. Start with valid take -> PASS
    2. Intentionally inject clipping defect -> HARD_REGRESSION caught
    3. Restore clean take -> PASS
    """
    scene = golden_suite.SCENES[0]
    clean_wav = tmp_path / "clean_cycle.wav"
    generate_golden_audio_wave(clean_wav, duration_sec=3.8)

    p_dir = PerformanceDirection(
        direction_id="pd_cycle", index=1, speaker=scene.speaker, surface_emotion="neutral",
        pause_after_ms=400
    )
    clean_take = TakeVariant(
        take_id="t_cycle",
        segment_uid="s_cycle",
        segment_index=1,
        variant_type="standard",
        audio_path=str(clean_wav),
        direction=p_dir,
        is_selected=True,
    )

    # Step 1: Initial state passes
    res_initial = golden_suite.evaluate_scene(scene, clean_take)
    assert res_initial.status == "PASS"

    # Step 2: Break with clipping defect -> must be caught
    broken_take = GoldenPerformanceSuite.inject_failure(scene, clean_take, "clipping", tmp_path)
    res_broken = golden_suite.evaluate_scene(scene, broken_take)
    assert res_broken.status == "HARD_REGRESSION"
    assert not res_broken.technical_pass

    # Step 3: Restore clean take -> must pass again
    res_restored = golden_suite.evaluate_scene(scene, clean_take)
    assert res_restored.status == "PASS"
    assert res_restored.technical_pass
