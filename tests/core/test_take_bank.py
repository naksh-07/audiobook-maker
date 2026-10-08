#!/usr/bin/env python3
"""
Unit tests for Tier 1 TakeBank Content-Addressed Audio Cache.
Tests hash determinism, cache lookup hit/miss, audio persistence, and LRU pruning.
"""

import wave
from pathlib import Path
import pytest
import numpy as np

from audiobook_factory.contracts.screenplay import ScreenplaySegment
from audiobook_factory.core.cache.ledger import PipelineLedger
from audiobook_factory.core.cache.take_bank import TakeBank


def create_dummy_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 48000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = int(duration_sec * sample_rate)
    samples = (np.sin(2 * np.pi * 440 * np.arange(n_samples) / sample_rate) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return path


@pytest.fixture
def take_bank_fixture(tmp_path: Path):
    db_file = tmp_path / "test_ledger.db"
    ledger = PipelineLedger(db_path=db_file)
    cache_dir = tmp_path / "cache"
    bank = TakeBank(cache_dir=cache_dir, ledger=ledger, max_cache_bytes=50000)
    return bank, tmp_path


class TestTakeBank:
    def test_deterministic_take_hash(self, take_bank_fixture):
        bank, _ = take_bank_fixture
        seg1 = ScreenplaySegment(
            segment_uid="s01",
            beat_ref="b01",
            speaker="Geralt",
            voice_id="Charon",
            text="विचर ने तलवार निकाली।",
            pitch_shift=-4.0,
            speed_multiplier=0.95,
            temperature=0.35,
        )
        seg2 = ScreenplaySegment(
            segment_uid="s01_copy",
            beat_ref="b01",
            speaker="Geralt",
            voice_id="Charon",
            text="विचर ने तलवार निकाली।",
            pitch_shift=-4.0,
            speed_multiplier=0.95,
            temperature=0.35,
        )
        assert bank.compute_take_hash(seg1) == bank.compute_take_hash(seg2)

    def test_store_and_lookup_take(self, take_bank_fixture):
        bank, tmp_path = take_bank_fixture
        seg = ScreenplaySegment(
            segment_uid="ch01_seg001",
            beat_ref="b01",
            speaker="Narrator",
            voice_id="Aoede",
            text="सड़क खाली थी।",
            pitch_shift=0.0,
            speed_multiplier=1.0,
            temperature=0.32,
        )

        # Cache Miss
        assert bank.lookup_take(seg) is None

        # Store take
        dummy_wav = create_dummy_wav(tmp_path / "temp_take.wav", duration_sec=1.5)
        stored_meta = bank.store_take(seg, dummy_wav, project_id="test_proj", chapter_id=1)
        assert stored_meta.duration_sec >= 1.4
        assert stored_meta.was_cache_hit is False

        # Cache Hit
        cached_meta = bank.lookup_take(seg)
        assert cached_meta is not None
        assert cached_meta.was_cache_hit is True
        assert cached_meta.take_content_hash == stored_meta.take_content_hash
        assert Path(cached_meta.take_wav_path).exists()

    def test_lru_pruning(self, take_bank_fixture):
        bank, tmp_path = take_bank_fixture

        # Create multiple takes exceeding max_cache_bytes (50,000 bytes)
        for i in range(10):
            seg = ScreenplaySegment(
                segment_uid=f"seg_{i}",
                beat_ref="b01",
                speaker="Speaker",
                voice_id="Puck",
                text=f"Line number {i} text content for testing LRU cache eviction.",
            )
            dummy_wav = create_dummy_wav(tmp_path / f"temp_{i}.wav", duration_sec=0.5)
            bank.store_take(seg, dummy_wav, project_id="test_proj", chapter_id=1)

        # Run LRU prune
        pruned_count = bank.prune_lru(max_bytes=10000)
        assert pruned_count > 0
