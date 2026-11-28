"""The contract of the reports (ReportsService), what it refuses, and its ports: where they are kept, the images of a folder and when they were
taken, and an image of a report made small to be shown."""
from __future__ import annotations

import builtins

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Protocol


class ReportMissing(Exception):
    """A report, or an image of it, that is not there."""


class BadFormat(Exception):
    """A report can be had as json or csv."""


class ReportsService(ABC):
    @abstractmethod
    def list(self) -> builtins.list[dict]:
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

    @abstractmethod
    def delete_older_than(self, days: int) -> int:
        """Deletes the reports older than `days` days, and says how many."""

    # what the other modules keep: the report of what each of them did — its id
    @abstractmethod
    def save_validation(self, found: dict, folder: Path, checks: Iterable[str] | None) -> str: ...

    @abstractmethod
    def save_postvalidation(self, result: dict, deployment_id: str, folder: Path, parameters: dict | None) -> str: ...

    @abstractmethod
    def save_preprocessing(self, records: builtins.list[dict], skipped: builtins.list[dict], deployment_id: str, source: Path, dest: Path, options: dict) -> str: ...

    @abstractmethod
    def save_visits_import(self, project: str, result: dict, saved: int) -> str: ...

    @abstractmethod
    def save_upload(self, collection: str, project: str, items: builtins.list[dict], started_at: str, finished_at: str) -> str: ...

    @abstractmethod
    def save_repair(self, deployment_id: str, dest: Path, files: builtins.list[tuple[str, bool, str]], seal: dict | None,
                    preprocessing: dict[str, dict[str, str]]) -> str: ...


class KeptReports(ABC):
    """Where the reports are kept, by their ids."""

    @abstractmethod
    def keep(self, report: dict, kind: str, name: str) -> str:
        """Keeps a report under a new id — its date, its kind and its name — and says it."""

    @abstractmethod
    def read(self, report_id: str) -> dict:
        """Raises ReportMissing when there is no such report."""

    @abstractmethod
    def all(self) -> builtins.list[dict]:
        """Every report kept, newest first."""

    @abstractmethod
    def delete(self, report_id: str) -> None: ...


class FolderImages(ABC):
    @abstractmethod
    def images(self, folder: Path) -> builtins.list[str]:
        """The images of a folder, as their paths in it, in natural file-name order."""

    @abstractmethod
    def small(self, folder: Path, relative: str, size: int) -> bytes:
        """An image of the folder as a JPEG that fits in size × size. Raises ReportMissing when it is not in the folder or can't be shown."""


class ImageDates(Protocol):
    def dates(self, paths: builtins.list[Path]) -> dict[Path, datetime | None]:
        """When each image says it was taken (modules.fileinfo)."""
        ...
