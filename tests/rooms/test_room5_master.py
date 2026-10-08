#!/usr/bin/env python3
"""
Unit tests for Room 5 Broadcast Vocal Mastering Engine.
Standard: v6.0-ENTERPRISE-DAG
"""

import wave
import numpy as np
from pathlib import Path
import pytest

from audiobook_factory.contracts.editorial import (
    ChapterDialogueManifest,
    TimelineCueRecord,
    TimelineLedger,
)
from audiobook_factory.contracts.ledger import ProjectMetadataRecord
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.rooms.room5_master.master_engine import BroadcastMasteringEngine


def _create_mock_wav(file_path: Path, duration_sec: float = 3.0, sample_rate: int = 48000) -> Path:
    """Generates a clean 48kHz mono test wav file."""
    n_samples = int(duration_sec * sample_rate)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    # 440Hz sine wave at approx -18 dBFS amplitude
    signal = (0.25 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)

    file_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(signal.tobytes())
    return file_path


class TestRoom5Master:
    def test_mastering_engine_end_to_end(self, tmp_path: Path):
        ledger = PipelineLedger(db_path=tmp_path / "test_ledger.db")
        proj_dir = tmp_path / "project"

        ledger.upsert_project(ProjectMetadataRecord(
            project_id="test_book",
            source_file_path=str(tmp_path / "source.txt"),
            title="Test Book",
            author="Author",
            book_bible_path=str(proj_dir / "book_bible.json"),
            cast_lock_path=str(proj_dir / "cast_lock.json"),
        ))

        master_engine = BroadcastMasteringEngine(project_dir=proj_dir, ledger=ledger)

        # Create input dialogue stem
        wav_path = _create_mock_wav(proj_dir / "dialogue_ch01.wav", duration_sec=3.0)

        dialogue_manifest = ChapterDialogueManifest(
            chapter_id=1,
            script_hash="script_hash_dummy",
            lossless_dialogue_wav_path=str(wav_path),
            timeline_ledger=TimelineLedger(
                chapter_id=1,
                total_duration_sec=3.0,
                cues=[
                    TimelineCueRecord(
                        segment_uid="ch01_seg001",
                        speaker="Narrator",
                        start_time_sec=0.0,
                        end_time_sec=3.0,
                    )
                ]
            ),
            takes=[],
        )

        artifact, gate_audit = master_engine.master_chapter(
            dialogue_manifest=dialogue_manifest,
            project_id="test_book",
            target_lufs=-19.0,
        )

        assert artifact.chapter_id == 1
        assert Path(artifact.mastered_audio_path).exists()
        assert artifact.compliance.integrated_lufs == pytest.approx(-19.0, abs=0.6)
        assert artifact.compliance.true_peak_dbfs <= -1.4
        assert gate_audit.decision == "PASSED"
        assert gate_audit.gate_name == "GATE_5_0_MASTER"

        # Verify SQLite ledger state
        stage = ledger.get_stage("ch001_room5_master")
        assert stage is not None
        assert stage.status == "COMPLETED"
        artifacts = ledger.get_artifacts_for_stage("ch001_room5_master")
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "MASTERED_M4A"

        # Test packaging complete M4B audiobook
        m4b_manifest = master_engine.package_audiobook(
            master_artifacts=[artifact],
            book_id="test_book",
            title="Test Mastered Audiobook",
            author="Test Author",
        )

        assert Path(m4b_manifest.container_m4b_path).exists()
        assert len(m4b_manifest.chapters) == 1
        assert m4b_manifest.total_duration_sec > 0
