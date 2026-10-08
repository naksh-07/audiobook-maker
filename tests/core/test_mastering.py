#!/usr/bin/env python3
"""
Unit tests for Broadcast Mastering & M4B Packaging platform services.
Tests Two-Pass Loudnorm calculations, compliance report generation, and FFMETADATA1 chapter markers.
"""

from pathlib import Path
import pytest

from audiobook_factory.core.mastering.loudnorm import (
    MasteringSpec,
    TwoPassLoudnormEngine,
)
from audiobook_factory.core.mastering.packager import (
    ChapterMetadata,
    M4BPackager,
)
from tests.core.test_take_bank import create_dummy_wav


class TestBroadcastMastering:
    def test_two_pass_loudnorm_engine(self, tmp_path: Path):
        spec = MasteringSpec(
            target_lufs=-19.0,
            true_peak_ceiling=-1.5,
            loudness_range=6.5,
        )
        engine = TwoPassLoudnormEngine(spec=spec)

        input_wav = create_dummy_wav(tmp_path / "dialogue.wav", duration_sec=2.0)
        output_m4a = tmp_path / "chapter_003_mastered.m4a"

        stats = engine.measure_pass1(input_wav)
        assert "input_i" in stats
        assert "input_tp" in stats

        artifact = engine.apply_pass2(
            input_wav_path=input_wav,
            output_file_path=output_m4a,
            stats=stats,
            chapter_id=3,
        )

        assert artifact.chapter_id == 3
        assert artifact.compliance.integrated_lufs == -19.0
        assert artifact.compliance.true_peak_dbfs <= -1.5
        assert artifact.compliance.is_compliant is True

    def test_m4b_packager_metadata_and_container(self, tmp_path: Path):
        packager = M4BPackager()

        chapters = [
            ChapterMetadata(chapter_index=1, title="Chapter 1: The Voice of Reason", start_ms=0, end_ms=500000),
            ChapterMetadata(chapter_index=2, title="Chapter 2: A Grain of Truth", start_ms=500000, end_ms=1200000),
        ]

        meta_file = tmp_path / "ffmetadata.txt"
        packager.generate_ffmetadata(
            chapters=chapters,
            output_metadata_path=meta_file,
            title="The Last Wish",
            author="Andrzej Sapkowski",
        )

        assert meta_file.exists()
        content = meta_file.read_text(encoding="utf-8")
        assert ";FFMETADATA1" in content
        assert "title=The Last Wish" in content
        assert "[CHAPTER]" in content
        assert "START=500000" in content

        # Package container
        wav1 = create_dummy_wav(tmp_path / "ch1.wav", duration_sec=1.0)
        wav2 = create_dummy_wav(tmp_path / "ch2.wav", duration_sec=1.0)
        out_m4b = tmp_path / "The_Last_Wish.m4b"

        manifest = packager.package_container(
            audio_files=[wav1, wav2],
            chapters=chapters,
            output_m4b_path=out_m4b,
            book_id="the-last-wish",
            title="The Last Wish",
            author="Andrzej Sapkowski",
        )

        assert manifest.book_id == "the-last-wish"
        assert len(manifest.chapters) == 2
        assert manifest.chapters[1].title == "Chapter 2: A Grain of Truth"
        assert manifest.total_duration_sec == 1200.0
