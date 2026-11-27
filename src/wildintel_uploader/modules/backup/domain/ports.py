"""The contract of the backups (BackupService), what it refuses, and what its use cases are given: the backups as files."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path


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


class Backups(ABC):
    """The backups as zip files beside the collections folder."""

    @abstractmethod
    def describe(self, project: str) -> dict: ...

    @abstractmethod
    def create(self, dest_dir: Path, project: str | None, choice: Choice) -> Iterator[dict]: ...

    @abstractmethod
    def staging_dir(self) -> Path:
        """Where the backups to be downloaded are made; those older than a day are removed."""

    @abstractmethod
    def is_download_name(self, name: str) -> bool: ...

    @abstractmethod
    def read(self, path: Path) -> dict: ...

    @abstractmethod
    def restore(self, path: Path, choice: Choice, replace: bool) -> Iterator[dict]: ...
