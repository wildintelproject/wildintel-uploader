"""The settings of the visits — the section FIELDLOG of settings.toml: how the visits of a field trip are read, and what is made of them —,
registered with the module of the settings."""
from __future__ import annotations

from dataclasses import dataclass

from wildintel_uploader.modules.settings.domain.registry import Section
from wildintel_uploader.modules.settings.domain.rules import one_of

TIME_SOURCES = ("created_at", "hour")


@dataclass(frozen=True)
class FieldlogSettings:
    """How the visits of a field trip are read from the file of the field app, and what is made of them."""
    time_source: str = "created_at"         # when a visit happened: when its entry was created (UTC), or the hour typed (the wall clock of its location)
    keep_seconds: bool = False              # the seconds of the visits kept in the logs; off, cut to the minute

    def __post_init__(self) -> None:
        one_of("FIELDLOG.time_source", self.time_source, TIME_SOURCES)


# The sections of settings.toml this module owns — put together with the others by the module of the settings (domain.models).
SECTIONS = (
    Section("FIELDLOG", "fieldlog", 110, FieldlogSettings),
)
