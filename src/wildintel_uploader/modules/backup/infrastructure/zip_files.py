"""Backups over the code of before (backup_service): zip files with a manifest, the collections folder they are of, the version of the app that
made them. What it refuses is the module's BackupError; what fails mid-way says what failed."""
from __future__ import annotations

import logging
import re
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypeVar

from wildintel_uploader.modules.backup.domain.ports import BackupError, Backups, Choice

logger = logging.getLogger(__name__)
T = TypeVar("T")
_DOWNLOADS = re.compile(r"^wildintel-backup_[A-Za-z0-9_.-]+_\d{8}-\d{6}\.zip$")
_KEPT_FOR = 24 * 3600   # a backup made to be downloaded is kept a day: it can be downloaded again meanwhile


def _old():
    from wildintel_uploader.modules.backup.infrastructure import backup_service
    return backup_service


def _root() -> Path:
    from wildintel_uploader.entrypoints import config
    return config.collections_dir()


def _ours(call: Callable[[], T]) -> T:
    try:
        return call()
    except _old().BackupError as exc:
        raise BackupError(str(exc)) from exc


def _told(events: Iterator[dict], what: str) -> Iterator[dict]:
    """The events; the first is taken as they are asked for — what can't be done at all is said then, before anything is written."""
    try:
        yield from events
    except _old().BackupError as exc:
        raise BackupError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        from wildintel_uploader.shared.logs import debugging
        logger.warning("%s failed: %s", what, exc, exc_info=debugging())
        raise BackupError(f"{what} failed: {exc}") from exc


class ZipBackups(Backups):
    def describe(self, project: str) -> dict:
        return _ours(lambda: _old().describe_project(_root(), project))

    def create(self, dest_dir: Path, project: str | None, choice: Choice) -> Iterator[dict]:
        from wildintel_uploader.shared.version import current_version
        events = _ours(lambda: _old().create_backup(_root(), dest_dir, settings=choice.settings, research_project_id=project, project_files=choice.project_files,
                                                    visits=choice.visits, deployments=choice.deployments, images=choice.images, app_version=current_version()))
        return _told(events, "The backup")

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

    def is_download_name(self, name: str) -> bool:
        return bool(_DOWNLOADS.match(name))

    def read(self, path: Path) -> dict:
        return _ours(lambda: _old().read_backup(_root(), path))

    def restore(self, path: Path, choice: Choice, replace: bool) -> Iterator[dict]:
        events = _ours(lambda: _old().restore_backup(_root(), path, settings=choice.settings, project_files=choice.project_files, visits=choice.visits,
                                                     deployments=choice.deployments, images=choice.images, replace=replace))
        return _told(events, "The restoration")
