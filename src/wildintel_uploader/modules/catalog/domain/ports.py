"""The contracts of the catalog (#248), on both sides of it:

- **In** — `CatalogService`: what the module offers, which the entry points (and the other modules) call. Implemented by
  `application.use_cases.CatalogUseCases`.
- **Out** — what it needs from outside: `CatalogRepository`, where its records are kept (the JSON files of the collections folder,
  `infrastructure.json_repository`); `LegacyTrappers`, the people versions before kept in the settings (`infrastructure.legacy`, through the contract
  of the module of the settings); `VisitHistory`, what the visits say, read only (`infrastructure.visits` — the module of the visits, once there is
  one); `StatusHistory`, where each change of status is written down; `Clock`, the instant and the day."""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, Protocol

from wildintel_uploader.modules.catalog.domain.models import Location, ResearchProject, Trapper


@dataclass(frozen=True)
class AddedTrappers:
    """What adding people did: the usernames added, and those left out because they were taken."""
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

    def held_by_project(self, acronym: str) -> list[str]:
        """What the folder of the research project holds besides its own records — collections, deployments, images —, by name."""

    def read_locations(self, project: str) -> list[Location]:
        """The locations of a research project as they are kept, the removed ones too; one kept before the ids existed gets the same id whenever it is
        read. Empty when it has none — or there is no such research project."""

    def write_locations(self, project: str, locations: list[Location]) -> None:
        """Keeps these as all the locations of the research project."""


class VisitHistory(Protocol):
    """What the visits say, as far as the catalog needs it."""

    def has_visits(self, acronym: str) -> bool:
        """Whether any visit was kept to the research project."""

    def visits_at(self, project: str, location_id: str) -> int:
        """How many visits were kept to a location."""

    def site_status_refusal(self, project: str, locations: list[Location], location: Location, wanted: str) -> str | None:
        """Why the status of a site cannot be set to `wanted` by hand — None when it can: a camera that is out there, a visit still to be made in a
        revision that has begun… The visits' rules."""


class StatusHistory(Protocol):
    """Where each change of the status of a location, a camera or an SD card is written down."""

    def record_location(self, project: str, before: Location | None, after: Location) -> None:
        """A line when `after` has another status than `before` had — or when it is new, with the status it starts with."""


class LegacyTrappers(Protocol):
    """The people versions before kept in the settings."""

    def take(self) -> list[Trapper]:
        """Gives them, and they are no longer there: the catalog keeps them from now on."""


class Clock(Protocol):
    def now(self) -> str:
        """The instant, as the dates of a record are written: ISO 8601, UTC, with a Z."""

    def today(self) -> str:
        """The day, here, YYYY-MM-DD."""
