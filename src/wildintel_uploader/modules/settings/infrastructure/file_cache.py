"""What was read of each settings file, kept while the file is the same — apart from how a file is read (toml_files): reading one with Dynaconf takes
time, and the app reads the settings at almost every step. A file is read again when its version changes (its size, when it was changed, the
variables of the environment that override it) or when it is forgotten (written). A copy is given each time: what is given may be changed by who
asked.

The lock guards only the dict, never a read: two reads of the same file at once both read it, and one of them is kept. The routes that read the
settings are synchronous (FastAPI runs them in its pool of threads), so nothing here holds the event loop."""
from __future__ import annotations

import copy
import threading
from collections.abc import Callable, Hashable
from pathlib import Path
from typing import Generic, TypeVar

T = TypeVar("T")


class CachedReading(Generic[T]):
    """`read(path)` as `reader` gives it, read again only when `version(path)` changes; `forget(path)` drops what was kept of it."""

    def __init__(self, reader: Callable[[Path], T], version: Callable[[Path], Hashable], copy_of: Callable[[T], T] = copy.deepcopy) -> None:
        self._reader, self._version, self._copy = reader, version, copy_of
        self._kept: dict[Path, tuple[Hashable, T]] = {}
        self._lock = threading.Lock()

    def read(self, path: Path) -> T:
        version = self._version(path)
        with self._lock:
            kept = self._kept.get(path)
        if kept is None or kept[0] != version:
            kept = (version, self._reader(path))
            with self._lock:
                self._kept[path] = kept
        return self._copy(kept[1])

    def forget(self, path: Path) -> None:
        with self._lock:
            self._kept.pop(path, None)
