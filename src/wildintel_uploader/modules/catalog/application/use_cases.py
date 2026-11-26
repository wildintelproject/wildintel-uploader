"""The use cases of the catalog: `CatalogUseCases` implements its port in (`domain.ports.CatalogService`), given its ports out — where the records are
kept (`CatalogRepository`), the people versions before kept in the settings (`LegacyTrappers`), what the visits say (`VisitHistory`), where the
changes of status are written down (`StatusHistory`) and the clock (`Clock`) — and how a new id is made."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from wildintel_uploader.modules.catalog.domain import rules
from wildintel_uploader.modules.catalog.domain.models import (
    DEFAULT_TIMEZONE, Location, LocationArchived, LocationExists, LocationFromTrapper, LocationHasVisits, LocationTimeFixed, NewLocationStatus,
    ProjectArchived, ProjectExists, ProjectHasVisits, ProjectNotActive, ProjectNotEmpty, ResearchProject, SiteStatusRefused, Trapper, UnknownLocation,
    UnknownProject, is_utc,
)
from wildintel_uploader.modules.catalog.domain.ports import (
    AddedTrappers, CatalogRepository, CatalogService, Clock, LegacyTrappers, StatusHistory, VisitHistory,
)
from wildintel_uploader.shared import ids


class CatalogUseCases(CatalogService):
    def __init__(self, repository: CatalogRepository, *, legacy_trappers: LegacyTrappers, visits: VisitHistory, status_history: StatusHistory,
                 clock: Clock, new_id: Callable[[], str] = ids.new_id) -> None:
        self.repository, self.legacy_trappers, self.visits, self.status_history = repository, legacy_trappers, visits, status_history
        self.clock, self.new_id = clock, new_id

    # ── the people ──

    def _all_trappers(self) -> list[Trapper]:
        """All the people kept — the first time, the ones versions before left in the settings come into the catalog."""
        kept = self.repository.read_trappers()
        if kept:
            return kept
        # as they were kept — with the id they had, which the roles and the visits point to —, not as new ones
        adopted = rules.checked_trappers(self.legacy_trappers.take())
        if adopted:
            self.repository.write_trappers(adopted)
        return adopted

    def trappers(self, include_deleted: bool = False) -> list[Trapper]:
        everyone = self._all_trappers()
        return everyone if include_deleted else [t for t in everyone if not t.deleted]

    def save_trappers(self, trappers: list[Trapper]) -> list[Trapper]:
        wanted = rules.checked_trappers(trappers)
        kept = rules.saved_trappers(self._all_trappers(), wanted, self.clock.now(), self.new_id)
        self.repository.write_trappers(kept)
        return [t for t in kept if not t.deleted]

    def add_trappers(self, trappers: list[Trapper]) -> AddedTrappers:
        alive = self.trappers()
        taken = {t.username.lower() for t in alive}
        added, skipped, new = [], [], []
        for trapper in trappers:
            if trapper.username.lower() in taken:
                skipped.append(trapper.username)
                continue
            taken.add(trapper.username.lower())
            new.append(Trapper(**{**{k: getattr(trapper, k) for k in ("username", "name", "affiliation", "email", "trapper_pk")}, "status": "active"}))
            added.append(trapper.username)
        if new:
            self.save_trappers([*alive, *new])
        return AddedTrappers(added=added, skipped=skipped)

    # ── the research projects ──

    def projects(self, include_deleted: bool = False) -> list[ResearchProject]:
        kept = self.repository.read_projects()
        return kept if include_deleted else [p for p in kept if not p.deleted]

    def _kept(self, acronym: str) -> ResearchProject:
        """The research project kept by that acronym — whatever its case — and not removed. UnknownProject."""
        project = self.repository.read_project(acronym)
        if project is None:
            project = next((p for p in self.repository.read_projects() if p.acronym.lower() == acronym.lower()), None)
        if project is None or project.deleted:
            raise UnknownProject(acronym)
        return project

    def project(self, acronym: str) -> ResearchProject:
        return self._kept(acronym)

    def add_project(self, project: ResearchProject) -> ResearchProject:
        before = self.repository.read_project(project.acronym)
        if before is not None and not before.deleted:
            raise ProjectExists(project.acronym)
        kept = rules.stamped(project, before, self.clock.now(), self.new_id)
        if before is None:
            self.repository.add_project(kept)
        else:
            self.repository.save_project(kept)
        return kept

    def update_project(self, acronym: str, changes: Mapping[str, Any]) -> ResearchProject:
        project = self._kept(acronym)
        if project.status == "archived":
            raise ProjectArchived(acronym)
        wanted = {k: v for k, v in changes.items() if k not in ("acronym", "audit")}
        if wanted.get("status") == "planned" and project.status != "planned" and self.visits.has_visits(project.acronym):
            raise ProjectHasVisits(acronym)
        kept = rules.stamped(replace(project, **wanted), project, self.clock.now(), self.new_id)
        self.repository.save_project(kept)
        return kept

    def delete_project(self, acronym: str) -> None:
        project = self._kept(acronym)
        if project.status == "archived":
            raise ProjectArchived(acronym)
        held = self.repository.held_by_project(project.acronym)
        if held:
            raise ProjectNotEmpty(acronym, held)
        self.repository.save_project(rules.removed(project, self.clock.now()))

    def require_project(self, acronym: str, *, active: bool = False, modifiable: bool = False) -> ResearchProject:
        project = self._kept(acronym)
        if active and project.status != "active":
            raise ProjectNotActive(acronym, project.status)
        if modifiable and project.status == "archived":
            raise ProjectArchived(acronym)
        return project

    # ── the locations ──

    def _require_modifiable(self, acronym: str) -> None:
        """An archived research project can't be modified — nor its locations. One that is not kept is not refused here: it has no locations."""
        project = self.repository.read_project(acronym) or next((p for p in self.repository.read_projects() if p.acronym.lower() == acronym.lower()), None)
        if project is not None and project.status == "archived":
            raise ProjectArchived(acronym)

    @staticmethod
    def _index(locations: list[Location], location_id: str, deleted: bool = False) -> int | None:
        return next((i for i, loc in enumerate(locations) if loc.location_id.lower() == location_id.lower() and loc.deleted == deleted), None)

    def locations(self, project: str, include_deleted: bool = False) -> list[Location]:
        kept = self.repository.read_locations(project)
        return kept if include_deleted else [loc for loc in kept if not loc.deleted]

    def location(self, project: str, location_id: str) -> Location:
        locations = self.repository.read_locations(project)
        index = self._index(locations, location_id)
        if index is None:
            raise UnknownLocation(project, location_id)
        return locations[index]

    def add_location(self, project: str, location: Location, *, by_hand: bool = False) -> Location:
        self._require_modifiable(project)
        self.require_project(project)
        if by_hand and location.status not in ("pending", "planned"):
            raise NewLocationStatus(location.location_id, location.status)
        locations = self.repository.read_locations(project)
        if self._index(locations, location.location_id) is not None:
            raise LocationExists(project, location.location_id)
        location = replace(location, in_service=location.in_service or self.clock.today())   # put into production the day it is made, unless said
        back = self._index(locations, location.location_id, deleted=True)
        kept = rules.stamped(location, locations[back] if back is not None else None, self.clock.now(), self.new_id)
        if back is not None:
            locations[back] = kept
        else:
            locations.append(kept)
        self.repository.write_locations(project, locations)
        self.status_history.record_location(project, None, kept)
        return kept

    def update_location(self, project: str, location_id: str, changes: Mapping[str, Any], *, by_visit: bool = False) -> Location:
        self._require_modifiable(project)
        locations = self.repository.read_locations(project)
        index = self._index(locations, location_id)
        if index is None:
            raise UnknownLocation(project, location_id)
        before = locations[index]
        if before.status == "archived" and changes.get("status", "archived") != "archived":
            raise LocationArchived(location_id)
        wanted = changes.get("status")
        if not by_visit and wanted and wanted != before.status:
            why = self.visits.site_status_refusal(project, locations, before, wanted)
            if why:
                raise SiteStatusRefused(why)
        # the timezone and the summer-time setting say the same as they did, or are refused (UTC has none: what it says of it does not count)
        zone = before.timezone or DEFAULT_TIMEZONE
        now = {"timezone": zone, "ignore_dst": bool(before.ignore_dst) and not is_utc(zone)}
        changes = dict(changes)
        for key, label in (("timezone", "timezone"), ("ignore_dst", "summer-time setting")):
            if key in changes:
                asked = (changes[key] or DEFAULT_TIMEZONE) if key == "timezone" else bool(changes[key])
                if asked != now[key]:
                    raise LocationTimeFixed(location_id, label, now[key])
                del changes[key]
        changes = {k: v for k, v in changes.items() if k not in ("location_id", "audit", "id", "created_at", "updated_at", "deleted_at")}
        kept = rules.stamped(replace(before, **changes), before, self.clock.now(), self.new_id)
        locations[index] = kept
        self.repository.write_locations(project, locations)
        self.status_history.record_location(project, before, kept)
        return kept

    def delete_location(self, project: str, location_id: str) -> None:
        self._require_modifiable(project)
        locations = self.repository.read_locations(project)
        index = self._index(locations, location_id)
        if index is None:
            raise UnknownLocation(project, location_id)
        if locations[index].trapper_pk is not None:
            raise LocationFromTrapper(location_id)
        visits = self.visits.visits_at(project, location_id)
        if visits:
            raise LocationHasVisits(location_id, visits)
        locations[index] = rules.removed(locations[index], self.clock.now())
        self.repository.write_locations(project, locations)

    def location_time(self, project: str, location_id: str | None) -> dict[str, Any]:
        if not location_id:
            return {}
        found = next((loc for loc in self.repository.read_locations(project) if loc.location_id.lower() == location_id.lower()), None)
        return {k: getattr(found, k) for k in ("timezone", "ignore_dst") if found is not None and getattr(found, k) is not None}
