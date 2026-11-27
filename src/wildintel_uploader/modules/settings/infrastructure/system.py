"""The ports out of the module that are the system's: the log of the app (`ActivityLog`, over activity_log — its rotating file in the log folder
the settings say, and the level the environment may force with WILDINTEL_UPLOADER_WEB_LOG_LEVEL), what the computer has (`Machine`), and the
backends the records of the research projects can be kept in (`RecordStorage`, over shared.storage)."""
from __future__ import annotations

import os
from pathlib import Path

from wildintel_uploader.modules.settings.infrastructure import activity_log as logging_setup
from wildintel_uploader.shared import storage
from wildintel_uploader.modules.settings.domain.ports import ActivityLog, Machine, RecordStorage, StoredSettings


class AppActivityLog(ActivityLog):
    """`settings` say the log folders and the level, as settings.toml keeps them."""

    def __init__(self, settings: StoredSettings) -> None:
        self._settings = settings

    def file(self) -> Path:
        return logging_setup.log_file(self._settings.get_logs_dir())

    def level_override(self) -> str | None:
        return logging_setup.env_override()

    def configure(self, *, console_level: str | None = None) -> None:
        """The handlers set up, at the level the environment or the settings say."""
        level = logging_setup.effective_level(lambda: self._settings.load_settings().GENERAL.log_level)
        logging_setup.configure(self._settings.get_logs_dir(), self._settings.legacy_logs_dir(), level, console_level=console_level)

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
