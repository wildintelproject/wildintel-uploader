"""The contracts of the catalog (#248), on both sides of it:

- **In** — `CatalogService`: what the module offers, which the entry points (and the other modules) call. Implemented by
  `application.use_cases.CatalogUseCases`. The catalog as records, for what still reads and writes it as it is kept, is apart: see
  `domain.records`.
- **Out** — what it needs from outside: `CatalogRepository`, where its records are kept (the JSON files of the collections folder,
  `infrastructure.json_repository`); `LegacyTrappers`, the people versions before kept in the settings (`infrastructure.legacy`, through the contract
  of the module of the settings); `VisitHistory`, what the visits say, read only (`infrastructure.visits` — the module of the visits, once there is
  one); `StatusHistory`, where each change of status is written down; `ProjectFolders`, the folders of the research projects in the collections
  folder; `Clock`, the instant and the day."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from wildintel_uploader.modules.catalog.domain.models import Camera, Location, ResearchProject, Role, SdCard, Trapper

Equipment = Camera | SdCard


@dataclass(frozen=True)
class Fieldwork:
    """The field work as the settings page shows it: the people, and the cameras, SD cards and roles of every research project — each with its
    research project, None for one versions before left in the settings with none yet."""
    trappers: list[Trapper]
    cameras: list[tuple[str | None, Camera]]
    sd_cards: list[tuple[str | None, SdCard]]
    roles: list[tuple[str | None, Role]]


@dataclass(frozen=True)
class AddedTrappers:
    """What adding people — or cameras, or SD cards — did: those added, and those left out because they were taken (by username, or by label)."""
    added: list[str]
    skipped: list[str]


# ── in: what the module offers ──

class CatalogService(Protocol):
    """The catalog. Besides the errors each method names, a record or a list that cannot be is the domain's CatalogError."""


    def trappers(self, include_deleted: bool = False) -> list[Trapper]:
        """The people. A removed one is not listed unless asked for: the visits it made still say who it was."""

    def save_trappers(self, trappers: list[Trapper]) -> list[Trapper]:
        """Keeps these people as all of them (see domain.rules.saved_trappers), and gives them as they were kept."""

    def add_trappers(self, trappers: list[Trapper]) -> AddedTrappers:
        """Adds the people that are not kept yet — active —; one with the username of another, whatever its case, is left out."""

    # the research projects
    def projects(self, include_deleted: bool = False) -> list[ResearchProject]:
        """The research projects — a removed one only when asked for: everything it had is still kept."""

    def project(self, acronym: str) -> ResearchProject:
        """One research project, by its acronym, whatever its case. UnknownProject."""

    def add_project(self, project: ResearchProject) -> ResearchProject:
        """Keeps a new research project, and its folder, where its collections will go; one removed comes back, with its own creation. ProjectExists."""

    def update_project(self, acronym: str, changes: Mapping[str, Any]) -> ResearchProject:
        """Changes the fields of a research project that `changes` names — not its acronym, which names its folder. UnknownProject, ProjectArchived,
        ProjectHasVisits (it can't go back to planned)."""

    def delete_project(self, acronym: str) -> None:
        """Removes a research project — logically: it is no longer listed, and everything it has is kept. UnknownProject, ProjectArchived,
        ProjectNotEmpty (its folder holds collections, deployments or images)."""

    # the locations of a research project
    def locations(self, project: str, include_deleted: bool = False) -> list[Location]:
        """Its locations — a removed one only when asked for: the visits made there still need its timezone."""

    def location(self, project: str, location_id: str) -> Location:
        """One location, by its id, whatever its case. UnknownLocation."""

    def add_location(self, project: str, location: Location, *, by_hand: bool = False) -> Location:
        """A new location, put into production today unless it says another day; one removed comes back, as the one now said. By hand it starts
        pending or planned (NewLocationStatus). UnknownProject, ProjectArchived, LocationExists."""

    def update_location(self, project: str, location_id: str, changes: Mapping[str, Any], *, by_visit: bool = False) -> Location:
        """Changes the fields of a location that `changes` names; its timezone and summer-time setting are fixed (LocationTimeFixed), an archived one
        stays archived (LocationArchived), and by hand — not by a visit — its status changes only as the visits allow (SiteStatusRefused).
        ProjectArchived, UnknownLocation."""

    def delete_location(self, project: str, location_id: str) -> None:
        """Removes a location — logically: it is kept, its visits still need its timezone. Not one from TRAPPER (LocationFromTrapper) nor one with
        visits (LocationHasVisits). ProjectArchived, UnknownLocation."""

    def location_time(self, project: str, location_id: str | None) -> dict[str, Any]:
        """The timezone and the summer-time setting kept for a location — only the ones it has; empty when it is not kept: what every deployment
        there is read in."""

    # the equipment of a research project: its cameras and its SD cards
    def equipment(self, project: str, kind: str, include_deleted: bool = False) -> list[Equipment]:
        """Its cameras (`kind` "cameras") or its SD cards ("sd_cards") — a removed one only when asked for."""

    def all_equipment(self, kind: str) -> list[tuple[str, Equipment]]:
        """The cameras or the SD cards of every research project, project after project, each with its research project."""

    def save_equipment(self, project: str, kind: str, items: list[Equipment], *, by_hand: bool = False) -> list[Equipment]:
        """Keeps these as all its cameras or SD cards (see domain.rules.saved_records), each change of status written down. By hand — a person, not a
        visit — the status changes only as the visits allow (EquipmentStatusRefused). UnknownProject, ProjectArchived."""

    def camera(self, project: str | None, key: str | None) -> Camera | None:
        """The camera a deployment or a visit names: the one with that label, else the one with that serial number — case aside. None when it names
        none, or the research project has none."""

    def set_camera_identity(self, project: str, label: str, make: str | None, model: str | None) -> Camera:
        """Keeps in the record of a camera the make and the model its images say. UnknownCamera."""

    def add_equipment(self, project: str, kind: str, items: list[Equipment]) -> AddedTrappers:
        """Adds the cameras or SD cards that are not kept yet — active —; one with the label of another (as written) is left out: {added, skipped}
        by label."""

    def retire_equipment(self, project: str, kind: str, key: str, reason: str, day: str | None, note: str | None) -> bool:
        """Archives the camera or SD card a visit names — its label, or a camera's serial number, as written — because it was found stolen, lost or
        broken ("archived": for another reason). False when the research project keeps none called that, or it is archived already: that is for
        good."""

    # the roles of the people in a research project
    def roles(self, project: str, include_deleted: bool = False) -> list[Role]:
        """Its roles, each told with the name its trapper has now."""

    def all_roles(self) -> list[tuple[str, Role]]:
        """The roles of every research project, project after project."""

    def add_roles(self, project: str, roles: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Gives trappers — by name, whatever its case — a role in a research project; the ones it has already are left as they are. Gives the
        (trapper, role) added. UnknownTrapper: one is not among the people."""

    def save_roles(self, project: str, roles: list[Role]) -> list[Role]:
        """Keeps these as all its roles — each by the id of its trapper, found by name; one whose trapper is not among the people keeps the name it was
        given. UnknownProject, ProjectArchived."""

    # the history of the states of the locations, the cameras and the SD cards
    def status_history(self, project: str, kind: str | None = None, name: str | None = None) -> list[dict[str, Any]]:
        """The lines of the history of a research project — of one kind and of one of them, when they are said —, the oldest first. UnknownProject."""

    def rebuild_status_history(self, project: str) -> int:
        """Adds the lines the visits say and the history lacks — nothing of it is changed nor removed —, and says how many. UnknownProject."""

    def checkpoint(self, project: str) -> Callable[[], None]:
        """What the catalog keeps of a research project now — its locations, cameras, SD cards, roles and history, and the people —, and how to put
        it back: a save made of several writes (an import of visits) calls it when one of them fails, so nothing is left half written."""

    # the field work of the settings page
    def fieldwork(self) -> Fieldwork:
        """The people, and the cameras, SD cards and roles of every research project — and those versions before left in the settings, which are
        taken to their research project first when it is kept."""

    def save_fieldwork(self, trappers: list[Trapper], cameras: list[tuple[str | None, Camera]], sd_cards: list[tuple[str | None, SdCard]],
                       roles: list[tuple[str | None, Role]]) -> Fieldwork:
        """Saves the field work as the settings page has it: the people; and the cameras, SD cards and roles of each research project, which replace
        its own — an archived camera or card can't be changed (EquipmentArchived), each belongs to a research project (EquipmentWithoutProject), and
        their status changes only as the visits allow. Gives what is of a research project that is not kept — to stay in the settings."""

    def require_project(self, acronym: str, *, active: bool = False, modifiable: bool = False) -> ResearchProject:
        """The research project, if it is kept — and, asked for, being worked on (ProjectNotActive: what new visits need) or one that can be modified
        (ProjectArchived). UnknownProject."""


# ── out: what the module needs ──

class CatalogRepository(Protocol):
    """Where the records of the catalog are kept."""

    def read_trappers(self) -> list[Trapper]:
        """All the people kept, the removed ones too; one kept before the ids existed gets the same id whenever it is read."""

    def write_trappers(self, trappers: list[Trapper]) -> None:
        """Keeps these as all the people."""

    def read_projects(self) -> list[ResearchProject]:
        """Every research project kept, the removed ones too."""

    def read_project(self, acronym: str) -> ResearchProject | None:
        """One research project as it is kept — removed or not —, or None."""

    def add_project(self, project: ResearchProject) -> None:
        """Keeps a new research project, and makes its folder."""

    def save_project(self, project: ResearchProject) -> None:
        """Replaces a research project that is kept."""

    def files_of(self, acronym: str) -> set[str]:
        """The names of the files the records of a research project are kept in, in its folder of the collections folder — none of its own for
        a database, which still leaves out the files of records a move from them may have left."""

    def read_locations(self, project: str) -> list[Location]:
        """The locations of a research project as they are kept, the removed ones too; one kept before the ids existed gets the same id whenever it is
        read. Empty when it has none — or there is no such research project."""

    def write_locations(self, project: str, locations: list[Location]) -> None:
        """Keeps these as all the locations of the research project."""

    def read_equipment(self, project: str, kind: str) -> list[Equipment]:
        """The cameras or the SD cards of a research project as they are kept, the removed ones too (one kept before the ids existed gets the same id
        whenever it is read). Empty when it has none."""

    def write_equipment(self, project: str, kind: str, items: list[Equipment]) -> None:
        """Keeps these as all its cameras or SD cards."""

    def read_roles(self, project: str) -> list[Role]:
        """The roles of a research project as they are kept, the removed ones too."""

    def write_roles(self, project: str, roles: list[Role]) -> None:
        """Keeps these as all its roles."""


class VisitHistory(Protocol):
    """What the visits say, as far as the catalog needs it."""

    def has_visits(self, acronym: str) -> bool:
        """Whether any visit was kept to the research project."""

    def visits_at(self, project: str, location_id: str) -> int:
        """How many visits were kept to a location."""

    def site_status_refusal(self, project: str, locations: list[Location], location: Location, wanted: str) -> str | None:
        """Why the status of a site cannot be set to `wanted` by hand — None when it can: a camera that is out there, a visit still to be made in a
        revision that has begun… The visits' rules."""

    def equipment_status_refusal(self, project: str, kind: str, item: Equipment, wanted: str) -> str | None:
        """Why the status of a camera or an SD card cannot be set to `wanted` by hand — None when it can: it is put up, or in a camera. The visits'
        rules."""


class StatusHistory(Protocol):
    """Where each change of the status of a location, a camera or an SD card is written down."""

    def checkpoint(self, project: str) -> Callable[[], None]:
        """The history of a research project now, and how to put it back (see CatalogService.checkpoint)."""

    def record_location(self, project: str, before: Location | None, after: Location) -> None:
        """A line when `after` has another status than `before` had — or when it is new, with the status it starts with."""

    def record_equipment(self, project: str, kind: str, before: list[Equipment], after: list[Equipment]) -> None:
        """A line for each of `after` whose status is not the one it had in `before` — found there by its id —, or that is new."""

    def lines(self, project: str, kind: str | None, name: str | None) -> list[dict[str, Any]]:
        """The lines kept — of one kind and of one of them, when they are said —, the oldest first."""

    def rebuild(self, project: str) -> int:
        """Adds the lines the visits say and the history lacks, and says how many."""


class LegacyFieldwork(Protocol):
    """The cameras, the SD cards and the roles versions before kept in the settings, each with the research project it says (or none)."""

    def items(self, kind: str) -> list[tuple[str | None, Any]]:
        """What is left of one kind — "cameras", "sd_cards", "roles" —, each with its research project."""

    def keep(self, kind: str, items: list[tuple[str | None, Any]]) -> None:
        """What is left of one kind once the catalog took what it could: kept in the settings, the rest no longer there."""


class LegacyTrappers(Protocol):
    """The people versions before kept in the settings."""

    def take(self) -> list[Trapper]:
        """Gives them, and they are no longer there: the catalog keeps them from now on."""


class Clock(Protocol):
    def now(self) -> str:
        """The instant, as the dates of a record are written: ISO 8601, UTC, with a Z."""

    def today(self) -> str:
        """The day, here, YYYY-MM-DD."""


class ProjectFolders(Protocol):
    """The folders of the research projects in the collections folder, where their collections go."""

    def make(self, acronym: str) -> None:
        """Makes the folder of a research project, when it is not there."""

    def held(self, acronym: str, besides: set[str]) -> list[str]:
        """What the folder of a research project holds besides the files `besides` — collections, deployments, images —, by name."""

