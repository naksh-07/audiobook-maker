import os
import pytest
from pathlib import Path
import sqlite3

from audiobook_factory.sound_bank.verification_gate import (
    AudioVerificationGate,
    VerificationResult,
    ERA_BANNED_KEYWORDS,
)
from audiobook_factory.sound_bank import get_sound_bank


def test_verification_gate_nonexistent_file():
    gate = AudioVerificationGate()
    res = gate.verify_asset("non_existent_audio_file.wav", category="AMB")
    assert not res.is_valid
    assert res.fallback_recommended
    assert "does not exist" in res.reason


def test_verification_gate_anachronism_rejection(tmp_path):
    # Create dummy wav
    fake_wav = tmp_path / "medieval_traffic_car_horn.wav"
    fake_wav.write_bytes(b"RIFF" + b"\x00" * 2000)

    gate = AudioVerificationGate()
    res = gate.verify_asset(fake_wav, category="SFX", era="MEDIEVAL_FANTASY")
    assert not res.is_valid
    assert res.fallback_recommended
    assert "Anachronism Detected" in res.reason
    assert "traffic" in res.reason or "car" in res.reason


def test_verification_gate_ambience_duration_contract(tmp_path):
    # Test file that exists in sound bank or create test fixture
    bank = get_sound_bank()
    gate = AudioVerificationGate()

    # If we probe an authentic Witcher ambience (e.g. >= 100s)
    w3_amb = list(Path(bank.bank_root).rglob("05_Ambience_and_Environments/*.wav"))
    if not w3_amb:
        # Search catalog
        res = bank.search("tavern", category="ambience", limit=1, franchise_affinity="the_witcher")
        if res and os.path.exists(res[0]["filepath"]):
            w3_amb = [Path(res[0]["filepath"])]

    if w3_amb and w3_amb[0].exists():
        v = gate.verify_asset(w3_amb[0], category="AMB", era="MEDIEVAL_FANTASY", is_continuous_bed=True)
        assert v.is_valid
        assert v.metrics["duration_sec"] >= 45.0
        assert not v.fallback_recommended


def test_resolver_with_verification_fallback():
    bank = get_sound_bank()
    # Resolve real Witcher ambience with verify=True
    resolved = bank.resolve_sound(
        query="tavern",
        category="ambience",
        era="MEDIEVAL_FANTASY",
        franchise_affinity="the_witcher",
        verify=True,
        is_continuous_bed=True,
    )
    assert resolved is not None
    assert resolved.exists()
    assert resolved.name.endswith((".wav", ".ogg", ".mp3"))

    # Verify that the resolved file is at least 45s long
    gate = AudioVerificationGate()
    probe = gate.probe_audio(resolved)
    assert probe["duration_sec"] >= 45.0


def test_telemetry_self_healing():
    from audiobook_factory.telemetry import get_telemetry_ledger
    ledger = get_telemetry_ledger()
    test_run_id = "test_verification_run_001"

    # Ensure run registers automatically without FK failure
    ledger.record_api_call(
        run_id=test_run_id,
        service="gemini-test",
        endpoint="gemini-2.5-flash",
        status_code=200,
        latency_sec=0.45,
        is_rate_limit=False,
        prompt_tokens=150,
        completion_tokens=50,
        est_cost_usd=0.00002,
    )

    ledger.record_acoustic_metrics(
        run_id=test_run_id,
        chapter_num=999,
        duration_sec=120.5,
        integrated_lufs=-19.0,
        true_peak_dbtp=-1.5,
        loudness_range_lu=4.5,
        phase_correlation=0.88,
    )

    ledger.end_run(run_id=test_run_id, status="SUCCESS")

    # Verify rows in DB
    with sqlite3.connect(str(ledger.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        run = conn.execute("SELECT * FROM production_runs WHERE run_id = ?", (test_run_id,)).fetchone()
        assert run is not None
        assert run["status"] == "SUCCESS"
        assert run["total_duration_sec"] is not None

        api = conn.execute("SELECT * FROM api_telemetry WHERE run_id = ?", (test_run_id,)).fetchone()
        assert api is not None
        assert api["prompt_tokens"] == 150

        ac = conn.execute("SELECT * FROM acoustic_telemetry WHERE run_id = ? AND chapter_num = 999", (test_run_id,)).fetchone()
        assert ac is not None
        assert ac["duration_sec"] == 120.5
        assert ac["integrated_lufs"] == -19.0


def test_verification_gate_foley_duration_limit(tmp_path):
    # Test that > 15s file is rejected as Foley
    gate = AudioVerificationGate()
    bank = get_sound_bank()
    # Resolve long ambience but pass as Foley category
    res = bank.search("tavern", category="ambience", limit=1, franchise_affinity="the_witcher")
    if res and os.path.exists(res[0]["filepath"]):
        v = gate.verify_asset(res[0]["filepath"], category="FOL")
        assert not v.is_valid
        assert v.fallback_recommended
        assert "Foley Action Rejected" in v.reason


def test_sound_spotter_resolution_uses_verification():
    from audiobook_factory.sound_spotter import SoundSpotter
    spotter = SoundSpotter()
    # Test _resolve_ambience_beds with Witcher franchise affinity
    amb_scenes = [{"name": "tavern_inn", "target_lufs": -32.0, "reverb_preset": "room"}]
    resolved = spotter._resolve_ambience_beds(
        ambience_scenes=amb_scenes,
        total_duration_ms=60000,
        banned_tags={"car", "traffic"},
        era="MEDIEVAL_FANTASY",
        franchise_affinity="the_witcher",
    )
    assert len(resolved) == 1
    cue = resolved[0]
    assert Path(cue["asset_path"]).exists()
    assert cue["asset_name"].endswith((".wav", ".ogg", ".mp3"))
    # Verify that the asset is authentic Witcher or certified bed
    gate = AudioVerificationGate()
    p = gate.probe_audio(cue["asset_path"])
    assert p["duration_sec"] >= 45.0
