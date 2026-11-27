"""The web API of the catalog as JSON — Pydantic models of what the requests send, part of the module's adapter of entry (#248): the routers of
`entrypoints/api/catalog.py` take them from here, and turn them into the records of the domain. They check what HTTP has to — a field that must be
there, a number in its range, a timezone that is one —; the rules of the records are the domain's.

The models of the research projects and the locations are those the pages of before send, with their fields and their checks as they were, so that
the API did not change. And the field work as the settings page shows it and sends it (`entrypoints/api/settings_page.py`)."""
from __future__ import annotations

from typing import Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

from dataclasses import replace

from wildintel_uploader.modules.catalog.domain.models import Audit, Role, Trapper, is_utc
from wildintel_uploader.modules.catalog.domain.ports import Fieldwork
from wildintel_uploader.modules.catalog.infrastructure.mapping import (
    equipment_from_record, equipment_to_record, role_to_record, trapper_from_record, trapper_to_record,
)


# ── the research projects and the locations, as the pages of before send them ──

class ResearchProjectRecord(BaseModel):
    """A research project kept in the collections folder — the fields of
    Trapper's own "Add research project" form, its choice fields holding
    Trapper's option numbers. The acronym names its folder."""

    name: str = Field(min_length=1, max_length=255)
    acronym: str = Field(min_length=3, max_length=10, pattern=r"^[0-9A-Za-z][0-9A-Za-z_.-]*$")
    sampling_design: int = Field(default=1, ge=1, le=6)
    sensor_method: int = Field(default=1, ge=1, le=3)
    animal_types: int = Field(default=1, ge=1, le=3)
    bait_use: int = Field(default=1, ge=1, le=6)
    event_interval: int = Field(default=0, ge=0)
    # Whether it is being prepared, running or over: a finished one is not offered when a deployment is imported.
    status: Literal["planned", "active", "finished", "archived"] = "active"
    keywords: str = ""
    abstract: str = Field(default="", max_length=2000)
    methods: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=2000)
    # Set when it was filled in from Trapper — to find its locations there later.
    trapper_pk: Optional[int] = None


class UpdateResearchProjectRequest(ResearchProjectRecord):
    """Change a research project already kept: the fields given are the ones that change, the rest stay. The acronym names it, and its folder,
    so it is the one that is found, never changed."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)  # type: ignore[assignment]
    acronym: str = Field(min_length=1)
    sampling_design: Optional[int] = Field(default=None, ge=1, le=6)  # type: ignore[assignment]
    sensor_method: Optional[int] = Field(default=None, ge=1, le=3)  # type: ignore[assignment]
    animal_types: Optional[int] = Field(default=None, ge=1, le=3)  # type: ignore[assignment]
    bait_use: Optional[int] = Field(default=None, ge=1, le=6)  # type: ignore[assignment]
    event_interval: Optional[int] = Field(default=None, ge=0)  # type: ignore[assignment]
    status: Optional[Literal["planned", "active", "finished", "archived"]] = None  # type: ignore[assignment]
    keywords: Optional[str] = None  # type: ignore[assignment]
    abstract: Optional[str] = Field(default=None, max_length=2000)  # type: ignore[assignment]
    methods: Optional[str] = Field(default=None, max_length=2000)  # type: ignore[assignment]
    description: Optional[str] = Field(default=None, max_length=2000)  # type: ignore[assignment]


class LocationRecord(BaseModel):
    """A location of a research project kept in the collections folder."""

    location_id: str = Field(min_length=1, max_length=100)
    name: Optional[str] = None
    # IANA timezone and whether its cameras ignore summer time. Both belong to the location — never to a deployment: every deployment there uses them,
    # and Trapper only accepts a package that declares the same. They are always said when a location is made: the cameras' clocks are taken as UTC, and the
    # time of a field visit is read in the timezone of its location.
    timezone: str = Field(min_length=1)
    ignore_dst: bool
    # Where it is — WGS84 decimal degrees, as in Camtrap DP's deployments table. Always said.
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_uncertainty: Optional[int] = Field(default=None, ge=1)
    # The day it was put into production (YYYY-MM-DD).
    in_service: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    trapper_pk: Optional[int] = None
    # Whether it is in use; an archived or a planned one is not offered for a visit. When it changed (YYYY-MM-DD) and why are free to leave out. A new one is pending: its first
    # visit starts it — it is not waited for in the revisions before.
    status: Literal["planned", "pending", "ready", "active", "archived"] = "pending"
    status_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status_note: Optional[str] = None

    # what was kept as "retired" is archived now
    _legacy_status = field_validator("status", mode="before")(lambda cls, v: "archived" if v == "retired" else v)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("is not a known IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def _no_summer_time_in_utc(self) -> "LocationRecord":
        # UTC has no summer time: whether the cameras ignore it does not apply there, so it is never said to.
        if is_utc(self.timezone):
            self.ignore_dst = False
        return self


class LocalLocationsRequest(BaseModel):
    research_project_id: str = Field(min_length=1)


class DeleteLocationRequest(LocalLocationsRequest):
    location_id: str = Field(min_length=1)


class SaveLocationRequest(LocalLocationsRequest):
    location: LocationRecord
    # A person making it in the settings: it can only start as pending, or planned — a visit makes it ready (Location start) or active (an Installation).
    by_hand: bool = False


class UpdateLocationRequest(LocalLocationsRequest):
    """Change a location already kept — its name, where it is, its timezone and/or summer-time setting. The fields left out stay as
    they are; one given as null is cleared."""

    location_id: str = Field(min_length=1)
    name: Optional[str] = None
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    coordinate_uncertainty: Optional[int] = Field(default=None, ge=1)
    timezone: Optional[str] = None
    ignore_dst: Optional[bool] = None
    in_service: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status: Optional[Literal["planned", "pending", "ready", "active", "archived"]] = None
    status_date: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    status_note: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("is not a known IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def _no_summer_time_in_utc(self) -> "UpdateLocationRequest":
        if is_utc(self.timezone) and self.ignore_dst is not None:
            self.ignore_dst = False
        return self


# ── the people, the roles, the equipment, the history, where the catalog is kept ──

class TrapperBody(BaseModel):
    """A trapper as the page sends it: with its id when it is one that was kept."""
    username: str
    name: str
    affiliation: str | None = None
    email: str | None = None
    status: str = "active"
    trapper_pk: int | None = None
    id: str | None = None

    def to_domain(self) -> Trapper:
        return Trapper(username=self.username, name=self.name, affiliation=self.affiliation, email=self.email, status=self.status,
                       trapper_pk=self.trapper_pk, audit=Audit(id=self.id))


class NewTrapper(BaseModel):
    username: str = Field(min_length=1)
    name: str = Field(min_length=1)
    affiliation: str | None = None
    email: str | None = None


class NewTrappers(BaseModel):
    trappers: list[NewTrapper]


class MoveCatalogRequest(BaseModel):
    to: Literal["json", "sqlite"]
    database: str | None = None      # the SQLite database — else catalog.sqlite3 in the data folder
    replace: bool = False


class RoleBody(BaseModel):
    trapper: str = Field(min_length=1)
    role: Literal["contact", "principalInvestigator", "rightsHolder", "publisher", "contributor"] = "contributor"
    id: str | None = None


class CameraIdentityRequest(BaseModel):
    research_project_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    make: str | None = None
    model: str | None = None


class RolesRequest(BaseModel):
    research_project_id: str
    roles: list[RoleBody]


class FieldItem(BaseModel):
    label: str = Field(min_length=1)
    camera_id: str | None = None
    camera_make: str | None = None
    camera_model: str | None = None
    brand: str | None = None
    capacity: str | None = None


class FieldItemsRequest(BaseModel):
    research_project_id: str
    kind: Literal["cameras", "sd_cards"]
    items: list[FieldItem]


class FieldItemStatusRequest(BaseModel):
    research_project_id: str
    kind: Literal["cameras", "sd_cards"]
    key: str                  # what the visits call it: a camera's serial number, or its label; an SD card's label
    status: Literal["archived", "stolen", "lost", "broken"]   # stolen, lost or broken are the reason it is archived
    status_date: str | None = None
    status_note: str | None = None


class StatusHistoryRequest(BaseModel):
    research_project_id: str
    kind: Literal["locations", "cameras", "sd_cards"] | None = None
    name: str | None = None


class RebuildStatusHistoryRequest(BaseModel):
    research_project_id: str


class DefaultResearchProjectRequest(BaseModel):
    acronym: str


# ── the field work as the settings page has it: the people, and the cameras, SD cards and roles of the research projects ──

def fieldwork_shown(fieldwork: Fieldwork) -> dict:
    """The field work of the catalog as the page shows it, each item with its research project."""
    return {
        "trappers": [trapper_to_record(t) for t in fieldwork.trappers],
        **{kind: [{**equipment_to_record(i, kind), "research_project": p} for p, i in getattr(fieldwork, kind)] for kind in ("cameras", "sd_cards")},
        "roles": [{**{k: v for k, v in role_to_record(r).items() if k != "trapper_ref"}, "trapper": r.trapper, "research_project": p}
                  for p, r in fieldwork.roles if not r.deleted],
    }


def _page_equipment(item, kind: str):
    """A camera or an SD card as the page sends it: with the id it says — none for a new one, which the catalog gives."""
    record = item.model_dump(mode="json")
    found = equipment_from_record(record, kind, item.research_project or "")
    return found if record.get("id") else replace(found, audit=Audit())


def fieldwork_saved(page) -> tuple[list, list, list, list]:
    """The field work the page sends (the FIELDWORK section of the settings), as the catalog saves it: the people, and the cameras, SD cards and
    roles each with its research project."""
    return ([trapper_from_record({**t.model_dump(mode="json"), "id": t.id or None}) for t in page.trappers],
            [(i.research_project, _page_equipment(i, "cameras")) for i in page.cameras],
            [(i.research_project, _page_equipment(i, "sd_cards")) for i in page.sd_cards],
            [(r.research_project, Role(trapper=r.trapper, role=r.role, audit=Audit(id=r.id))) for r in page.roles])
