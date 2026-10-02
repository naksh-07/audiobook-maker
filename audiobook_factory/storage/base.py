from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Protocol, List, Optional, runtime_checkable
from pathlib import Path


@dataclass
class StorageMetadata:
    """Metadata attributes for a stored object."""
    key: str
    size_bytes: int = 0
    updated_at: float = field(default_factory=time.time)
    mime_type: Optional[str] = None
    sha256: Optional[str] = None


@dataclass
class StorageObject:
    """Full container for retrieved storage data and its metadata."""
    metadata: StorageMetadata
    data: bytes


@runtime_checkable
class IStorageBackend(Protocol):
    """Abstract interface defining required storage operations for studio asset pipelines."""

    def read_bytes(self, key: str) -> bytes:
        """Reads raw binary content for the given key."""
        ...

    def write_bytes(self, key: str, data: bytes, atomic: bool = True) -> str:
        """Writes binary content to the given key, returning its canonical location."""
        ...

    def exists(self, key: str) -> bool:
        """Checks if an object exists at the given key."""
        ...

    def delete(self, key: str) -> bool:
        """Deletes the object at the given key if it exists."""
        ...

    def list_keys(self, prefix: str = "") -> List[str]:
        """Lists all stored object keys matching prefix."""
        ...

    def get_local_path(self, key: str) -> Path:
        """Resolves local absolute Path if supported by backend, else raises NotImplementedError."""
        ...
