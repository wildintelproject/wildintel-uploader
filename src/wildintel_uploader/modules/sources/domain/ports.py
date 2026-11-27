"""The ports of the sources: the contract the rest of the app asks them through (SourcesService), a source of visits as a contract (VisitSource),
and what the use cases are given — Epicollect5 and the settings of the sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from wildintel_uploader.modules.sources.domain.settings import Epicollect5Settings


@dataclass(frozen=True)
class VisitRows:
    """What a source gives of the visits: the text of a CSV with a row per visit and the columns a visit has (VISIT_COLUMNS), and how it is read —
    `time_source` when the source says when a visit happened (the form has no date: when its entry was created), and whether it comes from the
    form of the field flow (a New site then makes its location, with the coordinates of the visit)."""
    csv: str
    time_source: str | None = None
    from_form: bool = True


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


class SourcesService(ABC):

    @abstractmethod
    def sources(self) -> list[VisitSource]:
        """The sources of visits there are."""

    @abstractmethod
    def visits(self, key: str, text: str | None = None, settings: Epicollect5Settings | None = None) -> VisitRows:
        """The visits of the source of this key. SourceError: no such source, or it can't give them."""

    @abstractmethod
    def project_form(self, settings: Epicollect5Settings | None = None) -> dict:
        """The inputs of the Epicollect5 project saved in the settings: {"project": {name, slug}, "inputs": [...]}."""

    @abstractmethod
    def test_connection(self, slug: str | None, client_id: str | None, client_secret: str | None, settings: Epicollect5Settings | None = None) -> dict:
        """Whether a project can be read with these values, saving nothing — a blank secret next to the saved client id is the saved one."""

    @abstractmethod
    def deployment_entries(self, location_ids: list[str], revision: int | None, settings: Epicollect5Settings | None = None) -> dict[str, list[dict]]:
        """The entries of the project that say the details of a deployment of these locations (and revision), newest first, by location in lower
        case: {"uuid", "title", "created_at", "fields"}."""

    @abstractmethod
    def location_entries(self, location_id: str, revision: int | None, settings: Epicollect5Settings | None = None) -> list[dict]:
        """The entries of one location (and revision), newest first. SourceError when no location is chosen."""

    @abstractmethod
    def form_columns(self, text: str) -> dict[str, str]:
        """The columns of a CSV that answer the questions of the form of a visit — empty if it is not the form."""

    @abstractmethod
    def form_error(self, text: str) -> str | None:
        """Why a CSV can't be read as the download of the form of a visit, or None."""

    @abstractmethod
    def forget_tokens(self) -> None: ...
