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
    def unknown(self, project: str) -> list[Visit]:
        """The visits known only to have been made — a revision before the ones kept."""

    @abstractmethod
    def kept_count(self, project: str) -> int:
        """How many records of visits the research project keeps — those removed too: what a backup takes."""

    @abstractmethod
    def replace_all(self, project: str, visits: list[Visit]) -> None:
        """Keeps these visits, as `visits` tells them, as all of the research project's — a backup restored: each keeps its id and its dates."""

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

    @abstractmethod
    def has_deployment(self, project: str, deployment_id: str) -> bool:
        """Whether a deployment is of a visit of the research project: linked to one already, or one the visits say."""


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
    def kept_count(self, project: str) -> int: ...

    @abstractmethod
    def replace_all(self, project: str, visits: list[Visit]) -> None: ...

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

    @abstractmethod
    def write_states(self, project: str, states: dict[tuple[str, str], str | None]) -> int:
        """Keeps the state of the visits — by their site (ignoring case) and their instant — where it changed; says how many."""


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
    """The folders of the collections the visits give deployments to — what the deployments say a collection is."""

    @abstractmethod
    def make_collection(self, project: str, collection: str) -> None:
        """Its folder, with its collection.json."""


class VisitFile(ABC):
    """A file of visits as text — any CSV —, and its cells and records as the app checks them. What a row can't be is a RowError
    (domain.visit_file), with the code of what is wrong."""

    @abstractmethod
    def table(self, text: str) -> list[list[str]]:
        """Its rows, the first its header. VisitsCsvError when it is empty."""

    @abstractmethod
    def write(self, rows: list[list[str]]) -> str:
        """Rows as the text of a file a spreadsheet reads with its accents."""

    @abstractmethod
    def cells(self, row: dict[str, str]) -> dict:
        """What the cells of a row (keyed by the fields they give) say of a visit, each read as its field takes it — only what the row says."""

    @abstractmethod
    def record(self, visit: dict) -> Visit:
        """A visit as a record of a visit has it."""

    @abstractmethod
    def location(self, fields: dict) -> dict:
        """A location a row creates (domain.visit_file.location_fields), as the catalog takes one."""

    @abstractmethod
    def normalized(self, visit: Visit) -> Visit:
        """A visit as a record of a visit has it — what it refuses raised as it is."""


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
