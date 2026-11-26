"""The use cases of the catalog: `CatalogUseCases` implements its port in (`domain.ports.CatalogService`), given its ports out — where the records are
kept (`CatalogRepository`), the people versions before kept in the settings (`LegacyTrappers`), what the visits say (`VisitHistory`) and the instant
(`Clock`) — and how a new id is made."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from wildintel_uploader.modules.catalog.domain import rules
from wildintel_uploader.modules.catalog.domain.models import (
    ProjectArchived, ProjectExists, ProjectHasVisits, ProjectNotActive, ProjectNotEmpty, ResearchProject, Trapper, UnknownProject,
)
from wildintel_uploader.modules.catalog.domain.ports import AddedTrappers, CatalogRepository, CatalogService, Clock, LegacyTrappers, VisitHistory
from wildintel_uploader.shared import ids


class CatalogUseCases(CatalogService):
    def __init__(self, repository: CatalogRepository, *, legacy_trappers: LegacyTrappers, visits: VisitHistory, clock: Clock,
                 new_id: Callable[[], str] = ids.new_id) -> None:
        self.repository, self.legacy_trappers, self.visits, self.clock, self.new_id = repository, legacy_trappers, visits, clock, new_id

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
