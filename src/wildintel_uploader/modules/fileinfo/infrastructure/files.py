"""FileStamps and Hasher over the file system."""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import Stamp
from wildintel_uploader.modules.fileinfo.domain.ports import FileStamps, Hasher

logger = logging.getLogger(__name__)


def stamp(path: Path | str) -> Stamp | None:
    """The stamp of a file, as the system says it.

    Args:
        path: The file.

    Returns:
        ``(path, size, mtime, ctime)`` — the path as given, the size in bytes, and the modification and change
        times in nanoseconds; None when it cannot be looked at: then nothing is remembered of it.

    Example::

        stamp(Path("/media/sd/IMG_0001.JPG"))
        ("/media/sd/IMG_0001.JPG", 2345678, 1729332312000000000, 1729339517123456789)
    """
    try:
        status = os.stat(path)
    except OSError:
        return None
    return (str(path), status.st_size, status.st_mtime_ns, status.st_ctime_ns)


class OsStamps(FileStamps):
    def stamp(self, path: Path) -> Stamp | None:
        """See FileStamps.stamp: ``stamp``, over the file system."""
        return stamp(path)

    def is_folder(self, path: Path) -> bool:
        """See FileStamps.is_folder."""
        return path.is_dir()

    def files_in(self, folder: Path) -> list[Path]:
        """See FileStamps.files_in: every file under the folder, at any depth, hidden ones too."""
        return [p for p in folder.rglob("*") if p.is_file()]


class FileHasher(Hasher):
    def hash(self, path: Path, algorithm: str) -> str | None:
        """See Hasher.hash: the file read a mebibyte at a time."""
        digest = hashlib.new(algorithm)
        try:
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            logger.debug("Could not read %s for its %s: %s", path, algorithm, exc)
            return None
        return digest.hexdigest()
