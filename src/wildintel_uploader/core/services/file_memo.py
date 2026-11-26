"""What was found out about a file, kept in memory for as long as the file is the same.

The steps of an import — the validation of the images, the preprocessing, the seal — are separate requests, and each reads the same images again: ExifTool for their
camera, and a full decoding to see that they are not corrupted. The result of each is remembered here under the file's path, its size and its modification time: a file
that has been changed — or replaced by another — has other ones and is read again, so what is remembered is never what an earlier file said.

It lives in the process, is bounded (the oldest is forgotten first) and is not written anywhere: a restart starts empty — except what ExifTool read, which
exif_store also keeps on disk."""
from __future__ import annotations

import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Generic, TypeVar

V = TypeVar("V")

# What a file is, for this: where it is, how big and when it was last modified (in nanoseconds, to tell two writes in the same second).
Stamp = tuple[str, int, int]


def stamp(path: Path | str) -> Stamp | None:
    """The stamp of a file, or None when it cannot be looked at: then nothing is remembered of it."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return (str(path), status.st_size, status.st_mtime_ns)


class FileMemo(Generic[V]):
    """A bounded memory of what was found out about files, by their stamp. Safe to use from several threads."""

    def __init__(self, limit: int = 50_000) -> None:
        self._limit = limit
        self._items: OrderedDict[Stamp, V] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Stamp | None) -> V | None:
        if key is None:
            return None
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: Stamp | None, value: V) -> None:
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


# What ExifTool read of an image — its tags by their names in lowercase (see camera_info._metadata) —, also kept on disk (see exif_store).
EXIF: FileMemo[dict[str, str | None]] = FileMemo()
# The camera of an image as Pillow read it, when there is no ExifTool, and with which reader ("pillow").
CAMERAS: FileMemo[tuple[object, str]] = FileMemo()
# The images that were decoded in full without an error: not corrupted. An image that failed is not kept: it is looked at again.
DECODED: FileMemo[bool] = FileMemo()


def forget_all() -> None:
    EXIF.clear()
    CAMERAS.clear()
    DECODED.clear()
