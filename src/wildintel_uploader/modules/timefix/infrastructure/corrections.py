"""The fixes made to the dates of a folder, written down beside its images in time_corrections.json — what, to which images, by how much, why,
when and by whom —, so a shift can be undone by shifting back. Nothing is changed without a record of it."""
from __future__ import annotations

import datetime as dt
import getpass
import json
from pathlib import Path

from wildintel_uploader.modules.timefix.domain.ports import Corrections

CORRECTIONS_FILE = "time_corrections.json"


class CorrectionsFile(Corrections):
    def read(self, folder: Path) -> list[dict]:
        try:
            data = json.loads((folder / CORRECTIONS_FILE).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def write(self, folder: Path, entry: dict) -> None:
        try:
            user = getpass.getuser()
        except Exception:
            user = None
        entries = self.read(folder)
        entries.append({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "by": user, **entry})
        (folder / CORRECTIONS_FILE).write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
