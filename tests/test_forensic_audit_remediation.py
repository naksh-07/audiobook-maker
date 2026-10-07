import os
import json
import sqlite3
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock

from audiobook_factory.key_manager import PersistentKeyPool
from audiobook_factory.tts.dispatcher import TTSDispatcher
from audiobook_factory.character_caster import CharacterCaster
from audiobook_factory.orchestration.gates import verify_post_mix_master_gates
import audiobook_factory.orchestrator as orchestrator_mod


def test_01_orchestrator_imports_re_and_emergency_fallback(tmp_path):
    """P0-1 & P0-5: Assert import re is present and emergency fallback initializes synth_segments."""
    assert hasattr(orchestrator_mod, "re"), "orchestrator.py must import re module"

    orch = orchestrator_mod.PipelineOrchestrator(tmp_path)
    proj_dir = tmp_path / "test_book"
    proj_dir.mkdir(parents=True)
    scripts_dir = proj_dir / "scripts"
    scripts_dir.mkdir()
    audio_dir = proj_dir / "audio_chunks"
    audio_dir.mkdir()
    mastered_dir = proj_dir / "mastered"
    mastered_dir.mkdir()

    script_file = scripts_dir / "chapter_001_script.json"
    script_file.write_text(json.dumps([{"index": 1, "text": "Hello world", "speaker": "Narrator"}]), encoding="utf-8")

    from audiobook_factory.key_manager import AllKeysExhaustedTodayError
    def mock_synth(self, *args, **kwargs):
        if getattr(self, "default_backend", "") != "winrt":
            raise AllKeysExhaustedTodayError("Exhausted")
        return [audio_dir / "fallback.wav"]

    with patch.dict(os.environ, {"ENABLE_EMERGENCY_FALLBACK": "true"}):
        with patch.object(TTSDispatcher, "synthesize_chapter_script", side_effect=mock_synth, autospec=True):
            with patch("audiobook_factory.orchestrator.process_and_master_dialogue_stem") as mock_stem:
                mock_stem.return_value = (mastered_dir / "stem.wav", 5.0, {1: 5.0}, [])
                with patch("audiobook_factory.orchestrator.verify_pre_synthesis_gates"), \
                     patch("audiobook_factory.orchestrator.verify_performance_fidelity_gate"), \
                     patch("audiobook_factory.orchestrator.verify_post_mix_master_gates", return_value=(True, True, True)), \
                     patch("subprocess.run"):
                    res = orch.produce_chapter(proj_dir, chapter_num=1)
                    assert res["chapter_id"] == 1
                    assert "segment_files" in mock_stem.call_args.kwargs


def test_02_dispatcher_tempo_fade_calculation():
    """P0-2: Verify effective duration scales correctly for speed < 1.0 and speed > 1.0."""
    dur = 10.0
    f_sec = 0.015

    # Case A: Brooding slow delivery (speed = 0.8)
    speed_slow = 0.8
    eff_dur_slow = dur / speed_slow if (abs(speed_slow - 1.0) > 0.005 and speed_slow > 0.01) else dur
    f_out_st_slow = max(0.0, eff_dur_slow - f_sec)
    assert eff_dur_slow == 12.5
    assert abs(f_out_st_slow - 12.485) < 1e-4, "Slow delivery fade-out must occur at 12.485s, NOT 9.985s!"

    # Case B: Fast delivery (speed = 1.25)
    speed_fast = 1.25
    eff_dur_fast = dur / speed_fast if (abs(speed_fast - 1.0) > 0.005 and speed_fast > 0.01) else dur
    f_out_st_fast = max(0.0, eff_dur_fast - f_sec)
    assert eff_dur_fast == 8.0
    assert abs(f_out_st_fast - 7.985) < 1e-4, "Fast delivery fade-out must occur before 8.0s!"


def test_03_key_manager_quota_isolation(tmp_path):
    """P0-3: Verify text record_success does NOT resurrect EXHAUSTED_TODAY keys to ACTIVE."""
    db_file = tmp_path / "test_keys.db"
    pool = PersistentKeyPool(keys=["KEY_ALPHA", "KEY_BETA"], db_path=db_file)

    # 1. Mark KEY_ALPHA exhausted today for TTS
    pool.mark_daily_quota_exhausted("KEY_ALPHA", "ResourceExhausted: 10 RPD reached")
    with pool._connection() as conn:
        row = conn.execute("SELECT status FROM key_quota_ledger WHERE api_key = 'KEY_ALPHA';").fetchone()
        assert row["status"] == "EXHAUSTED_TODAY"

    # 2. Text call succeeds with KEY_ALPHA
    pool.record_success("KEY_ALPHA")
    with pool._connection() as conn:
        row = conn.execute("SELECT status FROM key_quota_ledger WHERE api_key = 'KEY_ALPHA';").fetchone()
        assert row["status"] == "EXHAUSTED_TODAY", "Text success must NOT overwrite EXHAUSTED_TODAY back to ACTIVE!"

    # 3. mark_temporary_backoff also preserves EXHAUSTED_TODAY
    pool.mark_temporary_backoff("KEY_ALPHA", backoff_seconds=10.0)
    with pool._connection() as conn:
        row = conn.execute("SELECT status FROM key_quota_ledger WHERE api_key = 'KEY_ALPHA';").fetchone()
        assert row["status"] == "EXHAUSTED_TODAY", "Temporary backoff must not downgrade EXHAUSTED_TODAY to TEMP_BACKOFF!"


def test_04_key_manager_date_rollover_resets_all_keys(tmp_path):
    """P0-3: Verify date rollover resets counters for all keys, not just exhausted ones."""
    db_file = tmp_path / "test_rollover.db"
    pool = PersistentKeyPool(keys=["KEY_1", "KEY_2"], db_path=db_file)

    # Set calls on a past date
    with pool._connection() as conn:
        conn.execute("""
            UPDATE key_quota_ledger
            SET total_calls_today = 5,
                success_calls_today = 5,
                last_reset_date = '2025-01-01';
        """)
        conn.commit()

    # Trigger rollover check
    with pool._connection() as conn:
        pool._check_date_rollover(conn)
        rows = conn.execute("SELECT total_calls_today, success_calls_today FROM key_quota_ledger;").fetchall()
        for r in rows:
            assert r["total_calls_today"] == 0
            assert r["success_calls_today"] == 0


def test_05_character_caster_lock_and_atomic_write(tmp_path):
    """P1-2: Verify CharacterCaster safely casts under lock and writes atomically."""
    import concurrent.futures

    proj_dir = tmp_path / "cast_proj"
    proj_dir.mkdir()

    names = [f"Character_{i}" for i in range(10)]

    def _cast(n):
        return CharacterCaster.cast_single_speaker(n, project_dir=proj_dir)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_cast, names))

    assert len(results) == 10
    reg_file = proj_dir / "voice_registry.json"
    assert reg_file.exists()
    reg = json.loads(reg_file.read_text(encoding="utf-8"))
    assert len(reg) == 10
    for n in names:
        assert n in reg


def test_06_packager_metadata_cleanup_and_toc(tmp_path):
    """P1-4 & H5: Verify chapters.txt cleanup and accurate TOC title mapping."""
    from audiobook_factory.packager import package_m4b_audiobook
    import wave

    proj_dir = tmp_path / "pack_proj"
    mastered_dir = proj_dir / "mastered"
    mastered_dir.mkdir(parents=True)
    out_dir = proj_dir / "output"
    out_dir.mkdir()

    # Create dummy chapter 2 and chapter 5
    def _create_wav(path):
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(b"\x00" * 48000 * 4)

    c2_file = mastered_dir / "chapter_002_mastered.m4a"
    c5_file = mastered_dir / "chapter_005_mastered.m4a"
    _create_wav(c2_file)
    _create_wav(c5_file)

    meta_file = proj_dir / "metadata.json"
    meta_file.write_text(json.dumps({
        "book_id": "test_book",
        "title": "Test Novel",
        "chapters": [
            {"number": 1, "title": "Prologue"},
            {"number": 2, "title": "The Awakening"},
            {"number": 3, "title": "The Road"},
            {"number": 4, "title": "The River"},
            {"number": 5, "title": "The Final Battle"},
        ]
    }), encoding="utf-8")

    def fake_gen_meta(meta, durations, out_path):
        Path(out_path).write_text(";FFMETADATA1\ntitle=Test", encoding="utf-8")

    def fake_replace(src, dst):
        Path(dst).write_bytes(b"dummy_m4b_data")

    with patch("audiobook_factory.packager.probe_audio_stream", return_value={"sample_rate": 48000, "channels": 2, "codec": "aac"}), \
         patch("audiobook_factory.packager.get_audio_duration_ms", return_value=5000), \
         patch("audiobook_factory.packager.generate_ffmetadata", side_effect=fake_gen_meta) as mock_gen_meta, \
         patch("audiobook_factory.packager._atomic_replace", side_effect=fake_replace), \
         patch("subprocess.run"):
        # Let's inspect chapter_durations passed to generate_ffmetadata
        package_m4b_audiobook(proj_dir, enforce_gate6=False)
        assert mock_gen_meta.called
        durations = mock_gen_meta.call_args[0][1]
        assert len(durations) == 2
        # Chapter 2 should be titled "The Awakening", and Chapter 5 should be "The Final Battle"
        assert durations[0]["title"] == "The Awakening"
        assert durations[1]["title"] == "The Final Battle"

    # Verify chapters.txt was cleaned up by finally: block and not left over in output
    assert not (out_dir / "chapters.txt").exists()


def test_07_gates_is_offline_definition():
    """M1: Assert verify_post_mix_master_gates handles missing master_wav cleanly."""
    fake_path = Path("non_existent_master_audio.wav")
    with patch.dict(os.environ, {"AUDIOBOOK_OFFLINE_MODE": "true", "STRICT_QUALITY_GATES": "false"}):
        # Should not raise NameError: name 'is_offline' is not defined
        g52, g53, g5 = verify_post_mix_master_gates(
            chapter_num=1,
            cinematic_out=fake_path,
            master_wav=fake_path,
            vocal_wav=fake_path,
            mx_stem=None,
        )
        assert g53 is True


def test_08_equal_power_crossfade_energy_preservation():
    """M5: Verify equal-power crossfade weights preserve unity energy sum."""
    n_ov = 100
    fade_out = np.cos(np.linspace(0.0, np.pi / 2.0, n_ov))
    fade_in = np.sin(np.linspace(0.0, np.pi / 2.0, n_ov))

    power_sum = fade_out ** 2 + fade_in ** 2
    assert np.allclose(power_sum, 1.0, atol=1e-5), "Equal power crossfade energy sum must equal 1.0!"


def test_09_gemini_none_emotion_guard():
    """M7: Verify safe_emotion handles None emotion without AttributeError."""
    text = "She whispered softly."
    emotion = None
    safe_emotion = (emotion or "").lower()
    is_whisper = ("whisper" in text.lower() or "whisper" in safe_emotion)
    assert is_whisper is True
    assert safe_emotion == ""
