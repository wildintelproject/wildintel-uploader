"""#248: the use cases of the visits (modules.visits) over ports in memory — no files: planning a revision, refusing a visit that breaks the rules,
one save at a time, and the module's own settings (FIELDLOG)."""
from contextlib import nullcontext

import pytest

from wildintel_uploader.modules.settings.domain import models as _settings_models
from wildintel_uploader.modules.visits.application.use_cases import VisitsUseCases, save_lock
from wildintel_uploader.modules.visits.domain.models import ImportOptions, VisitLocked, VisitRefused
from wildintel_uploader.modules.visits.domain.settings import FieldlogSettings


class Kept:
    def __init__(self, visits=(), planned=()) -> None:
        self.visits, self.planned_ = list(visits), list(planned)

    def list(self, project, location_id=None):
        return list(self.visits)

    def add(self, project, visit):
        self.visits.append(visit)
        return visit

    def unknown(self, project):
        return []

    def planned_revisions(self, project):
        return list(self.planned_)

    def plan_revision(self, project, session):
        self.planned_.append(session)
        return session


class Catalog:
    def __init__(self, locations=()) -> None:
        self.locations_ = list(locations)

    def require_project(self, project, *, active=False):
        pass

    def locations(self, project, include_deleted=False):
        return list(self.locations_)

    def equipment(self, project, kind):
        return []

    def trappers(self):
        return [{"name": "Ana", "username": "ana"}]

    def trapper_names(self):
        return ["Ana"]


class Settings:
    def keep_seconds(self):
        return False

    def time_source(self):
        return "created_at"


class History:
    def because(self, reason, day, why=None):
        return nullcontext()


def _visits(kept=None, catalog=None) -> VisitsUseCases:
    return VisitsUseCases(kept or Kept(), catalog or Catalog(), deployments=None, file=None, sources=None, uploads=None, reports=None, history=History(),
                          settings=Settings(), clock=None)


def test_a_revision_is_planned_for_the_locations_that_can_be_visited():
    kept = Kept()
    service = _visits(kept, Catalog([{"location_id": "DONA_01", "status": "ready"}, {"location_id": "DONA_02", "status": "archived"}]))
    assert service.create_revision("DONA") == {"session": "R0001", "planned": ["DONA_01"], "previous": None}
    with pytest.raises(VisitLocked, match="R0001 is planned and has no visit yet"):
        service.create_revision("DONA")
    with pytest.raises(VisitLocked, match="No location can be visited"):
        _visits(catalog=Catalog([{"location_id": "DONA_01", "status": "planned"}])).create_revision("DONA")


def test_a_visit_that_names_no_trapper_of_the_people_is_refused():
    visit = {"location_id": "DONA_01", "session": "R0001", "date": "2026-10-02", "time": "08:00:00", "actions": ["Installation"], "trappers": "Nobody"}
    with pytest.raises(VisitRefused, match="Nobody is not one of the trappers"):
        _visits(catalog=Catalog([{"location_id": "DONA_01", "status": "ready", "timezone": "UTC"}])).save("DONA", visit)


def test_one_save_at_a_time_for_a_research_project():
    lock = save_lock("DONA")
    lock.acquire()
    try:
        with pytest.raises(VisitLocked, match="already being saved"):
            _visits().import_file(ImportOptions(research_project_id="dona", save=True))
    finally:
        lock.release()


def test_its_settings_are_its_own():
    assert _section("FIELDLOG").domain is FieldlogSettings


def _section(name: str):
    return next(x for x in _settings_models.SECTIONS if x.name == name)
