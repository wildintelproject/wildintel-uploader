"""The deployments kept in the collections folder as their statistics read them: their folders, when their images were taken — from the
images.json kept beside them, whether the deployment was imported here or synced from TRAPPER, else from the EXIF of the images (modules.fileinfo)
—, their metrics kept in statistics.json beside them, and their deployment.json."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from wildintel_uploader.modules.deployments.domain import statistics as rules
from wildintel_uploader.modules.deployments.domain.naming import DEPLOYMENT_METADATA_FILE, IMAGES_FILE
from wildintel_uploader.modules.deployments.domain.ports import RevisionFolders, StatisticsSettings
from wildintel_uploader.modules.deployments.domain.statistics import KeptDeployment
from wildintel_uploader.modules.fileinfo.domain.models import IMAGE_EXTENSIONS
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.postvalidation.domain.statistics import DeploymentTimes
from wildintel_uploader.modules.settings.domain.ports import StoredSettings

logger = logging.getLogger(__name__)

STATS_FILE = "statistics.json"
_CACHE_VERSION = 4


def _timestamp(iso: str) -> float | None:
    try:
        parsed = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    # only the gaps between one deployment's images matter, so a naive time can stand as UTC
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp()


def _deployments(collection: Path) -> list[KeptDeployment]:
    out = []
    for folder in sorted(collection.iterdir()):
        found = rules.revision_of(folder.name)
        if folder.is_dir() and found:
            out.append(KeptDeployment(found[0], folder.name, found[1], folder))
    return out


class RevisionFoldersOnDisk(RevisionFolders):
    """`root` says the collections folder, asked each time; `files` what is known of the images."""

    def __init__(self, root: Callable[[], Path], files: Callable[[], FileInfoService]) -> None:
        self._root, self._files = root, files

    def _collections(self, project: str) -> list[Path]:
        folder = self._root() / project
        return [c for c in sorted(folder.iterdir()) if c.is_dir() and rules.is_collection(c.name)] if folder.is_dir() else []

    def kept(self, project: str) -> list[KeptDeployment]:
        return [d for collection in self._collections(project) for d in _deployments(collection)]

    def in_collection(self, project: str, collection: str) -> list[KeptDeployment] | None:
        folder = self._root() / project / collection
        return _deployments(folder) if folder.is_dir() else None

    def times_of_folder(self, folder: Path) -> DeploymentTimes:
        """The images of a folder and when each was taken, from their EXIF."""
        images = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]
        stamps = [taken.replace(tzinfo=timezone.utc).timestamp() for taken in self._files().dates(images).values() if taken is not None]
        return DeploymentTimes(len(images), sorted(stamps))

    def times(self, where: object) -> DeploymentTimes:
        path = Path(where)
        log = path / IMAGES_FILE
        if log.is_file():
            try:
                images = json.loads(log.read_text(encoding="utf-8")).get("images", [])
                stamps = [t for t in (_timestamp(i.get("local_time") or "") for i in images) if t is not None]
                return DeploymentTimes(len(images), sorted(stamps))
            except (json.JSONDecodeError, OSError, AttributeError) as exc:
                logger.warning("Could not read %s (%s) — reading the images instead.", log, exc)
        return self.times_of_folder(path)

    @staticmethod
    def _fingerprint(path: Path, gap_seconds: float) -> dict | None:
        log = path / IMAGES_FILE
        if not log.is_file():
            return None   # a folder that is still changing: not kept
        stat = log.stat()
        return {"version": _CACHE_VERSION, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "gap_seconds": gap_seconds}

    def cached_metrics(self, where: object, gap_seconds: float) -> dict | None:
        path = Path(where)
        fingerprint, cache = self._fingerprint(path, gap_seconds), path / STATS_FILE
        if fingerprint and cache.is_file():
            try:
                kept = json.loads(cache.read_text(encoding="utf-8"))
                if kept.get("fingerprint") == fingerprint:
                    return kept["metrics"]
            except (OSError, json.JSONDecodeError, AttributeError, KeyError):
                pass
        return None

    def keep_metrics(self, where: object, gap_seconds: float, metrics: dict) -> None:
        path = Path(where)
        fingerprint = self._fingerprint(path, gap_seconds)
        if fingerprint:
            try:
                (path / STATS_FILE).write_text(json.dumps({"fingerprint": fingerprint, "metrics": metrics}, indent=2), encoding="utf-8")
            except OSError as exc:   # a read-only folder just means no cache
                logger.warning("Could not keep %s (%s).", path / STATS_FILE, exc)

    def details(self, where: object) -> dict | None:
        try:
            details = json.loads((Path(where) / DEPLOYMENT_METADATA_FILE).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return details if isinstance(details, dict) else None


class StatisticsInUse(StatisticsSettings):
    def __init__(self, settings: StoredSettings) -> None:
        self._settings = settings

    def _post(self):
        return self._settings.load_settings().POSTVALIDATION

    def gap_seconds(self) -> float:
        return self._post().sequence_gap_seconds

    def min_revisions(self) -> int:
        return self._post().min_revisions

    def method(self) -> str:
        return self._post().similarity_method

    def tolerances(self) -> dict[str, float]:
        post = self._post()
        return {"image_count": post.image_count_tolerance, "sequence_count": post.sequence_count_tolerance, "sequence_length": post.sequence_length_tolerance}
