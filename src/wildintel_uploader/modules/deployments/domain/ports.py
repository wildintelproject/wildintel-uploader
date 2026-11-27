"""The ports of the deployments: the contract (DeploymentsService), and what its use cases are given — the memory cards, the collections folder,
the scan of a folder, the previous revisions, the photos, the copy of a folder as it is, and the contracts of the visits and of the preprocessing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.statistics import KeptDeployment
from wildintel_uploader.modules.postvalidation.domain.statistics import DeploymentTimes
from typing import Any, Protocol

Deployment = Any   # the record of a deployment of Camtrap DP (shared.camtrap.DeploymentFields)


class CollectionLayout(ABC):
    """How a collection holds its deployments, for what brings images into one (the preprocessing): what it refuses is DeploymentsFailed."""

    @abstractmethod
    def check_paths(self, source: Path, dest: Path) -> None:
        """The images can go from source to dest."""

    @abstractmethod
    def is_pending(self, dest: Path) -> bool:
        """Whether dest holds a deployment preprocessed and not consolidated yet — one that may be done again."""

    @abstractmethod
    def check_not_kept(self, dest: Path) -> None:
        """No deployment is kept there already."""

    @abstractmethod
    def is_synced(self, dest: Path) -> bool:
        """Whether it came from TRAPPER: then it can't be changed here."""

    @abstractmethod
    def shortfall(self, folder: Path, needed: int, what: str, where: str) -> str | None:
        """Why `needed` bytes don't fit in `folder`, or None."""

    @abstractmethod
    def write_collection_metadata(self, collection: Path, name: str | None) -> None: ...

    @abstractmethod
    def image_entry(self, name: str, local_time: str | None, source: str, extra: dict) -> dict: ...

    @abstractmethod
    def write_images_file(self, folder: Path, deployment_id: str, images: list[dict], source: str = "local") -> None: ...

    @abstractmethod
    def write_deployment_metadata(self, dest: Path, deployment: dict) -> None: ...

    @abstractmethod
    def seal(self, source: Path, dest: Path, deployment: Deployment, **details) -> bool:
        """Checks the source images and seals the deployment kept in dest; whether it was sealed."""


class DeploymentsService(ABC):

    @abstractmethod
    def layout(self) -> CollectionLayout:
        """How a collection holds its deployments."""

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
    def imported_images(self, project: str, exclude_deployment: str | None = None) -> dict[str, list[dict]]:
        """The images already imported into a research project, by the SHA-1 of the original: {"deployment_id", "collection", "original"}."""

    @abstractmethod
    def log_entry(self, project: str, deployment_id: str) -> dict: ...

    @abstractmethod
    def seal_status(self, project: str, deployment_id: str) -> dict: ...

    @abstractmethod
    def previous(self, project: str, deployment_ids: list[str]) -> dict[str, dict | None]: ...

    @abstractmethod
    def next_revision(self, project: str, location_id: str) -> dict: ...

    @abstractmethod
    def previous_revisions(self, project: str, deployment_id: str) -> list[dict]:
        """The previous revisions of the location of a deployment, oldest first: {"revision", "deployment_id", "image_count", "times"} — the
        times when its images were taken, in seconds, sorted."""

    # importing one
    @abstractmethod
    def import_local(self, source_dir: str, collection_dir: str, collection_name: str | None, deployment: Deployment, preprocessing: dict | None,
                     consolidate: bool = True) -> Iterator[dict]:
        """Brings the images of a folder into a local collection — prepared by the preprocessing as `preprocessing` says (with the timezone of
        the location kept), or copied as they are —, sealed when `consolidate`. Refused before any image is touched when the deployment is of no
        visit of its research project."""

    @abstractmethod
    def consolidate(self, source_dir: str, collection_dir: str, deployment: Deployment) -> Iterator[dict]: ...

    @abstractmethod
    def organize(self, research_project_id: str, source_dir: str, deployment: Deployment) -> tuple[Path, Iterator[dict]]:
        """The images of a folder copied, as they are, to the folder of the deployment in its collection — the default one of the research
        project —, with its metadata: where they go, and the events of the copy. DeploymentsFailed, before anything is copied, on bad paths."""

    # checking and repairing those kept, and the statistics of a revision
    @abstractmethod
    def repair_collections(self, project: str) -> list[dict]: ...

    @abstractmethod
    def inspect(self, project: str, collection: str, deployment_id: str) -> dict: ...

    @abstractmethod
    def repair(self, project: str, collection: str, deployment_id: str) -> Iterator[dict]: ...

    @abstractmethod
    def revision_statistics(self, project: str, collection: str) -> list[dict]: ...

    @abstractmethod
    def compare(self, project: str, first: str, second: str) -> dict:
        """Two deployments side by side — the same location in two revisions: {"first", "second", "metrics"}."""

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

class RevisionFolders(ABC):
    """The deployments kept in the collections of the research projects, as their statistics read them."""

    @abstractmethod
    def kept(self, project: str) -> list[KeptDeployment]:
        """Every deployment kept in a collection of the research project (R0001, R0002_winter…)."""

    @abstractmethod
    def in_collection(self, project: str, collection: str) -> list[KeptDeployment] | None:
        """The deployments of a collection, or None when it isn't there."""

    @abstractmethod
    def times(self, where: object) -> DeploymentTimes:
        """When each image of a deployment was taken: from the images.json kept beside them, else from their EXIF."""

    @abstractmethod
    def cached_metrics(self, where: object, gap_seconds: float) -> dict | None:
        """The metrics kept beside a deployment, while its images.json and the gap are the same."""

    @abstractmethod
    def keep_metrics(self, where: object, gap_seconds: float, metrics: dict) -> None: ...

    @abstractmethod
    def details(self, where: object) -> dict | None:
        """What its deployment.json keeps."""


class StatisticsSettings(ABC):
    """POSTVALIDATION: what a sequence is and what is similar."""

    @abstractmethod
    def gap_seconds(self) -> float: ...

    @abstractmethod
    def min_revisions(self) -> int: ...

    @abstractmethod
    def method(self) -> str: ...

    @abstractmethod
    def tolerances(self) -> dict[str, float]: ...


class MemoryCard(ABC):
    """A camera's memory card, as it is copied — only read — and ejected."""

    @abstractmethod
    def files(self, card: str) -> tuple[Path, list[tuple[Path, int]]]:
        """The card's folder and each of its files, by its path inside the card, with its size. A CardCopyError (domain.cards) when the card
        is not a folder or can't be read."""

    @abstractmethod
    def eject(self, card: str) -> dict:
        """Ejects the removable drive the card is on, so it can be taken out: {"ejected", "message"} — never a folder of a fixed disk. It never
        raises: when it cannot, it says why."""


class CardCopies(ABC):
    """The folder the copies of the cards are made in, each in a folder of its own (its holder)."""

    @abstractmethod
    def base(self) -> Path:
        """The folder of the copies, resolved."""

    @abstractmethod
    def resolve(self, path: str) -> Path:
        """A path as the system has it — its user folder and its links followed."""

    @abstractmethod
    def holders(self) -> list[tuple[Path, float]]:
        """The holders kept, with when each was last modified."""

    @abstractmethod
    def shortfall(self, needed: int) -> str | None:
        """Why `needed` bytes do not fit in the folder of the copies — None when they do, or when it can't be told."""

    @abstractmethod
    def new_holder(self) -> Path: ...

    @abstractmethod
    def copy(self, card: Path, file: Path, to: Path) -> None:
        """The card's file `file` copied to `to`/`file`. A CardCopyError when it can't be."""

    @abstractmethod
    def remove(self, holder: Path) -> bool:
        """Removes a holder; whether it was there. What can't be removed is left, and said in the log."""


class Folders(ABC):
    """The collections folder as the rest of the app keeps it."""

    @abstractmethod
    def root(self) -> Path: ...

    @abstractmethod
    def project_of(self, collection_dir: str) -> str | None:
        """The research project a collection is of, when it is in the collections folder — None when it is elsewhere."""

    @abstractmethod
    def check_collection(self, folder: Path) -> dict: ...

    @abstractmethod
    def local_deployments(self, folder: Path) -> list[dict]: ...

    @abstractmethod
    def imported(self, project: str, exclude_deployment: str | None) -> dict[str, list[dict]]: ...

    @abstractmethod
    def seal_status(self, folder: Path) -> dict: ...

    @abstractmethod
    def location_time(self, project_dir: Path, location_id: str | None) -> dict:
        """The timezone and the summer-time setting of a location kept in the research project of that folder."""


class Photos(ABC):
    """The photos of a deployment kept, to look at them. DeploymentMissing when the deployment, or the photo, is not there."""

    @abstractmethod
    def list(self, project: str, collection: str, deployment_id: str) -> list[dict]: ...

    @abstractmethod
    def jpeg(self, project: str, collection: str, deployment_id: str, name: str, large: bool) -> bytes: ...


class PhotoFolder(ABC):
    """The folder of a deployment in the collections folder, as its photos are looked at. DeploymentMissing when it is not there."""

    @abstractmethod
    def names(self, project: str, collection: str, deployment_id: str) -> list[str]:
        """The names of the files in it."""

    @abstractmethod
    def taken(self, project: str, collection: str, deployment_id: str) -> dict[str, str | None]:
        """When each image was taken, as images.json says — nothing when it can't."""

    @abstractmethod
    def jpeg(self, project: str, collection: str, deployment_id: str, name: str, size: int) -> bytes:
        """A file of the folder as a JPEG that fits in size × size; DeploymentMissing when it is not one of its files, or can't be shown."""


class SealedFolder(ABC):
    """A deployment's folder as its seal reads it: its images, their hashes, its deployment.json and its seal.json."""

    @abstractmethod
    def images(self, folder: Path) -> list[str]:
        """Its images, by their paths in it, in natural file-name order."""

    @abstractmethod
    def hashes(self, folder: Path, names: list[str]) -> list[str]:
        """The SHA-256 of each, in that order."""

    @abstractmethod
    def metadata_hash(self, folder: Path) -> str | None:
        """The SHA-256 of its deployment.json, or None when it has none."""

    @abstractmethod
    def read_seal(self, folder: Path) -> dict | None:
        """Its seal.json, or None when it has none. ValueError when it can't be read."""

    @abstractmethod
    def write_seal(self, folder: Path, seal: dict) -> None: ...


class CheckSettings(ABC):
    """The sections of the settings that say which checks run, and how: VALIDATION and POSTVALIDATION, as settings.toml keeps them."""

    @abstractmethod
    def validation(self) -> Any: ...

    @abstractmethod
    def postvalidation(self) -> Any: ...


class RepairFolder(ABC):
    """The collections folder as a repair reads and writes it. What the research project, a collection or a deployment can't be is a RepairError
    (domain.repair)."""

    @abstractmethod
    def collections(self, project: str) -> list[tuple[str, Path]]: ...

    @abstractmethod
    def collection(self, project: str, collection: str) -> Path: ...

    @abstractmethod
    def folders(self, collection_dir: Path) -> list[Path]: ...

    @abstractmethod
    def images(self, folder: Path) -> list[Path]: ...

    @abstractmethod
    def file_state(self, folder: Path, name: str) -> str:
        """"ok", "missing" or "unreadable"."""

    @abstractmethod
    def read_json(self, folder: Path, name: str) -> object: ...

    @abstractmethod
    def synced(self, folder: Path) -> bool: ...

    @abstractmethod
    def log_row(self, collection_dir: Path, deployment_id: str) -> tuple[dict | None, str | None]:
        """The deployment's row in the collection's timestamp log, and what is wrong with the log if it can't be read."""

    @abstractmethod
    def has_log(self, collection_dir: Path) -> bool: ...

    @abstractmethod
    def taken(self, images: list[Path]) -> dict[Path, Any]:
        """When each image was taken, as its EXIF says (None when it doesn't)."""

    @abstractmethod
    def cameras(self, images: list[Path]) -> dict[Path, Any]:
        """The camera of each image that says it: its model and its id."""

    @abstractmethod
    def modified(self, path: Path) -> Any: ...

    @abstractmethod
    def size(self, path: Path) -> int: ...

    @abstractmethod
    def dimensions(self, path: Path) -> tuple[int | None, int | None]: ...

    @abstractmethod
    def sha1s(self, images: list[Path]) -> list[str]: ...

    @abstractmethod
    def xmp(self, images: list[Path]) -> dict[Path, dict]:
        """What the XMP of each image says — {"identifier": bool, "source_hash"} — when ExifTool is there; empty when it isn't."""

    @abstractmethod
    def as_deployment(self, record: dict) -> Deployment:
        """Raises ValueError, saying what is wrong, when it is not a valid deployment."""

    @abstractmethod
    def record_of(self, deployment: Deployment) -> dict:
        """A valid deployment as deployment.json keeps it."""

    @abstractmethod
    def write_deployment(self, folder: Path, record: dict) -> None: ...

    @abstractmethod
    def write_preprocessing(self, folder: Path, log: dict) -> None: ...

    @abstractmethod
    def write_images(self, folder: Path, deployment_id: str, images: list[tuple[str, str, dict]]) -> None:
        """images.json: (name, the camera's wall clock, extras) of each."""


class ImportFolder(ABC):
    """The folders of images on this computer, and the collections folder, as an import reads and writes them."""

    @abstractmethod
    def root(self) -> Path:
        """The collections folder."""

    @abstractmethod
    def is_dir(self, folder: Path) -> bool: ...

    @abstractmethod
    def files(self, folder: Path) -> list[Path]:
        """Every file under the folder."""

    @abstractmethod
    def subfolders(self, folder: Path) -> list[Path]:
        """The folders in it that are not hidden, by their names ignoring case."""

    @abstractmethod
    def loose(self, folder: Path) -> list[str]:
        """The names of the files in it that are not hidden."""

    @abstractmethod
    def resolve(self, path: Path) -> Path:
        """A DeploymentImportError when it can't be resolved."""

    @abstractmethod
    def has_content(self, folder: Path) -> bool:
        """Whether it is a folder with something in it; False when it can't be told."""

    @abstractmethod
    def has(self, folder: Path, name: str) -> bool: ...

    @abstractmethod
    def synced(self, folder: Path) -> bool:
        """Whether the deployment kept there came from TRAPPER."""

    @abstractmethod
    def timestamp_rows(self, log: Path) -> list[dict]:
        """The rows of a timestamp log — none when there is none. A StorageError when it can't be read as one."""

    @abstractmethod
    def fieldwork_rows(self, collection: Path) -> list[dict]:
        """The rows of the collection's fieldwork log — none when there is none. A StorageError when it can't be read as one."""

    @abstractmethod
    def copy(self, file: Path, to: Path) -> None: ...

    @abstractmethod
    def size(self, path: Path) -> int: ...

    @abstractmethod
    def dimensions(self, path: Path) -> tuple[int | None, int | None]:
        """Its width and height, (None, None) when it can't be opened as an image."""

    @abstractmethod
    def write_collection(self, collection: Path, name: str | None) -> None: ...

    @abstractmethod
    def write_deployment(self, folder: Path, deployment: Deployment) -> None:
        """deployment.json, as a deployment is kept."""

    @abstractmethod
    def write_images(self, folder: Path, deployment_id: str, images: list[tuple[str, str | None, dict]]) -> None:
        """images.json: (name, the camera's wall clock, extras) of each."""


class SessionFolder(ABC):
    """Where the sessions of the import wizard are kept, by task id — one the app makes (domain.sessions)."""

    @abstractmethod
    def read(self, task_id: str) -> dict | None:
        """Its manifest, or None when there is none or it can't be read."""

    @abstractmethod
    def write(self, task_id: str, manifest: dict) -> None: ...

    @abstractmethod
    def remove(self, task_id: str) -> None: ...

    @abstractmethod
    def names(self) -> list[str]:
        """The names of what is kept — sessions or not."""

    @abstractmethod
    def move_old(self) -> None:
        """Moves the sessions kept where they used to be to where they are kept now — those not there already."""


class DeploymentSealer(Protocol):
    """What the adapters of the deployments ask of the seal (application.seal.Sealing): whether a deployment kept is still what it says."""

    def verify(self, dest: Path) -> dict:
        """{"status": "none" | "valid" | "broken", "changed", "missing", "added", "deployment_changed", "seal_changed"}."""


class CollectionImporter(Protocol):
    """What the adapters of the deployments ask of an import (application.imports.Importing): the paths a folder of images can be brought
    through, what is kept already, and the seal of what was brought."""

    def check_paths(self, source: Path, dest: Path) -> None: ...

    def is_pending(self, dest: Path) -> bool: ...

    def check_not_kept(self, dest: Path) -> None: ...

    def seal(self, source: Path, dest: Path, deployment: Deployment, **details) -> bool: ...

