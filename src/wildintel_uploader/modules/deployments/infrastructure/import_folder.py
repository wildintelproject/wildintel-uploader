"""The folders of images on this computer, and the collections folder, as an import reads and writes them: their files, the collection's logs,
the size and the pixels of an image, and collection.json, deployment.json and images.json written as the deployments keep them."""
from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from wildintel_uploader.modules.deployments.domain.models import DeploymentImportError
from wildintel_uploader.modules.deployments.domain.ports import ImportFolder
from wildintel_uploader.modules.deployments.infrastructure import collections as layout


class ImportFolderOnDisk(ImportFolder):
    """`root` says the collections folder, asked each time."""

    def __init__(self, root: Callable[[], Path]) -> None:
        self._root = root

    def root(self) -> Path:
        return self._root()

    def is_dir(self, folder: Path) -> bool:
        return folder.is_dir()

    def files(self, folder: Path) -> list[Path]:
        return [p for p in folder.rglob("*") if p.is_file()]

    def subfolders(self, folder: Path) -> list[Path]:
        return sorted((p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.lower())

    def loose(self, folder: Path) -> list[str]:
        return [p.name for p in folder.iterdir() if p.is_file() and not p.name.startswith(".")]

    def resolve(self, path: Path) -> Path:
        try:
            return path.resolve()
        except OSError as exc:
            raise DeploymentImportError(f"Could not resolve the path: {exc}") from exc

    def has_content(self, folder: Path) -> bool:
        try:
            return folder.is_dir() and any(folder.iterdir())
        except OSError:
            return False

    def has(self, folder: Path, name: str) -> bool:
        return (folder / name).exists()

    def synced(self, folder: Path) -> bool:
        return layout.is_synced(folder)

    def timestamp_rows(self, log: Path) -> list[dict]:
        return layout.read_timestamp_log(log)

    def fieldwork_rows(self, collection: Path) -> list[dict]:
        return layout.read_fieldwork_log(layout.fieldwork_log_path(collection))

    def copy(self, file: Path, to: Path) -> None:
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, to)

    def size(self, path: Path) -> int:
        return path.stat().st_size

    def dimensions(self, path: Path) -> tuple[int | None, int | None]:
        try:
            with Image.open(path) as img:
                return img.width, img.height
        except Exception:  # noqa: BLE001 — not an image Pillow can open
            return None, None

    def write_collection(self, collection: Path, name: str | None) -> None:
        layout.write_collection_metadata(collection, name)

    def write_deployment(self, folder: Path, deployment) -> None:
        layout.write_deployment_metadata(folder, deployment.model_dump())

    def write_images(self, folder: Path, deployment_id: str, images: list[tuple[str, str | None, dict]]) -> None:
        layout.write_images_file(folder, deployment_id, [layout.image_entry(name, local, "local", extra) for name, local, extra in images])
