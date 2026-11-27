"""DeploymentFolders over how a collection holds its deployments (the contract of the deployments) — and where a deployment is prepared:
<collection>/.staging/<deployment id>, moved to its place in one rename. What the deployments refuse is the preprocessing's error, with its words."""
from __future__ import annotations

import json
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from wildintel_uploader.modules.deployments.domain.models import DeploymentsError
from wildintel_uploader.modules.deployments.domain.ports import CollectionLayout
from wildintel_uploader.modules.deployments.domain.seal import SEAL_FILE
from wildintel_uploader.modules.preprocessing.domain.models import PREPROCESSING_LOG_FILE, STAGING_DIR, DeploymentLike, ImageWork, PreprocessingError
from wildintel_uploader.modules.preprocessing.domain.ports import DeploymentFolders, Reports
from wildintel_uploader.modules.preprocessing.infrastructure.images import dimensions
from wildintel_uploader.modules.reports.domain.ports import ReportsService

T = TypeVar("T")
# On Windows a file that is open for a moment (the antivirus, the indexer, a viewer, ExifTool finishing) keeps a folder from being renamed: it is
# tried again.
PUBLISH_TRIES = 20
PUBLISH_WAIT = 0.5


def _as_ours(call: Callable[[], T]) -> T:
    """What the deployments refuse, as the preprocessing's error."""
    try:
        return call()
    except DeploymentsError as exc:
        raise PreprocessingError(str(exc)) from exc


def staging_dir(collection: Path, deployment_id: str) -> Path:
    """The folder where the deployment of `collection` is prepared until it is saved."""
    return collection / STAGING_DIR / deployment_id


def _hide(path: Path) -> None:
    """Marks a folder as hidden on Windows, where a name that starts with a dot does not hide it. Best effort: nothing depends on it."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x2)  # type: ignore[attr-defined]  # FILE_ATTRIBUTE_HIDDEN
    except Exception:  # noqa: BLE001
        pass


def publish(work: Path, dest: Path) -> None:
    """Moves a prepared deployment from its staging folder to its place in the collection, in one rename.

    Raises:
        PreprocessingError: the deployment's folder could not be moved — after trying again for a few seconds, as an open file may be the cause.
    """
    if dest.is_dir() and not any(dest.iterdir()):
        dest.rmdir()  # an empty folder in the way: Windows refuses to replace it, and nothing is lost
    last: OSError | None = None
    for _ in range(PUBLISH_TRIES):
        try:
            os.replace(work, dest)  # not rename: on Windows that fails when the destination exists
            last = None
            break
        except PermissionError as exc:  # Windows: something has a file of the folder open — it usually lets go in a moment
            last = exc
            time.sleep(PUBLISH_WAIT)
        except OSError as exc:
            raise PreprocessingError(f"Could not move {work.name} into its collection: {exc}") from exc
    if last is not None:
        raise PreprocessingError(f"Could not move {work.name} into its collection — a file in it is in use by another program: {last}") from last
    try:
        work.parent.rmdir()  # .staging, when nothing else is being prepared
    except OSError:
        pass


def _as_dict(deployment: DeploymentLike) -> dict:
    return deployment.model_dump() if hasattr(deployment, "model_dump") else dict(vars(deployment))  # type: ignore[attr-defined]


class CollectionFolders(DeploymentFolders):
    """Over how a collection holds its deployments — the contract of the deployments (CollectionLayout), given when it is needed —, with the
    .staging folder the preprocessing prepares a deployment in."""

    def __init__(self, layout: Callable[[], CollectionLayout]) -> None:
        self._layout = layout

    def check_paths(self, source: Path, dest: Path) -> None:
        _as_ours(lambda: self._layout().check_paths(source, dest))

    def clear_left_pending(self, dest: Path) -> None:
        layout = self._layout()
        if layout.is_pending(dest) and not layout.is_synced(dest):
            shutil.rmtree(dest)   # preprocessed by a version that did it in the collection, and never consolidated: nothing froze it

    def check_not_kept(self, dest: Path) -> None:
        _as_ours(lambda: self._layout().check_not_kept(dest))

    def is_synced(self, dest: Path) -> bool:
        return self._layout().is_synced(dest)

    def shortfall(self, folder: Path, needed: int, what: str) -> str | None:
        return self._layout().shortfall(folder, needed, what, "the folder they are prepared in")

    def staging(self, collection: Path, deployment_id: str) -> Path:
        return staging_dir(collection, deployment_id)

    def clear_staging(self, work: Path) -> None:
        if work.exists():
            shutil.rmtree(work)

    def start_staging(self, work: Path) -> None:
        work.mkdir(parents=True, exist_ok=True)
        _hide(work.parent)

    def copy_as_it_is(self, source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    def write_collection_metadata(self, collection: Path, name: str | None) -> None:
        self._layout().write_collection_metadata(collection, name)

    def write_images_file(self, work: Path, deployment_id: str, works: list[ImageWork]) -> None:
        """Each image: its name and when it was taken (the camera's wall clock) and, as extras, its original name, the instant and its epoch
        seconds, the camera and its serial number, the file's size and pixels and its hashes."""
        layout = self._layout()

        def entry(record: dict) -> dict:
            target: Path = record["_target"]
            width, height = dimensions(target)
            return layout.image_entry(record["name"], record["_local"].isoformat(), "local", {
                "original": record["original"], "taken_at": record["date"], "timestamp": record["_date"].timestamp(),
                "date_source": record["date_source"], "camera": record["camera"], "camera_id": record.get("camera_id"), "width": width,
                "height": height, "size_bytes": target.stat().st_size, "resized": record["resized"], "sha1": record["final_hash"],
                "source_sha1": record["source_hash"],
            })
        layout.write_images_file(work, deployment_id, [entry(w.record) for w in works])

    def files(self, folder: Path) -> list[Path]:
        return [p for p in folder.rglob("*") if p.is_file()]

    def size_of(self, files: list[Path]) -> int:
        return sum(p.stat().st_size for p in files)

    def write_log(self, folder: Path, log: dict) -> None:
        (folder / PREPROCESSING_LOG_FILE).write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    def read_log(self, folder: Path) -> dict | None:
        path = folder / PREPROCESSING_LOG_FILE
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise PreprocessingError(f"Could not read {path}: {exc}") from exc

    def is_sealed(self, dest: Path) -> bool:
        return (dest / SEAL_FILE).exists()

    def publish(self, work: Path, dest: Path) -> None:
        publish(work, dest)

    def write_deployment_metadata(self, dest: Path, deployment: DeploymentLike) -> None:
        self._layout().write_deployment_metadata(dest, _as_dict(deployment))

    def seal(self, source: Path, dest: Path, deployment: DeploymentLike, *, originals: dict[str, str], source_hashes: dict[str, str],
             preprocessing: dict) -> bool:
        return self._layout().seal(source, dest, deployment, originals=originals, source_hashes=source_hashes, preprocessing=preprocessing)


class SavedReports(Reports):
    """Through the contract of the reports."""

    def __init__(self, reports: ReportsService) -> None:
        self._reports = reports

    def preprocessing(self, records: list[dict], skipped: list[dict], deployment_id: str, source: Path, dest: Path, options: dict) -> str | None:
        return self._reports.save_preprocessing(records, skipped, deployment_id, source, dest, options)
