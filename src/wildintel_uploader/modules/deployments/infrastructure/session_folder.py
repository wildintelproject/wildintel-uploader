"""The sessions of the import wizard on disk: a folder each, named by its task id, inside the sessions folder of the app's state, holding its
session.json — written whole or not at all."""
from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.deployments.domain import sessions as rules
from wildintel_uploader.modules.deployments.domain.ports import SessionFolder


class SessionsOnDisk(SessionFolder):
    """`root` says the sessions folder and `old` where they used to be kept (<documents>/wildintel-uploader/sessions), asked each time."""

    def __init__(self, root: Callable[[], Path], old: Callable[[], Path]) -> None:
        self._root, self._old = root, old

    def read(self, task_id: str) -> dict | None:
        path = self._root() / task_id / rules.MANIFEST
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def write(self, task_id: str, manifest: dict) -> None:
        folder = self._root() / task_id
        folder.mkdir(parents=True, exist_ok=True)
        tmp = folder / f"{rules.MANIFEST}.tmp"   # a crash never leaves half a manifest behind
        tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(folder / rules.MANIFEST)

    def remove(self, task_id: str) -> None:
        shutil.rmtree(self._root() / task_id, ignore_errors=True)

    def names(self) -> list[str]:
        root = self._root()
        return [entry.name for entry in root.iterdir()] if root.is_dir() else []

    def move_old(self) -> None:
        old, new = self._old(), self._root()
        if not old.is_dir() or old.resolve() == new.resolve():
            return
        for entry in old.iterdir():
            if entry.is_dir() and rules.valid_task_id(entry.name) and (entry / rules.MANIFEST).is_file() and not (new / entry.name).exists():
                new.mkdir(parents=True, exist_ok=True)
                shutil.move(str(entry), str(new / entry.name))
        try:
            old.rmdir()
        except OSError:
            pass
