#!/usr/bin/env python3
"""
Audiobook Factory - Integration Test Suite for Dialogue Editorial Layer (DE-01 - DE-04).
Validates:
1. All 7 golden dialogue scenarios through DialogueEditor.
2. End-to-end downstream dialogue stem mastering pipeline (DialogueEditor -> concatenate_and_master_chapter).
3. Fail-closed fallback resilience when QC hard failures occur.
"""

import wave
import pytest
from pathlib import Path
import numpy as np

from audiobook_factory.dialogue_editing import (
    DialogueEditor,
    DialogueEditPlan,
    DialogueEditorialConfig,
    DialogueQCReport,
)
from audiobook_factory.mastering import concatenate_and_master_chapter
from tests.fixtures.dialogue_editorial_fixtures import create_scenario_fixtures


@pytest.fixture
def scenario_set(tmp_path: Path):
    fixture_dir = tmp_path / "fixtures"
    return create_scenario_fixtures(fixture_dir)


def test_golden_7_dialogue_scenarios(tmp_path: Path, scenario_set):
    """
    Executes all 7 canonical dialogue scenarios through DialogueEditor
    and validates specific editorial actions against ground truth requirements.
    """
    editor = DialogueEditor(project_dir=tmp_path)

    # 1. Normal Conversation
    s1 = scenario_set["normal_conversation"]
    p1 = editor.plan_segment_edit(
        audio_path=s1["audio_path"],
        text=s1["text"],
        speaker=s1["speaker"],
        direction=s1["direction"],
        alignment=s1["alignment"],
        segment_uid="s1",
    )
    assert p1.pause_classification == "NORMAL_TURN"
    assert 280 <= p1.pause_after_ms <= 450
    assert p1.head_trim_ms == 0

    # 2. Rapid Exchange
    s2 = scenario_set["rapid_exchange"]
    p2 = editor.plan_segment_edit(
        audio_path=s2["audio_path"],
        text=s2["text"],
        speaker=s2["speaker"],
        direction=s2["direction"],
        alignment=s2["alignment"],
        segment_uid="s2",
    )
    assert p2.pause_classification == "RAPID_TURN"
    assert 120 <= p2.pause_after_ms <= 240

    # 3. Emotional Line (Grief / Emotional Release)
    s3 = scenario_set["emotional_line"]
    p3 = editor.plan_segment_edit(
        audio_path=s3["audio_path"],
        text=s3["text"],
        speaker=s3["speaker"],
        direction=s3["direction"],
        alignment=s3["alignment"],
        segment_uid="s3",
    )
    assert p3.pause_classification == "EMOTIONAL_PAUSE"
    assert p3.pause_after_ms >= 1000
    assert p3.tail_classification == "EMOTIONAL_TAIL"
    assert p3.tail_trim_ms == 0  # Emotional tail preserved!

    # 4. Breath-Heavy Line (Combat Exertion)
    s4 = scenario_set["breath_heavy_line"]
    p4 = editor.plan_segment_edit(
        audio_path=s4["audio_path"],
        text=s4["text"],
        speaker=s4["speaker"],
        direction=s4["direction"],
        evidence=s4.get("evidence"),
        alignment=s4["alignment"],
        segment_uid="s4",
    )
    assert p4.head_classification == "NATURAL_BREATH"
    assert p4.pre_breath_action == "KEEP"
    assert p4.head_trim_ms == 0  # Inhale preserved!

    # 5. Long Trailing Silence (TTS Dead Air Carrier)
    s5 = scenario_set["long_trailing_silence"]
    p5 = editor.plan_segment_edit(
        audio_path=s5["audio_path"],
        text=s5["text"],
        speaker=s5["speaker"],
        direction=s5["direction"],
        alignment=s5["alignment"],
        segment_uid="s5",
    )
    assert p5.tail_classification == "UNWANTED_SILENCE"
    assert p5.tail_trim_ms >= 1000  # Dead air trimmed!

    # 6. Hesitation
    s6 = scenario_set["hesitation"]
    p6 = editor.plan_segment_edit(
        audio_path=s6["audio_path"],
        text=s6["text"],
        speaker=s6["speaker"],
        direction=s6["direction"],
        alignment=s6["alignment"],
        segment_uid="s6",
    )
    assert p6.pause_classification == "HESITATION"
    assert p6.pause_after_ms >= 450

    # 7. Realization / Reaction Pause
    s7 = scenario_set["realization_reaction"]
    p7 = editor.plan_segment_edit(
        audio_path=s7["audio_path"],
        text=s7["text"],
        speaker=s7["speaker"],
        direction=s7["direction"],
        alignment=s7["alignment"],
        segment_uid="s7",
    )
    assert p7.pause_classification in ("THINKING_PAUSE", "REACTION_PAUSE", "SUSPENSE_PAUSE")
    assert p7.pause_after_ms >= 600


def test_end_to_end_dialogue_editorial_to_mastering_path(tmp_path: Path, scenario_set):
    """
    Proves full production path:
    Selected Takes -> DialogueEditor.process_chapter -> edited_chunks + edit_plans -> concatenate_and_master_chapter -> Mastered Vocal Stem.
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = project_dir / "audio_chunks"
    audio_dir.mkdir(parents=True, exist_ok=True)
    mastered_dir = project_dir / "mastered"
    mastered_dir.mkdir(parents=True, exist_ok=True)

    # Use first 3 scenarios as chapter dialogue
    scenarios_to_run = [
        scenario_set["normal_conversation"],
        scenario_set["rapid_exchange"],
        scenario_set["long_trailing_silence"],
    ]

    audio_segments = []
    script_segments = []
    for i, sc in enumerate(scenarios_to_run, 1):
        target_path = audio_dir / f"c001_s{i:04d}_{sc['speaker'].lower()}.wav"
        import shutil
        shutil.copy2(sc["audio_path"], target_path)
        audio_segments.append(target_path)
        script_segments.append({
            "index": i,
            "speaker": sc["speaker"],
            "text": sc["text"],
            "uid": f"seg_{i}",
            "pause_after_ms": sc["direction"].pause_after_ms,
        })

    # 1. Dialogue Editor Process Chapter
    editor = DialogueEditor(project_dir=project_dir)
    edited_segments, edit_plans, qc_report = editor.process_chapter(
        chapter_num=1,
        audio_segments=audio_segments,
        script_segments=script_segments,
    )

    assert qc_report.passed
    assert len(edited_segments) == 3
    assert len(edit_plans) == 3
    for p in edited_segments:
        assert p.exists()
        assert p.stat().st_size > 1000

    # 2. Downstream Mastering Path
    vocal_wav = mastered_dir / "c001_dialogue.wav"
    mastered_output = concatenate_and_master_chapter(
        audio_segments=edited_segments,
        output_chapter_file=vocal_wav,
        script_segments=script_segments,
        edit_plans=edit_plans,
        loudnorm=False,  # Fast PCM concat without loudnorm in unit test
    )

    assert mastered_output.exists()
    assert mastered_output.stat().st_size > 5000

    with wave.open(str(mastered_output), "rb") as wf:
        n_frames = wf.getnframes()
        fr = wf.getframerate()
        dur = n_frames / float(fr)
        assert dur > 2.0  # Mastered audio is valid and has expected duration


def test_qc_hard_failure_triggers_safe_fallback(tmp_path: Path):
    """
    Proves fail-closed safety invariant:
    If a segment has corrupt/truncated boundary, process_chapter falls back to unedited takes.
    """
    project_dir = tmp_path / "fallback_proj"
    audio_dir = project_dir / "audio_chunks"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # Create dummy WAV
    raw_wav = audio_dir / "c001_s0001_take.wav"
    with wave.open(str(raw_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00" * 4800)  # 100ms of silence

    editor = DialogueEditor(project_dir=project_dir)
    # Mock endpoint editor to produce an impossible plan that trims 200ms from 100ms file
    original_analyze = editor.endpoint_editor.analyze_endpoints

    def mock_bad_endpoints(*args, **kwargs):
        return {
            "speech_start_ms": 10,
            "speech_end_ms": 90,
            "head_trim_ms": 80,
            "tail_trim_ms": 80,  # 160ms total trim on 100ms audio!
            "head_classification": "UNWANTED_SILENCE",
            "tail_classification": "UNWANTED_SILENCE",
            "crossfade_in_ms": 5.0,
            "crossfade_out_ms": 5.0,
            "decision_reasons": ["Mock bad trim"],
        }

    editor.endpoint_editor.analyze_endpoints = mock_bad_endpoints

    edited_segments, edit_plans, qc_report = editor.process_chapter(
        chapter_num=1,
        audio_segments=[raw_wav],
        script_segments=[{"index": 1, "speaker": "Dev", "text": "Test"}],
    )

    # QC should fail or confidence drops to 0, falling back to original raw audio
    assert not qc_report.passed or edit_plans[0].confidence == 0.0
    # Returned audio is the safe unedited fallback
    assert edited_segments[0] == raw_wav
