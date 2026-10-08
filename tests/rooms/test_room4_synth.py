#!/usr/bin/env python3
"""
Unit tests for Room 4 Multi-Cast TTS & Dialogue Editorial Engine.
Standard: v6.0-ENTERPRISE-DAG
"""

from pathlib import Path
import pytest

from audiobook_factory.contracts.screenplay import ScreenplayScript, ScreenplaySegment, SegmentProvenance
from audiobook_factory.contracts.ledger import ProjectMetadataRecord
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.core.cache.take_bank import TakeBank
from audiobook_factory.rooms.room4_synth.synth_engine import SynthesisAndEditorialEngine


class TestRoom4Synth:
    def test_synthesis_and_editorial_engine_end_to_end(self, tmp_path: Path):
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

        take_bank = TakeBank(cache_dir=proj_dir / ".cache", ledger=ledger)
        synth_engine = SynthesisAndEditorialEngine(
            project_dir=proj_dir,
            take_bank=take_bank,
            ledger=ledger,
        )

        # Create sample screenplay script
        segments = [
            ScreenplaySegment(
                segment_uid="ch01_seg001",
                beat_ref="ch01_beat001",
                speaker="गेराल्ट",
                voice_id="Charon",
                text="मैं जानता हूँ तुम कौन हो।",
                formant_signature="p-4_t0.95",
                pitch_shift=-4.0,
                speed_multiplier=0.95,
                temperature=0.38,
                acting_instruction="understated natural dialogue",
                pre_speech_pause_ms=150,
                post_speech_pause_ms=250,
                provenance=SegmentProvenance(
                    origin="AUTO_ATTRIBUTED",
                    user_locked=False,
                    content_hash="hash_seg001",
                ),
            ),
            ScreenplaySegment(
                segment_uid="ch01_seg002",
                beat_ref="ch01_beat001",
                speaker="Narrator",
                voice_id="Aoede",
                text="अंगीठी में आग ज़ोर से जल रही थी।",
                formant_signature="p0_t0_eq0",
                pitch_shift=0.0,
                speed_multiplier=1.0,
                temperature=0.32,
                acting_instruction="calm, steady, articulate",
                pre_speech_pause_ms=200,
                post_speech_pause_ms=400,
                provenance=SegmentProvenance(
                    origin="AUTO_ATTRIBUTED",
                    user_locked=False,
                    content_hash="hash_seg002",
                ),
            ),
        ]

        script = ScreenplayScript(
            chapter_id=1,
            translation_hash="trans_hash_dummy",
            segments=segments,
        )

        # Pass 1: Cold cache -> All misses
        manifest1, gate1 = synth_engine.synthesize_chapter(
            script=script,
            project_id="test_book",
        )

        assert manifest1.chapter_id == 1
        assert len(manifest1.takes) == 2
        assert all(t.was_cache_hit is False for t in manifest1.takes)
        assert Path(manifest1.lossless_dialogue_wav_path).exists()
        assert len(manifest1.timeline_ledger.cues) == 2
        assert manifest1.timeline_ledger.total_duration_sec > 0
        assert gate1.decision == "PASSED"
        assert gate1.gate_name == "GATE_4_0_AUDIO"

        # Pass 2: Warm cache -> All hits
        manifest2, gate2 = synth_engine.synthesize_chapter(
            script=script,
            project_id="test_book",
        )

        assert len(manifest2.takes) == 2
        assert all(t.was_cache_hit is True for t in manifest2.takes)
        assert gate2.decision == "PASSED"

        # Verify SQLite ledger state
        stage = ledger.get_stage("ch001_room4_synth")
        assert stage is not None
        assert stage.status == "COMPLETED"
        artifacts = ledger.get_artifacts_for_stage("ch001_room4_synth")
        assert len(artifacts) == 1
        assert artifacts[0].artifact_type == "DIALOGUE_WAV"
