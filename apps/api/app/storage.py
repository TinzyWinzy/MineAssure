"""Object storage abstraction.

Pilot implementation: local filesystem. Production should provide an S3-compatible
implementation behind the same interface. No business code should touch the
filesystem directly.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path


class ObjectStorage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str | None = None) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalStorage(ObjectStorage):
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal.
        safe = key.replace("\\", "/").lstrip("/")
        target = (self.root / safe).resolve()
        if self.root.resolve() not in target.parents and target != self.root.resolve():
            raise ValueError("invalid storage key")
        return target

    def put(self, key, data, content_type=None):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, key):
        p = self._path(key)
        if not p.is_file():
            raise FileNotFoundError(key)
        return p.read_bytes()

    def exists(self, key):
        return self._path(key).is_file()

    def delete(self, key):
        p = self._path(key)
        if p.is_file():
            p.unlink()


def get_storage() -> ObjectStorage:
    root = os.environ.get("STORAGE_ROOT", "storage")
    return LocalStorage(root)
