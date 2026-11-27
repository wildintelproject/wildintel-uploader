"""The use cases of the backups: what can't be done at all is said before anything is written — the first step is taken before answering —, and a
backup made to be downloaded says which file it is."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from wildintel_uploader.modules.backup.domain.ports import BackupGone, Backups, BackupService, Choice


class BackupUseCases(BackupService):
    def __init__(self, backups: Backups) -> None:
        self._backups = backups

    def describe(self, project: str) -> dict:
        return self._backups.describe(project)

    def create(self, dest_dir: Path | None, project: str | None, choice: Choice) -> Iterator[dict]:
        staged = dest_dir is None
        events = self._backups.create(self._backups.staging_dir() if staged else dest_dir, project, choice)
        first = next(events)

        def chained() -> Iterator[dict]:
            for event in (first, *events):
                # made to be downloaded: the last event says which file the browser asks for
                yield {**event, "download": Path(event["path"]).name} if staged and event.get("type") == "done" else event
        return chained()

    def download(self, name: str) -> Path:
        if not self._backups.is_download_name(name):
            raise BackupGone("There is no such backup.")
        path = self._backups.staging_dir() / name
        if not path.is_file():
            raise BackupGone("That backup is not there any more: make it again.")
        return path

    def read(self, path: Path) -> dict:
        return self._backups.read(path)

    def restore(self, path: Path, choice: Choice, replace: bool) -> Iterator[dict]:
        events = self._backups.restore(path, choice, replace)
        try:
            first = next(events)
        except StopIteration:
            first = {"type": "done", "summary": {}}

        def chained() -> Iterator[dict]:
            yield first
            yield from events
        return chained()
