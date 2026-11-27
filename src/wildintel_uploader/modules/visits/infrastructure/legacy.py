"""The ports of the visits over the code of before, as the rest of the app still keeps them: the visits in the folders of the research projects
(local_folder_service), the catalog as dicts, the deployments the visits say (visit_deployments), the history of the states (status_history), the
file of visits (visits_csv), where the deployments were uploaded (their folders, the settings of TRAPPER and Agouti), the reports. What they refuse
is VisitsFailed, with their words. Each is moved into the module as the module that keeps it comes to be."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from wildintel_uploader.modules.visits.domain.models import VisitsFailed
from wildintel_uploader.modules.visits.domain.ports import (
    Clock, StateHistory, Uploads, Visit, VisitCatalog, VisitDeployments, VisitFile, VisitReports, VisitRepository, VisitSettings,
)
from wildintel_uploader.modules.visits.infrastructure.records import VisitRecord


def _old():
    from wildintel_uploader.core.services import local_folder_service
    return local_folder_service


@contextmanager
def _failed() -> Iterator[None]:
    """What the code of before refuses, as VisitsFailed."""
    from wildintel_uploader.core.services import visits_csv
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
            return _old().list_visits(self.root, project, location_id)

    def add(self, project: str, visit: Visit) -> Visit:
        with _failed():
            return _old().write_visit(self.root, project, visit)

    def add_many(self, project: str, visits: list[Visit]) -> int:
        with _failed():
            return _old().write_visits(self.root, project, visits)

    def update(self, project: str, location_id: str, session: str, visit: Visit) -> Visit:
        with _failed():
            return _old().update_visit(self.root, project, location_id, session, visit)

    def unknown(self, project: str) -> list[Visit]:
        with _failed():
            return _old().list_unknown(self.root, project)

    def add_unknown(self, project: str, unknown: list[Visit]) -> int:
        with _failed():
            return _old().write_unknown(self.root, project, unknown)

    def planned_revisions(self, project: str) -> list[str]:
        with _failed():
            return _old().list_planned_revisions(self.root, project)

    def plan_revision(self, project: str, session: str) -> str:
        with _failed():
            return _old().plan_revision(self.root, project, session)

    def closed(self, project: str) -> list[dict]:
        with _failed():
            return _old().closed_visits(self.root, project)

    def link(self, project: str, location_id: str, date: str, time: str, deployment_id: str) -> Visit:
        with _failed():
            return _old().link_visit(self.root, project, location_id, date, time, deployment_id)


class CatalogOfTheVisits(VisitCatalog):
    """The catalog through the functions of before, which ask the module of the catalog."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def require_project(self, project: str, *, active: bool = False) -> None:
        with _failed():
            (_old().require_active_research_project if active else _old().require_research_project)(self.root, project)

    def locations(self, project: str, include_deleted: bool = False) -> list[dict]:
        with _failed():
            return _old().list_locations(self.root, project, include_deleted=include_deleted)

    def equipment(self, project: str, kind: str) -> list[dict]:
        with _failed():
            return _old().list_field_items(self.root, project, kind)

    def trappers(self) -> list[dict]:
        with _failed():
            return _old().list_trappers(self.root)

    def trapper_names(self) -> list[str]:
        return [t["name"] for t in self.trappers()]

    def add_trappers(self, trappers: list[dict]) -> None:
        with _failed():
            _old().write_trappers(self.root, [*_old().list_trappers(self.root), *trappers])

    def add_location(self, project: str, location: dict) -> None:
        with _failed():
            _old().write_location(self.root, project, location)

    def change_location(self, project: str, location_id: str, changes: dict) -> None:
        with _failed():
            _old().update_location(self.root, project, location_id, changes, by_visit=True)

    def keep_equipment(self, project: str, kind: str, items: list[dict]) -> None:
        with _failed():
            _old().write_field_items(self.root, project, kind, items)


class StoredStateHistory(StateHistory):
    def because(self, reason: str, day: str | None, why: dict | None = None) -> AbstractContextManager:
        from wildintel_uploader.core.services import status_history
        return status_history.because(reason, day, why)


class DeploymentsOfTheVisits(VisitDeployments):
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def _vd():
        from wildintel_uploader.core.services import visit_deployments
        return visit_deployments

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
        from wildintel_uploader.core.services import visits_csv
        return visits_csv

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


# Where a deployment can be sent, and the settings that say whether each is used: only the uploaders in use have an upload planned.
UPLOADERS = {"trapper": lambda settings: settings.TRAPPER.enabled, "agouti": lambda settings: settings.AGOUTI.enabled}


class FolderUploads(Uploads):
    """Where a deployment was uploaded, as its folder says: its upload.json, or images.json when it was synced from TRAPPER."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _folder(self, project: str, deployment_id: str) -> Path:
        return self.root / project / deployment_id.split("-", 1)[0] / deployment_id

    @staticmethod
    def _upload(folder: Path):
        from wildintel_uploader.core.services import trapper_upload_service
        return _old()._read_json(folder / trapper_upload_service.UPLOAD_LOG_FILE)

    def trapper_state(self, project: str, deployment_id: str | None) -> tuple[str | None, bool]:
        """Whether the deployment a visit gave is on Trapper — uploaded from here, or synced from there — and when it was uploaded."""
        if not deployment_id:
            return None, False
        folder = self._folder(project, deployment_id)
        upload = self._upload(folder)
        uploaded_at = upload.get("uploaded_at") if isinstance(upload, dict) else None
        return uploaded_at, bool(uploaded_at) or _old().is_synced(folder)

    def uploads_of(self, project: str, deployment_id: str) -> list[dict]:
        """One upload for each platform it was sent to (only "trapper" for now) — "uploaded" with the day and what it did, or "synced"."""
        from wildintel_uploader.core import config
        folder = self._folder(project, deployment_id)
        upload = self._upload(folder)
        # the page of the deployment in Trapper — or of its revision —, as it was when it was sent; an upload made before that was kept goes to the site
        site = (config.load_settings().TRAPPER.base_url or "").rstrip("/") or None
        if isinstance(upload, dict) and upload.get("uploaded_at"):
            return [{"destination": "trapper", "kind": "uploaded", "uploaded_at": upload.get("uploaded_at"), "parts": upload.get("parts"),
                     "location_created": bool(upload.get("location_created")), "deployment_created": bool(upload.get("deployment_created")),
                     "url": upload.get("deployment_url") or upload.get("collection_url") or site}]
        if _old().is_synced(folder):
            return [{"destination": "trapper", "kind": "synced", "uploaded_at": None, "parts": None, "location_created": None, "deployment_created": None,
                     "url": site}]
        return []

    def upload_states(self, project: str, imported: str | None, deployment_id: str) -> list[dict]:
        """The upload to each uploader in use: "planned" from the start, then "done" or "failed" — {"destination", "state", "kind", "uploaded_at", "note"}."""
        from wildintel_uploader.core import config
        settings = config.load_settings()
        done = {u["destination"]: u for u in (self.uploads_of(project, imported) if imported else [])}
        failed = {f["destination"]: f for f in _old().list_upload_failures(self.root, project) if f.get("deployment_id") == deployment_id}
        out = []
        for destination, used in UPLOADERS.items():
            if not used(settings) and destination not in done:
                continue
            if destination in done:
                out.append({"destination": destination, "state": "done", "kind": done[destination]["kind"], "uploaded_at": done[destination].get("uploaded_at"),
                            "note": None})
            elif destination in failed:
                out.append({"destination": destination, "state": "failed", "kind": None, "uploaded_at": None, "note": failed[destination].get("note")})
            else:
                out.append({"destination": destination, "state": "planned", "kind": None, "uploaded_at": None, "note": None})
        return out


class SavedVisitReports(VisitReports):
    def import_report(self, project: str, result: dict, saved: int) -> str | None:
        """The report of an import, kept with the other reports — its id; None when it could not be written."""
        from wildintel_uploader.core.services import report_service
        try:
            return report_service.save(report_service.visits_import_report(project, result, saved))
        except OSError:
            return None


class FieldlogInUse(VisitSettings):
    """FIELDLOG as the code of before reads the settings (config.load_settings), as the other adapters here do."""

    @staticmethod
    def _fieldlog():
        from wildintel_uploader.core import config
        return config.load_settings().FIELDLOG

    def keep_seconds(self) -> bool:
        return self._fieldlog().keep_seconds

    def time_source(self) -> str:
        return self._fieldlog().time_source


class AuditClock(Clock):
    def today(self) -> str:
        from wildintel_uploader.shared import audit
        return audit.now()[:10]
