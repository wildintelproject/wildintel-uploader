"""The runs of the import wizard, kept step by step so that an unfinished one can be resumed. The rules are the domain's (domain.sessions); where
they are kept is what it is given."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from wildintel_uploader.modules.deployments.domain import sessions as rules
from wildintel_uploader.modules.deployments.domain.ports import ImportSessions, SessionFolder


class WizardSessions(ImportSessions):
    def __init__(self, folder: SessionFolder, now: Callable[[], str] = lambda: datetime.now(timezone.utc).isoformat()) -> None:
        self._folder, self._now = folder, now

    def _read(self, task_id: str) -> dict | None:
        return self._folder.read(task_id) if rules.valid_task_id(task_id) else None

    def list(self) -> list[dict]:
        """Every session kept, newest first — those kept where they used to be moved first to where they are kept now."""
        self._folder.move_old()
        return rules.newest_first([m for name in self._folder.names() if rules.valid_task_id(name) and (m := self._folder.read(name)) is not None])

    def save_scan(self, task_id: str | None, source_dir: str, scan: dict) -> dict:
        task_id = rules.check_task_id(task_id) if task_id else rules.new_task_id()
        manifest = rules.scanned(self._read(task_id), task_id, source_dir, scan, self._now())
        self._folder.write(task_id, manifest)
        return manifest

    def save_selection(self, task_id: str, selection: dict) -> dict:
        manifest = rules.selected(self._read(task_id), task_id, selection, self._now())
        self._folder.write(task_id, manifest)
        return manifest

    def save_details(self, task_id: str, deployment: dict) -> dict:
        manifest = rules.ready(self._read(task_id), task_id, deployment, self._now())
        self._folder.write(task_id, manifest)
        return manifest

    def discard(self, task_id: str) -> None:
        self._folder.remove(rules.check_task_id(task_id))
