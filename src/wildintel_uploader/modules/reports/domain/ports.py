"""The contract of the reports (ReportsService), what it refuses, and the port to where they are kept."""
from __future__ import annotations

from abc import ABC, abstractmethod


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
