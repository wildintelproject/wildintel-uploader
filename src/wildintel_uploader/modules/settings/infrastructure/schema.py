"""The format of the settings files: what settings.toml holds, section by section (GENERAL, TRAPPER, DATA…), as Pydantic validates it when it is read
— and what the settings page sends and receives, for now.

This is an adapter's business, not the domain's (#248): the settings as the app understands them are the dataclasses of `domain.models`, and
`infrastructure.mapping` turns one into the other. FIELDWORK still holds the cameras, the SD cards, the trappers and their roles, as versions before
kept them here: they belong to the research projects, and the domain of the settings keeps them only as what is still to be moved there."""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationInfo, create_model, field_validator, model_validator

from wildintel_uploader.modules.settings.domain import models as _domain
from wildintel_uploader.shared import ids

LogLevel = Literal["ERROR", "WARNING", "INFO", "DEBUG"]

MAX_WORKERS = 64


def default_workers() -> int:
    """How many images are worked on at once unless the settings say otherwise: the CPUs of this machine, by the domain's rule (workers_for)."""
    return _domain.workers_for(os.cpu_count())


class GeneralSettings(BaseModel):
    log_level: LogLevel = Field(
        default="INFO",
        description="How much the app logs, to the console and its log file. (GENERAL.log_level)",
    )
    workers: int = Field(
        default_factory=default_workers, ge=1, le=MAX_WORKERS,
        description="How many images are validated or preprocessed at once — up to the CPUs of the machine pays off. (GENERAL.workers)",
    )
    default_research_project: Optional[str] = Field(
        default=None,
        description="The acronym of the research project that comes filled in wherever one is asked for; it can still be changed there. (GENERAL.default_research_project)",
    )

    show_welcome: bool = Field(
        default=True,
        description="Whether the welcome page is shown when the app opens: off, the app opens on what comes after it (the menu). (GENERAL.show_welcome)",
    )

    @field_validator("default_research_project")
    @classmethod
    def _default_research_project(cls, value: Optional[str]) -> Optional[str]:
        return (value or "").strip() or None


class DataSettings(BaseModel):
    # None until first read/saved — resolved against default_data_dir() so
    # moving the app's documents dir (a platformdirs choice) doesn't strand
    # an old absolute path baked into settings.toml.
    dir: Optional[str] = Field(
        default=None,
        description="The data folder, where the app keeps what it makes: its collections (collections/<research project id>/<collection>/<deployment id>), reports and packages go in folders inside it, unless each has one of its own. (DATA.dir)",
    )
    collections_dir: Optional[str] = Field(
        default=None,
        description="A folder of its own for the collections, instead of the \"collections\" folder inside DATA.dir: <folder>/<research project id>/<collection>/<deployment id>. (DATA.collections_dir)",
    )
    reports_dir: Optional[str] = Field(
        default=None,
        description="A folder of its own for the reports of the validations, postvalidations and preprocessings, instead of the \"reports\" folder inside DATA.dir. (DATA.reports_dir)",
    )
    storage: str = Field(
        default="json",
        description="Where the app keeps its records — the research projects and their locations, visits, cameras and SD cards: \"json\" (files in the collections folder, the one there is for now). (DATA.storage)",
    )
    packages_dir: Optional[str] = Field(
        default=None,
        description="A folder of its own for the packages made to upload to TRAPPER, instead of the \"packages\" folder inside DATA.dir: <folder>/<research project id>/<collection>. (DATA.packages_dir)",
    )
    catalog_storage: Literal["json", "sqlite"] = Field(
        default="json",
        description="Where the catalog is kept — the research projects, the people, their equipment —: \"json\" (files in the collections folder) or \"sqlite\" (a database, see DATA.catalog_database). Change it with `catalog migrate`, which takes what is kept along. (DATA.catalog_storage)",
    )
    catalog_database: Optional[str] = Field(
        default=None,
        description="The SQLite database of the catalog, when DATA.catalog_storage is \"sqlite\": instead of catalog.sqlite3 inside DATA.dir. (DATA.catalog_database)",
    )

    @field_validator("dir", "collections_dir", "reports_dir", "packages_dir", "catalog_database")
    @classmethod
    def _absolute(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        if not Path(value.strip()).expanduser().is_absolute():
            raise ValueError("must be an absolute path (or start with ~)")
        return value.strip()


def username_from(name: str, taken: set[str] | None = None) -> str:
    """A username made from a full name — `Ana Pérez` is `ana.perez` —, one that is not among those `taken` (lower case): a number is added when it is."""
    folded = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", ".", folded).strip(".") or "trapper"
    username, n = base, 1
    while taken and username in taken:
        n += 1
        username = f"{base}{n}"
    return username


_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class Trapper(BaseModel):
    """One of the people who go to the field — {username, name, affiliation, email}. The people are global: they belong to no research project (what each is in a project is
    its role, which is the project's). Its `username` is what it is called in the app, as the label of an SD card is, and no two have the same."""
    username: str = Field(min_length=1, description="What the trapper is called in the app — required, and unique among the trappers (whatever its case), as the label of an SD card is.")
    name: str = Field(min_length=1, description="The trapper's full name, written as it should be on a visit.")
    affiliation: Optional[str] = Field(default=None, description="Where the trapper works, free text.")
    email: Optional[str] = Field(default=None, description="The trapper's email address — optional.")
    status: Literal["active", "inactive", "archived"] = Field(default="active", description="Whether the trapper still goes to the field: an inactive one is no longer suggested, and an archived one is out of use for good (it never goes back).")
    trapper_pk: Optional[int] = Field(default=None, description="Its id in TRAPPER, when it was taken from there — such a trapper can only be seen here.")
    id: Optional[str] = Field(default=None, description="Its internal id — a UUID the app generates when it is kept, that never changes and is never typed: what the records that refer to it point to.")
    created_at: Optional[str] = Field(default=None, description="When it was kept here (ISO 8601, UTC, with a Z): written by the app, never typed.")
    updated_at: Optional[str] = Field(default=None, description="When it was last changed (ISO 8601, UTC, with a Z): written by the app, never typed.")
    deleted_at: Optional[str] = Field(default=None, description="When it was removed (ISO 8601, UTC, with a Z), if it was: it is no longer listed, but it is kept — nothing is deleted.")

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        value = value.strip()
        if not value or re.search(r"\s", value):
            raise ValueError("can't be blank or have spaces")
        return value

    @field_validator("email")
    @classmethod
    def _email_address(cls, value: Optional[str]) -> Optional[str]:
        value = (value or "").strip()
        if value and not _EMAIL.match(value):
            raise ValueError("is not an email address")
        return value or None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("affiliation")
    @classmethod
    def _affiliation(cls, value: Optional[str]) -> Optional[str]:
        return (value or "").strip() or None


def _tidy(value: Optional[str]) -> Optional[str]:
    return (" ".join(value.split()) if value else "") or None


def _blank_date(value):
    """A date left blank is no date."""
    return None if isinstance(value, str) and not value.strip() else value


def migrate_gear(data):
    """A camera or an SD card as it was kept before: "retired" is archived, and "stolen", "lost" and "broken" are archived with that reason. An archived one has a reason."""
    if not isinstance(data, dict):
        return data
    data = dict(data)
    status = data.get("status")
    if status in ("stolen", "lost", "broken"):
        data["status"], data["archive_reason"] = "archived", data.get("archive_reason") or status
    elif status == "retired":
        data["status"] = "archived"
    if data.get("status") == "archived" and not data.get("archive_reason"):
        data["archive_reason"] = "other"
    return data


TRAPPER_ROLES = ("contact", "principalInvestigator", "rightsHolder", "publisher", "contributor")


class TrapperRole(BaseModel):
    """What a trapper is in a research project — one of the roles of a contributor in Camtrap DP (contributors.role)."""
    research_project: str = Field(min_length=1, description="The acronym of the research project.")
    trapper: str = Field(min_length=1, description="The name of the trapper, as it is in the list of trappers.")
    role: Literal["contact", "principalInvestigator", "rightsHolder", "publisher", "contributor"] = Field(default="contributor", description="Its role in the research project.")
    id: Optional[str] = Field(default=None, description="Its internal id — a UUID the app generates when it is kept, that never changes and is never typed: what the records that refer to it point to.")
    created_at: Optional[str] = Field(default=None, description="When it was kept here (ISO 8601, UTC, with a Z): written by the app, never typed.")
    updated_at: Optional[str] = Field(default=None, description="When it was last changed (ISO 8601, UTC, with a Z): written by the app, never typed.")
    deleted_at: Optional[str] = Field(default=None, description="When it was removed (ISO 8601, UTC, with a Z), if it was: it is no longer listed, but it is kept — nothing is deleted.")

    @field_validator("trapper")
    @classmethod
    def _trapper(cls, value: str) -> str:
        return " ".join(value.split())


class SdCard(BaseModel):
    """One of the SD cards of the field work — its label, as it is written on it, and optionally its brand, its capacity and the
    day it was put into production."""
    label: str = Field(min_length=1, description="What the card is called — its number or the label on it (e.g. A12).")
    brand: Optional[str] = Field(default=None, description="Who makes it, free text (e.g. SanDisk).")
    capacity: Optional[str] = Field(default=None, description="How much it holds, free text (e.g. 64 GB).")
    in_service: Optional[date] = Field(default=None, description="The day it was put into production.")
    research_project: Optional[str] = Field(default=None, description="The acronym of the research project it belongs to: every one belongs to one (a card or camera without it, as older settings had, waits to be assigned).")
    status: Literal["planned", "ready", "active", "archived"] = Field(default="ready", description="Planned: only in Settings, not in the app. Ready: available, not in the field yet. Active: in use. Archived: out of use for good (see archive_reason).")
    archive_reason: Optional[Literal["lost", "stolen", "broken", "other"]] = Field(default=None, description="Why it was archived; other when it is none of the others (the status note says it).")
    status_date: Optional[date] = Field(default=None, description="The day it stopped being active.")
    status_note: Optional[str] = Field(default=None, description="Why, free text.")
    id: Optional[str] = Field(default=None, description="Its internal id — a UUID the app generates when it is kept, that never changes and is never typed: what the records that refer to it point to.")
    created_at: Optional[str] = Field(default=None, description="When it was kept here (ISO 8601, UTC, with a Z): written by the app, never typed.")
    updated_at: Optional[str] = Field(default=None, description="When it was last changed (ISO 8601, UTC, with a Z): written by the app, never typed.")
    deleted_at: Optional[str] = Field(default=None, description="When it was removed (ISO 8601, UTC, with a Z), if it was: it is no longer listed, but it is kept — nothing is deleted.")

    _blank_in_service = field_validator("in_service", mode="before")(_blank_date)
    _blank_status_date = field_validator("status_date", mode="before")(_blank_date)
    _research_project = field_validator("research_project")(lambda cls, v: _tidy(v))
    _status_note = field_validator("status_note")(lambda cls, v: _tidy(v))
    _migrated = model_validator(mode="before")(lambda cls, data: migrate_gear(data))

    @field_validator("brand")
    @classmethod
    def _brand(cls, value: Optional[str]) -> Optional[str]:
        return _tidy(value)

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("capacity")
    @classmethod
    def _capacity(cls, value: Optional[str]) -> Optional[str]:
        return _tidy(value)


class Camera(BaseModel):
    """One of the camera traps — its label (what it is called), optionally its id (the serial number) and its model, as Camtrap DP names
    them, and the day it was put into production."""
    label: str = Field(min_length=1, description="What the camera is called — the name it goes by in the field.")
    camera_id: Optional[str] = Field(default=None, description="The camera's id — its serial number. (cameraID)")
    camera_make: Optional[str] = Field(default=None, description="The manufacturer, as the camera writes it in its images (EXIF Make): Browning, Reconyx…")
    camera_model: Optional[str] = Field(default=None, description="The model, as the camera writes it in its images (EXIF Model): 6DCL, HC600… Camtrap DP's cameraModel is the make and the model, make-model.")
    connectivity: Optional[Literal["none", "4g", "5g"]] = Field(default=None, description="The mobile network the camera sends its images through: none when it does not.")
    power_source: Optional[Literal["cells", "battery"]] = Field(default=None, description="What it runs on: cells (AA, AAA… the ones that are changed) or a battery.")
    battery_removable: Optional[Literal["yes", "no"]] = Field(default=None, description="Whether the battery can be taken out of the camera: only said of a battery, as cells are always taken out to be changed.")
    in_service: Optional[date] = Field(default=None, description="The day it was put into production.")
    research_project: Optional[str] = Field(default=None, description="The acronym of the research project it belongs to: every one belongs to one (a card or camera without it, as older settings had, waits to be assigned).")
    status: Literal["planned", "ready", "active", "archived"] = Field(default="ready", description="Planned: only in Settings, not in the app. Ready: available, not in the field yet. Active: in use. Archived: out of use for good (see archive_reason).")
    archive_reason: Optional[Literal["lost", "stolen", "broken", "other"]] = Field(default=None, description="Why it was archived; other when it is none of the others (the status note says it).")
    status_date: Optional[date] = Field(default=None, description="The day it stopped being active.")
    status_note: Optional[str] = Field(default=None, description="Why, free text.")
    id: Optional[str] = Field(default=None, description="Its internal id — a UUID the app generates when it is kept, that never changes and is never typed: what the records that refer to it point to.")
    created_at: Optional[str] = Field(default=None, description="When it was kept here (ISO 8601, UTC, with a Z): written by the app, never typed.")
    updated_at: Optional[str] = Field(default=None, description="When it was last changed (ISO 8601, UTC, with a Z): written by the app, never typed.")
    deleted_at: Optional[str] = Field(default=None, description="When it was removed (ISO 8601, UTC, with a Z), if it was: it is no longer listed, but it is kept — nothing is deleted.")

    _blank_in_service = field_validator("in_service", mode="before")(_blank_date)
    _blank_status_date = field_validator("status_date", mode="before")(_blank_date)
    _research_project = field_validator("research_project")(lambda cls, v: _tidy(v))
    _status_note = field_validator("status_note")(lambda cls, v: _tidy(v))
    _migrated = model_validator(mode="before")(lambda cls, data: migrate_gear(data))

    @model_validator(mode="after")
    def _removable_only_of_a_battery(self) -> "Camera":
        # cells are always taken out to be changed: only a battery says whether it can be
        if self.power_source != "battery":
            self.battery_removable = None
        return self

    @model_validator(mode="before")
    @classmethod
    def _label_from_id(cls, data):
        """A camera kept before it had a label is called by its id."""
        if isinstance(data, dict) and not str(data.get("label") or "").strip() and str(data.get("camera_id") or "").strip():
            return {**data, "label": data["camera_id"]}
        return data

    @field_validator("label")
    @classmethod
    def _label(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("A camera needs a label.")
        return value

    @field_validator("camera_id")
    @classmethod
    def _camera_id(cls, value: Optional[str]) -> Optional[str]:
        return _tidy(value)

    @field_validator("camera_model", "camera_make")
    @classmethod
    def _camera_model(cls, value: Optional[str]) -> Optional[str]:
        return _tidy(value)


def _unique(items: list, key: str, scope: str | None = None) -> list:
    """What is listed once by its `key` — as written: `7b` and `7B` are two —, within its `scope` (whatever its case) when it has one, in the order given; the blank ones go."""
    kept: dict[tuple, object] = {}
    for item in items:
        name = getattr(item, key)
        if name:
            kept.setdefault(((getattr(item, scope) or "").lower() if scope else "", name), item)
    return list(kept.values())


class FieldworkSettings(BaseModel):
    trappers: list[Trapper] = Field(
        default_factory=list,
        description="The people who go to the field — suggested when a visit is registered, as who went. (FIELDWORK.trappers)",
    )
    sd_cards: list[SdCard] = Field(default_factory=list, description="The SD cards of the field work. (FIELDWORK.sd_cards)")
    cameras: list[Camera] = Field(default_factory=list, description="The camera traps of the field work. (FIELDWORK.cameras)")
    roles: list[TrapperRole] = Field(default_factory=list, description="What each trapper is in each research project: a trapper can have several in the same project, one entry for each. (FIELDWORK.roles)")

    @field_validator("trappers", mode="before")
    @classmethod
    def _from_names(cls, trappers, info: ValidationInfo):
        """A plain name is a trapper without affiliation. What was kept before the trappers had a username (settings read from the file or from an old backup, validated with
        `context={"migrate": True}`) gets one made from its name — never the same as another's; what comes from a client does not: it has to say it."""
        if not isinstance(trappers, list):
            return trappers
        trappers = [{"name": t} if isinstance(t, str) else t for t in trappers]
        if (info.context or {}).get("migrate"):
            taken = {str(t.get("username")).strip().lower() for t in trappers if isinstance(t, dict) and t.get("username")}
            migrated = []
            for t in trappers:
                if isinstance(t, dict) and not t.get("username") and t.get("name"):
                    username = username_from(str(t["name"]), taken)
                    taken.add(username)
                    t = {**t, "username": username}
                if isinstance(t, dict) and not t.get("id") and t.get("username"):   # kept before the ids existed: the same one whenever it is read
                    t = {**t, "id": ids.legacy_id("trapper", t["username"])}
                migrated.append(t)
            trappers = migrated
        return trappers

    @field_validator("trappers")
    @classmethod
    def _unique_trappers(cls, trappers: list[Trapper]) -> list[Trapper]:
        # a full name is listed once among those that were not deleted (a deleted one is kept as it is); a username is the trapper's own, and only one has it
        alive = {id(t) for t in _unique([t for t in trappers if not t.deleted_at], "name")}
        trappers = [t for t in trappers if t.deleted_at or id(t) in alive]
        seen: dict[str, str] = {}
        for t in trappers:
            # a username is the account of the trapper, an email: it is read whatever its case, while the full name counts it
            if t.username.lower() in seen:
                raise ValueError(f"The username '{t.username}' is used by more than one trapper ({seen[t.username.lower()]} and {t.name}): it is unique.")
            seen[t.username.lower()] = t.name
        return trappers

    @field_validator("roles")
    @classmethod
    def _unique_roles(cls, roles: list[TrapperRole]) -> list[TrapperRole]:
        kept: dict[tuple, TrapperRole] = {}
        for r in roles:
            kept.setdefault((r.research_project.lower(), r.trapper.lower(), r.role), r)
        return list(kept.values())

    @field_validator("sd_cards")
    @classmethod
    def _unique_sd_cards(cls, cards: list[SdCard]) -> list[SdCard]:
        return _unique(cards, "label", "research_project")

    @field_validator("cameras")
    @classmethod
    def _unique_cameras(cls, cameras: list[Camera]) -> list[Camera]:
        return _unique(cameras, "label", "research_project")


# The format of each section: this module's own, and those each module with settings says (its infrastructure/settings.py) — by name, as the
# domain lists them.
from wildintel_uploader.modules.uploaders.infrastructure import settings as _uploaders
from wildintel_uploader.modules.sources.infrastructure import settings as _sources
from wildintel_uploader.modules.prevalidation.infrastructure import settings as _prevalidation
from wildintel_uploader.modules.postvalidation.infrastructure import settings as _postvalidation
from wildintel_uploader.modules.preprocessing.infrastructure import settings as _preprocessing
from wildintel_uploader.modules.visits.infrastructure import settings as _visits

SCHEMAS: dict[str, type[BaseModel]] = {
    "GENERAL": GeneralSettings,
    "DATA": DataSettings,
    "FIELDWORK": FieldworkSettings,
    **_uploaders.SCHEMAS,
    **_sources.SCHEMAS,
    **_prevalidation.SCHEMAS,
    **_postvalidation.SCHEMAS,
    **_preprocessing.SCHEMAS,
    **_visits.SCHEMAS,
}

# The whole file: every section of the settings, in the order they are written in.
Settings = create_model("Settings", **{x.name: (SCHEMAS[x.name], Field(default_factory=SCHEMAS[x.name])) for x in _domain.sorted_sections()})  # type: ignore[call-overload]


def secret_fields() -> tuple[tuple[str, str], ...]:
    """The settings that are secrets — `(section, field)` of each one marked `json_schema_extra={"secret": True}` —: never shown, never sent to the frontend,
    never put in a backup. Read from the schema, so a secret added later is one by marking it."""
    out = []
    for section, info in Settings.model_fields.items():
        model = info.annotation
        for name, field in getattr(model, "model_fields", {}).items():
            if isinstance(field.json_schema_extra, dict) and field.json_schema_extra.get("secret"):
                out.append((section, name))
    return tuple(out)
