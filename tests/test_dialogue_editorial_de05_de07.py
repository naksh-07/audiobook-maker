#!/usr/bin/env python3
"""
Tests for Dialogue Editorial Layer Increments DE-05, DE-06, DE-07 & Dither Determinism:
1. DE-05: Interruption & Overlap (abrupt_cut, overlap_start, fade_under, em-dash cutoff with eager counter, mastering cross-talk mix).
2. DE-06: Take Boundary Continuity (inter-take gain leveling +/-2.5dB, elevated noise-floor micro-fade expansion to 15ms).
3. DE-07: Mid-Line Breath Editing (intra-segment breath detection, calm line reduction, emotional breath protection whitelist, word collision audit).
4. TPDF Dither Determinism (SHA256 seeded bit-exact reproducibility across process invocations).
"""

import math
import wave
import hashlib
from pathlib import Path
import numpy as np
import pytest

from audiobook_factory.alignment_contracts import AlignmentResult, WordAlignment, PauseInterval
from audiobook_factory.performance.contracts import PerformanceDirection, PerformanceEvidence, BreathEvidence
from audiobook_factory.dialogue_editing.contracts import (
    DialogueEditPlan,
    DialogueEditorialConfig,
    MidLineBreathEdit,
)
from audiobook_factory.dialogue_editing.breath_editor import BreathEditor
from audiobook_factory.dialogue_editing.pause_editor import PauseEditor
from audiobook_factory.dialogue_editing.editor import DialogueEditor
from audiobook_factory.dialogue_editing.qc import DialogueEditingQC
from audiobook_factory.mastering import concatenate_and_master_chapter


def _generate_wav(
    path: Path,
    duration_ms: int = 1500,
    sample_rate: int = 24000,
    freq: float = 440.0,
    noise_db: float = -60.0,
    mid_gap_ms: tuple = None,
) -> Path:
    """Helper to synthesize test WAV with controllable signal, noise floor, and mid-line gaps."""
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    t = np.linspace(0.0, duration_ms / 1000.0, num_samples, endpoint=False)

    # Base tone (realistic dialogue level ~ -19 dBFS)
    samples = 5000.0 * np.sin(2.0 * np.pi * freq * t)

    # Noise floor
    noise_amp = 32768.0 * (10.0 ** (noise_db / 20.0))
    rng = np.random.default_rng(42)
    noise = rng.normal(0.0, noise_amp, num_samples)
    samples += noise

    # Optional mid-gap (silence/breath simulation)
    if mid_gap_ms:
        g_s, g_e = mid_gap_ms
        s_idx = int(g_s / 1000.0 * sample_rate)
        e_idx = int(g_e / 1000.0 * sample_rate)
        # Breath gasp: audible inhale in gap (~ -28 dBFS)
        samples[s_idx:e_idx] = rng.normal(0.0, 1200.0, e_idx - s_idx)

    # Fade in/out edges (5ms)
    f_s = int(0.005 * sample_rate)
    samples[:f_s] *= np.linspace(0.0, 1.0, f_s)
    samples[-f_s:] *= np.linspace(1.0, 0.0, f_s)

    int16_samples = np.clip(np.round(samples), -32768.0, 32767.0).astype(np.int16)
    int16_samples[0] = 0
    int16_samples[-1] = 0

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(int16_samples.tobytes())
    return path


# =============================================================================
# 1. DE-05: Interruption & Overlap Tests
# =============================================================================

def test_interruption_overlap_start(tmp_path: Path):
    """Verifies overlap_start realizes conversational cross-talk overlap (150ms) and zero pause."""
    editor = DialogueEditor()
    audio_path = _generate_wav(tmp_path / "take1.wav", duration_ms=2000)

    dir_curr = PerformanceDirection(
        direction_id="pd_1",
        segment_uid="seg_1",
        index=1,
        speaker="SpeakerA",
        interruption_behavior="overlap_start",
    )

    plan = editor.plan_segment_edit(
        audio_path=audio_path,
        text="Wait, don't open that—",
        speaker="SpeakerA",
        direction=dir_curr,
        segment_uid="seg_1",
        segment_index=1,
    )

    assert plan.interruption_mode == "overlap_start"
    assert plan.overlap_ms == 150
    assert plan.pause_after_ms == 0
    assert plan.pause_classification == "INTERRUPTED_TURN"


def test_interruption_fade_under(tmp_path: Path):
    """Verifies fade_under triggers tail ducking and overlap realization."""
    editor = DialogueEditor()
    audio_path = _generate_wav(tmp_path / "take_fade.wav", duration_ms=2000)
    out_path = tmp_path / "take_fade_edited.wav"

    dir_curr = PerformanceDirection(
        direction_id="pd_1",
        segment_uid="seg_1",
        index=1,
        speaker="SpeakerA",
        interruption_behavior="fade_under",
    )

    plan = editor.plan_segment_edit(
        audio_path=audio_path,
        text="I was just trying to explain—",
        speaker="SpeakerA",
        direction=dir_curr,
        segment_uid="seg_1",
        segment_index=1,
    )

    assert plan.interruption_mode == "fade_under"
    assert plan.overlap_ms == 120
    assert plan.pause_after_ms == 0

    rendered = editor.apply_edit_plan(audio_path, plan, out_path)
    assert rendered.exists()

    # Verify tail ducking: compare RMS of the last 100ms between original and rendered
    orig_samples, sr = editor._load_wav_samples(audio_path)
    rend_samples, _ = editor._load_wav_samples(rendered)

    span = int(0.08 * sr)
    orig_tail_rms = np.sqrt(np.mean(orig_samples[-span:] ** 2))
    rend_tail_rms = np.sqrt(np.mean(rend_samples[-span:] ** 2))
    assert rend_tail_rms < orig_tail_rms * 0.75, "Tail was not ducked for fade_under"


def test_interruption_abrupt_cut(tmp_path: Path):
    """Verifies abrupt_cut sets snappy 2ms micro-fade and 35ms pause gap."""
    editor = DialogueEditor()
    audio_path = _generate_wav(tmp_path / "take_cut.wav", duration_ms=1800)

    dir_curr = PerformanceDirection(
        direction_id="pd_1",
        segment_uid="seg_1",
        index=1,
        speaker="SpeakerA",
        interruption_behavior="abrupt_cut",
    )

    plan = editor.plan_segment_edit(
        audio_path=audio_path,
        text="Stop right there!",
        speaker="SpeakerA",
        direction=dir_curr,
        segment_uid="seg_1",
        segment_index=1,
    )

    assert plan.interruption_mode == "abrupt_cut"
    assert plan.overlap_ms == 0
    assert plan.pause_after_ms == 35
    assert plan.crossfade_out_ms == 2.0


def test_em_dash_eager_counter_detection(tmp_path: Path):
    """Verifies aposiopesis em-dash cut off by eager counter triggers overlap_start."""
    editor = DialogueEditor()
    audio_path = _generate_wav(tmp_path / "take_dash.wav", duration_ms=1500)

    dir_curr = PerformanceDirection(
        direction_id="pd_1",
        segment_uid="seg_1",
        index=1,
        speaker="SpeakerA",
    )
    dir_next = PerformanceDirection(
        direction_id="pd_2",
        segment_uid="seg_2",
        index=2,
        speaker="SpeakerB",
        turn_taking_behavior="eager_counter",
    )

    plan = editor.plan_segment_edit(
        audio_path=audio_path,
        text="I didn't mean to—",
        speaker="SpeakerA",
        direction=dir_curr,
        next_direction=dir_next,
        segment_uid="seg_1",
        segment_index=1,
    )

    assert plan.interruption_mode == "overlap_start"
    assert plan.overlap_ms == 150
    assert plan.pause_after_ms == 0


def test_mastering_overlap_transition_rendering(tmp_path: Path):
    """Verifies mastering cleanly stitches overlapping takes into a continuous timeline."""
    t1 = _generate_wav(tmp_path / "t1.wav", duration_ms=1500, freq=440.0)
    t2 = _generate_wav(tmp_path / "t2.wav", duration_ms=1200, freq=880.0)
    out_master = tmp_path / "master_overlap.wav"

    plan1 = DialogueEditPlan(
        segment_uid="seg_1",
        source_take="t1",
        speech_start_ms=0,
        speech_end_ms=1500,
        overlap_ms=150,
        interruption_mode="overlap_start",
        pause_after_ms=0,
        metadata={"segment_index": 1},
    )
    plan2 = DialogueEditPlan(
        segment_uid="seg_2",
        source_take="t2",
        speech_start_ms=0,
        speech_end_ms=1200,
        overlap_ms=0,
        pause_after_ms=200,
        metadata={"segment_index": 2},
    )

    res = concatenate_and_master_chapter(
        audio_segments=[t1, t2],
        output_chapter_file=out_master,
        edit_plans=[plan1, plan2],
        loudnorm=False,
    )

    assert res.exists()
    assert res.stat().st_size > 1000

    # Read output frames: expected duration ~ 1500 + 1200 - 150 + 200 = 2750ms
    with wave.open(str(res), "rb") as wf:
        out_dur_ms = wf.getnframes() / float(wf.getframerate()) * 1000.0

    # Within +/- 150ms of mathematically expected duration
    assert 2550 <= out_dur_ms <= 2950


# =============================================================================
# 2. DE-06: Take Boundary Continuity Tests
# =============================================================================

def test_take_boundary_gain_leveling(tmp_path: Path):
    """Verifies inter-take gain leveling compensates for random TTS volume jumps (+/-2.5dB)."""
    editor = DialogueEditor()

    # Take 1: quiet (-28 dBFS)
    # Take 2: loud (-22 dBFS, jump of +6dB)
    t1 = _generate_wav(tmp_path / "c001_s0001_take.wav", duration_ms=1200, freq=440.0, noise_db=-55.0)
    t2 = _generate_wav(tmp_path / "c001_s0002_take.wav", duration_ms=1200, freq=440.0, noise_db=-55.0)

    # Scale samples of take 2 to make it significantly louder
    samples, sr = editor._load_wav_samples(t2)
    loud_samples = np.clip(samples * 1.8, -32768.0, 32767.0).astype(np.int16)
    with wave.open(str(t2), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(loud_samples.tobytes())

    plan1 = DialogueEditPlan(segment_uid="seg_1", source_take="t1", speech_start_ms=0, speech_end_ms=1200)
    plan2 = DialogueEditPlan(segment_uid="seg_2", source_take="t2", speech_start_ms=0, speech_end_ms=1200)

    plans = [plan1, plan2]
    editor.smooth_take_boundaries(plans, [t1, t2])

    # Take 2 should have negative gain adjustment clamped to config max (-2.5dB)
    assert plan2.gain_adjustment_db < -0.5
    assert plan2.gain_adjustment_db >= -2.5
    assert "Inter-take gain leveling" in plan2.decision_reason


def test_take_boundary_elevated_noise_floor_expansion(tmp_path: Path):
    """Verifies takes with elevated noise floor expand micro-fades to 15ms and flag room_match_required."""
    editor = DialogueEditor()
    # Noisy take with background vocoder hiss (-42 dBFS > -48 dBFS threshold)
    noisy_take = _generate_wav(tmp_path / "c001_s0001_noisy.wav", duration_ms=1000, noise_db=-40.0)

    plan = DialogueEditPlan(
        segment_uid="seg_1",
        source_take="noisy",
        speech_start_ms=0,
        speech_end_ms=1000,
        crossfade_in_ms=5.0,
        crossfade_out_ms=5.0,
    )

    editor.smooth_take_boundaries([plan], [noisy_take])

    assert plan.crossfade_in_ms == 15.0
    assert plan.crossfade_out_ms == 15.0
    assert plan.metadata.get("room_match_required") is True
    assert "Elevated noise floor" in plan.decision_reason


# =============================================================================
# 3. DE-07: Mid-Line Breath Editing Tests
# =============================================================================

def test_mid_line_breath_calm_gasp_reduction(tmp_path: Path):
    """Verifies exaggerated mid-line gasps on calm dialogue lines are attenuated (-6dB)."""
    editor = DialogueEditor()
    audio_path = _generate_wav(
        tmp_path / "take_mid_breath.wav",
        duration_ms=2500,
        mid_gap_ms=(900, 1300),
    )

    alignment = AlignmentResult(
        aligned=True,
        segment_uid="seg_1",
        duration_ms=2500,
        confidence=1.0,
        confidence_category="HIGH",
        words=[
            WordAlignment(token="The", normalized_token="the", start_ms=100, end_ms=400, confidence=1.0),
            WordAlignment(token="path", normalized_token="path", start_ms=450, end_ms=880, confidence=1.0),
            WordAlignment(token="was", normalized_token="was", start_ms=1320, end_ms=1600, confidence=1.0),
            WordAlignment(token="clear", normalized_token="clear", start_ms=1650, end_ms=2300, confidence=1.0),
        ],
        pauses=[
            PauseInterval(start_ms=880, end_ms=1320, duration_ms=440, classification="natural_pause"),
        ],
    )

    dir_calm = PerformanceDirection(
        direction_id="pd_1",
        segment_uid="seg_1",
        index=1,
        speaker="Narrator",
        surface_emotion="neutral",
    )

    plan = editor.plan_segment_edit(
        audio_path=audio_path,
        text="The path was clear.",
        speaker="Narrator",
        direction=dir_calm,
        alignment=alignment,
        segment_uid="seg_1",
        segment_index=1,
    )

    assert len(plan.mid_breath_edits) >= 1
    edit = plan.mid_breath_edits[0]
    assert edit.action == "REDUCE"
    assert edit.attenuation_db == -6.0

    # Apply edit plan and verify audio reduction in the breath gap
    out_edited = tmp_path / "take_mid_edited.wav"
    editor.apply_edit_plan(audio_path, plan, out_edited)

    orig_samples, sr = editor._load_wav_samples(audio_path)
    rend_samples, _ = editor._load_wav_samples(out_edited)

    gap_s = int(0.95 * sr)
    gap_e = int(1.25 * sr)
    orig_gap_rms = np.sqrt(np.mean(orig_samples[gap_s:gap_e] ** 2))
    rend_gap_rms = np.sqrt(np.mean(rend_samples[gap_s:gap_e] ** 2))

    assert rend_gap_rms < orig_gap_rms * 0.70, "Mid-line breath gasp was not attenuated"


def test_mid_line_breath_emotional_preservation(tmp_path: Path):
    """Verifies emotional/strain breaths (combat, grief, high restraint) are whitelisted and preserved (KEEP)."""
    breath_editor = BreathEditor()
    audio_path = _generate_wav(
        tmp_path / "take_combat_breath.wav",
        duration_ms=2500,
        mid_gap_ms=(900, 1300),
    )
    samples, sr = DialogueEditor()._load_wav_samples(audio_path)

    alignment = AlignmentResult(
        aligned=True,
        segment_uid="seg_1",
        duration_ms=2500,
        confidence=1.0,
        confidence_category="HIGH",
        words=[
            WordAlignment(token="Hold", normalized_token="hold", start_ms=100, end_ms=850, confidence=1.0),
            WordAlignment(token="on", normalized_token="on", start_ms=1350, end_ms=2200, confidence=1.0),
        ],
        pauses=[PauseInterval(start_ms=850, end_ms=1350, duration_ms=500, classification="natural_pause")],
    )

    dir_combat = PerformanceDirection(
        direction_id="pd_1",
        segment_uid="seg_1",
        index=1,
        speaker="Warrior",
        physical_state="combat_strain",
        surface_emotion="fear",
    )

    edits = breath_editor.evaluate_mid_line_breaths(
        samples=samples,
        sample_rate=sr,
        speech_start_ms=100,
        speech_end_ms=2200,
        speech_db=-20.0,
        direction=dir_combat,
        alignment=alignment,
    )

    assert len(edits) >= 1
    assert edits[0].action == "KEEP"
    assert "preserved" in edits[0].reason.lower()


# =============================================================================
# 4. QC Gates for DE-05 & DE-07
# =============================================================================

def test_qc_overlap_duration_limits():
    """Verifies QC gate triggers HARD_FAILURE on excessive overlap duration (>400ms or >50% duration)."""
    qc = DialogueEditingQC()

    # Case 1: Overlap > 400ms
    plan_long = DialogueEditPlan(
        segment_uid="seg_1",
        source_take="t1",
        speech_start_ms=0,
        speech_end_ms=2000,
        overlap_ms=450,
    )
    diags1 = qc.audit_segment_plan(plan_long, total_audio_ms=2000)
    assert any(d.code == "EXCESSIVE_OVERLAP_DURATION" and d.severity == "HARD_FAILURE" for d in diags1)

    # Case 2: Overlap > 50% take duration
    plan_half = DialogueEditPlan(
        segment_uid="seg_2",
        source_take="t2",
        speech_start_ms=0,
        speech_end_ms=600,
        overlap_ms=350,  # 350ms > 600 * 0.5 = 300ms
    )
    diags2 = qc.audit_segment_plan(plan_half, total_audio_ms=600)
    assert any(d.code == "OVERLAP_EXCEEDS_HALF_TAKE" and d.severity == "HARD_FAILURE" for d in diags2)


def test_qc_mid_breath_word_collision():
    """Verifies QC gate prevents mid-line breath attenuation from encroaching into spoken words."""
    qc = DialogueEditingQC()

    alignment = AlignmentResult(
        aligned=True,
        segment_uid="seg_1",
        duration_ms=2000,
        confidence=1.0,
        confidence_category="HIGH",
        words=[
            WordAlignment(token="danger", normalized_token="danger", start_ms=400, end_ms=900, confidence=1.0),
        ],
    )

    # Corrupt breath edit encroaching into "danger"
    colliding_edit = MidLineBreathEdit(
        start_ms=700,
        end_ms=1100,
        action="REDUCE",
        attenuation_db=-6.0,
        reason="Erroneous breath detection",
    )

    plan = DialogueEditPlan(
        segment_uid="seg_1",
        source_take="t1",
        speech_start_ms=0,
        speech_end_ms=2000,
        mid_breath_edits=[colliding_edit],
    )

    diags = qc.audit_segment_plan(plan, total_audio_ms=2000, alignment=alignment)
    assert any(d.code == "MID_BREATH_WORD_COLLISION" and d.severity == "HARD_FAILURE" for d in diags)


# =============================================================================
# 5. TPDF Dither Determinism Test
# =============================================================================

def test_tpdf_dither_determinism(tmp_path: Path):
    """Verifies SHA256 seeded TPDF dither is 100% bit-exact across independent render calls."""
    editor = DialogueEditor()
    audio_path = _generate_wav(tmp_path / "source_take.wav", duration_ms=1200)

    plan = DialogueEditPlan(
        segment_uid="seg_dither_test",
        source_take="source_take",
        speech_start_ms=50,
        speech_end_ms=1150,
        head_trim_ms=40,
        tail_trim_ms=40,
        gain_adjustment_db=-1.5,
    )

    out1 = tmp_path / "render1.wav"
    out2 = tmp_path / "render2.wav"

    editor.apply_edit_plan(audio_path, plan, out1)
    editor.apply_edit_plan(audio_path, plan, out2)

    with open(out1, "rb") as f1, open(out2, "rb") as f2:
        hash1 = hashlib.sha256(f1.read()).hexdigest()
        hash2 = hashlib.sha256(f2.read()).hexdigest()

    assert hash1 == hash2, "TPDF dither was not bit-exact across independent runs"
