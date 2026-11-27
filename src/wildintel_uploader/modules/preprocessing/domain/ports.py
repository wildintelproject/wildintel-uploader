"""The contract of the preprocessing (PreprocessingService), and what its use cases are given: what is known of the files (the contract of
modules.fileinfo), the folders of the collections — where a deployment is prepared, saved and sealed —, and the reports."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path

from wildintel_uploader.modules.preprocessing.domain.models import DeploymentLike, PreprocessOptions


class PreprocessingService(ABC):

    @abstractmethod
    def preprocess(self, source_dir: Path, collection_dir: Path, collection_name: str | None, deployment: DeploymentLike, options: PreprocessOptions,
                   consolidate: bool = True) -> Iterator[dict]:
        """Imports the images of source_dir preprocessed as `options` say, prepared in collection_dir/.staging/<deployment id> and — with
        consolidate — moved to collection_dir/<deployment id> and sealed there; without it, left pending in .staging. What can't be done is said
        before anything is written (PreprocessingError). Events: {"type": "copy", index, total, name} per file, {"type": "skipped", name, detail}
        for one that couldn't be processed (the rest go on), {"type": "metadata", index, total} as the XMP is written, {"type": "sealing"} and
        {"type": "done", dest_dir, processed, skipped, sealed, report_id, resize?}."""

    @abstractmethod
    def consolidate(self, source_dir: Path, collection_dir: Path, deployment: DeploymentLike) -> Iterator[dict]:
        """Saves a preprocessed (pending) deployment: moves it to its place in the collection and seals it. Events: {"type": "sealing"} and
        {"type": "done", dest_dir, processed, skipped, sealed}. PreprocessingError: not preprocessed, already sealed or synced, its place taken."""


class DeploymentFolders(ABC):
    """The folders of the collections, as the rest of the app keeps them."""

    @abstractmethod
    def check_paths(self, source: Path, dest: Path) -> None:
        """PreprocessingError when the images can't go from source to dest."""

    @abstractmethod
    def clear_left_pending(self, dest: Path) -> None:
        """Removes a deployment a version before left preprocessed in the collection itself and never consolidated: it is done again."""

    @abstractmethod
    def check_not_kept(self, dest: Path) -> None:
        """PreprocessingError when a deployment is already kept there."""

    @abstractmethod
    def is_synced(self, dest: Path) -> bool:
        """Whether it came from TRAPPER: then it can't be changed here."""

    @abstractmethod
    def shortfall(self, folder: Path, needed: int, what: str) -> str | None:
        """Why there isn't room for `needed` bytes in `folder`, or None."""

    @abstractmethod
    def staging(self, collection: Path, deployment_id: str) -> Path:
        """Where a deployment of the collection is prepared: <collection>/.staging/<deployment id>."""

    @abstractmethod
    def clear_staging(self, work: Path) -> None:
        """Removes what a run before left in the folder a deployment is prepared in — prepared and not saved, or interrupted: it is done again."""

    @abstractmethod
    def start_staging(self, work: Path) -> None:
        """Makes the folder a deployment is prepared in, and .staging hidden where a name with a dot is not."""

    @abstractmethod
    def copy_as_it_is(self, source: Path, target: Path) -> None:
        """A file that is not an image goes across as it is."""

    @abstractmethod
    def write_collection_metadata(self, collection: Path, name: str | None) -> None: ...

    @abstractmethod
    def write_images_file(self, work: Path, deployment_id: str, works: list) -> None:
        """images.json of the deployment: each image prepared, its name, when it was taken and what else is known of it."""

    @abstractmethod
    def publish(self, work: Path, dest: Path) -> None:
        """Moves a prepared deployment to its place in the collection, in one rename. PreprocessingError when it can't."""

    @abstractmethod
    def write_deployment_metadata(self, dest: Path, deployment: DeploymentLike) -> None: ...

    @abstractmethod
    def seal(self, source: Path, dest: Path, deployment: DeploymentLike, *, originals: dict[str, str], source_hashes: dict[str, str],
             preprocessing: dict) -> bool:
        """Seals a deployment in its place: from then on the app notices any change to it. Whether it was sealed."""


class Reports(ABC):
    @abstractmethod
    def preprocessing(self, records: list[dict], skipped: list[dict], deployment_id: str, source: Path, dest: Path, options: dict) -> str | None:
        """Saves the report of a preprocessing; its id."""
