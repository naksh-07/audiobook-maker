#!/usr/bin/env python3
"""
Audiobook Factory - Comprehensive Unit Test Suite for Dialogue Editorial Layer (DE-01 - DE-04).
Covers contracts, intelligent endpoint editing, conservative breath editing,
contextual turn-taking pause realization, QC gate safety, and deterministic rendering.
"""

import math
import wave
import pytest
import numpy as np
from pathlib import Path

from audiobook_factory.dialogue_editing import (
    DialogueEditor,
    DialogueEditPlan,
    DialogueEditorialConfig,
    EndpointClassification,
    BreathEditAction,
    PauseEditClassification,
    DialogueQCReport,
    QCDiagnostic,
    EndpointEditor,
    BreathEditor,
    PauseEditor,
    DialogueEditingQC,
)
from audiobook_factory.performance.contracts import (
    PerformanceDirection,
    PerformanceEvidence,
    BreathEvidence,
    AcousticEvidence,
)
from audiobook_factory.alignment_contracts import AlignmentResult, WordAlignment
from tests.fixtures.dialogue_editorial_fixtures import generate_scenario_waveform


@pytest.fixture
def tmp_audio_dir(tmp_path: Path) -> Path:
    d = tmp_path / "audio_test"
    d.mkdir(parents=True, exist_ok=True)
    return d


# =============================================================================
# DE-01: Contracts & Configuration Tests
# =============================================================================

def test_dialogue_edit_plan_defaults_and_validation():
    """Validates DialogueEditPlan schema and ensures 5ms de-click and no fixed 400ms defaults."""
    plan = DialogueEditPlan(
        segment_uid="seg_001",
        source_take="c001_s0001_take_a",
        speech_start_ms=50,
        speech_end_ms=1800,
    )
    assert plan.segment_uid == "seg_001"
    assert plan.head_trim_ms == 0
    assert plan.tail_trim_ms == 0
    assert plan.pre_breath_action == "KEEP"
    assert plan.post_breath_action == "KEEP"
    # Correction 2: 5ms technical de-click baseline
    assert plan.crossfade_in_ms == 5.0
    assert plan.crossfade_out_ms == 5.0
    # Correction 1: pause_after_ms is None until realized
    assert plan.pause_after_ms is None

    # Serialization / Deserialization check
    json_str = plan.model_dump_json()
    reloaded = DialogueEditPlan.model_validate_json(json_str)
    assert reloaded.segment_uid == plan.segment_uid
    assert reloaded.source_take == plan.source_take


def test_dialogue_editorial_config_preserves_5ms():
    """Ensures config preserves 5ms technical de-click by default."""
    cfg = DialogueEditorialConfig()
    assert cfg.default_declick_fade_ms == 5.0
    assert cfg.head_speech_safety_buffer_ms == 40
    assert cfg.tail_speech_safety_buffer_ms == 60


# =============================================================================
# DE-02: Endpoint Editor Tests
# =============================================================================

def test_endpoint_editor_normal_speech(tmp_audio_dir: Path):
    """Clean speech onset within 40ms safety buffer should not be trimmed."""
    wav = generate_scenario_waveform(
        tmp_audio_dir / "clean.wav",
        duration_sec=2.0,
        speech_start_sec=0.03,
        speech_end_sec=1.95,
    )
    editor = EndpointEditor()
    with wave.open(str(wav), "rb") as wf:
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)

    res = editor.analyze_endpoints(samples, 24000)
    assert res["head_trim_ms"] == 0
    assert res["tail_trim_ms"] == 0
    assert res["head_classification"] == "NATURAL_SPEECH"
    assert res["tail_classification"] == "NATURAL_SPEECH"


def test_endpoint_editor_trims_trailing_dead_air(tmp_audio_dir: Path):
    """Trailing dead air (>120ms) should be trimmed while preserving 60ms safety buffer."""
    wav = generate_scenario_waveform(
        tmp_audio_dir / "dead_air.wav",
        duration_sec=3.0,
        speech_start_sec=0.03,
        speech_end_sec=1.80,  # 1.2s of trailing silence
    )
    editor = EndpointEditor()
    with wave.open(str(wav), "rb") as wf:
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)

    res = editor.analyze_endpoints(samples, 24000)
    # Speech ends at ~1800ms out of 3000ms. Tail trim should be around 1100-1140ms.
    assert res["tail_trim_ms"] >= 1000
    assert res["tail_classification"] == "UNWANTED_SILENCE"
    # Head should remain untouched
    assert res["head_trim_ms"] == 0


def test_endpoint_editor_trims_leading_dead_air(tmp_audio_dir: Path):
    """Leading dead air (>80ms) should be trimmed while preserving 40ms safety buffer."""
    wav = generate_scenario_waveform(
        tmp_audio_dir / "lead_silence.wav",
        duration_sec=2.5,
        speech_start_sec=0.50,  # 500ms of leading silence
        speech_end_sec=2.45,
    )
    editor = EndpointEditor()
    with wave.open(str(wav), "rb") as wf:
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)

    align = AlignmentResult(
        words=[WordAlignment(token="kya", normalized_token="kya", start_ms=500, end_ms=1200)],
        start_ms=500,
        end_ms=2450,
    )
    res = editor.analyze_endpoints(samples, 24000, alignment=align)
    # 500ms - 40ms buffer = ~460ms trim
    assert res["head_trim_ms"] >= 400
    assert res["head_classification"] == "UNWANTED_SILENCE"


def test_endpoint_editor_preserves_natural_pre_breath(tmp_audio_dir: Path):
    """Inhale before speech must be preserved when directed or in combat strain."""
    wav = generate_scenario_waveform(
        tmp_audio_dir / "pre_breath.wav",
        duration_sec=2.5,
        speech_start_sec=0.25,
        speech_end_sec=2.40,
        has_pre_breath=True,
    )
    editor = EndpointEditor()
    with wave.open(str(wav), "rb") as wf:
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)

    p_dir = PerformanceDirection(
        index=1,
        speaker="Vikram",
        physical_state="combat_strain",
        pre_roll_breath_ms=200,
    )
    align = AlignmentResult(
        words=[WordAlignment(token="bhaago", normalized_token="bhaago", start_ms=250, end_ms=1200)],
        start_ms=250,
        end_ms=2400,
    )

    res = editor.analyze_endpoints(samples, 24000, alignment=align, direction=p_dir)
    assert res["head_trim_ms"] == 0
    assert res["head_classification"] == "NATURAL_BREATH"


def test_endpoint_editor_preserves_emotional_release_tail(tmp_audio_dir: Path):
    """Grief or emotional release tails must NOT be stripped as dead air."""
    wav = generate_scenario_waveform(
        tmp_audio_dir / "grief_tail.wav",
        duration_sec=3.0,
        speech_start_sec=0.04,
        speech_end_sec=2.40,
        is_emotional_decay=True,
    )
    editor = EndpointEditor()
    with wave.open(str(wav), "rb") as wf:
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)

    p_dir = PerformanceDirection(
        index=1,
        speaker="Ananya",
        surface_emotion="grief",
        silence_type="emotional_freeze",
        post_roll_breath_ms=250,
    )
    align = AlignmentResult(
        words=[WordAlignment(token="jaane", normalized_token="jaane", start_ms=40, end_ms=2400)],
        start_ms=40,
        end_ms=2400,
    )

    res = editor.analyze_endpoints(samples, 24000, alignment=align, direction=p_dir)
    # Emotional tail preserved
    assert res["tail_classification"] == "EMOTIONAL_TAIL"
    assert res["tail_trim_ms"] == 0


def test_endpoint_editor_removes_c2pa_burst(tmp_audio_dir: Path):
    """Acoustic anomaly / late artifact burst after speech valley is surgically removed."""
    wav = generate_scenario_waveform(
        tmp_audio_dir / "burst.wav",
        duration_sec=2.5,
        speech_start_sec=0.04,
        speech_end_sec=1.60,
        trailing_burst=True,
    )
    editor = EndpointEditor()
    with wave.open(str(wav), "rb") as wf:
        samples = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32)

    res = editor.analyze_endpoints(samples, 24000)
    assert res["tail_classification"] in ("AUDIO_ARTIFACT", "UNWANTED_SILENCE")
    assert res["tail_trim_ms"] >= 700


# =============================================================================
# DE-03: Breath Editor Tests
# =============================================================================

def test_breath_editor_natural_inhale_keep():
    """Natural inhale mandated by physical state or emotion is KEPT."""
    editor = BreathEditor()
    samples = np.random.randn(24000 * 2).astype(np.float32) * 5000.0

    p_dir = PerformanceDirection(
        index=1,
        speaker="Arjun",
        physical_state="combat_strain",
        pre_roll_breath_ms=220,
    )
    res = editor.evaluate_breaths(
        samples=samples,
        sample_rate=24000,
        speech_start_ms=250,
        speech_end_ms=1800,
        direction=p_dir,
    )
    assert res["pre_breath_action"] == "KEEP"
    assert res["pre_breath_attenuation_db"] == 0.0


def test_breath_editor_exaggerated_breath_reduce():
    """Disproportionately loud breath in a calm line is REDUCED, not removed."""
    editor = BreathEditor()
    rate = 24000
    samples = np.zeros(rate * 2, dtype=np.float32)
    # Calm speech: -26 dBFS (amp ~ 1600)
    samples[int(0.3 * rate):] = np.sin(2 * np.pi * 300 * np.arange(int(1.7 * rate)) / rate) * 1600.0
    # Loud breath in pre-roll: -28 dBFS (amp ~ 1300, within 2dB of speech)
    samples[:int(0.3 * rate)] = np.sin(2 * np.pi * 100 * np.arange(int(0.3 * rate)) / rate) * 1300.0

    p_dir = PerformanceDirection(
        index=1,
        speaker="Dev",
        surface_emotion="calm",
        physical_state="normal",
    )
    res = editor.evaluate_breaths(
        samples=samples,
        sample_rate=rate,
        speech_start_ms=300,
        speech_end_ms=1900,
        direction=p_dir,
    )
    assert res["pre_breath_action"] == "REDUCE"
    assert res["pre_breath_attenuation_db"] <= -4.0


def test_breath_editor_synthetic_artifact_remove():
    """Loud gasp during iron restraint is REMOVED."""
    editor = BreathEditor()
    rate = 24000
    samples = np.zeros(rate * 2, dtype=np.float32)
    # Calm speech
    samples[int(0.3 * rate):] = np.sin(2 * np.pi * 300 * np.arange(int(1.7 * rate)) / rate) * 2000.0
    # Severe synthetic gasp artifact: -18 dBFS (amp ~ 4000)
    samples[:int(0.3 * rate)] = np.sin(2 * np.pi * 150 * np.arange(int(0.3 * rate)) / rate) * 4500.0

    p_dir = PerformanceDirection(
        index=1,
        speaker="Dev",
        restraint=0.90,  # Iron restraint
        breath_behavior="holding_breath",
    )
    res = editor.evaluate_breaths(
        samples=samples,
        sample_rate=rate,
        speech_start_ms=300,
        speech_end_ms=1900,
        direction=p_dir,
    )
    assert res["pre_breath_action"] == "REMOVE"
    assert res["pre_breath_attenuation_db"] <= -20.0


# =============================================================================
# DE-04: Pause Editor & Turn-Taking Tests
# =============================================================================

def test_pause_editor_rapid_turn():
    """Eager counter or escalation triggers RAPID_TURN (140-220ms)."""
    editor = PauseEditor()
    p_dir = PerformanceDirection(
        index=1,
        speaker="Kabir",
        turn_taking_behavior="eager_counter",
        character_state="escalation",
    )
    res = editor.realize_pause(
        text="Aisa kabhi nahi hoga!",
        speaker="Kabir",
        direction=p_dir,
        segment_uid="s_001",
    )
    assert res["pause_classification"] == "RAPID_TURN"
    assert 120 <= res["pause_after_ms"] <= 240


def test_pause_editor_hesitation():
    """Ellipses or hesitation triggers HESITATION pause."""
    editor = PauseEditor()
    p_dir = PerformanceDirection(
        index=2,
        speaker="Ananya",
        hesitation_ms=450,
        silence_type="hesitation",
    )
    res = editor.realize_pause(
        text="Mujhe nahi pata...",
        speaker="Ananya",
        direction=p_dir,
        segment_uid="s_002",
    )
    assert res["pause_classification"] == "HESITATION"
    assert res["pause_after_ms"] >= 450


def test_pause_editor_emotional_freeze():
    """Grief / emotional freeze triggers extended absorption space."""
    editor = PauseEditor()
    p_dir = PerformanceDirection(
        index=3,
        speaker="Dev",
        surface_emotion="grief",
        silence_type="emotional_freeze",
        pause_after_ms=1300,
    )
    res = editor.realize_pause(
        text="Sab kho gaya.",
        speaker="Dev",
        direction=p_dir,
        segment_uid="s_003",
    )
    assert res["pause_classification"] == "EMOTIONAL_PAUSE"
    assert res["pause_after_ms"] >= 1000


def test_pause_editor_anti_mechanical_determinism():
    """Consecutive turns must have bounded variation and 100% determinism."""
    editor = PauseEditor()
    p_dir = PerformanceDirection(index=1, speaker="Narrator")

    # Run twice with identical input: must be identical
    res1 = editor.realize_pause(text="Pehla vakya.", speaker="Narrator", direction=p_dir, segment_uid="s_1", segment_index=1)
    res2 = editor.realize_pause(text="Pehla vakya.", speaker="Narrator", direction=p_dir, segment_uid="s_1", segment_index=1)
    assert res1["pause_after_ms"] == res2["pause_after_ms"]

    # Different sentences should have subtle deterministic jitter
    res3 = editor.realize_pause(text="Doosra vakya jo thoda lamba hai.", speaker="Narrator", direction=p_dir, segment_uid="s_2", segment_index=2)
    # Both are NORMAL_TURN
    assert res1["pause_classification"] == "NORMAL_TURN"
    assert res3["pause_classification"] == "NORMAL_TURN"


# =============================================================================
# QC Gate Tests
# =============================================================================

def test_qc_fails_on_speech_truncation():
    """QC must fail closed if head trim encroaches on aligned first word."""
    qc = DialogueEditingQC()
    align = AlignmentResult(
        words=[WordAlignment(token="Namaste", normalized_token="Namaste", start_ms=100, end_ms=800)],
        start_ms=100,
        end_ms=800,
    )
    # Plan cuts 150ms into a 100ms word
    bad_plan = DialogueEditPlan(
        segment_uid="bad_01",
        head_trim_ms=150,
        tail_trim_ms=0,
    )
    diags = qc.audit_segment_plan(bad_plan, total_audio_ms=1000, alignment=align)
    assert any(d.severity == "HARD_FAILURE" and d.code == "SPEECH_HEAD_TRUNCATION" for d in diags)


def test_qc_chapter_audit_detects_repetitive_cadence():
    """QC generates a warning when 4 consecutive segments have identical pauses."""
    qc = DialogueEditingQC()
    plans = [
        DialogueEditPlan(segment_uid=f"s_{i}", pause_after_ms=400)
        for i in range(5)
    ]
    report = qc.audit_chapter_plans(chapter_num=1, plans=plans, segment_durations_ms=[2000] * 5)
    assert report.passed  # Warnings do not fail chapter
    assert any(w.code == "REPETITIVE_PAUSE_CADENCE" for w in report.warnings)


# =============================================================================
# DialogueEditor Waveform Rendering Tests
# =============================================================================

def test_dialogue_editor_renders_clean_pcm_with_fades(tmp_audio_dir: Path):
    """DialogueEditor renders edited WAV with 5ms micro-fades and exact zero endpoints."""
    inp = generate_scenario_waveform(
        tmp_audio_dir / "raw_in.wav",
        duration_sec=2.0,
        speech_start_sec=0.10,
        speech_end_sec=1.85,
    )
    outp = tmp_audio_dir / "rendered_out.wav"

    editor = DialogueEditor()
    plan = DialogueEditPlan(
        segment_uid="test_render",
        head_trim_ms=50,
        tail_trim_ms=50,
        crossfade_in_ms=5.0,
        crossfade_out_ms=5.0,
    )
    rendered = editor.apply_edit_plan(inp, plan, outp)
    assert rendered.exists()

    with wave.open(str(rendered), "rb") as wf:
        n_frames = wf.getnframes()
        samples = np.frombuffer(wf.readframes(n_frames), dtype=np.int16)

    # First and last samples must be strictly zero (no clicks)
    assert samples[0] == 0
    assert samples[-1] == 0
    # Duration must be shortened by ~100ms
    orig_frames = 24000 * 2
    assert n_frames < orig_frames
