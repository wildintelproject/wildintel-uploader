"""The ports of the uploaders: the contract (UploadersService), and what its use cases are given — TRAPPER, the research projects and the
collections kept, where an upload that failed is written down, and the reports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from wildintel_uploader.modules.uploaders.domain.models import Account, Credentials

Deployment = Any   # the record of a deployment of Camtrap DP (shared.camtrap.DeploymentFields)


class UploadersService(ABC):

    # the account and what TRAPPER has
    @abstractmethod
    def account_defaults(self) -> dict: ...

    @abstractmethod
    def test_connection(self, account: Account) -> dict:
        """Checks the account, and keeps it in the settings once it works."""

    @abstractmethod
    def research_projects(self, account: Account) -> list[dict]: ...

    @abstractmethod
    def classification_projects(self, account: Account, research_project_pk: int) -> list[dict]: ...

    @abstractmethod
    def locations(self, account: Account, research_project_pk: int) -> list[dict]: ...

    @abstractmethod
    def deployments(self, account: Account, research_project_pk: int) -> list[dict]: ...

    # importing a deployment into TRAPPER from the wizard
    @abstractmethod
    def import_deployment(self, account: Account, research_project_pk: int, classification_project_pk: int | None, source_dir: str, deployment: Deployment,
                          research_project_id: str | None, register: bool, timezone: str | None = None) -> Iterator[dict]:
        """The images in the timezone of the location kept — or in `timezone`, when it is given (the command line asks it)."""

    # uploading the deployments kept
    @abstractmethod
    def collections(self, project: str) -> list[dict]: ...

    @abstractmethod
    def project_classification_projects(self, account: Account, project: str) -> list[dict]: ...

    @abstractmethod
    def check_selection(self, account: Account, project: str, collection: str | None) -> list[dict]: ...

    @abstractmethod
    def check_access(self, account: Account, project: str, collection: str | None, deployment_ids: list[str],
                     classification_project_pk: int | None) -> list[dict]: ...

    @abstractmethod
    def upload(self, account: Account, project: str, collection: str, deployment_id: str, mode: str, classification_project_pk: int | None,
               delete_files: bool) -> Iterator[dict]: ...

    @abstractmethod
    def upload_report(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> str | None: ...

    # where the deployments kept were uploaded
    @abstractmethod
    def trapper_state(self, project: str, deployment_id: str | None) -> tuple[str | None, bool]:
        """When the deployment was uploaded to TRAPPER, and whether it is there — uploaded from here, or synced from there."""

    @abstractmethod
    def uploads_of(self, project: str, deployment_id: str) -> list[dict]:
        """One upload for each platform it was sent to: "uploaded" with the day and what it did, or "synced"."""

    @abstractmethod
    def upload_states(self, project: str, imported: str | None, deployment_id: str) -> list[dict]:
        """The upload to each uploader in use: planned, done or failed."""

    # bringing back what TRAPPER has
    @abstractmethod
    def collection_names(self, account: Account, research_project_pk: int, classification_project_pk: int) -> list[dict]: ...

    @abstractmethod
    def sync(self, account: Account, project: dict, classification_project_pk: int, collections: list[str], deployments: list[str] | None,
             download_images: bool) -> Iterator[dict]: ...


# ── out ──

class Trapper(ABC):
    """TRAPPER, through its client; what it refuses is an UploaderError of the kind it is (see the module's errors)."""

    @abstractmethod
    def credentials(self, account: Account) -> Credentials:
        """The account, completed from the settings; UploaderError naming what is still missing."""

    @abstractmethod
    def defaults(self) -> dict: ...

    @abstractmethod
    def keep_account(self, credentials: Credentials) -> None: ...

    @abstractmethod
    def ask(self, what: str, credentials: Credentials, *args: Any) -> Any:
        """One question to TRAPPER — test_connection, list_research_projects, list_classification_projects, list_locations, list_deployments —
        its errors as the module's."""

    @abstractmethod
    def find_research_project(self, credentials: Credentials, record: dict) -> int: ...

    @abstractmethod
    def check_selection(self, credentials: Credentials, record: dict, collection: str | None, describe: Callable[[Exception], str]) -> list[dict]: ...

    @abstractmethod
    def check_access(self, credentials: Credentials, record: dict, location_ids: list[str], classification_project_pk: int | None,
                     describe: Callable[[Exception], str]) -> list[dict]: ...

    @abstractmethod
    def upload(self, credentials: Credentials | None, record: dict, collection_dir: Path, deployment_id: str, mode: str, classification_project_pk: int | None,
               delete_files: bool) -> Iterator[dict]: ...

    @abstractmethod
    def import_deployment(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int | None, source_dir: str, deployment: Deployment,
                          timezone: str | None, research_project_id: str | None, ignore_dst: bool, register: bool) -> Iterator[dict]: ...

    @abstractmethod
    def collection_names(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int) -> list[dict]: ...

    @abstractmethod
    def sync(self, credentials: Credentials, project: dict, classification_project_pk: int, collections: list[str], deployments: list[str] | None,
             download_images: bool) -> Iterator[dict]: ...

    @abstractmethod
    def describe(self, exc: Exception) -> str:
        """What an error of TRAPPER is, told: its own words for what the uploaders refuse, else what its kind says."""


class KeptCollections(ABC):
    """The research projects and the collections kept in the collections folder."""

    @abstractmethod
    def project(self, project: str) -> dict | None: ...

    @abstractmethod
    def collection_dir(self, project: str, collection: str) -> Path: ...

    @abstractmethod
    def collections(self, project: str) -> list[dict]: ...

    @abstractmethod
    def location_of(self, collection_dir: Path, deployment_id: str) -> str | None: ...

    @abstractmethod
    def location_time(self, project: str, location_id: str | None) -> dict: ...

    @abstractmethod
    def check_project_dir(self, project: str) -> None: ...

    @abstractmethod
    def note_failure(self, project: str, deployment_id: str, destination: str, note: str | None) -> None:
        """Writes down how the upload of a deployment went: a failure, with why, or that it worked (None)."""


class DeploymentUploads(ABC):
    @abstractmethod
    def trapper_state(self, project: str, deployment_id: str | None) -> tuple[str | None, bool]: ...

    @abstractmethod
    def uploads_of(self, project: str, deployment_id: str) -> list[dict]: ...

    @abstractmethod
    def upload_states(self, project: str, imported: str | None, deployment_id: str) -> list[dict]: ...


class UploadReports(ABC):
    @abstractmethod
    def upload(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> str | None: ...
