from __future__ import annotations
import os
import tempfile
import hashlib
from pathlib import Path
from typing import List, Optional

from audiobook_factory.storage.base import IStorageBackend, StorageMetadata, StorageObject


class LocalStorageBackend:
    """
    Standard filesystem implementation of IStorageBackend.
    Enforces atomic write semantics, strict directory isolation, and zero path traversal vulnerabilities.
    """

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        """Resolves relative storage key to an absolute Path, preventing traversal attacks."""
        clean_key = key.replace("\\", "/").lstrip("/")
        target_path = (self.base_dir / clean_key).resolve()
        # Security invariant: target must remain strictly inside base_dir
        if not str(target_path).startswith(str(self.base_dir)):
            raise ValueError(f"Path traversal detected: '{key}' escapes root '{self.base_dir}'")
        return target_path

    def read_bytes(self, key: str) -> bytes:
        target = self._resolve(key)
        if not target.exists():
            raise FileNotFoundError(f"Storage object not found: {key}")
        return target.read_bytes()

    def write_bytes(self, key: str, data: bytes, atomic: bool = True) -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)

        if atomic:
            # Write to temporary file in the same target directory before rename to ensure atomic POSIX/Windows swap
            with tempfile.NamedTemporaryFile("wb", dir=str(target.parent), delete=False) as tf:
                tf.write(data)
                temp_name = tf.name
            os.replace(temp_name, str(target))
        else:
            target.write_bytes(data)

        return str(target)

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).exists()
        except ValueError:
            return False

    def delete(self, key: str) -> bool:
        try:
            target = self._resolve(key)
            if target.exists() and target.is_file():
                target.unlink()
                return True
            return False
        except Exception:
            return False

    def list_keys(self, prefix: str = "") -> List[str]:
        keys: List[str] = []
        for p in self.base_dir.rglob("*"):
            if p.is_file():
                rel_key = p.relative_to(self.base_dir).as_posix()
                if not prefix or rel_key.startswith(prefix):
                    keys.append(rel_key)
        return sorted(keys)

    def get_local_path(self, key: str) -> Path:
        return self._resolve(key)
