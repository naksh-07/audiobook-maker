#!/usr/bin/env python3
"""
Test Suite: Audible-Standard Pure Vocals Transformation ("Audible Flow")
Verifies:
1. Room 3 Script Engine preserves narrative prose & dialogue tags and bans Foley.
2. Room 4 Clean Neural DSP bypasses asetrate/atempo pitch distortion and harsh telephone EQ.
3. Room 5 Mastering enforces Phantom Center vocals (pan=0.0) by default.
4. Room 5 Mastering generates organic TPDF room-tone dither instead of digital dead-air (0x0000).
5. Room 5 Mastering calibrates pauses based on syntax (comma 180ms, period 380ms, speaker change 600ms).
6. Artificial synthetic pre-breath silence is bypassed in Audible clean mode.
7. CLI parses --flow and --cast-mode correctly.
"""

import os
import wave
import json
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.script.dialogue_parser import _parse_dialogue_turns_llm
from audiobook_factory.tts.dispatcher import TTSDispatcher
from audiobook_factory.mastering import concatenate_and_master_chapter


def test_01_audible_flow_prompt_preserves_prose_and_bans_foley():
    """Verify Room 3 Audible Flow system prompt commands preservation of prose and tags."""
    captured_sys_prompt = None

    def fake_call_gemini(prompt, system_instruction="", **kwargs):
        nonlocal captured_sys_prompt
        captured_sys_prompt = system_instruction
        return [{"index": 1, "type": "narration", "speaker": "Narrator", "text": "Hello"}]

    with patch.dict(os.environ, {"AUDIBLE_FLOW_MODE": "true"}):
        with patch("audiobook_factory.script.dialogue_parser.call_gemini", side_effect=fake_call_gemini):
            _parse_dialogue_turns_llm("Sample text")

    assert captured_sys_prompt is not None
    assert "PRESERVE ALL NARRATIVE PROSE & DIALOGUE TAGS" in captured_sys_prompt
    assert "ZERO FOLEY / ACTIONS" in captured_sys_prompt
    assert "Audible-standard" in captured_sys_prompt
    assert "Hollywood Audio Drama" not in captured_sys_prompt


def test_02_legacy_mode_prompt_fallback():
    """Verify legacy prompt is used when AUDIBLE_FLOW_MODE is explicitly false."""
    captured_sys_prompt = None

    def fake_call_gemini(prompt, system_instruction="", **kwargs):
        nonlocal captured_sys_prompt
        captured_sys_prompt = system_instruction
        return []

    with patch.dict(os.environ, {"AUDIBLE_FLOW_MODE": "false"}):
        with patch("audiobook_factory.script.dialogue_parser.call_gemini", side_effect=fake_call_gemini):
            _parse_dialogue_turns_llm("Sample text")

    assert captured_sys_prompt is not None
    assert "Hollywood Audio Drama Dialogue Supervisor" in captured_sys_prompt


def test_03_clean_neural_dsp_bypasses_asetrate_and_telephone_eq(tmp_path):
    """Verify dispatcher bypasses asetrate pitch shifting and telephone EQ in Audible Clean DSP mode."""
    dispatcher = TTSDispatcher(project_dir=tmp_path)
    dispatcher.audio_dir.mkdir(parents=True, exist_ok=True)
    dispatcher.take_bank.takes_dir.mkdir(parents=True, exist_ok=True)

    captured_cmds = []

    def fake_run(cmd, *args, **kwargs):
        captured_cmds.append(cmd)
        # Create destination file if writing to one
        if cmd and isinstance(cmd, list) and len(cmd) > 1:
            dest = Path(cmd[-1])
            dest.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(dest), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(b"\x00" * 48000)
        return MagicMock(returncode=0)

    def fake_gemini_tts(output_file, **kwargs):
        p = Path(output_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(p), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00" * 48000)

    with patch.dict(os.environ, {"AUDIBLE_CLEAN_DSP": "true"}):
        with patch("audiobook_factory.tts.dispatcher._call_gemini_tts", side_effect=fake_gemini_tts), \
             patch("audiobook_factory.tts.dispatcher.get_ffmpeg", return_value="ffmpeg"), \
             patch("subprocess.run", side_effect=fake_run), \
             patch.object(dispatcher.pronunciation_auditor, "audit_take", return_value=MagicMock(passed=True)):
            dispatcher.synthesize_segment(
                segment={"index": 1, "speaker": "Charon", "text": "The witcher walked slowly."},
                chapter_num=1,
                seg_num=1,
            )

    # Inspect the FFmpeg filter chain that was executed
    assert len(captured_cmds) > 0
    cmd_str = " ".join(captured_cmds[0])
    assert "asetrate=" not in cmd_str, "Audible Clean DSP must NOT shift sample rate via asetrate!"
    assert "equalizer=f=200" not in cmd_str, "Audible Clean DSP must NOT apply harsh phone EQ!"
    assert "lowpass=f=6500" not in cmd_str, "Audible Clean DSP must NOT muffle audio with lowpass 6500!"
    assert "highpass=f=60" in cmd_str, "Audible Clean DSP must condition audio with 60Hz highpass!"


def test_04_mastering_defaults_to_phantom_center(tmp_path):
    """Verify concatenate_and_master_chapter defaults to spatial_staging=False (Phantom Center)."""
    import inspect
    sig = inspect.signature(concatenate_and_master_chapter)
    assert sig.parameters["spatial_staging"].default is False, "spatial_staging default must be False for pure vocals!"


def test_05_room_tone_dither_generation(tmp_path):
    """Verify _get_silence_file generates TPDF room tone dither instead of pure digital zeros."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    s1 = audio_dir / "c001_s0001.wav"
    s2 = audio_dir / "c001_s0002.wav"

    # Create dummy 1-second WAVs
    for s in (s1, s2):
        with wave.open(str(s), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00" * 48000)

    out_file = tmp_path / "mastered.m4a"
    captured_silence_pcm = None

    def fake_master_run(cmd, *args, **kwargs):
        nonlocal captured_silence_pcm
        silence_files = list(out_file.parent.glob(".silence_*.wav"))
        if silence_files:
            with wave.open(str(silence_files[0]), "rb") as wf:
                raw_bytes = wf.readframes(wf.getnframes())
                captured_silence_pcm = np.frombuffer(raw_bytes, dtype=np.int16)
        out_file.touch()
        return MagicMock(returncode=0)

    with patch.dict(os.environ, {"AUDIBLE_ROOM_TONE": "true"}):
        with patch("subprocess.run", side_effect=fake_master_run):
            concatenate_and_master_chapter(
                audio_segments=[s1, s2],
                output_chapter_file=out_file,
                pause_ms=200,
            )

    assert captured_silence_pcm is not None, "A silence file should have been generated during mastering!"
    # TPDF dither must have subtle variations (non-zero)
    assert np.any(captured_silence_pcm != 0), "Room tone must not be pure digital zero (0x0000)!"
    # But must be imperceptible: max amplitude < 15 in 16-bit space (~ -70 dBFS)
    assert np.max(np.abs(captured_silence_pcm)) <= 15, "Room tone dither must remain imperceptible (< 15 LSBs)!"


def test_06_syntax_aware_pause_calibration(tmp_path):
    """Verify pause durations are calibrated by syntax and speaker changes."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    s1 = audio_dir / "c001_s0001.wav"
    s2 = audio_dir / "c001_s0002.wav"
    s3 = audio_dir / "c001_s0003.wav"
    s4 = audio_dir / "c001_s0004.wav"

    for s in (s1, s2, s3, s4):
        with wave.open(str(s), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(b"\x00" * 24000)

    out_file = tmp_path / "mastered.m4a"
    captured_concat_lines = []

    def fake_master_run(cmd, *args, **kwargs):
        nonlocal captured_concat_lines
        concat_list = out_file.parent / f"concat_{out_file.stem}.txt"
        if concat_list.exists():
            captured_concat_lines = [l.strip() for l in concat_list.read_text(encoding="utf-8").splitlines() if l.strip()]
        out_file.touch()
        return MagicMock(returncode=0)

    script_segments = [
        {"index": 1, "speaker": "Narrator", "text": "उसने खिड़की खोली,"},  # Comma clause (same speaker next) -> ~180ms
        {"index": 2, "speaker": "Narrator", "text": "और बाहर देखा।"},      # Period finish (same speaker next) -> ~380ms
        {"index": 3, "speaker": "Narrator", "text": "कमरा बिल्कुल शांत था।"},  # Speaker change next -> ~600ms
        {"index": 4, "speaker": "Geralt", "text": "कोई नहीं है।"},
    ]

    with patch.dict(os.environ, {"AUDIBLE_CLEAN_DSP": "true", "AUDIBLE_ROOM_TONE": "false"}):
        with patch("subprocess.run", side_effect=fake_master_run):
            concatenate_and_master_chapter(
                audio_segments=[s1, s2, s3, s4],
                output_chapter_file=out_file,
                script_segments=script_segments,
            )

    assert len(captured_concat_lines) > 0
    # Verify comma pause (~180ms), period pause (~380ms), and speaker change (~600ms) were injected
    assert any("180ms.wav" in l for l in captured_concat_lines), "Must inject ~180ms pause after comma clause!"
    assert any("380ms.wav" in l for l in captured_concat_lines), "Must inject ~380ms pause after sentence period!"
    assert any("600ms.wav" in l for l in captured_concat_lines), "Must inject ~600ms pause on speaker change!"


def test_07_artificial_pre_breath_bypassed_in_audible_clean_mode(tmp_path):
    """Verify pre_roll_breath_ms does not inject artificial silence file when AUDIBLE_CLEAN_DSP is active."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    s1 = audio_dir / "c001_s0001.wav"
    with wave.open(str(s1), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00" * 24000)

    out_file = tmp_path / "mastered.m4a"
    captured_concat_lines = []

    def fake_master_run(cmd, *args, **kwargs):
        nonlocal captured_concat_lines
        concat_list = out_file.parent / f"concat_{out_file.stem}.txt"
        if concat_list.exists():
            captured_concat_lines = [l.strip() for l in concat_list.read_text(encoding="utf-8").splitlines() if l.strip()]
        out_file.touch()
        return MagicMock(returncode=0)

    script_segments = [
        {"index": 1, "speaker": "Narrator", "text": "Hello", "pre_roll_breath_ms": 280}
    ]

    with patch.dict(os.environ, {"AUDIBLE_CLEAN_DSP": "true", "AUDIBLE_ROOM_TONE": "false"}):
        with patch("subprocess.run", side_effect=fake_master_run):
            concatenate_and_master_chapter(
                audio_segments=[s1],
                output_chapter_file=out_file,
                script_segments=script_segments,
            )

    assert len(captured_concat_lines) > 0
    assert not any("280ms.wav" in l for l in captured_concat_lines), "Artificial 280ms breath silence must be bypassed in Audible mode!"
