"""The use cases of the catalog: `CatalogUseCases` implements its port in (`domain.ports.CatalogService`), given its ports out — where the records are
kept (`CatalogRepository`), the people versions before kept in the settings (`LegacyTrappers`), what the visits say (`VisitHistory`), where the
changes of status are written down (`StatusHistory`) and the clock (`Clock`) — and how a new id is made."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from wildintel_uploader.modules.catalog.domain import rules
from wildintel_uploader.modules.catalog.domain.models import (
    DEFAULT_TIMEZONE, EQUIPMENT_KINDS, CatalogError, EquipmentArchived, EquipmentStatusRefused, EquipmentWithoutProject, Location, LocationArchived, LocationExists, LocationFromTrapper, LocationHasVisits, LocationTimeFixed, NewLocationStatus,
    ProjectArchived, ProjectExists, ProjectHasVisits, ProjectNotActive, ProjectNotEmpty, ResearchProject, Role, SiteStatusRefused, Trapper,
    UnknownCamera, UnknownLocation, UnknownProject, UnknownTrapper, is_utc,
)
from wildintel_uploader.modules.catalog.domain.ports import (
    AddedTrappers, CatalogRepository, CatalogService, Clock, Equipment, Fieldwork, LegacyFieldwork, LegacyTrappers, StatusHistory, VisitHistory,
)
from wildintel_uploader.shared import ids


class CatalogUseCases(CatalogService):
    def __init__(self, repository: CatalogRepository, *, legacy_trappers: LegacyTrappers, visits: VisitHistory, status_history: StatusHistory,
                 clock: Clock, legacy_fieldwork: LegacyFieldwork | None = None, new_id: Callable[[], str] = ids.new_id) -> None:
        self.repository, self.legacy_trappers, self.visits, self._history = repository, legacy_trappers, visits, status_history
        self.clock, self.legacy_fieldwork, self.new_id = clock, legacy_fieldwork, new_id

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
        self._history.record_location(project, None, kept)
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
        self._history.record_location(project, before, kept)
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

    # ── the equipment: cameras and SD cards ──

    @staticmethod
    def _kind(kind: str) -> str:
        if kind not in EQUIPMENT_KINDS:
            raise CatalogError("kind", f"must be one of {', '.join(EQUIPMENT_KINDS)}")
        return kind

    def equipment(self, project: str, kind: str, include_deleted: bool = False) -> list[Equipment]:
        kept = self.repository.read_equipment(project, self._kind(kind))
        return kept if include_deleted else [i for i in kept if not i.deleted]

    def all_equipment(self, kind: str) -> list[tuple[str, Equipment]]:
        return [(p.acronym, item) for p in self.projects() for item in self.equipment(p.acronym, kind)]

    def save_equipment(self, project: str, kind: str, items: list[Equipment], *, by_hand: bool = False) -> list[Equipment]:
        self._kind(kind)
        self._require_modifiable(project)
        self.require_project(project)
        kept = self.repository.read_equipment(project, kind)
        if by_hand:   # what a visit does to a camera or a card, it does through the app, not by hand
            alive = [i for i in kept if not i.deleted]
            by_label, by_id = {i.label: i for i in alive}, {i.audit.id: i for i in alive if i.audit.id}
            for item in items:
                old = (by_id.get(item.audit.id) if item.audit.id else None) or by_label.get(item.label)
                if old is not None and item.status and item.status != old.status:
                    why = self.visits.equipment_status_refusal(project, kind, old, item.status)
                    if why:
                        raise EquipmentStatusRefused(why)
        saved = rules.saved_records(kept, items, lambda i: i.label, self.clock.now(), self.new_id)   # as written: 7b and 7B are two
        self.repository.write_equipment(project, kind, saved)
        self._history.record_equipment(project, kind, kept, saved)
        return [i for i in saved if not i.deleted]

    def camera(self, project: str | None, key: str | None):
        if not project or not str(key or "").strip():
            return None
        try:
            cameras = self.equipment(project, "cameras")
        except Exception:  # noqa: BLE001 — no research project, nothing kept: no record to compare with
            return None
        wanted = str(key).strip().casefold()
        return (next((c for c in cameras if c.label.strip().casefold() == wanted), None)
                or next((c for c in cameras if (c.camera_id or "").strip().casefold() == wanted), None))

    def set_camera_identity(self, project: str, label: str, make: str | None, model: str | None):
        cameras = self.equipment(project, "cameras")
        record = next((c for c in cameras if c.label.strip() == label.strip()), None)
        if record is None:
            raise UnknownCamera(project, label)
        changed = replace(record, camera_make=(make or "").strip() or None, camera_model=(model or "").strip() or None)
        saved = self.save_equipment(project, "cameras", [changed if c is record else c for c in cameras])
        return next(c for c in saved if c.audit.id == record.audit.id)

    def add_equipment(self, project: str, kind: str, items: list[Equipment]) -> AddedTrappers:
        kept = self.equipment(project, kind)
        have = {i.label for i in kept}   # as written: 7b and 7B are two
        added, skipped, new = [], [], []
        for item in items:
            if item.label in have:
                skipped.append(item.label)
                continue
            have.add(item.label)
            new.append(replace(item, status="active"))
            added.append(item.label)
        if new:
            self.save_equipment(project, kind, [*kept, *new])
        return AddedTrappers(added=added, skipped=skipped)

    def retire_equipment(self, project: str, kind: str, key: str, reason: str, day: str | None, note: str | None) -> bool:
        items = self.equipment(project, kind)
        wanted, retired = key.strip(), False   # as written: 7b and 7B are two
        out = []
        for item in items:
            if wanted and wanted in item.names and item.status != "archived":
                item = replace(item, status="archived", status_date=day, status_note=note, archive_reason=reason if reason != "archived" else "other")
                retired = True
            out.append(item)
        if retired:
            self.save_equipment(project, kind, out)
        return retired

    # ── the roles ──

    def roles(self, project: str, include_deleted: bool = False) -> list[Role]:
        people = {t.audit.id: t for t in self.trappers(include_deleted=True) if t.audit.id}
        told = [replace(r, trapper=people[r.trapper_ref].name) if r.trapper_ref in people else r for r in self.repository.read_roles(project)]
        return told if include_deleted else [r for r in told if not r.deleted]

    def all_roles(self) -> list[tuple[str, Role]]:
        return [(p.acronym, role) for p in self.projects() for role in self.roles(p.acronym)]

    def add_roles(self, project: str, roles: list[tuple[str, str]]) -> list[tuple[str, str]]:
        self.require_project(project)
        people = {t.name.strip().lower(): t.name for t in self.trappers()}
        kept = self.roles(project)
        have = {((r.trapper or "").lower(), r.role) for r in kept}
        added: list[tuple[str, str]] = []
        for trapper, role in roles:
            name = people.get(trapper.strip().lower())
            if name is None:
                raise UnknownTrapper(trapper)
            if (name.lower(), role) not in have:
                have.add((name.lower(), role))
                added.append((name, role))
        if added:
            self.save_roles(project, [*kept, *[Role(trapper=n, role=r) for n, r in added]])
        return added

    @staticmethod
    def _role_key(role: Role) -> tuple:
        return (role.trapper_ref or (role.trapper or "").strip().lower(), role.role or "contributor")

    def save_roles(self, project: str, roles: list[Role]) -> list[Role]:
        self._require_modifiable(project)
        self.require_project(project)
        by_name = {t.name.strip().lower(): t for t in self.trappers(include_deleted=True)}
        stored = []
        for role in roles:
            person = by_name.get((role.trapper or "").strip().lower())
            # kept by the id of its trapper — so a trapper renamed still has it —, else by the name it was given
            stored.append(replace(role, trapper_ref=person.audit.id, trapper=None) if person and person.audit.id else replace(role, trapper_ref=None))
        saved = rules.saved_records(self.repository.read_roles(project), stored, self._role_key, self.clock.now(), self.new_id)
        self.repository.write_roles(project, saved)
        return self.roles(project)

    # ── the history of the states ──

    def status_history(self, project: str, kind: str | None = None, name: str | None = None) -> list[dict[str, Any]]:
        self.require_project(project)
        return self._history.lines(project, kind, name)

    def rebuild_status_history(self, project: str) -> int:
        self.require_project(project)
        return self._history.rebuild(project)

    # ── the field work of the settings page ──

    def _adopt_legacy_fieldwork(self) -> None:
        """What versions before left in the settings goes to its research project, when it is kept: what can't be moved — of a research project that
        is not kept yet, or of none — stays there, to wait. Nothing is done once there is nothing left."""
        if self.legacy_fieldwork is None:
            return
        known = {p.acronym.lower(): p.acronym for p in self.projects()}
        for kind in (*EQUIPMENT_KINDS, "roles"):
            legacy = self.legacy_fieldwork.items(kind)
            if not legacy:
                continue
            for acronym in known.values():
                mine = [item for project, item in legacy if (project or "").lower() == acronym.lower()]
                if not mine:
                    continue
                if kind == "roles":
                    kept = self.roles(acronym, include_deleted=True)
                    have = {((r.trapper or "").lower(), r.role) for r in kept}
                    added = [r for r in mine if ((r.trapper or "").lower(), r.role) not in have]
                    self.save_roles(acronym, [*[r for r in kept if not r.deleted], *added])
                else:
                    kept_items = self.equipment(acronym, kind)
                    have = {i.label for i in kept_items}   # as written: 7b and 7B are two
                    self.save_equipment(acronym, kind, [*kept_items, *[i for i in mine if i.label not in have]])
            left = [(project, item) for project, item in legacy if (project or "").lower() not in known]
            if len(left) != len(legacy):
                self.legacy_fieldwork.keep(kind, left)

    def fieldwork(self) -> Fieldwork:
        self._adopt_legacy_fieldwork()
        legacy = self.legacy_fieldwork
        return Fieldwork(
            trappers=self.trappers(),
            cameras=[*self.all_equipment("cameras"), *(legacy.items("cameras") if legacy else [])],
            sd_cards=[*self.all_equipment("sd_cards"), *(legacy.items("sd_cards") if legacy else [])],
            roles=[*self.all_roles(), *(legacy.items("roles") if legacy else [])],
        )

    def save_fieldwork(self, trappers, cameras, sd_cards, roles) -> Fieldwork:
        self.save_trappers(trappers)
        known = {p.acronym for p in self.projects()}
        left: dict[str, list] = {}
        for kind, items in (("cameras", cameras), ("sd_cards", sd_cards)):
            # an archived camera or SD card is archived for good: what is kept of it is not changed
            for project in {p for p, _ in items if p}:
                try:
                    kept = self.equipment(project, kind)
                except Exception:  # noqa: BLE001 — a research project that can't be read keeps nothing to compare with
                    continue
                archived = {i.label: i for i in kept if i.status == "archived"}
                for p, item in items:
                    before = archived.get(item.label) if p == project else None
                    if before is not None and rules._content(item) != rules._content(before):
                        raise EquipmentArchived(kind, item.label)
            free = [item for p, item in items if not p]
            if free:
                raise EquipmentWithoutProject(kind, free[0].label)
            by_project: dict[str, list] = {}
            for p, item in items:
                by_project.setdefault(p, []).append(item)
            # the list of each research project is replaced by what the page has; a research project that is not kept keeps them in the settings
            for project in known:
                self.save_equipment(project, kind, by_project.get(project, []), by_hand=True)
            left[kind] = [(p, item) for p, item in items if p not in known]
        by_project_roles: dict[str, list] = {}
        for p, role in roles:
            by_project_roles.setdefault(p, []).append(role)
        for project in known:
            self.save_roles(project, by_project_roles.get(project, []))
        return Fieldwork(trappers=[], cameras=left["cameras"], sd_cards=left["sd_cards"], roles=[(p, r) for p, r in roles if p not in known])
