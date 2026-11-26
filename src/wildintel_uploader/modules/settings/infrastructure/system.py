"""The ports out of the module that are the system's: the log of the app (`ActivityLog`, over core.logging_setup — its rotating file and the level the
environment may force with WILDINTEL_UPLOADER_WEB_LOG_LEVEL), what the computer has (`Machine`), and the backends the records of the research
projects can be kept in (`RecordStorage`, over core.storage)."""
from __future__ import annotations

import os
from pathlib import Path

from wildintel_uploader.core import logging_setup, storage
from wildintel_uploader.modules.settings.domain.ports import ActivityLog, Machine, RecordStorage


class AppActivityLog(ActivityLog):
    def file(self) -> Path:
        return logging_setup.log_file()

    def level_override(self) -> str | None:
        return logging_setup.env_override()

    def apply_level(self, level: str) -> None:
        logging_setup.apply_level(logging_setup.env_override() or level)

    def clear(self) -> int:
        return logging_setup.clear_log()


class ThisMachine(Machine):
    def cpu_count(self) -> int:
        return os.cpu_count() or 1


class AppRecordStorage(RecordStorage):
    def available(self) -> tuple[str, ...]:
        return tuple(storage.available())

    def use(self, name: str) -> None:
        storage.configure(name)
