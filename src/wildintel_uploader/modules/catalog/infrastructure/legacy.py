"""What versions before kept of the field work in the settings, taken from there through the contract of the module of the settings — the catalog
does not know where or how the settings are kept: it asks their module."""
from __future__ import annotations

from wildintel_uploader.modules.catalog.domain.models import Trapper
from wildintel_uploader.modules.catalog.domain.ports import Clock, LegacyTrappers
from wildintel_uploader.modules.catalog.infrastructure.mapping import trapper_from_record
from wildintel_uploader.modules.settings.domain.ports import SettingsService
from wildintel_uploader.shared import audit


class TrappersFromTheSettings(LegacyTrappers):
    def __init__(self, settings: SettingsService) -> None:
        self.settings = settings

    def take(self) -> list[Trapper]:
        legacy = [trapper_from_record(dict(t)) for t in self.settings.legacy_fieldwork().trappers]
        if legacy:
            self.settings.forget_legacy_fieldwork("trappers")
        return legacy


class SystemClock(Clock):
    """The clock of the app — shared.audit.now, the one every record of before is dated by."""

    def now(self) -> str:
        return audit.now()
