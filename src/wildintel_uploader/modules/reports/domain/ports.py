"""The contract of the reports (ReportsService), what it refuses, and the port to where they are kept."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path


class ReportMissing(Exception):
    """A report, or an image of it, that is not there."""


class BadFormat(Exception):
    """A report can be had as json or csv."""


class ReportsService(ABC):
    @abstractmethod
    def list(self) -> list[dict]:
        """What each report says of itself, newest first."""

    @abstractmethod
    def read(self, report_id: str) -> dict: ...

    @abstractmethod
    def as_file(self, report_id: str, fmt: str) -> tuple[str, str]:
        """The report as a file — its own JSON, or a CSV with a row per image and check —: (body, media type)."""

    @abstractmethod
    def image(self, report_id: str, path: str, large: bool = False) -> bytes: ...

    @abstractmethod
    def delete(self, report_id: str) -> None: ...

    # what the other modules keep: the report of what each of them did — its id
    @abstractmethod
    def save_validation(self, found: dict, folder: Path, checks: Iterable[str] | None) -> str: ...

    @abstractmethod
    def save_postvalidation(self, result: dict, deployment_id: str, folder: Path, parameters: dict | None) -> str: ...

    @abstractmethod
    def save_preprocessing(self, records: list[dict], skipped: list[dict], deployment_id: str, source: Path, dest: Path, options: dict) -> str: ...

    @abstractmethod
    def save_visits_import(self, project: str, result: dict, saved: int) -> str: ...

    @abstractmethod
    def save_upload(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> str: ...

    @abstractmethod
    def save_repair(self, deployment_id: str, dest: Path, files: list[tuple[str, bool, str]], seal: dict | None,
                    preprocessing: dict[str, dict[str, str]]) -> str: ...


class KeptReports(ABC):
    @abstractmethod
    def list(self) -> list[dict]: ...

    @abstractmethod
    def read(self, report_id: str) -> dict: ...

    @abstractmethod
    def csv(self, report: dict) -> str: ...

    @abstractmethod
    def image(self, report_id: str, path: str, large: bool) -> bytes: ...

    @abstractmethod
    def delete(self, report_id: str) -> None: ...

    @abstractmethod
    def save(self, kind: str, *args, **kwargs) -> str:
        """Builds the report of a kind (validation, postvalidation, preprocessing, visits, upload) from what was done, and keeps it: its id."""
