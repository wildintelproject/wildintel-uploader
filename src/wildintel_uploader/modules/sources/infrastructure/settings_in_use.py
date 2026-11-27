"""SourceSettings through the contract of the module of the settings."""
from __future__ import annotations

from wildintel_uploader.modules.settings.domain.ports import SettingsService
from wildintel_uploader.modules.sources.domain.ports import SourceSettings
from wildintel_uploader.modules.sources.domain.settings import Epicollect5Settings


class SettingsOfTheSources(SourceSettings):
    def __init__(self, settings: SettingsService) -> None:
        self._settings = settings

    def epicollect5(self) -> Epicollect5Settings:
        return self._settings.current().epicollect5  # type: ignore[attr-defined]
