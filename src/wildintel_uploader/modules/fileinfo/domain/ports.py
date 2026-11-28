"""The ports of what is known of the files: the contract the rest of the app asks it through (FileInfoService), and what its use cases are given —
a reader of metadata (ExifTool), one for when there is none (Pillow), a decoder, a hasher, and where it is remembered (in memory, and on disk)."""
from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import CameraInfo, Stamp, Tags


# ── in: the contract ──

class FileInfoService(ABC):
    """What is known of the files of images, each thing found out once while the file is the same."""

    @abstractmethod
    def tags(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        """The value of each tag asked for (by its ExifTool name: Make, ISO, GPSLatitude…) in each file, by the name asked — None where it has not
        got it. ExifTool reads them, all the files in one run; only without it, Pillow (the standard tags only)."""

    @abstractmethod
    def dates(self, paths: list[Path]) -> dict[Path, datetime | None]:
        """The capture date of each image, as the camera's wall clock — DateTimeOriginal, else CreateDate, else ModifyDate (#227)."""

    @abstractmethod
    def cameras(self, paths: list[Path]) -> tuple[dict[Path, CameraInfo], str]:
        """The camera of each image, and what read them: "exiftool" or "pillow"."""

    @abstractmethod
    def metadata(self, paths: list[Path], tags: list[str]) -> dict[Path, Tags] | None:
        """All that ExifTool read of each image — what every reading asks for and `tags` —, by the names in lowercase; None without ExifTool."""

    @abstractmethod
    def decode_error(self, path: Path) -> str | None:
        """None when the image opens and decodes in full; otherwise why not. Only one that decoded is remembered: one that failed is looked at again."""

    @abstractmethod
    def mark_decoded(self, path: Path) -> None:
        """Remembers that an image decodes — what a step that decoded it in full for its own sake (the preprocessing) found out."""

    @abstractmethod
    def hash(self, path: Path, algorithm: str) -> str | None:
        """The hash of the content of a file ("sha1", "sha256"), in hex; None when it cannot be read."""

    @abstractmethod
    def size(self, path: Path) -> int | None:
        """How many bytes a file is; None when it is not there."""

    @abstractmethod
    def prefetch(self, paths: list[Path], tags: list[str] | None = None) -> threading.Thread | None:
        """Starts reading in the background what the steps of an import will ask of these images, so that it is there when they ask (#140): one
        that asks meanwhile waits for it rather than reading them again. Nothing without ExifTool, or with no images. Gives the thread."""

    @abstractmethod
    def exiftool_path(self) -> str | None:
        """Where ExifTool is — None when there is none."""

    @abstractmethod
    def forget(self) -> None:
        """Forgets everything, in memory and on disk."""


# ── out: what the use cases are given ──

    @abstractmethod
    def is_folder(self, path: Path) -> bool: ...

    @abstractmethod
    def files_in(self, folder: Path) -> list[Path]:
        """Every file under a folder — what a folder of images is looked at by."""


class MetadataReader(ABC):
    """What reads the metadata of many images at once — ExifTool."""

    @abstractmethod
    def available(self) -> bool:
        """Whether there is one to read with."""

    def location(self) -> str | None:
        """Where the reader is, when it is a program — None otherwise."""
        return None

    @abstractmethod
    def read(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        """The tags asked of each file, by the names asked; a file it could not read is left out. Raises MetadataReadFailed when it fails."""


class MetadataReadFailed(Exception):
    """The reader failed as a whole: the use cases fall back to FallbackReader."""


class FallbackReader(ABC):
    """What reads an image at a time when there is no MetadataReader, or it failed — Pillow: the standard tags only."""

    @abstractmethod
    def tags(self, path: Path, tags: list[str]) -> dict[str, str | None]: ...

    @abstractmethod
    def date(self, path: Path) -> datetime | None: ...

    @abstractmethod
    def camera(self, path: Path) -> CameraInfo: ...


class Decoder(ABC):
    @abstractmethod
    def decode_error(self, path: Path) -> str | None:
        """None when the image decodes in full; otherwise why not."""


class Hasher(ABC):
    @abstractmethod
    def hash(self, path: Path, algorithm: str) -> str | None:
        """The hash of the content of a file, in hex; None when it cannot be read."""


class FileStamps(ABC):
    """What the system says of the files: their stamps, and which there are in a folder."""

    @abstractmethod
    def stamp(self, path: Path) -> Stamp | None:
        """The stamp of a file, or None when it cannot be looked at: then nothing is remembered of it."""

    @abstractmethod
    def is_folder(self, path: Path) -> bool: ...

    @abstractmethod
    def files_in(self, folder: Path) -> list[Path]:
        """Every file under a folder."""


class Memory(ABC):
    """What is remembered in the process: bounded, and empty after a restart."""

    @abstractmethod
    def get_tags(self, stamp: Stamp | None) -> Tags | None: ...

    @abstractmethod
    def put_tags(self, stamp: Stamp | None, tags: Tags) -> None: ...

    @abstractmethod
    def get_camera(self, stamp: Stamp | None) -> CameraInfo | None:
        """The camera Pillow read, when there is no ExifTool."""

    @abstractmethod
    def put_camera(self, stamp: Stamp | None, camera: CameraInfo) -> None: ...

    @abstractmethod
    def get_fact(self, stamp: Stamp | None, kind: str) -> str | None: ...

    @abstractmethod
    def put_fact(self, stamp: Stamp | None, kind: str, value: str) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


class Store(ABC):
    """What is kept on disk, for after a restart: a cache, that may be removed at any time — and that, when it cannot be used, is as if it were
    empty."""

    @abstractmethod
    def get_tags(self, stamps: list[Stamp]) -> dict[Stamp, Tags]: ...

    @abstractmethod
    def put_tags(self, values: dict[Stamp, Tags]) -> None: ...

    @abstractmethod
    def get_facts(self, stamps: list[Stamp], kind: str) -> dict[Stamp, str]: ...

    @abstractmethod
    def put_facts(self, values: dict[Stamp, str], kind: str) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


Progress = Callable[[int], None]
