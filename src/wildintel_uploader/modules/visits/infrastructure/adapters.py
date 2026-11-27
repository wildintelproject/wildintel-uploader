"""The adapters of the visits: the visits kept (KeptVisits), the catalog as records, the folders of the collections, the history of the states
(the catalog's), where the deployments were uploaded (the uploaders), the reports, the settings of FIELDLOG. What
they refuse is VisitsFailed, with their words."""
from __future__ import annotations

from typing import Any
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.ports import CatalogRecords
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.visits.domain.models import VisitsFailed
from wildintel_uploader.modules.visits.domain.visit_file import VisitsCsvError
from wildintel_uploader.modules.visits.domain.ports import (
    Clock, StateHistory, Uploads, Visit, VisitCatalog, VisitDeployments, VisitReports, VisitRepository, VisitSettings,
)
from wildintel_uploader.modules.deployments.domain.ports import CollectionLayout
from wildintel_uploader.modules.visits.infrastructure.kept_visits import KeptVisits



@contextmanager
def _failed() -> Iterator[None]:
    """What the files and the records refuse, as VisitsFailed."""
    from wildintel_uploader.shared.storage import StorageError
    try:
        yield
    except (StorageError, VisitsCsvError) as exc:
        raise VisitsFailed(str(exc)) from exc


class StoredVisits(VisitRepository):
    """The visits kept (KeptVisits), what they refuse told as VisitsFailed."""

    def __init__(self, kept: KeptVisits) -> None:
        self._kept = kept

    def list(self, project: str, location_id: str | None = None) -> list[Visit]:
        with _failed():
            return self._kept.list(project, location_id)

    def add(self, project: str, visit: Visit) -> Visit:
        with _failed():
            return self._kept.add(project, visit)

    def add_many(self, project: str, visits: list[Visit]) -> int:
        with _failed():
            return self._kept.add_many(project, visits)

    def update(self, project: str, location_id: str, session: str, visit: Visit) -> Visit:
        with _failed():
            return self._kept.update(project, location_id, session, visit)

    def unknown(self, project: str) -> list[Visit]:
        with _failed():
            return self._kept.unknown(project)

    def kept_count(self, project: str) -> int:
        with _failed():
            return self._kept.kept_count(project)

    def replace_all(self, project: str, visits: list[Visit]) -> None:
        with _failed():
            self._kept.replace_all(project, visits)

    def add_unknown(self, project: str, unknown: list[Visit]) -> int:
        with _failed():
            return self._kept.add_unknown(project, unknown)

    def planned_revisions(self, project: str) -> list[str]:
        with _failed():
            return self._kept.planned_revisions(project)

    def plan_revision(self, project: str, session: str) -> str:
        with _failed():
            return self._kept.plan_revision(project, session)

    def closed(self, project: str) -> list[dict]:
        with _failed():
            return self._kept.closed(project)

    def link(self, project: str, location_id: str, date: str, time: str, deployment_id: str) -> Visit:
        with _failed():
            return self._kept.link(project, location_id, date, time, deployment_id)

    def write_states(self, project: str, states: dict) -> int:
        with _failed():
            return self._kept.write_states(project, states)


class CatalogOfTheVisits(VisitCatalog):
    """The catalog as records — through its contract, given when it is needed."""

    def __init__(self, records: Callable[[], CatalogRecords]) -> None:
        self._records = records

    def require_project(self, project: str, *, active: bool = False) -> None:
        with _failed():
            self._records().require_project(project, active=active)

    def locations(self, project: str, include_deleted: bool = False) -> list[dict]:
        with _failed():
            return self._records().locations(project, include_deleted)

    def equipment(self, project: str, kind: str) -> list[dict]:
        with _failed():
            return self._records().equipment(project, kind)

    def trappers(self) -> list[dict]:
        with _failed():
            return self._records().trappers()

    def trapper_names(self) -> list[str]:
        return [t["name"] for t in self.trappers()]

    def add_trappers(self, trappers: list[dict]) -> None:
        with _failed():
            records = self._records()
            records.keep_trappers([*records.trappers(), *trappers])

    def add_location(self, project: str, location: dict) -> None:
        with _failed():
            self._records().add_location(project, location)

    def change_location(self, project: str, location_id: str, changes: dict) -> None:
        with _failed():
            self._records().change_location(project, location_id, changes, by_visit=True)

    def keep_equipment(self, project: str, kind: str, items: list[dict]) -> None:
        with _failed():
            self._records().keep_equipment(project, kind, items)


class StoredStateHistory(StateHistory):
    def because(self, reason: str, day: str | None, why: dict | None = None) -> AbstractContextManager:
        from wildintel_uploader.modules.catalog.domain.history import because
        return because(reason, day, why)


class CollectionFolders(VisitDeployments):
    """The folders of the collections, as the deployments make them — their contract: the layout of the collections."""

    def __init__(self, root: Path, layout: Callable[[], CollectionLayout]) -> None:
        self.root, self._layout = root, layout

    def make_collection(self, project: str, collection: str) -> None:
        with _failed():
            self._layout().write_collection_metadata(self.root / project / collection, collection)


class UploadsOfTheUploaders(Uploads):
    """Where the deployments were uploaded, as the uploaders say it — through their contract."""

    def __init__(self, uploaders) -> None:
        self._uploaders = uploaders

    def trapper_state(self, project: str, deployment_id: str | None) -> tuple[str | None, bool]:
        return self._uploaders.trapper_state(project, deployment_id)

    def uploads_of(self, project: str, deployment_id: str) -> list[dict]:
        return self._uploaders.uploads_of(project, deployment_id)

    def upload_states(self, project: str, imported: str | None, deployment_id: str) -> list[dict]:
        return self._uploaders.upload_states(project, imported, deployment_id)


class SavedVisitReports(VisitReports):
    """Through the contract of the reports."""

    def __init__(self, reports: ReportsService) -> None:
        self._reports = reports

    def import_report(self, project: str, result: dict, saved: int) -> str | None:
        """The report of an import, kept with the other reports — its id; None when it could not be written."""
        try:
            return self._reports.save_visits_import(project, result, saved)
        except OSError:
            return None


class FieldlogInUse(VisitSettings):
    """FIELDLOG as settings.toml keeps it."""

    def __init__(self, fieldlog: Callable[[], Any]) -> None:
        self._fieldlog = fieldlog   # the section, asked each time

    def keep_seconds(self) -> bool:
        return self._fieldlog().keep_seconds

    def time_source(self) -> str:
        return self._fieldlog().time_source


class AuditClock(Clock):
    def today(self) -> str:
        from wildintel_uploader.shared import audit
        return audit.now()[:10]
