from __future__ import annotations
from pathlib import Path
from typing import Optional

from audiobook_factory.storage.base import (
    IStorageBackend,
    StorageMetadata,
    StorageObject,
)
from audiobook_factory.storage.local import LocalStorageBackend

_DEFAULT_STORAGE: Optional[IStorageBackend] = None


def get_default_storage(base_dir: Optional[Path | str] = None) -> IStorageBackend:
    """Returns singleton or configured storage backend."""
    global _DEFAULT_STORAGE
    if base_dir:
        return LocalStorageBackend(base_dir)
    if _DEFAULT_STORAGE is None:
        default_dir = Path.cwd() / "audiobooks" / "storage"
        _DEFAULT_STORAGE = LocalStorageBackend(default_dir)
    return _DEFAULT_STORAGE


__all__ = [
    "IStorageBackend",
    "StorageMetadata",
    "StorageObject",
    "LocalStorageBackend",
    "get_default_storage",
]
