"""The ports of the deployments: the contract (DeploymentsService), and what its use cases are given — the memory cards, the collections folder,
the scan of a folder, the previous revisions, the photos, the copy of a folder as it is, and the contracts of the visits and of the preprocessing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

Deployment = Any   # the record of a deployment of Camtrap DP (shared.camtrap.DeploymentFields)


class DeploymentsService(ABC):

    # the memory card
    @abstractmethod
    def copy_card(self, path: str) -> Iterator[dict]:
        """Copies a camera's memory card, read only, to a temporary folder: "start", "progress" after each file, "done" with its `path`."""

    @abstractmethod
    def eject_card(self, path: str) -> dict: ...

    @abstractmethod
    def discard_card_copy(self, path: str) -> bool: ...

    # a folder of images
    @abstractmethod
    def scan_folder(self, folder: Path) -> dict:
        """What a folder holds — and, behind the answer, its images' metadata start being read."""

    @abstractmethod
    def guess_details(self, folder: Path) -> dict: ...

    @abstractmethod
    def scan_session(self, folder: Path) -> dict: ...

    # the collections
    @abstractmethod
    def check_collection(self, folder: Path) -> dict: ...

    @abstractmethod
    def collection_path(self, project: str, deployment_id: str) -> dict: ...

    @abstractmethod
    def existing(self, project: str, deployment_ids: list[str]) -> dict[str, str | None]: ...

    @abstractmethod
    def local_deployments(self, folder: Path) -> list[dict]: ...

    @abstractmethod
    def log_entry(self, project: str, deployment_id: str) -> dict: ...

    @abstractmethod
    def seal_status(self, project: str, deployment_id: str) -> dict: ...

    @abstractmethod
    def previous(self, project: str, deployment_ids: list[str]) -> dict[str, dict | None]: ...

    @abstractmethod
    def next_revision(self, project: str, location_id: str) -> dict: ...

    # importing one
    @abstractmethod
    def import_local(self, source_dir: str, collection_dir: str, collection_name: str | None, deployment: Deployment, preprocessing: dict | None,
                     consolidate: bool = True) -> Iterator[dict]:
        """Brings the images of a folder into a local collection — prepared by the preprocessing as `preprocessing` says (with the timezone of
        the location kept), or copied as they are —, sealed when `consolidate`. Refused before any image is touched when the deployment is of no
        visit of its research project."""

    @abstractmethod
    def consolidate(self, source_dir: str, collection_dir: str, deployment: Deployment) -> Iterator[dict]: ...

    # checking and repairing those kept, and the statistics of a revision
    @abstractmethod
    def repair_collections(self, project: str) -> list[dict]: ...

    @abstractmethod
    def inspect(self, project: str, collection: str, deployment_id: str) -> dict: ...

    @abstractmethod
    def repair(self, project: str, collection: str, deployment_id: str) -> Iterator[dict]: ...

    @abstractmethod
    def revision_statistics(self, project: str, collection: str) -> list[dict]: ...

    # the sessions of the wizard
    @abstractmethod
    def sessions(self) -> "ImportSessions":
        """The unfinished runs of the wizard, kept step by step."""

    # its photos
    @abstractmethod
    def photos(self, project: str, collection: str, deployment_id: str) -> list[dict]: ...

    @abstractmethod
    def photo(self, project: str, collection: str, deployment_id: str, name: str, large: bool = False) -> bytes: ...


# ── out ──

class ImportSessions(ABC):
    """The runs of the wizard that imports a deployment, kept step by step so that an unfinished one can be resumed."""

    @abstractmethod
    def list(self) -> list[dict]: ...

    @abstractmethod
    def save_scan(self, task_id: str | None, source_dir: str, scan: dict) -> dict:
        """DeploymentsFailed: not a task id."""

    @abstractmethod
    def save_selection(self, task_id: str, selection: dict) -> dict:
        """DeploymentMissing: no such session."""

    @abstractmethod
    def save_details(self, task_id: str, deployment: dict) -> dict:
        """DeploymentMissing: no such session."""

    @abstractmethod
    def discard(self, task_id: str) -> None: ...

class Repairs(ABC):
    """Checking and repairing the deployments kept: their metadata files written again from what their folders hold."""

    @abstractmethod
    def collections(self, project: str) -> list[dict]: ...

    @abstractmethod
    def inspect(self, project: str, collection: str, deployment_id: str) -> dict:
        """DeploymentMissing when it isn't there."""

    @abstractmethod
    def repair(self, project: str, collection: str, deployment_id: str) -> Iterator[dict]:
        """DeploymentsFailed, before anything is touched, when it isn't there or was synced from TRAPPER."""


class CollectionStatistics(ABC):
    @abstractmethod
    def revision(self, project: str, collection: str) -> list[dict]:
        """One row per deployment of the revision against the previous revisions of its location, as the settings of the postvalidation say.
        DeploymentMissing when the collection isn't there."""

class Cards(ABC):
    @abstractmethod
    def copy(self, path: str) -> Iterator[dict]: ...

    @abstractmethod
    def eject(self, path: str) -> dict: ...

    @abstractmethod
    def discard(self, path: str) -> bool: ...


class Folders(ABC):
    """A folder of images, and the collections folder as the rest of the app keeps it."""

    @abstractmethod
    def root(self) -> Path: ...

    @abstractmethod
    def scan(self, folder: Path) -> dict: ...

    @abstractmethod
    def read_ahead(self, folder: Path) -> None:
        """Starts reading the metadata of the images of a folder, in the background."""

    @abstractmethod
    def guess(self, folder: Path) -> dict: ...

    @abstractmethod
    def scan_session(self, folder: Path) -> dict: ...

    @abstractmethod
    def check_collection(self, folder: Path) -> dict: ...

    @abstractmethod
    def default_collection(self, project: str, deployment_id: str) -> Path: ...

    @abstractmethod
    def kept(self, project: str, deployment_id: str) -> Path | None: ...

    @abstractmethod
    def local_deployments(self, folder: Path) -> list[dict]: ...

    @abstractmethod
    def log_entry(self, project: str, deployment_id: str) -> dict: ...

    @abstractmethod
    def seal_status(self, folder: Path) -> dict: ...

    @abstractmethod
    def location_time(self, project_dir: Path, location_id: str | None) -> dict:
        """The timezone and the summer-time setting of a location kept in the research project of that folder."""

    @abstractmethod
    def copy_as_it_is(self, source_dir: str, collection_dir: str, collection_name: str | None, deployment: Deployment) -> Iterator[dict]: ...


class Revisions(ABC):
    @abstractmethod
    def previous(self, project: str, deployment_id: str) -> dict | None: ...

    @abstractmethod
    def next(self, project: str, location_id: str) -> dict: ...


class Photos(ABC):
    @abstractmethod
    def list(self, project: str, collection: str, deployment_id: str) -> list[dict]: ...

    @abstractmethod
    def jpeg(self, project: str, collection: str, deployment_id: str, name: str, large: bool) -> bytes: ...
