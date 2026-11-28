"""Memory — what was found out about a file, kept in the process for as long as the file is the same: bounded (the oldest forgotten first), not
written anywhere; a restart starts empty, but for what the Store kept on disk."""
from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Generic, TypeVar

from wildintel_uploader.modules.fileinfo.domain.models import CameraInfo, Stamp, Tags
from wildintel_uploader.modules.fileinfo.domain.ports import Memory

V = TypeVar("V")
K = TypeVar("K")


class FileMemo(Generic[V]):
    """A bounded memory of what was found out about files, by their stamp. Safe to use from several threads."""

    def __init__(self, limit: int = 50_000) -> None:
        self._limit = limit
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key) -> V | None:
        if key is None:
            return None
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key, value: V) -> None:
        if key is None:
            return
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self._limit:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        return len(self._items)


# What ExifTool read of an image — its tags by their names in lowercase —, also kept on disk.
EXIF: FileMemo[Tags] = FileMemo()
# The camera of an image as Pillow read it, when there is no ExifTool.
CAMERAS: FileMemo[CameraInfo] = FileMemo()
# What else is known of a file, by (stamp, kind): whether it decodes, its hashes.
FACTS: FileMemo[str] = FileMemo(limit=150_000)


def forget_all() -> None:
    EXIF.clear()
    CAMERAS.clear()
    FACTS.clear()


class ProcessMemory(Memory):
    """The memories of this module, the same for every instance: what one finds out, the others know."""

    def get_tags(self, key: Stamp | None) -> Tags | None:
        return EXIF.get(key)

    def put_tags(self, key: Stamp | None, tags: Tags) -> None:
        EXIF.put(key, tags)

    def get_camera(self, key: Stamp | None) -> CameraInfo | None:
        return CAMERAS.get(key)

    def put_camera(self, key: Stamp | None, camera: CameraInfo) -> None:
        CAMERAS.put(key, camera)

    def get_fact(self, key: Stamp | None, kind: str) -> str | None:
        return FACTS.get((key, kind)) if key is not None else None

    def put_fact(self, key: Stamp | None, kind: str, value: str) -> None:
        if key is not None:
            FACTS.put((key, kind), value)

    def clear(self) -> None:
        forget_all()
