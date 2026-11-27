"""What versions before kept of the field work in the settings, taken from there through the contract of the module of the settings — the catalog
does not know where or how the settings are kept: it asks their module."""
from __future__ import annotations

from wildintel_uploader.modules.catalog.domain.models import Trapper
from typing import Any

from wildintel_uploader.modules.catalog.domain.ports import LegacyFieldwork, LegacyTrappers
from wildintel_uploader.modules.catalog.infrastructure.mapping import (
    equipment_from_record, equipment_to_record, role_from_record, role_to_record, trapper_from_record,
)
from wildintel_uploader.modules.settings.domain.ports import SettingsService


class TrappersFromTheSettings(LegacyTrappers):
    def __init__(self, settings: SettingsService) -> None:
        self.settings = settings

    def take(self) -> list[Trapper]:
        legacy = [trapper_from_record(dict(t)) for t in self.settings.legacy_fieldwork().trappers]
        if legacy:
            self.settings.forget_legacy_fieldwork("trappers")
        return legacy


class FieldworkFromTheSettings(LegacyFieldwork):
    """The cameras, the SD cards and the roles versions before left in the settings, through the contract of their module."""

    def __init__(self, settings: SettingsService) -> None:
        self.settings = settings

    def items(self, kind: str) -> list[tuple[str | None, Any]]:
        out = []
        for record in getattr(self.settings.legacy_fieldwork(), kind):
            project = record.get("research_project") or None
            item = role_from_record(dict(record), project or "") if kind == "roles" else equipment_from_record(dict(record), kind, project or "")
            out.append((project, item))
        return out

    def keep(self, kind: str, items: list[tuple[str | None, Any]]) -> None:
        records = [{**(role_to_record(i) if kind == "roles" else equipment_to_record(i, kind)), "research_project": p} for p, i in items]
        self.settings.keep_legacy_fieldwork(kind, records)
