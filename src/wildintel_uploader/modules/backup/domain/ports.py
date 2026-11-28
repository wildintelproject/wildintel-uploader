"""The contract of the backups (BackupService), what it refuses, and what its use cases are given: the records of a research project, its folders,
the archives, and the settings of the app."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Generator, Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


class BackupError(Exception):
    """What can't be backed up or restored at all: nothing chosen, a folder or a file that is not there, a file that is not a backup…"""


class BackupGone(BackupError):
    """A backup made to be downloaded that is not there (any more)."""


@dataclass(frozen=True)
class Choice:
    """What is put in a backup, or taken from one."""
    settings: bool = False
    project_files: bool = False
    visits: bool = False
    deployments: list[str] = field(default_factory=list)
    images: bool = False


class BackupService(ABC):

    @abstractmethod
    def describe(self, project: str) -> dict:
        """What a research project has that can be put in a backup."""

    @abstractmethod
    def create(self, dest_dir: Path | None, project: str | None, choice: Choice) -> Iterator[dict]:
        """Makes a backup — in a folder, or, with none, to be downloaded (its last event then says which file: "download"). Steps, files, and
        {"type": "done", "path", "bytes", "manifest"}. BackupError, before anything is written, when it can't be made at all."""

    @abstractmethod
    def download(self, name: str) -> Path:
        """A backup made to be downloaded. BackupGone when it is not one, or not there any more."""

    @abstractmethod
    def read(self, path: Path) -> dict:
        """What a backup holds, and what of it is already here."""

    @abstractmethod
    def restore(self, path: Path, choice: Choice, replace: bool) -> Iterator[dict]:
        """Restores what is chosen of a backup: steps, files, and {"type": "done", "summary"}. BackupError, before anything is touched."""


class ProjectRecords(Protocol):
    """What a research project keeps as records — the catalog and the visits through their contracts, and the history of the states —, as the
    records are kept and with the ids of this computer."""

    def checkpoint(self, project: str) -> Callable[[], None]:
        """What is kept of a research project now — its records, history and visits — and the people, and how to put it back exactly as it was."""

    def require_project(self, project: str) -> None:
        """Raises BackupError when the research project is not kept."""
        ...

    def has_project(self, project: str) -> bool: ...
    def project_record(self, project: str) -> dict | None: ...
    def put_project_record(self, record: dict) -> None: ...
    def how_many(self, project: str, kind: str) -> int:
        """How many locations, cameras or SD cards ("locations", "cameras", "sd_cards") a research project keeps — those not removed."""
    def location_records(self, project: str) -> list[dict]: ...
    def put_location_records(self, project: str, records: list[dict]) -> None: ...
    def equipment_records(self, project: str, kind: str) -> list[dict]: ...
    def put_equipment_records(self, project: str, kind: str, records: list[dict]) -> None: ...
    def roles(self, project: str, include_deleted: bool = False) -> list[dict]: ...
    def keep_roles(self, project: str, roles: list[dict]) -> None: ...
    def trappers(self) -> list[dict]: ...
    def keep_trappers(self, trappers: list[dict]) -> None: ...
    def status_history(self, project: str) -> list[dict]: ...
    def keep_status_history(self, project: str, lines: list[dict]) -> None: ...
    def visits(self, project: str) -> list[dict]: ...
    def kept_visits(self, project: str) -> int: ...
    def replace_visits(self, project: str, visits: list[dict]) -> None: ...


@dataclass(frozen=True)
class FileOnDisk:
    name: str          # its path in the folder it is of, with "/"
    path: Path
    size: int


class ProjectFolders(ABC):
    """The folder of a research project in the collections folder: its collections and their deployments. Every method raises BackupError when the
    research project is not one."""

    @abstractmethod
    def check_project(self, project: str) -> None:
        """Raises BackupError when it is not the name of a research project."""

    @abstractmethod
    def collections(self, project: str) -> list[str]:
        """The folders of the research project, newest name first."""

    @abstractmethod
    def deployments(self, project: str, collection: str) -> list[str]:
        """The deployments of a collection — not .staging, where one is prepared."""

    @abstractmethod
    def deployment_files(self, project: str, collection: str, deployment: str) -> list[FileOnDisk] | None:
        """Every file of a deployment, or None when it is not there."""

    @abstractmethod
    def collection_files(self, project: str, collection: str) -> list[FileOnDisk]:
        """The files of a collection itself — its collection.json and its logs."""

    @abstractmethod
    def holds(self, project: str, relative: str) -> bool:
        """Whether a folder of the research project is there and holds something, or a file of it is there."""

    @abstractmethod
    def make_project(self, project: str) -> None: ...

    @abstractmethod
    def check_inside(self, project: str, relatives: list[str]) -> None:
        """Raises BackupError when any of them would be written out of the research project — none is written then."""

    @abstractmethod
    def write(self, project: str, relative: str, data: bytes) -> None:
        """Writes a file of the research project, whole or not at all."""

    @abstractmethod
    def remove(self, project: str, relative: str) -> None:
        """Removes a file of the research project — one a restoration wrote, when it is undone —, and the folders it leaves empty."""


class BackupArchive(AbstractContextManager, ABC):
    @abstractmethod
    def names(self) -> set[str]: ...

    @abstractmethod
    def read(self, name: str) -> bytes: ...


@dataclass(frozen=True)
class Entry:
    """A file of an archive being made: written from a file on disk, or from data."""
    name: str
    path: Path | None = None
    data: object = None


class Archives(ABC):
    @abstractmethod
    def check_destination(self, dest_dir: Path) -> None:
        """Raises BackupError when the folder is not there."""

    @abstractmethod
    def open(self, path: Path) -> BackupArchive:
        """Raises BackupError when the file is not there, is not an archive, or has a file whose path goes out of it."""

    @abstractmethod
    def make(self, dest_dir: Path, name: str, manifest: dict, entries: list[Entry]) -> Generator[dict, None, tuple[Path, int]]:
        """Writes the archive — its manifest first —, whole or not at all: an event for each file — {"type": "file", "index", "total", "name"} —;
        it returns its path and how many bytes it is."""

    @abstractmethod
    def staging_dir(self) -> Path:
        """Where the backups to be downloaded are made; those older than a day are removed."""

    @abstractmethod
    def is_there(self, path: Path) -> bool:
        """Whether a backup made is still there."""


class AppSettings(ABC):
    @abstractmethod
    def as_data(self) -> dict:
        """The settings of the app, section by section, as data."""

    @abstractmethod
    def secrets(self) -> list[tuple[str, str]]:
        """The secret settings — (section, field) —: never in a backup, and those here are kept when its settings are restored."""

    @abstractmethod
    def save(self, data: dict) -> None:
        """Raises BackupError when this version does not accept them."""
