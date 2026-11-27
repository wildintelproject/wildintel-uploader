"""The ports of the visits: the contract the rest of the app asks them through (VisitsService), and what its use cases are given — where the visits
are kept, the catalog as the visits see it (records as dicts, as the rules read them), the deployments the visits say, the file of visits, the
sources, the uploads, the reports, the history of the states, the settings and the clock.

The visits are dicts, as the rules (domain.rules) read them and as they are kept: their shape is the record of a visit (infrastructure.records)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from typing import Any

from wildintel_uploader.modules.visits.domain.models import ImportOptions

Visit = dict[str, Any]


# ── in: the contract ──

class VisitsService(ABC):

    @abstractmethod
    def visits(self, project: str, location_id: str | None = None) -> list[Visit]:
        """The visits kept for a research project, those to one location when it is given."""

    @abstractmethod
    def save(self, project: str, visit: Visit) -> Visit:
        """Registers a visit, if it follows the rules: what it does to the locations, the cameras and the SD cards is done, and the folders of the
        collections it changes are made — the visit kept, with "collection_folders"."""

    @abstractmethod
    def update(self, project: str, location_id: str, session: str, visit: Visit) -> Visit:
        """Edits a visit kept — its site and its revision are its key."""

    @abstractmethod
    def create_revision(self, project: str) -> dict:
        """Plans the next revision: {"session", "planned", "previous"}."""

    @abstractmethod
    def mark_not_visited(self, project: str, session: str) -> dict:
        """Finishes a revision: each location with no visit in it gets one that could not be made. {"session", "marked"}."""

    @abstractmethod
    def import_file(self, options: ImportOptions) -> dict:
        """Reads the visits of a file or a source: what can be kept and what is wrong with the rest — kept, all or nothing, when asked."""

    @abstractmethod
    def export_file(self, project: str, location_id: str | None = None) -> dict:
        """The visits as a CSV that the import reads back: {"csv", "filename", "count"}."""

    @abstractmethod
    def epicollect_download(self) -> dict:
        """The visits of the Epicollect5 project of the settings as a CSV: {"csv", "count"}."""

    @abstractmethod
    def file_columns(self, text: str) -> dict:
        """The columns of a CSV, whether it is the form, a few rows, the fields of a visit and the column that most likely gives each."""

    @abstractmethod
    def closed(self, project: str) -> list[dict]:
        """The visits that closed a deployment not imported yet, with the visit that started it and its details."""

    @abstractmethod
    def link(self, project: str, location_id: str, date: str, time: str, deployment_id: str) -> Visit:
        """Records which deployment a visit closed, once it is imported."""

    @abstractmethod
    def deployments(self, project: str, location_id: str | None = None) -> list[dict]:
        """The deployments the visits say, closed and open, with where they were uploaded."""

    @abstractmethod
    def book(self, project: str, location_id: str | None = None) -> list[dict]:
        """The visit book: the visits, each with its deployment, and the locations not visited in a session."""


# ── out: what the use cases are given ──

class VisitRepository(ABC):
    """Where the visits of the research projects are kept, told with the names of what they point to."""

    @abstractmethod
    def list(self, project: str, location_id: str | None = None) -> list[Visit]: ...

    @abstractmethod
    def add(self, project: str, visit: Visit) -> Visit: ...

    @abstractmethod
    def add_many(self, project: str, visits: list[Visit]) -> int: ...

    @abstractmethod
    def update(self, project: str, location_id: str, session: str, visit: Visit) -> Visit: ...

    @abstractmethod
    def unknown(self, project: str) -> list[Visit]:
        """The visits known only to have been made (a revision before the ones kept)."""

    @abstractmethod
    def add_unknown(self, project: str, unknown: list[Visit]) -> int: ...

    @abstractmethod
    def planned_revisions(self, project: str) -> list[str]: ...

    @abstractmethod
    def plan_revision(self, project: str, session: str) -> str: ...

    @abstractmethod
    def closed(self, project: str) -> list[dict]:
        """{"visit", "end"} of each deployment closed and not imported yet."""

    @abstractmethod
    def link(self, project: str, location_id: str, date: str, time: str, deployment_id: str) -> Visit: ...


class VisitCatalog(ABC):
    """The catalog as the visits see it: its records as dicts."""

    @abstractmethod
    def require_project(self, project: str, *, active: bool = False) -> None: ...

    @abstractmethod
    def locations(self, project: str, include_deleted: bool = False) -> list[dict]: ...

    @abstractmethod
    def equipment(self, project: str, kind: str) -> list[dict]: ...

    @abstractmethod
    def trappers(self) -> list[dict]: ...

    @abstractmethod
    def trapper_names(self) -> list[str]:
        """The names of the people, as a visit says who went."""

    @abstractmethod
    def add_trappers(self, trappers: list[dict]) -> None: ...

    @abstractmethod
    def add_location(self, project: str, location: dict) -> None: ...

    @abstractmethod
    def change_location(self, project: str, location_id: str, changes: dict) -> None:
        """What a visit does to a location — its status by the rules of a visit."""

    @abstractmethod
    def keep_equipment(self, project: str, kind: str, items: list[dict]) -> None: ...


class StateHistory(ABC):
    @abstractmethod
    def because(self, reason: str, day: str | None, why: dict | None = None) -> AbstractContextManager:
        """Says why what is written inside changes the states: the visit that did it, and its day."""


class VisitDeployments(ABC):
    """The deployments the visits say, and the folders of their collections."""

    @abstractmethod
    def refresh_states(self, project: str, keep_seconds: bool) -> None: ...

    @abstractmethod
    def locked(self, visits: list[Visit], keep_seconds: bool) -> set: ...

    @abstractmethod
    def make_collection_folders(self, project: str, visits: list[Visit], new: list[Visit], keep_seconds: bool) -> dict: ...

    @abstractmethod
    def deployments(self, visits: list[Visit], keep_seconds: bool) -> list[dict]: ...

    @abstractmethod
    def book(self, visits: list[Visit], keep_seconds: bool, locations: list[dict] | None, unknown: list[Visit], planned: list[str]) -> list[dict]: ...

    @abstractmethod
    def merged_details(self, visit: Visit, end: Visit) -> dict: ...


class VisitFile(ABC):
    """A file of visits: any CSV, with the column of each field said."""

    @abstractmethod
    def parse(self, text: str, locations: list[dict], kept: list[Visit], mapping: dict | None, options: dict) -> dict: ...

    @abstractmethod
    def export(self, visits: list[Visit]) -> str: ...

    @abstractmethod
    def columns(self, text: str) -> dict:
        """What suggest_mapping says of a CSV, and the fields of a visit: {"columns", "rows", "mapping"…, "fields"}."""

    @abstractmethod
    def normalized(self, visit: Visit) -> Visit:
        """A visit as a record of a visit has it."""


class Uploads(ABC):
    """Where the deployments of the visits were uploaded."""

    @abstractmethod
    def trapper_state(self, project: str, deployment_id: str | None) -> tuple[str | None, bool]: ...

    @abstractmethod
    def uploads_of(self, project: str, deployment_id: str) -> list[dict]: ...

    @abstractmethod
    def upload_states(self, project: str, imported: str | None, deployment_id: str) -> list[dict]: ...


class VisitReports(ABC):
    @abstractmethod
    def import_report(self, project: str, result: dict, saved: int) -> str | None: ...


class VisitSettings(ABC):
    @abstractmethod
    def keep_seconds(self) -> bool: ...

    @abstractmethod
    def time_source(self) -> str: ...


class Clock(ABC):
    @abstractmethod
    def today(self) -> str: ...
