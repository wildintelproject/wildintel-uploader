"""The ports of the uploaders: the contract (UploadersService), and what its use cases are given — TRAPPER, the research projects and the
collections kept, where an upload that failed is written down, and the reports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wildintel_uploader.modules.uploaders.domain.models import Account, Credentials, UploaderError

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
    def register(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int | None, deployment: Deployment, timezone: str,
                 ignore_dst: bool) -> None:
        """Registers a deployment in TRAPPER — its errors as the module's."""

    @abstractmethod
    def collection_names(self, credentials: Credentials, research_project_pk: int, classification_project_pk: int) -> list[dict]: ...

    @abstractmethod
    def sync(self, credentials: Credentials, project: dict, classification_project_pk: int, collections: list[str], deployments: list[str] | None,
             download_images: bool) -> Iterator[dict]: ...

    @abstractmethod
    def failure(self, exc: Exception) -> UploaderError:
        """An error of TRAPPER, of the network or of what is asked of it, as the module's."""

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


# ── what an upload is given ──

class TrapperSite(ABC):
    """TRAPPER's API for one account, as an upload asks it: what a research project has, what is created there, the uploader the packages go up
    through — a different door from the API's — and the processing of a package. What TRAPPER refuses passes through as it is; the uploader's
    refusal of an account is an UploaderError saying who refused it and what it answered."""

    @abstractmethod
    def research_projects(self, credentials: Credentials) -> list[dict]: ...

    @abstractmethod
    def classification_projects(self, credentials: Credentials, research_project_pk: int) -> list[dict]: ...

    @abstractmethod
    def locations(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        """pk, location_id, timezone, ignore_dst, owner and can_manage (None when TRAPPER can't say)."""

    @abstractmethod
    def deployments(self, credentials: Credentials, research_project_pk: int) -> list[dict]:
        """pk and deployment_id."""

    @abstractmethod
    def create_location(self, credentials: Credentials, research_project_pk: int, deployment: Deployment, timezone: str, ignore_dst: bool) -> None:
        """From the deployment's own coordinates and name."""

    @abstractmethod
    def create_deployment(self, credentials: Credentials, research_project_pk: int, deployment: Deployment, timezone: str, ignore_dst: bool,
                          location_id: str) -> None:
        """From its details, in the location named as TRAPPER has it."""

    @abstractmethod
    def log_in_to_uploader(self, credentials: Credentials) -> None: ...

    @abstractmethod
    def upload_file(self, credentials: Credentials, path: Path, report: Callable[[dict], None]) -> None:
        """Sends a file through the uploader — blocking —, reporting {"type": "upload_progress", "file", "bytes", "total"} as it goes."""

    @abstractmethod
    def process(self, credentials: Credentials, yaml_name: str, zip_name: str, remove_zip: bool) -> None:
        """Asks TRAPPER to process a package uploaded into a collection."""

    @abstractmethod
    def collection(self, credentials: Credentials, research_project_pk: int, name: str) -> dict | None:
        """The collection of the research project with that name — its pk —, or None."""


class KeptDeployment(ABC):
    """A deployment kept in its collection's folder, as an upload reads it and marks it."""

    @abstractmethod
    def metadata(self, deployment_dir: Path) -> object:
        """Its deployment.json, or None."""

    @abstractmethod
    def preprocessing(self, deployment_dir: Path) -> object:
        """What its preprocessing recorded (preprocessing.json), or None."""

    @abstractmethod
    def as_deployment(self, metadata: dict) -> Deployment: ...

    @abstractmethod
    def missing(self, deployment_dir: Path, names: list[str]) -> list[str]: ...

    @abstractmethod
    def sizes(self, deployment_dir: Path, names: list[str]) -> list[int]: ...

    @abstractmethod
    def mark_uploaded(self, deployment_dir: Path, record: dict) -> None:
        """Writes down where and when it was uploaded (upload.json)."""


@dataclass(frozen=True)
class PackagePart:
    """One zip and its yaml: the images of a deployment, as `named` in TRAPPER, in `collection`."""
    base: str
    collection: str
    project_id: int
    timezone: str
    ignore_dst: bool
    named: str
    deployment_dir: Path
    entries: list[dict]


@dataclass(frozen=True)
class Package:
    yaml: Path
    zip: Path
    files: int


class Packages(ABC):
    """The packages of an upload, and the deployments csv of a collection, in a folder."""

    @abstractmethod
    def build(self, output_dir: Path, parts: list[PackagePart], progress: Callable[[int, int], None]) -> list[Package]:
        """Writes each part — its yaml, its zip of <collection>/<named>/<file> —; `progress(done, total)` as each image goes in."""

    @abstractmethod
    def size(self, paths: list[Path]) -> int: ...

    @abstractmethod
    def file_sizes(self, paths: list[Path]) -> dict[str, int]: ...

    @abstractmethod
    def upsert_csv(self, path: Path, row: dict) -> dict:
        """Puts a deployment's row in the csv — the others stay, sorted; its own is replaced —: {"path", "action", "rows"}."""

    @abstractmethod
    def remove_from_csv(self, path: Path, deployment_id: str) -> None:
        """Takes a deployment's row out; the file goes when it has no row left."""

    @abstractmethod
    def remove(self, packages: list[Package], output_dir: Path) -> None:
        """The packages, and their folder when nothing else is left in it."""


class UploadPlaces(ABC):
    @abstractmethod
    def packages_dir(self, project: str) -> Path:
        """Where the packages of a research project are made."""

    @abstractmethod
    def max_zip_bytes(self) -> int: ...
