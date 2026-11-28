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

class FileInfoMetadata(ABC):
    """What the metadata of the images say — read with ExifTool, or Pillow when there is none —, and reading them ahead."""

    @abstractmethod
    def tags(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        """The value of each tag asked for, in each file.

        Read by ExifTool, all the files in one run, and remembered; only without it — or when it fails —, by Pillow,
        an image at a time: the standard EXIF tags only.

        Args:
            paths: The files.
            tags: The tags wanted, by their ExifTool names: ``Make``, ``ISO``, ``GPSLatitude``…

        Returns:
            For each file, the value of each tag by the name asked (its case kept), None where the file has not got
            it. Every file is in it, with no tag when none is asked.

        Example::

            tags([Path("/media/sd/IMG_0001.JPG")], ["Make", "ISO"])
            {Path("/media/sd/IMG_0001.JPG"): {"Make": "Browning", "ISO": None}}
        """

    @abstractmethod
    def dates(self, paths: list[Path]) -> dict[Path, datetime | None]:
        """The capture date of each image, as the camera's wall clock.

        The first there is of DateTimeOriginal (when it was taken), CreateDate (when it was digitized) and ModifyDate
        (when the camera last changed the file) (#227); any time zone is dropped.

        Args:
            paths: The images.

        Returns:
            The date of each image, naive; None for one that says none.

        Example::

            dates([Path("/media/sd/IMG_0001.JPG"), Path("/media/sd/IMG_0002.JPG")])
            {Path("/media/sd/IMG_0001.JPG"): datetime(2026, 10, 19, 14, 5, 12), Path("/media/sd/IMG_0002.JPG"): None}
        """

    @abstractmethod
    def cameras(self, paths: list[Path]) -> tuple[dict[Path, CameraInfo], str]:
        """The camera that took each image, and what read them.

        Args:
            paths: The images.

        Returns:
            ``(cameras, reader)``: the camera of each image — an empty CameraInfo for one that says nothing of it —,
            and ``"exiftool"`` or ``"pillow"``. Pillow reads only BodySerialNumber, so it finds the serial number of
            fewer cameras. With no image, ``({}, "pillow")``.

        Example::

            cameras([Path("/media/sd/IMG_0001.JPG")])
            ({Path("/media/sd/IMG_0001.JPG"): CameraInfo(model="Browning BTC-8A", camera_id="BR5071")}, "exiftool")
        """

    @abstractmethod
    def metadata(self, paths: list[Path], tags: list[str]) -> dict[Path, Tags] | None:
        """All that ExifTool read of each image.

        What every reading asks for (BASE_TAGS: the camera and the capture date) and ``tags``, besides what an earlier
        reading of the same file left. The images already remembered — in memory, then on disk — are not read again;
        the others, in one run.

        Args:
            paths: The images.
            tags: The tags wanted besides BASE_TAGS, by their ExifTool names.

        Returns:
            The tags of each image by their names in lowercase, None where it has not got one — every tag asked is
            there; for an image ExifTool could not read, every one is None, and it is read again the next time. None
            when there is no ExifTool, or when it failed: then the readings go to Pillow.

        Example::

            metadata([Path("/media/sd/IMG_0001.JPG")], ["ISO"])
            {Path("/media/sd/IMG_0001.JPG"): {"make": "Browning", "model": "BTC-8A", "serialnumber": "BR5071",
                                              "internalserialnumber": None, …, "datetimeoriginal": "2026:10:19 14:05:12",
                                              "createdate": None, "modifydate": None, "iso": "100"}}
        """

    @abstractmethod
    def prefetch(self, paths: list[Path], tags: list[str] | None = None) -> threading.Thread | None:
        """Starts reading in the background what the steps of an import will ask of these images (#140).

        It is there when they ask: one that asks meanwhile waits for the reading rather than reading them again.

        Args:
            paths: The images.
            tags: The tags wanted besides BASE_TAGS, by their ExifTool names.

        Returns:
            The thread that reads them; None — nothing is read — without ExifTool, with no images, or when reading
            ahead is turned off (the tests). A reading that fails only means the steps read the images themselves.
        """

    @abstractmethod
    def exiftool_path(self) -> str | None:
        """Where ExifTool is.

        Returns:
            The path of the executable — the one bundled with the app first, then the one on the PATH —; None when
            there is none.
        """


class FileInfoContent(ABC):
    """What the content of a file is: whether an image decodes, its hash, its size."""

    @abstractmethod
    def decode_error(self, path: Path) -> str | None:
        """Whether an image opens and decodes in full, and why not.

        Only an image that decoded is remembered: one that failed is decoded again the next time.

        Args:
            path: The image.

        Returns:
            None when it decodes in full; otherwise what failed, as the decoder says it.

        Example::

            decode_error(Path("/media/sd/IMG_0042.JPG"))
            "image file is truncated (12 bytes not processed)"
        """

    @abstractmethod
    def mark_decoded(self, path: Path) -> None:
        """Remembers that an image decodes.

        What a step that decoded it in full for its own sake (the preprocessing) found out, so that it is not
        decoded again.

        Args:
            path: The image.
        """

    @abstractmethod
    def hash(self, path: Path, algorithm: str) -> str | None:
        """The hash of the content of a file, remembered while the file is the same.

        Args:
            path: The file.
            algorithm: A name hashlib knows: ``"sha1"``, ``"sha256"``…

        Returns:
            The hash in hex; None when the file cannot be read.

        Example::

            hash(Path("/media/sd/IMG_0001.JPG"), "sha1")
            "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12"
        """

    @abstractmethod
    def size(self, path: Path) -> int | None:
        """How big a file is.

        Args:
            path: The file.

        Returns:
            Its size in bytes; None when it is not there.
        """


class FileInfoFiles(ABC):
    """The files of a folder, as what is known of them is asked for."""

    @abstractmethod
    def is_folder(self, path: Path) -> bool:
        """Whether a path is a folder.

        Args:
            path: The path.

        Returns:
            True when it is a folder that is there.
        """

    @abstractmethod
    def files_in(self, folder: Path) -> list[Path]:
        """Every file under a folder — what a folder of images is looked at by.

        Args:
            folder: The folder.

        Returns:
            Its files and those of all its subfolders, at any depth, in no particular order; not the folders.
        """


class FileInfoCache(ABC):
    """What is remembered of the files."""

    @abstractmethod
    def forget(self) -> None:
        """Forgets everything known of the files, in memory and on disk: all of it is found out again when asked."""


class FileInfoService(FileInfoMetadata, FileInfoContent, FileInfoFiles, FileInfoCache, ABC):
    """All that is known of the files — what the checks, the preprocessing and the reports ask. Whoever needs only a part asks for that one:
    FileInfoMetadata, FileInfoContent, FileInfoFiles or FileInfoCache."""


# ── out: what the use cases are given ──

class MetadataReader(ABC):
    """What reads the metadata of many images at once — ExifTool."""

    @abstractmethod
    def available(self) -> bool:
        """Whether there is one to read with.

        Returns:
            True when it can be asked to read; it is asked each time, so one installed while the app runs is found.
        """

    def location(self) -> str | None:
        """Where the reader is, when it is a program.

        Returns:
            Its path; None when it is not a program, or there is none.
        """
        return None

    @abstractmethod
    def read(self, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
        """The tags asked of each file, in one go.

        Args:
            paths: The files.
            tags: The tags wanted, by their ExifTool names.

        Returns:
            For each file read, the value of each tag by the name asked, None where it has not got it; a file it
            could not read is left out.

        Raises:
            MetadataReadFailed: The reader failed as a whole.
        """


class MetadataReadFailed(Exception):
    """The reader failed as a whole: the use cases fall back to FallbackReader."""


class FallbackReader(ABC):
    """What reads an image at a time when there is no MetadataReader, or it failed — Pillow: the standard tags only."""

    @abstractmethod
    def tags(self, path: Path, tags: list[str]) -> dict[str, str | None]:
        """The value of each tag asked for in one image — the standard EXIF tags only.

        Args:
            path: The image.
            tags: The tags wanted, by their ExifTool names; those Pillow knows by another name are translated.

        Returns:
            The value of each tag by the name asked; None where it has not got it, or the image cannot be read.
        """

    @abstractmethod
    def date(self, path: Path) -> datetime | None:
        """The capture date of one image, as the camera's wall clock.

        Args:
            path: The image.

        Returns:
            The first there is of DateTimeOriginal, DateTimeDigitized and DateTime; None when it says none, or the
            image cannot be read.
        """

    @abstractmethod
    def camera(self, path: Path) -> CameraInfo:
        """The camera that took one image.

        Args:
            path: The image.

        Returns:
            Its make and model, and its BodySerialNumber; an empty CameraInfo when the image cannot be read.
        """


class Decoder(ABC):
    @abstractmethod
    def decode_error(self, path: Path) -> str | None:
        """Whether an image decodes in full.

        Args:
            path: The image.

        Returns:
            None when it decodes in full; otherwise why not.
        """


class Hasher(ABC):
    @abstractmethod
    def hash(self, path: Path, algorithm: str) -> str | None:
        """The hash of the content of a file.

        Args:
            path: The file.
            algorithm: A name hashlib knows: ``"sha1"``, ``"sha256"``…

        Returns:
            The hash in hex; None when the file cannot be read.
        """


class FileStamps(ABC):
    """What the system says of the files: their stamps, and which there are in a folder."""

    @abstractmethod
    def stamp(self, path: Path) -> Stamp | None:
        """The stamp of a file: what tells it from an earlier version of it, or from another put in its place.

        Args:
            path: The file.

        Returns:
            ``(path, size, mtime, ctime)`` (see Stamp); None when it cannot be looked at — then nothing is remembered
            of it.
        """

    @abstractmethod
    def is_folder(self, path: Path) -> bool:
        """Whether a path is a folder.

        Args:
            path: The path.

        Returns:
            True when it is a folder that is there.
        """

    @abstractmethod
    def files_in(self, folder: Path) -> list[Path]:
        """Every file under a folder.

        Args:
            folder: The folder.

        Returns:
            Its files and those of all its subfolders, at any depth; not the folders.
        """


class Memory(ABC):
    """What is remembered in the process: bounded, and empty after a restart."""

    @abstractmethod
    def get_tags(self, stamp: Stamp | None) -> Tags | None:
        """The tags remembered of a file.

        Args:
            stamp: The stamp of the file; None — a file that could not be looked at — has nothing.

        Returns:
            Its tags by their names in lowercase; None when nothing is remembered of it.
        """

    @abstractmethod
    def put_tags(self, stamp: Stamp | None, tags: Tags) -> None:
        """Remembers the tags of a file, in place of what it had.

        Args:
            stamp: The stamp of the file; None remembers nothing.
            tags: Its tags by their names in lowercase.
        """

    @abstractmethod
    def get_camera(self, stamp: Stamp | None) -> CameraInfo | None:
        """The camera Pillow read of an image, when there is no ExifTool.

        Args:
            stamp: The stamp of the image; None has nothing.

        Returns:
            Its camera; None when it was not read.
        """

    @abstractmethod
    def put_camera(self, stamp: Stamp | None, camera: CameraInfo) -> None:
        """Remembers the camera Pillow read of an image.

        Args:
            stamp: The stamp of the image; None remembers nothing.
            camera: What Pillow read.
        """

    @abstractmethod
    def get_fact(self, stamp: Stamp | None, kind: str) -> str | None:
        """Something else remembered of a file: whether it decodes, a hash.

        Args:
            stamp: The stamp of the file; None has nothing.
            kind: What: ``"decoded"``, ``"sha1"``, ``"sha256"``…

        Returns:
            Its value (``"1"`` for one that decodes; the hash in hex); None when it is not remembered.
        """

    @abstractmethod
    def put_fact(self, stamp: Stamp | None, kind: str, value: str) -> None:
        """Remembers something else of a file.

        Args:
            stamp: The stamp of the file; None remembers nothing.
            kind: What: ``"decoded"``, ``"sha1"``, ``"sha256"``…
            value: Its value.
        """

    @abstractmethod
    def clear(self) -> None:
        """Forgets everything it remembers."""


class Store(ABC):
    """What is kept on disk, for after a restart: a cache, that may be removed at any time — and that, when it cannot be used, is as if it were
    empty."""

    @abstractmethod
    def get_tags(self, stamps: list[Stamp]) -> dict[Stamp, Tags]:
        """The tags kept of these files.

        Args:
            stamps: The stamps of the files.

        Returns:
            The tags of each one kept with that very stamp, by their names in lowercase; one that is not kept — or
            was kept for another version of the file — is left out. Empty when the store cannot be read.
        """

    @abstractmethod
    def put_tags(self, values: dict[Stamp, Tags]) -> None:
        """Keeps the tags of these files, in place of what an earlier version of each one said.

        Args:
            values: The tags of each file by its stamp. What cannot be written is not kept, and nothing fails.
        """

    @abstractmethod
    def get_facts(self, stamps: list[Stamp], kind: str) -> dict[Stamp, str]:
        """Something else kept of these files.

        Args:
            stamps: The stamps of the files.
            kind: What: ``"decoded"``, ``"sha1"``, ``"sha256"``…

        Returns:
            Its value for each one kept with that very stamp; the others are left out. Empty when the store cannot be
            read.
        """

    @abstractmethod
    def put_facts(self, values: dict[Stamp, str], kind: str) -> None:
        """Keeps something else of these files, in place of what an earlier version of each one had.

        Args:
            values: Its value for each file by its stamp.
            kind: What: ``"decoded"``, ``"sha1"``, ``"sha256"``…
        """

    @abstractmethod
    def clear(self) -> None:
        """Forgets everything it keeps."""


Progress = Callable[[int], None]
