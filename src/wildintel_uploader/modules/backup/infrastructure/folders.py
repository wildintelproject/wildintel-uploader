"""The folder of a research project in the collections folder, as a backup reads and restores it: its collections, their deployments and their
files; a file restored is written whole or not at all, and never out of the research project."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from wildintel_uploader.modules.backup.domain.ports import BackupError, FileOnDisk, ProjectFolders
from wildintel_uploader.shared import storage


def _files(folder: Path) -> list[FileOnDisk]:
    return [FileOnDisk(p.relative_to(folder).as_posix(), p, p.stat().st_size) for p in sorted(p for p in folder.rglob("*") if p.is_file())]


class CollectionsFolder(ProjectFolders):
    """`root` says the collections folder, asked each time."""

    def __init__(self, root: Callable[[], Path]) -> None:
        self._root = root

    def _project(self, project: str) -> Path:
        try:
            return self._root() / storage.valid_project_id(project)
        except storage.StorageError as exc:
            raise BackupError(str(exc)) from exc

    def check_project(self, project: str) -> None:
        self._project(project)

    def collections(self, project: str) -> list[str]:
        folder = self._project(project)
        return sorted((c.name for c in folder.iterdir() if c.is_dir()), reverse=True) if folder.is_dir() else []

    def deployments(self, project: str, collection: str) -> list[str]:
        return sorted(d.name for d in (self._project(project) / collection).iterdir() if d.is_dir() and not d.name.startswith("."))

    def deployment_files(self, project: str, collection: str, deployment: str) -> list[FileOnDisk] | None:
        folder = self._project(project) / collection / deployment
        return _files(folder) if folder.is_dir() else None

    def collection_files(self, project: str, collection: str) -> list[FileOnDisk]:
        folder = self._project(project) / collection
        return [FileOnDisk(p.name, p, p.stat().st_size) for p in sorted(p for p in folder.iterdir() if p.is_file())]

    def holds(self, project: str, relative: str) -> bool:
        target = self._project(project) / PurePosixPath(relative)
        return (target.is_dir() and any(target.iterdir())) or target.is_file()

    def make_project(self, project: str) -> None:
        self._project(project).mkdir(parents=True, exist_ok=True)

    def check_inside(self, project: str, relatives: list[str]) -> None:
        folder = self._project(project).resolve()
        for relative in relatives:
            if not (folder / PurePosixPath(relative)).resolve().is_relative_to(folder):
                raise BackupError("That backup has files with a path that goes out of it: it is not restored.")

    def write(self, project: str, relative: str, data: bytes) -> None:
        target = self._project(project) / PurePosixPath(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
        with os.fdopen(fd, "wb") as out:
            out.write(data)
        os.replace(tmp, target)

    def remove(self, project: str, relative: str) -> None:
        folder = self._project(project)
        target = folder / PurePosixPath(relative)
        target.unlink(missing_ok=True)
        for parent in target.parents:
            if parent == folder or not parent.is_relative_to(folder):
                break
            try:
                parent.rmdir()   # only when empty
            except OSError:
                break
