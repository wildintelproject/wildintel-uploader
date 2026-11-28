"""The collections folder as a repair reads and writes it: the collections and their deployments, their metadata files, the collection's old
timestamp log, what the images say (their dates and cameras through modules.fileinfo, their size, their SHA-1, their XMP through ExifTool), and
deployment.json, preprocessing.json and images.json written as the deployments keep them."""
from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from wildintel_uploader.modules.deployments.domain import repair as rules
from wildintel_uploader.modules.deployments.domain.ports import Deployment, RepairFolder
from wildintel_uploader.modules.deployments.infrastructure import collections as layout
from wildintel_uploader.modules.deployments.infrastructure.sealed_folder import images_of
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoMetadata
from wildintel_uploader.modules.preprocessing.domain.models import PREPROCESSING_LOG_FILE
from wildintel_uploader.shared import parallel

_XMP_BATCH = 200


def sha1(path: Path) -> str:
    digest = hashlib.sha1()  # noqa: S324 — an identifier, not a security measure; what wildintel-tools used
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class RepairFolderOnDisk(RepairFolder):
    """`root` says the collections folder, asked each time; `files` what is known of the images."""

    def __init__(self, root: Callable[[], Path], files: Callable[[], FileInfoMetadata]) -> None:
        self._root, self._files = root, files

    def _project(self, project: str) -> Path:
        try:
            return layout.project_dir(self._root(), project)
        except layout.LocalFolderError as exc:
            raise rules.RepairError(str(exc)) from exc

    def collections(self, project: str) -> list[tuple[str, Path]]:
        folder = self._project(project)
        return [(c.name, c) for c in sorted(folder.iterdir()) if c.is_dir()] if folder.is_dir() else []

    def collection(self, project: str, collection: str) -> Path:
        folder = self._project(project) / collection
        if not folder.is_dir():
            raise rules.RepairError(f"The collection {collection} isn't in {project}.")
        return folder

    def folders(self, collection_dir: Path) -> list[Path]:
        return [f for f in sorted(collection_dir.iterdir()) if f.is_dir()] if collection_dir.is_dir() else []

    def images(self, folder: Path) -> list[Path]:
        return images_of(folder)

    def file_state(self, folder: Path, name: str) -> str:
        path = folder / name
        return "missing" if not path.is_file() else ("ok" if self.read_json(folder, name) is not None else "unreadable")

    def read_json(self, folder: Path, name: str) -> object:
        try:
            return json.loads((folder / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def synced(self, folder: Path) -> bool:
        return layout.is_synced(folder)

    def log_row(self, collection_dir: Path, deployment_id: str) -> tuple[dict | None, str | None]:
        try:
            rows = layout.read_timestamp_log(layout.timestamp_log_path(collection_dir))
        except layout.LocalFolderError as exc:
            return None, str(exc)
        return next((r for r in rows if r["Deployment"].upper() == deployment_id.upper()), None), None

    def has_log(self, collection_dir: Path) -> bool:
        return layout.timestamp_log_path(collection_dir).is_file()

    def taken(self, images: list[Path]) -> dict[Path, Any]:
        return self._files().dates(images)

    def cameras(self, images: list[Path]) -> dict[Path, Any]:
        return self._files().cameras(images)[0]

    def modified(self, path: Path) -> datetime:
        return datetime.fromtimestamp(path.stat().st_mtime).replace(microsecond=0)

    def size(self, path: Path) -> int:
        return path.stat().st_size

    def dimensions(self, path: Path) -> tuple[int | None, int | None]:
        try:
            from PIL import Image
            with Image.open(path) as img:
                return img.width, img.height
        except Exception:
            return None, None

    def sha1s(self, images: list[Path]) -> list[str]:
        return parallel.pmap(sha1, images)

    def xmp(self, images: list[Path]) -> dict[Path, dict]:
        exiftool = self._files().exiftool_path()
        if not exiftool or not images:
            return {}
        found: dict[Path, dict] = {}
        for start in range(0, len(images), _XMP_BATCH):
            batch = images[start:start + _XMP_BATCH]
            try:
                completed = subprocess.run([exiftool, "-json", "-XMP-dc:Identifier", "-XMP-dc:Source", *map(str, batch)], capture_output=True, text=True,
                                           encoding="utf-8", check=False)
                rows = json.loads(completed.stdout or "[]")
            except (OSError, json.JSONDecodeError):
                return {}
            for path, row in zip(batch, rows):
                source = str(row.get("Source") or "")
                found[path] = {"identifier": bool(row.get("Identifier")),
                               "source_hash": source.removeprefix("WildINTEL:") if source.startswith("WildINTEL:") else None}
        return found

    def as_deployment(self, record: dict) -> Deployment:
        from pydantic import ValidationError

        from wildintel_uploader.shared.camtrap import DeploymentFields
        try:
            return DeploymentFields.model_validate(record)
        except ValidationError as exc:
            raise ValueError("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())) from exc

    def record_of(self, deployment: Deployment) -> dict:
        return deployment.model_dump()

    def write_deployment(self, folder: Path, record: dict) -> None:
        layout.write_deployment_metadata(folder, record)

    def write_preprocessing(self, folder: Path, log: dict) -> None:
        (folder / PREPROCESSING_LOG_FILE).write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_images(self, folder: Path, deployment_id: str, images: list[tuple[str, str, dict]]) -> None:
        layout.write_images_file(folder, deployment_id, [layout.image_entry(name, local, "local", extra) for name, local, extra in images])
