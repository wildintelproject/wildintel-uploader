"""The ports of the sources: the contract the rest of the app asks them through (SourcesService), a source of visits as a contract (VisitSource),
and what the use cases are given — Epicollect5 and the settings of the sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from wildintel_uploader.modules.sources.domain.models import VISIT_COLUMNS
from wildintel_uploader.modules.sources.domain.settings import Epicollect5Settings


@dataclass(frozen=True)
class VisitRows:
    """What a source gives of the visits, and how it is read:

    - `csv` — the text of a CSV with a row per visit, whose header is `columns`: the columns a visit has, named as a visit names them — so the
      reader of the file maps each to itself, and needs to know nothing of the source;
    - `time_source` — where the time of a visit comes from: what the source has to say (`"created_at"` for the CSV downloaded from the form,
      which has no date nor time to read: only when its entry was created), or None when the source has both and the settings choose
      (FIELDLOG.time_source — the entries of the API);
    - `from_form` — whether it comes from the form of the field flow (a New site then makes its location, with the coordinates of the visit)."""
    csv: str
    time_source: str | None = None
    from_form: bool = True
    columns: tuple[str, ...] = VISIT_COLUMNS


class VisitSource(ABC):
    """A source of visits: its key — what the pages ask it by: "epicollect-api", "epicollect-csv" —, its label, and the visits it gives."""
    key: ClassVar[str]
    label: ClassVar[str]

    @abstractmethod
    def visits(self, text: str | None, epicollect: "Epicollect5", settings: Epicollect5Settings) -> VisitRows:
        """The visits of the source — of `text`, a file the user gave, for those that read one. SourceError when it can't give them."""


class Epicollect5(ABC):
    """Epicollect5, through its API: a public project needs no client; a private one, its client id and secret."""

    @abstractmethod
    def project(self, slug: str, client_id: str | None, client_secret: str | None) -> dict[str, Any]:
        """The definition of the project, as Epicollect5 exports it. SourceError when it can't be read."""

    @abstractmethod
    def entries(self, slug: str, client_id: str | None, client_secret: str | None) -> list[dict[str, Any]]:
        """Every entry of the project. SourceError when they can't be read."""

    @abstractmethod
    def forget_tokens(self) -> None: ...


class SourceSettings(ABC):
    @abstractmethod
    def epicollect5(self) -> Epicollect5Settings:
        """The settings of Epicollect5 in use."""


class SourcesVisits(ABC):
    """Where the visits come from: the sources there are, the visits of one, and whether a CSV is the download of the form of a visit."""

    @abstractmethod
    def sources(self) -> list[VisitSource]:
        """The sources of visits there are."""

    @abstractmethod
    def visits(self, key: str, text: str | None = None, settings: Epicollect5Settings | None = None) -> VisitRows:
        """The visits of the source of this key. SourceError: no such source, or it can't give them."""

    @abstractmethod
    def form_columns(self, text: str) -> dict[str, str]:
        """The columns of a CSV that answer the questions of the form of a visit — empty if it is not the form."""

    @abstractmethod
    def form_error(self, text: str) -> str | None:
        """Why a CSV can't be read as the download of the form of a visit, or None."""


class SourcesDeployments(ABC):
    """The entries of the Epicollect5 project that say the details of a deployment."""

    @abstractmethod
    def deployment_entries(self, location_ids: list[str], revision: int | None, settings: Epicollect5Settings | None = None) -> dict[str, list[dict]]:
        """The entries of the project that say the details of a deployment of these locations (and revision), newest first, by location in lower
        case: {"uuid", "title", "created_at", "fields"}."""

    @abstractmethod
    def location_entries(self, location_id: str, revision: int | None, settings: Epicollect5Settings | None = None) -> list[dict]:
        """The entries of one location (and revision), newest first. SourceError when no location is chosen."""


class SourcesProject(ABC):
    """The Epicollect5 project of the settings: its form, whether it can be read, and forgetting the tokens of its API."""

    @abstractmethod
    def project_form(self, settings: Epicollect5Settings | None = None) -> dict:
        """The inputs of the Epicollect5 project saved in the settings: {"project": {name, slug}, "inputs": [...]}."""

    @abstractmethod
    def test_connection(self, slug: str | None, client_id: str | None, client_secret: str | None, settings: Epicollect5Settings | None = None) -> dict:
        """Whether a project can be read with these values, saving nothing — a blank secret next to the saved client id is the saved one."""

    @abstractmethod
    def forget_tokens(self) -> None: ...


class SourcesService(SourcesVisits, SourcesDeployments, SourcesProject, ABC):
    """All that the module of the sources offers. Whoever needs only a part asks for that one: SourcesVisits (the module of the visits),
    SourcesDeployments or SourcesProject."""


