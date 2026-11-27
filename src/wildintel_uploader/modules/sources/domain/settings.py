"""The settings of the sources — the sections EPICOLLECT5 and EPICOLLECTCSV of settings.toml —, registered with the module of the settings."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from wildintel_uploader.modules.settings.domain.registry import settings_registry
from wildintel_uploader.modules.settings.domain.rules import blank_is_none, tidy_field, secret


@settings_registry.section("EPICOLLECT5", "epicollect5", order=30)
@dataclass(frozen=True)
class Epicollect5Settings:
    enabled: bool = False                                # a source of visits and of the details of a deployment
    unmapped_to_comments: bool = False                   # what an input not mapped to any field says goes to the comments
    project_slug: str | None = None                      # the name in its URL: five.epicollect.net/project/<slug>
    client_id: str | None = None                         # of its API client app, for private projects
    client_secret: str | None = secret(default=None)
    mapping: Mapping[str, str] = field(default_factory=dict)   # deployment field -> input ref of the form

    def __post_init__(self) -> None:
        tidy_field(self, "project_slug", blank_is_none(self.project_slug))
        tidy_field(self, "client_id", blank_is_none(self.client_id))


@settings_registry.section("EPICOLLECTCSV", "epicollect_csv", order=50)
@dataclass(frozen=True)
class EpicollectCsvSettings:
    enabled: bool = True                                 # whether the CSV of the WildINTEL Epicollect project can be read for visits
