"""MediaFolder — the images of a folder and what is known of them, for those that look at them all (the prevalidation, the postvalidation): each
thing is asked of what is known of the files (FileInfoService) the first time it is asked for, and given again to the next — the camera, the dates, which images decode, the hashes (#140).
Two checks that ask at the same time get it once: each thing has its lock."""
from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from wildintel_uploader.modules.fileinfo.domain.models import CameraInfo
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.fileinfo.domain.models import IMAGE_EXTENSIONS

T = TypeVar("T")
R = TypeVar("R")
# How the images are gone through one by one: in parallel, telling how many are done.
ParallelMap = Callable[..., list]
# progress(step, done, total): how far a long step is.
Progress = Callable[[str, int, int], None]


class MediaFolder:
    def __init__(self, root: Path, info: FileInfoService, pmap: ParallelMap, progress: Progress | None = None,
                 files: list[Path] | None = None) -> None:
        self.root, self._info, self._pmap, self._progress = root, info, pmap, progress
        self.files = files if files is not None else [p for p in root.rglob("*") if p.is_file()]
        self.images = [p for p in self.files if p.suffix.lower() in IMAGE_EXTENSIONS]
        self._known: dict[str, object] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self.reader: str | None = None   # what read the cameras: "exiftool" or "pillow" — once they were read

    def relative(self, path: Path) -> str:
        return str(path.relative_to(self.root))

    def _once(self, name: str, find: Callable[[], T]) -> T:
        with self._guard:
            lock = self._locks.setdefault(name, threading.Lock())
        with lock:
            if name not in self._known:
                self._known[name] = find()
            return self._known[name]  # type: ignore[return-value]

    def _tell(self, step: str, done: int) -> None:
        if self._progress:
            self._progress(step, done, len(self.images))

    def cameras(self) -> dict[Path, CameraInfo]:
        def find() -> dict[Path, CameraInfo]:
            self._tell("cameras", 0)
            cameras, self.reader = self._info.cameras(self.images)
            self._tell("cameras", len(self.images))
            return cameras
        return self._once("cameras", find)

    def dates(self) -> dict[Path, datetime | None]:
        def find() -> dict[Path, datetime | None]:
            taken = self._info.dates(self.images)
            self._tell("dates", len(self.images))
            return taken
        return self._once("dates", find)

    def tags(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        """Asked each time: what is known of the files already remembers them."""
        return self._info.tags(paths, tags)

    def decode_errors(self) -> dict[Path, str | None]:
        """Why each image does not decode — None for one that does —, image by image, in parallel."""
        def find() -> dict[Path, str | None]:
            progress = None if self._progress is None else (lambda done: self._tell("corrupted", done))
            return dict(zip(self.images, self._pmap(self._info.decode_error, self.images, progress=progress)))
        return self._once("decoded", find)

    def decode_errors_if_known(self) -> dict[Path, str | None]:
        """Which images do not decode, only if a check already found it out: none otherwise."""
        return self._known.get("decoded", {})  # type: ignore[return-value]

    def hashes(self, paths: list[Path], algorithm: str) -> dict[Path, str | None]:
        """The hash of the content of these files, in parallel; remembered while each file is the same."""
        return dict(zip(paths, self._pmap(lambda p: self._info.hash(p, algorithm), paths)))
