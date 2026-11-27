"""The settings of the app as the app understands them — dataclasses and the rules they follow, in plain Python: no Pydantic, no files, no TOML (#248).

Each section is a frozen dataclass that checks itself when it is made: a value out of its range, a choice that is not one of its own, a folder that is
not absolute… raises SettingsError, naming the setting; what is only tidied (spaces around a name, a blank that means none, a field listed twice) is
tidied. A change is a new value — `dataclasses.replace(settings.general, workers=8)` —, never an edit in place.

Where they are kept, and in what format, is the infrastructure's business: settings.toml names its sections in capitals (GENERAL, DATA…), here they
are attributes (`settings.general`, `settings.data`), and `infrastructure.mapping` turns one into the other."""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Mapping


from wildintel_uploader.modules.settings.domain.registry import Section, in_order, put_together
from wildintel_uploader.modules.settings.domain.rules import (  # noqa: F401 — SettingsError: where the entry points find it
    SettingsError, blank_is_none, in_range, one_of, tidy_field,
)


# ── the sections ──

LOG_LEVELS = ("ERROR", "WARNING", "INFO", "DEBUG")
MAX_WORKERS = 64


WORKERS_AT_MOST = 4


def workers_for(cpus: int | None) -> int:
    """How many images are worked on at once unless the settings say otherwise: the CPUs there are, up to 4 — one when they can't be told.
    The CPUs are counted where the settings are read (infrastructure.schema): the domain does not look at the machine."""
    return max(1, min(WORKERS_AT_MOST, cpus or 1))


@dataclass(frozen=True)
class GeneralSettings:
    log_level: str = "INFO"                              # how much the app logs, to the console and its log file
    workers: int = WORKERS_AT_MOST                       # how many images are validated or preprocessed at once (see workers_for)
    default_research_project: str | None = None          # the one that comes filled in wherever one is asked for
    show_welcome: bool = True                            # whether the welcome page is shown when the app opens

    def __post_init__(self) -> None:
        one_of("GENERAL.log_level", self.log_level, LOG_LEVELS)
        in_range("GENERAL.workers", self.workers, 1, MAX_WORKERS)
        tidy_field(self, "default_research_project", blank_is_none(self.default_research_project))


# Where the catalog — the research projects, the people, their equipment — can be kept.
CATALOG_STORAGES = ("json", "sqlite")


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
        one_of("DATA.catalog_storage", self.catalog_storage, CATALOG_STORAGES)
        for name in ("dir", "collections_dir", "reports_dir", "packages_dir", "catalog_database"):
            value = blank_is_none(getattr(self, name))
            if value is not None and not Path(value).expanduser().is_absolute():
                raise SettingsError(f"DATA.{name}", "must be an absolute path (or start with ~)")
            tidy_field(self, name, value)


@dataclass(frozen=True)
class LegacyFieldwork:
    """What settings.toml still holds of the field work — cameras, SD cards, trappers and their roles —, as versions before kept it there. It is not a
    setting: it belongs to the research projects and is moved to them; until then it is kept as it was read, to be written back as it was."""
    trappers: tuple[Mapping[str, Any], ...] = ()
    sd_cards: tuple[Mapping[str, Any], ...] = ()
    cameras: tuple[Mapping[str, Any], ...] = ()
    roles: tuple[Mapping[str, Any], ...] = ()


# Every section of settings.toml: this module's own, and those each module with settings says it owns (its domain/settings.py) — by name, not found
# by looking: a module with settings is listed here, and an architecture test holds the list to the modules there are.
from wildintel_uploader.modules.uploaders.domain import settings as _uploaders
from wildintel_uploader.modules.sources.domain import settings as _sources
from wildintel_uploader.modules.prevalidation.domain import settings as _prevalidation
from wildintel_uploader.modules.postvalidation.domain import settings as _postvalidation
from wildintel_uploader.modules.preprocessing.domain import settings as _preprocessing
from wildintel_uploader.modules.visits.domain import settings as _visits

SECTIONS: tuple[Section, ...] = (
    Section("GENERAL", "general", 10, GeneralSettings),
    Section("DATA", "data", 60, DataSettings),
    Section("FIELDWORK", "legacy_fieldwork", 100, LegacyFieldwork),
    *_uploaders.SECTIONS,
    *_sources.SECTIONS,
    *_prevalidation.SECTIONS,
    *_postvalidation.SECTIONS,
    *_preprocessing.SECTIONS,
    *_visits.SECTIONS,
)


Settings = put_together(SECTIONS, __name__)


def sorted_sections() -> list[Section]:
    """Every section, in the order settings.toml has them."""
    return in_order(SECTIONS)


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
