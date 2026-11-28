"""The settings of the sources — the sections EPICOLLECT5 and EPICOLLECTCSV of settings.toml —, registered with the module of the settings."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from wildintel_uploader.modules.settings.domain.registry import Section
from wildintel_uploader.modules.settings.domain.rules import Secret, as_secret, blank_is_none, secret, tidy_field


@dataclass(frozen=True)
class Epicollect5Settings:
    enabled: bool = False                                # a source of visits and of the details of a deployment
    unmapped_to_comments: bool = False                   # what an input not mapped to any field says goes to the comments
    project_slug: str | None = None                      # the name in its URL: five.epicollect.net/project/<slug>
    client_id: str | None = None                         # of its API client app, for private projects
    client_secret: Secret | None = secret(default=None)
    mapping: Mapping[str, str] = field(default_factory=dict)   # deployment field -> input ref of the form

    def __post_init__(self) -> None:
        tidy_field(self, "project_slug", blank_is_none(self.project_slug))
        tidy_field(self, "client_id", blank_is_none(self.client_id))
        tidy_field(self, "client_secret", as_secret(self.client_secret))


@dataclass(frozen=True)
class EpicollectCsvSettings:
    enabled: bool = True                                 # whether the CSV of the WildINTEL Epicollect project can be read for visits


# The sections of settings.toml this module owns — put together with the others by the module of the settings (domain.models).
SECTIONS = (
    Section("EPICOLLECT5", "epicollect5", 30, Epicollect5Settings),
    Section("EPICOLLECTCSV", "epicollect_csv", 50, EpicollectCsvSettings),
)
