"""The ports of the visits over the code of before, as the rest of the app still keeps them: the visits in the folders of the research projects
(local_folder_service), the catalog as dicts, the deployments the visits say (deployments), the history of the states (the catalog's), the
file of visits (csv_file), where the deployments were uploaded (their folders, the settings of TRAPPER and Agouti), the reports. What they refuse
is VisitsFailed, with their words. Each is moved into the module as the module that keeps it comes to be."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.ports import CatalogRecords
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.visits.domain.models import VisitsFailed
from wildintel_uploader.modules.visits.domain.ports import (
    Clock, StateHistory, Uploads, Visit, VisitCatalog, VisitDeployments, VisitFile, VisitReports, VisitRepository, VisitSettings,
)
from wildintel_uploader.modules.visits.infrastructure import kept_visits
from wildintel_uploader.modules.visits.infrastructure.records import VisitRecord
from wildintel_uploader.modules.settings.domain.ports import StoredSettings



@contextmanager
def _failed() -> Iterator[None]:
    """What the code of before refuses, as VisitsFailed."""
    from wildintel_uploader.modules.visits.infrastructure import csv_file as visits_csv
    from wildintel_uploader.shared.storage import StorageError
    try:
        yield
    except (StorageError, visits_csv.VisitsCsvError) as exc:
        raise VisitsFailed(str(exc)) from exc


class StoredVisits(VisitRepository):
    def __init__(self, root: Path) -> None:
        self.root = root

    def list(self, project: str, location_id: str | None = None) -> list[Visit]:
        with _failed():
            return kept_visits.list_visits(self.root, project, location_id)

    def add(self, project: str, visit: Visit) -> Visit:
        with _failed():
            return kept_visits.write_visit(self.root, project, visit)

    def add_many(self, project: str, visits: list[Visit]) -> int:
        with _failed():
            return kept_visits.write_visits(self.root, project, visits)

    def update(self, project: str, location_id: str, session: str, visit: Visit) -> Visit:
        with _failed():
            return kept_visits.update_visit(self.root, project, location_id, session, visit)

    def unknown(self, project: str) -> list[Visit]:
        with _failed():
            return kept_visits.list_unknown(self.root, project)

    def kept_count(self, project: str) -> int:
        with _failed():
            return len(kept_visits._raw_visits(self.root, project))

    def replace_all(self, project: str, visits: list[Visit]) -> None:
        with _failed():
            kept_visits.replace_visits(self.root, project, visits)

    def add_unknown(self, project: str, unknown: list[Visit]) -> int:
        with _failed():
            return kept_visits.write_unknown(self.root, project, unknown)

    def planned_revisions(self, project: str) -> list[str]:
        with _failed():
            return kept_visits.list_planned_revisions(self.root, project)

    def plan_revision(self, project: str, session: str) -> str:
        with _failed():
            return kept_visits.plan_revision(self.root, project, session)

    def closed(self, project: str) -> list[dict]:
        with _failed():
            return kept_visits.closed_visits(self.root, project)

    def link(self, project: str, location_id: str, date: str, time: str, deployment_id: str) -> Visit:
        with _failed():
            return kept_visits.link_visit(self.root, project, location_id, date, time, deployment_id)


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


class DeploymentsOfTheVisits(VisitDeployments):
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _vd():
        from wildintel_uploader.modules.visits.infrastructure import deployments
        return deployments

    def refresh_states(self, project: str, keep_seconds: bool) -> None:
        with _failed():
            self._vd().refresh_states(self.root, project, keep_seconds)

    def locked(self, visits: list[Visit], keep_seconds: bool) -> set:
        return self._vd().locked(visits, keep_seconds)

    def make_collection_folders(self, project: str, visits: list[Visit], new: list[Visit], keep_seconds: bool) -> dict:
        with _failed():
            vd = self._vd()
            return vd.make_collection_folders(self.root, project, vd.collections_of(visits, new, keep_seconds), keep_seconds)

    def deployments(self, visits: list[Visit], keep_seconds: bool) -> list[dict]:
        return self._vd().deployments(visits, keep_seconds)

    def book(self, visits: list[Visit], keep_seconds: bool, locations: list[dict] | None, unknown: list[Visit], planned: list[str]) -> list[dict]:
        return self._vd().visit_book(visits, keep_seconds, locations, unknown, planned)

    def merged_details(self, visit: Visit, end: Visit) -> dict:
        return self._vd().merged_details(visit, end)


class CsvVisitFile(VisitFile):
    @staticmethod
    def _csv():
        from wildintel_uploader.modules.visits.infrastructure import csv_file
        return csv_file

    def parse(self, text: str, locations: list[dict], kept: list[Visit], mapping: dict | None, options: dict) -> dict:
        with _failed():
            return self._csv().parse_visits(text, locations, kept, mapping, options)

    def export(self, visits: list[Visit]) -> str:
        return self._csv().export_visits(visits)

    def columns(self, text: str) -> dict:
        vc = self._csv()
        with _failed():
            needed_by = {f: [e for e, spec in vc.CREATABLE.items() if f in spec["required"]] for f, _, _ in vc.FIELDS}
            return {**vc.suggest_mapping(text), "fields": [
                {"field": f, "label": label, "required": required, "entity": vc.ENTITY_ONLY.get(f), "required_with": needed_by[f]}
                for f, label, required in vc.FIELDS]}

    def normalized(self, visit: Visit) -> Visit:
        return VisitRecord.model_validate(visit).model_dump(mode="json")


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

    def __init__(self, settings: StoredSettings) -> None:
        self._settings = settings   # the settings as settings.toml keeps them

    def _fieldlog(self):
        return self._settings.load_settings().FIELDLOG

    def keep_seconds(self) -> bool:
        return self._fieldlog().keep_seconds

    def time_source(self) -> str:
        return self._fieldlog().time_source


class AuditClock(Clock):
    def today(self) -> str:
        from wildintel_uploader.shared import audit
        return audit.now()[:10]
