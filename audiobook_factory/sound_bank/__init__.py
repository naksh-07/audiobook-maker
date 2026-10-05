#!/usr/bin/env python3
"""
Audiobook Factory - Pillar 3.6: High-Performance Local Sound Bank Engine.
Unified facade exporting SoundBank class, singleton accessor, and domain defaults.
Decomposed into modular subpackages (db, indexer, downloader, search, sound_card,
resolver, dsp_metrics, harvester) with 100% backward compatibility.
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional

from audiobook_factory.sound_bank_cache import SoundBankCacheManager
from audiobook_factory.deterministic_audio_analyzer import DeterministicAudioAnalyzer

from .db import DatabaseMixin, DEFAULT_BANK_DIR, DEFAULT_DB_PATH
from .indexer import IndexerMixin
from .downloader import DownloaderMixin
from .search import SearchMixin
from .sound_card import SoundCardMixin
from .resolver import ResolverMixin, SoundAssetStagingError
from .dsp_metrics import DSPMetricsMixin
from .harvester import HarvesterMixin
from .verification_gate import AudioVerificationGate, VerificationResult
from .metadata_backfill import BBCMetadataBackfillEngine


class SoundBank(
    DatabaseMixin,
    IndexerMixin,
    DownloaderMixin,
    SearchMixin,
    SoundCardMixin,
    ResolverMixin,
    DSPMetricsMixin,
    HarvesterMixin,
):
    """High-performance SQLite FTS5 Sound Bank catalog for audio drama production."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        bank_root: Optional[Path] = None,
    ):
        self.bank_root = Path(bank_root or DEFAULT_BANK_DIR).resolve()
        self.bank_root.mkdir(parents=True, exist_ok=True)
        self.bank_dir = self.bank_root
        self.cache_dir = self.bank_root / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(db_path or (self.bank_root / "sound_bank.db")).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_manager = SoundBankCacheManager(db_path=self.db_path, cache_dir=self.cache_dir)
        self.audio_analyzer = DeterministicAudioAnalyzer()
        self._init_db()


_GLOBAL_SOUND_BANK: Optional[SoundBank] = None


def get_sound_bank(bank_dir: Optional[Path] = None) -> SoundBank:
    """Returns singleton instance of SoundBank."""
    global _GLOBAL_SOUND_BANK
    if _GLOBAL_SOUND_BANK is None:
        _GLOBAL_SOUND_BANK = SoundBank(bank_root=bank_dir or DEFAULT_BANK_DIR)
    return _GLOBAL_SOUND_BANK


__all__ = [
    "SoundBank",
    "get_sound_bank",
    "DEFAULT_BANK_DIR",
    "DEFAULT_DB_PATH",
    "DatabaseMixin",
    "IndexerMixin",
    "DownloaderMixin",
    "SearchMixin",
    "SoundCardMixin",
    "ResolverMixin",
    "DSPMetricsMixin",
    "HarvesterMixin",
    "AudioVerificationGate",
    "VerificationResult",
    "SoundAssetStagingError",
]
