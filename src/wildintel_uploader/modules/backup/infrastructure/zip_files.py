"""The backups as zip files: a manifest first, the data compressed, the images stored as they are — already compressed —, written whole or not
at all; read only when no file of it has a path that goes out of it. Those made to be downloaded are made in a folder of the system's, and kept
a day."""
from __future__ import annotations

import json
import os
import tempfile
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path

from wildintel_uploader.modules.backup.domain import archive as rules
from wildintel_uploader.modules.backup.domain.ports import Archives, BackupArchive, BackupError, Entry

_KEPT_FOR = 24 * 3600   # a backup made to be downloaded is kept a day: it can be downloaded again meanwhile


class ZipArchive(BackupArchive):
    def __init__(self, zf: zipfile.ZipFile) -> None:
        self._zf = zf

    def names(self) -> set[str]:
        return set(self._zf.namelist())

    def read(self, name: str) -> bytes:
        return self._zf.read(name)

    def __exit__(self, *exc) -> None:
        self._zf.close()


class ZipBackups(Archives):
    def check_destination(self, dest_dir: Path) -> None:
        if not dest_dir.is_dir():
            raise BackupError(f"The folder {dest_dir} is not there.")

    def open(self, path: Path) -> BackupArchive:
        if not path.is_file():
            raise BackupError(f"The file {path} is not there.")
        try:
            zf = zipfile.ZipFile(path)
        except zipfile.BadZipFile as exc:
            raise BackupError("That file is not a backup: it is not a .zip.") from exc
        if any(rules.leaves_the_backup(name) for name in zf.namelist()):
            zf.close()
            raise BackupError("That backup has files with a path that goes out of it: it is not restored.")
        return ZipArchive(zf)

    def make(self, dest_dir: Path, name: str, manifest: dict, entries: list[Entry]) -> Iterator[dict]:
        target = dest_dir / name
        fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=".backup.", suffix=".tmp")
        os.close(fd)
        try:
            with zipfile.ZipFile(tmp, "w") as zf:
                zf.writestr(rules.MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False), compress_type=zipfile.ZIP_DEFLATED)
                for index, entry in enumerate(entries, start=1):
                    if entry.path is None:
                        zf.writestr(entry.name, json.dumps(entry.data, indent=2, ensure_ascii=False), compress_type=zipfile.ZIP_DEFLATED)
                    else:   # an image is already compressed: it is stored as it is
                        zf.write(entry.path, entry.name, compress_type=zipfile.ZIP_STORED if rules.is_image(entry.name) else zipfile.ZIP_DEFLATED)
                    yield {"type": "file", "index": index, "total": len(entries), "name": entry.name}
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return target, target.stat().st_size

    def staging_dir(self) -> Path:
        folder = Path(tempfile.gettempdir()) / "wildintel-uploader-backups"
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.iterdir():
            try:
                if old.is_file() and time.time() - old.stat().st_mtime > _KEPT_FOR:
                    old.unlink()
            except OSError:
                pass
        return folder

    def is_there(self, path: Path) -> bool:
        return path.is_file()
