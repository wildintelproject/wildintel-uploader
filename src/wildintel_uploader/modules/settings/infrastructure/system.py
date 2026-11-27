"""The ports out of the module that are the system's: the log of the app (`ActivityLog`, over activity_log — its rotating file in the log folder
the settings say, and the level the environment may force with WILDINTEL_UPLOADER_WEB_LOG_LEVEL), what the computer has (`Machine`), and the
backends the records of the research projects can be kept in (`RecordStorage`, over shared.storage)."""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.settings.infrastructure import activity_log as logging_setup
from wildintel_uploader.shared import storage
from wildintel_uploader.modules.settings.domain.ports import ActivityLog, Machine, RecordStorage


class AppActivityLog(ActivityLog):
    """`logs_dir` and `old_logs_dir` say where the log is kept and where it used to be, and `level` the level the settings say — each asked each
    time."""

    def __init__(self, logs_dir: Callable[[], Path], old_logs_dir: Callable[[], Path], level: Callable[[], str]) -> None:
        self._logs_dir, self._old_logs_dir, self._level = logs_dir, old_logs_dir, level

    def file(self) -> Path:
        return logging_setup.log_file(self._logs_dir())

    def level_override(self) -> str | None:
        return logging_setup.env_override()

    def configure(self, *, console_level: str | None = None) -> None:
        """The handlers set up, at the level the environment or the settings say."""
        logging_setup.configure(self._logs_dir(), self._old_logs_dir(), logging_setup.effective_level(self._level), console_level=console_level)

    def apply_level(self, level: str) -> None:
        logging_setup.apply_level(logging_setup.env_override() or level, self.file())

    def clear(self) -> int:
        return logging_setup.clear_log(self.file())


class ThisMachine(Machine):
    def cpu_count(self) -> int:
        return os.cpu_count() or 1


class AppRecordStorage(RecordStorage):
    def available(self) -> tuple[str, ...]:
        return tuple(storage.available())

    def use(self, name: str) -> None:
        storage.configure(name)
