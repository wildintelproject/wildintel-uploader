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
    """The stamp of a file, or None when it cannot be looked at: then nothing is remembered of it."""
    try:
        status = os.stat(path)
    except OSError:
        return None
    return (str(path), status.st_size, status.st_mtime_ns, status.st_ctime_ns)


class OsStamps(FileStamps):
    def stamp(self, path: Path) -> Stamp | None:
        return stamp(path)

    def is_folder(self, path: Path) -> bool:
        return path.is_dir()

    def files_in(self, folder: Path) -> list[Path]:
        return [p for p in folder.rglob("*") if p.is_file()]


class FileHasher(Hasher):
    def hash(self, path: Path, algorithm: str) -> str | None:
        digest = hashlib.new(algorithm)
        try:
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            logger.debug("Could not read %s for its %s: %s", path, algorithm, exc)
            return None
        return digest.hexdigest()
