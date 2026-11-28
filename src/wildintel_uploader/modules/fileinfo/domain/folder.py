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
    """The images of a folder and what is known of them, for those that look at them all.

    Each thing is asked of what is known of the files the first time a check asks for it, and given again to the
    next; two checks that ask at the same time get it once.

    Args:
        root: The folder.
        info: What is known of the files.
        pmap: How the images are gone through one by one: in parallel, telling how many are done.
        progress: ``progress(step, done, total)``, how far a long step is (``"cameras"``, ``"dates"``,
            ``"corrupted"``); None tells nothing.
        files: The files of the folder, when the caller has them already; None looks for them under ``root``.

    Attributes:
        files: Every file under the folder.
        images: Those of them that are images (by their extension, IMAGE_EXTENSIONS).
        reader: What read the cameras, ``"exiftool"`` or ``"pillow"`` — None until they were read.
    """
    def __init__(self, root: Path, info: FileInfoService, pmap: ParallelMap, progress: Progress | None = None,
                 files: list[Path] | None = None) -> None:
        self.root, self._info, self._pmap, self._progress = root, info, pmap, progress
        self.files = files if files is not None else info.files_in(root)
        self.images = [p for p in self.files if p.suffix.lower() in IMAGE_EXTENSIONS]
        self._known: dict[str, object] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()
        self.reader: str | None = None   # what read the cameras: "exiftool" or "pillow" — once they were read

    def relative(self, path: Path) -> str:
        """The path of a file of the folder, relative to it.

        Args:
            path: A file under the folder.

        Returns:
            Its path from the folder, as the results of the checks say it.

        Example::

            MediaFolder(Path("/media/sd"), …).relative(Path("/media/sd/DCIM/IMG_0001.JPG"))
            "DCIM/IMG_0001.JPG"
        """
        return str(path.relative_to(self.root))

    def _once(self, name: str, find: Callable[[], T]) -> T:
        """A thing of the folder, found out the first time it is asked for.

        Args:
            name: What it is: ``"cameras"``, ``"dates"``, ``"decoded"``.
            find: How it is found out.

        Returns:
            What ``find`` gave the first time; one that asks while it is being found out waits for it.
        """
        with self._guard:
            lock = self._locks.setdefault(name, threading.Lock())
        with lock:
            if name not in self._known:
                self._known[name] = find()
            return self._known[name]  # type: ignore[return-value]

    def _tell(self, step: str, done: int) -> None:
        """Tells how far a long step is, when there is someone to tell it.

        Args:
            step: The step.
            done: How many images it went through, of all the images of the folder.
        """
        if self._progress:
            self._progress(step, done, len(self.images))

    def cameras(self) -> dict[Path, CameraInfo]:
        """The camera of each image of the folder, read once.

        Returns:
            The camera of each image — an empty CameraInfo for one that says nothing of it. What read them is left
            in ``reader``.
        """
        def find() -> dict[Path, CameraInfo]:
            self._tell("cameras", 0)
            cameras, self.reader = self._info.cameras(self.images)
            self._tell("cameras", len(self.images))
            return cameras
        return self._once("cameras", find)

    def dates(self) -> dict[Path, datetime | None]:
        """The capture date of each image of the folder, read once.

        Returns:
            The date of each image, as the camera's wall clock; None for one that says none.
        """
        def find() -> dict[Path, datetime | None]:
            taken = self._info.dates(self.images)
            self._tell("dates", len(self.images))
            return taken
        return self._once("dates", find)

    def tags(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        """The value of some tags in some files — asked each time: what is known of the files already remembers them.

        Args:
            paths: The files.
            tags: The tags, by their ExifTool names.

        Returns:
            For each file, the value of each tag by the name asked; None where it has not got it.
        """
        return self._info.tags(paths, tags)

    def decode_errors(self) -> dict[Path, str | None]:
        """Why each image of the folder does not decode, found out once, image by image, in parallel.

        Returns:
            For each image, None when it decodes in full, otherwise why not.
        """
        def find() -> dict[Path, str | None]:
            progress = None if self._progress is None else (lambda done: self._tell("corrupted", done))
            return dict(zip(self.images, self._pmap(self._info.decode_error, self.images, progress=progress)))
        return self._once("decoded", find)

    def decode_errors_if_known(self) -> dict[Path, str | None]:
        """Which images do not decode, only if a check already found it out.

        Returns:
            What ``decode_errors`` gave; empty when it was not asked for yet — nothing is decoded for it.
        """
        return self._known.get("decoded", {})  # type: ignore[return-value]

    def sizes(self, paths: list[Path]) -> dict[Path, int | None]:
        """How big some files are.

        Args:
            paths: The files.

        Returns:
            The size of each one in bytes; None for one that is not there.
        """
        return {path: self._info.size(path) for path in paths}

    def hashes(self, paths: list[Path], algorithm: str) -> dict[Path, str | None]:
        """The hash of the content of some files, in parallel; remembered while each file is the same.

        Args:
            paths: The files.
            algorithm: A name hashlib knows: ``"sha1"``, ``"sha256"``…

        Returns:
            The hash of each one in hex; None for one that cannot be read.
        """
        return dict(zip(paths, self._pmap(lambda p: self._info.hash(p, algorithm), paths)))
