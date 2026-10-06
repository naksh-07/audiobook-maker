#!/usr/bin/env python3
"""
Audiobook Factory - Sound Bank Stub (Vocals-Only Engine).
Provides a lightweight, zero-dependency stub of SoundBank for the pure vocals engine.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path

DEFAULT_BANK_DIR = Path("audiobooks/sound_bank")
DEFAULT_DB_PATH = Path("audiobooks/sound_bank/sound_bank.db")


class SoundBank:
    """Lightweight stub SoundBank for Vocals-Only engine."""

    def __init__(self, db_path=None, bank_dir=None):
        self.db_path = db_path
        self.bank_dir = bank_dir

    def stats(self) -> Dict[str, Any]:
        return {
            "total_sounds": 0,
            "total_duration": 0.0,
            "categories": {},
            "status": "decoupled_vocals_only",
        }

    def search(self, query: str, limit: int = 5, category: Optional[str] = None) -> List[Any]:
        return []

    def get_sound(self, asset_id: str) -> Optional[Any]:
        return None

    def resolve_asset_path(self, path: Any) -> Path:
        return Path(str(path))

    def resolve_sound(self, *args, **kwargs) -> Optional[Any]:
        return None

    def _extract_duration(self, *args, **kwargs) -> float:
        return 0.0

    def query(self, *args, **kwargs) -> List[Any]:
        return []


_sound_bank_instance: Optional[SoundBank] = None


def get_sound_bank() -> Optional[SoundBank]:
    """Returns None in Vocals-Only mode."""
    return None
