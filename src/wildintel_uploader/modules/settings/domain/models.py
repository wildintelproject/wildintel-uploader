"""The settings of the app as the app understands them — dataclasses and the rules they follow, in plain Python: no Pydantic, no files, no TOML (#248).

Each section is a frozen dataclass that checks itself when it is made: a value out of its range, a choice that is not one of its own, a folder that is
not absolute… raises SettingsError, naming the setting; what is only tidied (spaces around a name, a blank that means none, a field listed twice) is
tidied. A change is a new value — `dataclasses.replace(settings.general, workers=8)` —, never an edit in place.

Where they are kept, and in what format, is the infrastructure's business: settings.toml names its sections in capitals (GENERAL, DATA…), here they
are attributes (`settings.general`, `settings.data`), and `infrastructure.mapping` turns one into the other."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, Mapping


class SettingsError(ValueError):
    """A setting that cannot be: `setting` names it as settings.toml does — GENERAL.workers —, and the message says why."""

    def __init__(self, setting: str, message: str) -> None:
        super().__init__(f"{setting}: {message}")
        self.setting, self.message = setting, message


# ── the rules shared by the sections ──

def _set(obj: object, name: str, value: object) -> None:
    """Tidies a field of a frozen dataclass while it is being made."""
    object.__setattr__(obj, name, value)


def _blank_is_none(value: str | None) -> str | None:
    return (value or "").strip() or None


def _in_range(setting: str, value: float, low: float, high: float, *, low_open: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SettingsError(setting, "must be a number")
    if (value <= low if low_open else value < low) or value > high:
        raise SettingsError(setting, f"must be {'more than' if low_open else 'at least'} {low:g} and at most {high:g}")


def _one_of(setting: str, value: object, choices: tuple[str, ...]) -> None:
    if value not in choices:
        raise SettingsError(setting, f"must be one of {', '.join(choices)}")


# The name of an EXIF field, as ExifTool gives it: Model, SerialNumber, GPS:GPSLatitude…
_EXIF_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(:[A-Za-z][A-Za-z0-9_-]*)?")


def _exif_name(setting: str, name: object) -> str:
    name = str(name).strip()
    if not _EXIF_FIELD.fullmatch(name):
        raise SettingsError(setting, f"'{name}' is not the name of an EXIF field")
    return name


def secret(**kwargs: Any):
    """A setting that is a secret: never shown, never sent to the frontend, never put in a backup (see secret_fields)."""
    return field(metadata={"secret": True}, **kwargs)


# ── the sections ──

LOG_LEVELS = ("ERROR", "WARNING", "INFO", "DEBUG")
MAX_WORKERS = 64


def default_workers() -> int:
    """How many images are worked on at once unless the settings say otherwise: the CPUs there are, up to 4."""
    return max(1, min(4, os.cpu_count() or 1))


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


@dataclass(frozen=True)
class TrapperSettings:
    enabled: bool = True                                 # whether TRAPPER is a place to upload deployments to
    base_url: str | None = None
    user_name: str | None = None                         # its email: the import form only accepts that
    user_password: str | None = secret(default=None)
    max_zip_mb: int = 500                                # the images of a deployment go in packages of at most this many megabytes

    def __post_init__(self) -> None:
        _in_range("TRAPPER.max_zip_mb", self.max_zip_mb, 1, 5000)


@dataclass(frozen=True)
class AgoutiSettings:
    """What an upload to Agouti needs (https://docs.agouti.eu/api/endpoints.html) — kept; nothing is uploaded to Agouti yet."""
    enabled: bool = False
    base_url: str | None = None                          # the address of its API, https://api.agouti.eu
    api_key: str | None = secret(default=None)           # sent as X-API-KEY
    project_id: str | None = None

    def __post_init__(self) -> None:
        _set(self, "base_url", _blank_is_none(self.base_url))
        _set(self, "project_id", _blank_is_none(self.project_id))


@dataclass(frozen=True)
class EpicollectCsvSettings:
    enabled: bool = True                                 # whether the CSV of the WildINTEL Epicollect project can be read for visits


@dataclass(frozen=True)
class Epicollect5Settings:
    enabled: bool = False                                # a source of visits and of the details of a deployment
    unmapped_to_comments: bool = False                   # what an input not mapped to any field says goes to the comments
    project_slug: str | None = None                      # the name in its URL: five.epicollect.net/project/<slug>
    client_id: str | None = None                         # of its API client app, for private projects
    client_secret: str | None = secret(default=None)
    mapping: Mapping[str, str] = field(default_factory=dict)   # deployment field -> input ref of the form


@dataclass(frozen=True)
class DataSettings:
    """Where the app keeps what it makes. A folder left as None is the default one — see domain.folders."""
    dir: str | None = None                               # the data folder
    collections_dir: str | None = None                   # else <data folder>/collections
    reports_dir: str | None = None                       # else <data folder>/reports
    packages_dir: str | None = None                      # else <data folder>/packages
    storage: str = "json"                                # where the records of the research projects are kept

    def __post_init__(self) -> None:
        for name in ("dir", "collections_dir", "reports_dir", "packages_dir"):
            value = _blank_is_none(getattr(self, name))
            if value is not None and not Path(value).expanduser().is_absolute():
                raise SettingsError(f"DATA.{name}", "must be an absolute path (or start with ~)")
            _set(self, name, value)


# How a check starts in an import, when it is on: it has to pass (required), it only warns (warn), or it is offered unticked (skip).
CHECK_LEVELS = ("required", "warn", "skip")
IMAGE_CHECKS = ("corrupted", "sequence", "structure", "camera", "exif", "duplicates")
DEPLOYMENT_CHECKS = ("deployment_id", "collection_prefix", "collection_name", "location", "time_range", "camera", "image_count", "sequence_count",
                     "sequence_length", "sd_card", "photo_count")
# As they started before they could be set: the dates of the images and the SD card have to pass, the rest warn.
IMAGE_CHECK_DEFAULTS: Mapping[str, str] = {c: "warn" for c in IMAGE_CHECKS}
DEPLOYMENT_CHECK_DEFAULTS: Mapping[str, str] = {c: ("required" if c in ("time_range", "sd_card") else "warn") for c in DEPLOYMENT_CHECKS}


def _check_levels(setting: str, given: Mapping[str, str], checks: tuple[str, ...], start: Mapping[str, str]) -> dict[str, str]:
    """The level each check starts at: the ones given, and the default of the rest. A name that is not a check, or a level that is not one, is refused."""
    unknown = sorted(set(given) - set(checks))
    if unknown:
        raise SettingsError(setting, f"not checks: {', '.join(unknown)}")
    for check, level in given.items():
        _one_of(f"{setting}.{check}", level, CHECK_LEVELS)
    return {**start, **given}


@dataclass(frozen=True)
class ValidationSettings:
    """Which checks of the images an import offers — each looks at the folder alone —, and how they start."""
    corrupted: bool = True
    sequence: bool = True
    structure: bool = True
    camera: bool = True
    # How two images are told to be of the same camera: levels of EXIF fields, the most reliable first — the first level every image has is used.
    camera_levels: tuple[tuple[str, ...], ...] = (("SerialNumber",), ("Make", "Model"), ("Model",))
    exif: bool = True
    # The EXIF fields expected on every image besides the capture date (DateTimeOriginal), which is always expected.
    exif_fields: tuple[str, ...] = ("Model",)
    duplicates: bool = True
    defaults: Mapping[str, str] = field(default_factory=lambda: dict(IMAGE_CHECK_DEFAULTS))

    def __post_init__(self) -> None:
        # each level its fields once, as written, and each level once; a level with no field is left out
        levels: list[tuple[str, ...]] = []
        for level in self.camera_levels:
            names: list[str] = []
            for name in ((level,) if isinstance(level, str) else level):
                name = _exif_name("VALIDATION.camera_levels", name)
                if name.lower() not in (n.lower() for n in names):
                    names.append(name)
            if names and [n.lower() for n in names] not in ([n.lower() for n in kept] for kept in levels):
                levels.append(tuple(names))
        _set(self, "camera_levels", tuple(levels))
        # each field once, as written; the capture date is always expected, so it is not one of them
        exif: list[str] = []
        for name in self.exif_fields:
            name = _exif_name("VALIDATION.exif_fields", name)
            if name.lower() != "datetimeoriginal" and name.lower() not in (n.lower() for n in exif):
                exif.append(name)
        _set(self, "exif_fields", tuple(exif))
        _set(self, "defaults", _check_levels("VALIDATION.defaults", self.defaults, IMAGE_CHECKS, IMAGE_CHECK_DEFAULTS))


SIMILARITY_METHODS = ("median", "mean", "last", "range")


@dataclass(frozen=True)
class PostvalidationSettings:
    """Which checks of a deployment an import offers, how they start, and the parameters those that take one start from."""
    deployment_id: bool = True
    collection_prefix: bool = True
    collection_name: bool = True
    location: bool = True
    time_range: bool = True
    camera: bool = True
    image_count: bool = True
    sequence_count: bool = True
    sequence_length: bool = True
    sd_card: bool = True
    photo_count: bool = True
    defaults: Mapping[str, str] = field(default_factory=lambda: dict(DEPLOYMENT_CHECK_DEFAULTS))
    sequence_gap_seconds: float = 60.0      # a new sequence starts when the gap to the image before is at least this
    min_revisions: int = 2                  # how many previous revisions the statistical checks need to judge
    similarity_method: str = "median"       # what this revision is compared to: the median, the mean, the last one or the range of the previous ones
    image_count_tolerance: float = 50.0     # percent
    sequence_count_tolerance: float = 50.0
    sequence_length_tolerance: float = 50.0
    tolerance_hours: float = 1.0            # leeway around the start and the end when the dates of the images are checked

    def __post_init__(self) -> None:
        _set(self, "defaults", _check_levels("POSTVALIDATION.defaults", self.defaults, DEPLOYMENT_CHECKS, DEPLOYMENT_CHECK_DEFAULTS))
        _in_range("POSTVALIDATION.sequence_gap_seconds", self.sequence_gap_seconds, 0, 86400, low_open=True)
        _in_range("POSTVALIDATION.min_revisions", self.min_revisions, 1, 50)
        _one_of("POSTVALIDATION.similarity_method", self.similarity_method, SIMILARITY_METHODS)
        for name in ("image_count_tolerance", "sequence_count_tolerance", "sequence_length_tolerance"):
            _in_range(f"POSTVALIDATION.{name}", getattr(self, name), 0, 1000)
        _in_range("POSTVALIDATION.tolerance_hours", self.tolerance_hours, 0, 8760)


@dataclass(frozen=True)
class PreprocessingSettings:
    """What is done to the images as they go into their collection: the steps a new import starts with, and their values."""
    rename: bool = True                     # <DEPLOYMENT>__<YYYYMMDD>_<n>.<EXT>
    resize: bool = True
    resize_width: int = 2400                # images wider than this are resized to it
    metadata: bool = True                   # authorship, rights and license as XMP
    owner: str = ""
    publisher: str = ""
    coverage: str = ""                      # where the images were taken; blank, the location of the deployment
    license_url: str = "https://creativecommons.org/licenses/by-nc/4.0/"
    ignore_dst: bool = True                 # the camera's clock read as if it never changed to summer time
    convert_to_utc: bool = True             # the capture dates, in names and metadata, in UTC

    def __post_init__(self) -> None:
        _in_range("PREPROCESSING.resize_width", self.resize_width, 100, 20000)
        for name in ("owner", "publisher", "coverage", "license_url"):
            _set(self, name, (getattr(self, name) or "").strip())


TIME_SOURCES = ("created_at", "hour")


@dataclass(frozen=True)
class FieldlogSettings:
    """How the visits of a field trip are read from the file of the field app, and what is made of them."""
    time_source: str = "created_at"         # when a visit happened: when its entry was created (UTC), or the hour typed (the wall clock of its location)
    keep_seconds: bool = False              # the seconds of the visits kept in the logs; off, cut to the minute

    def __post_init__(self) -> None:
        _one_of("FIELDLOG.time_source", self.time_source, TIME_SOURCES)


@dataclass(frozen=True)
class LegacyFieldwork:
    """What settings.toml still holds of the field work — cameras, SD cards, trappers and their roles —, as versions before kept it there. It is not a
    setting: it belongs to the research projects and is moved to them; until then it is kept as it was read, to be written back as it was."""
    trappers: tuple[Mapping[str, Any], ...] = ()
    sd_cards: tuple[Mapping[str, Any], ...] = ()
    cameras: tuple[Mapping[str, Any], ...] = ()
    roles: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class Settings:
    """All the settings of one config."""
    general: GeneralSettings = field(default_factory=GeneralSettings)
    trapper: TrapperSettings = field(default_factory=TrapperSettings)
    epicollect5: Epicollect5Settings = field(default_factory=Epicollect5Settings)
    agouti: AgoutiSettings = field(default_factory=AgoutiSettings)
    epicollect_csv: EpicollectCsvSettings = field(default_factory=EpicollectCsvSettings)
    data: DataSettings = field(default_factory=DataSettings)
    validation: ValidationSettings = field(default_factory=ValidationSettings)
    postvalidation: PostvalidationSettings = field(default_factory=PostvalidationSettings)
    preprocessing: PreprocessingSettings = field(default_factory=PreprocessingSettings)
    fieldlog: FieldlogSettings = field(default_factory=FieldlogSettings)
    legacy_fieldwork: LegacyFieldwork = field(default_factory=LegacyFieldwork)

    # The name of each section in settings.toml, and in what the settings page sends and receives.
    SECTIONS: ClassVar[Mapping[str, str]] = {
        "general": "GENERAL", "trapper": "TRAPPER", "epicollect5": "EPICOLLECT5", "agouti": "AGOUTI", "epicollect_csv": "EPICOLLECTCSV", "data": "DATA",
        "validation": "VALIDATION", "postvalidation": "POSTVALIDATION", "preprocessing": "PREPROCESSING", "fieldlog": "FIELDLOG",
        "legacy_fieldwork": "FIELDWORK",
    }


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
