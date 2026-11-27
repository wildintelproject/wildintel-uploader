"""The settings of the app as the app understands them — dataclasses and the rules they follow, in plain Python: no Pydantic, no files, no TOML (#248).

Each section is a frozen dataclass that checks itself when it is made: a value out of its range, a choice that is not one of its own, a folder that is
not absolute… raises SettingsError, naming the setting; what is only tidied (spaces around a name, a blank that means none, a field listed twice) is
tidied. A change is a new value — `dataclasses.replace(settings.general, workers=8)` —, never an edit in place.

Where they are kept, and in what format, is the infrastructure's business: settings.toml names its sections in capitals (GENERAL, DATA…), here they
are attributes (`settings.general`, `settings.data`), and `infrastructure.mapping` turns one into the other."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields, make_dataclass, replace
from pathlib import Path
from typing import Any, Mapping


from wildintel_uploader.modules.settings.domain.registry import discover, settings_registry
from wildintel_uploader.modules.settings.domain.rules import (  # noqa: F401 — where the sections of the other modules, and the code of before, find them
    CHECK_LEVELS, SettingsError, _blank_is_none, _check_levels, _exif_name, _in_range, _one_of, _set, secret,
)


# ── the sections ──

LOG_LEVELS = ("ERROR", "WARNING", "INFO", "DEBUG")
MAX_WORKERS = 64


def default_workers() -> int:
    """How many images are worked on at once unless the settings say otherwise: the CPUs there are, up to 4."""
    return max(1, min(4, os.cpu_count() or 1))


@settings_registry.section("GENERAL", "general", order=10)
@dataclass(frozen=True)
class GeneralSettings:
    log_level: str = "INFO"                              # how much the app logs, to the console and its log file
    workers: int = field(default_factory=default_workers)   # how many images are validated or preprocessed at once
    default_research_project: str | None = None          # the one that comes filled in wherever one is asked for
    show_welcome: bool = True                            # whether the welcome page is shown when the app opens

    def __post_init__(self) -> None:
        _one_of("GENERAL.log_level", self.log_level, LOG_LEVELS)
        _in_range("GENERAL.workers", self.workers, 1, MAX_WORKERS)
        _set(self, "default_research_project", _blank_is_none(self.default_research_project))


# Where the catalog — the research projects, the people, their equipment — can be kept.
CATALOG_STORAGES = ("json", "sqlite")


@settings_registry.section("DATA", "data", order=60)
@dataclass(frozen=True)
class DataSettings:
    """Where the app keeps what it makes. A folder left as None is the default one — see domain.folders."""
    dir: str | None = None                               # the data folder
    collections_dir: str | None = None                   # else <data folder>/collections
    reports_dir: str | None = None                       # else <data folder>/reports
    packages_dir: str | None = None                      # else <data folder>/packages
    storage: str = "json"                                # where the records of the research projects are kept
    catalog_storage: str = "json"                        # where the catalog is kept: the JSON files of the collections folder, or a SQLite database
    catalog_database: str | None = None                  # the SQLite database of the catalog; else <data folder>/catalog.sqlite3

    def __post_init__(self) -> None:
        _one_of("DATA.catalog_storage", self.catalog_storage, CATALOG_STORAGES)
        for name in ("dir", "collections_dir", "reports_dir", "packages_dir", "catalog_database"):
            value = _blank_is_none(getattr(self, name))
            if value is not None and not Path(value).expanduser().is_absolute():
                raise SettingsError(f"DATA.{name}", "must be an absolute path (or start with ~)")
            _set(self, name, value)


@settings_registry.section("FIELDWORK", "legacy_fieldwork", order=100)
@dataclass(frozen=True)
class LegacyFieldwork:
    """What settings.toml still holds of the field work — cameras, SD cards, trappers and their roles —, as versions before kept it there. It is not a
    setting: it belongs to the research projects and is moved to them; until then it is kept as it was read, to be written back as it was."""
    trappers: tuple[Mapping[str, Any], ...] = ()
    sd_cards: tuple[Mapping[str, Any], ...] = ()
    cameras: tuple[Mapping[str, Any], ...] = ()
    roles: tuple[Mapping[str, Any], ...] = ()


# The sections of the other modules register themselves when their domain/settings.py is imported.
discover("domain")


def _put_together() -> type:
    sections = [x for x in settings_registry.sections() if x.domain is not None]
    cls = make_dataclass("Settings", [(x.attribute, x.domain, field(default_factory=x.domain)) for x in sections], frozen=True,
                         namespace={"__module__": __name__})
    cls.__doc__ = """All the settings of one config: the sections of this module and those the other modules registered (see registry)."""
    # The name of each section in settings.toml, and in what the settings page sends and receives.
    cls.SECTIONS = {x.attribute: x.name for x in sections}  # type: ignore[attr-defined]
    return cls


Settings = _put_together()


def secret_fields() -> tuple[tuple[str, str], ...]:
    """The settings that are secrets — `(section, field)`, as settings.toml names them: ("TRAPPER", "user_password")… Read from the models, so a secret
    added later is one by being declared with `secret(...)`."""
    out = []
    for section in fields(Settings):
        kind = section.default_factory  # type: ignore[misc]
        for f in fields(kind) if isinstance(kind, type) else ():
            if f.metadata.get("secret"):
                out.append((Settings.SECTIONS[section.name], f.name))
    return tuple(out)


def keep_secrets(before: Settings, after: Settings) -> Settings:
    """`after`, with each secret it leaves blank as `before` had it: a secret is never shown, so what comes back blank is one that was not changed —
    it is cleared only by being given another."""
    sections = {}
    for section, name in secret_fields():
        attribute = next(a for a, s in Settings.SECTIONS.items() if s == section)
        values = sections.get(attribute, getattr(after, attribute))
        if not getattr(values, name):
            sections[attribute] = replace(values, **{name: getattr(getattr(before, attribute), name)})
    return replace(after, **sections) if sections else after
