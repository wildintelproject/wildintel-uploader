"""How a collection holds its deployments — the contract the other modules bring images into a collection through: the paths, what is kept
and the seal as an import says (CollectionImporter), the files as the collections folder keeps them, and the room on the disk."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.ports import CollectionImporter, CollectionLayout, Deployment
from wildintel_uploader.modules.deployments.infrastructure import collections as layout
from wildintel_uploader.modules.deployments.infrastructure import disk_space


class LayoutOfTheCollections(CollectionLayout):
    def __init__(self, importing: Callable[[], CollectionImporter]) -> None:
        self._importing = importing

    def check_paths(self, source: Path, dest: Path) -> None:
        self._importing().check_paths(source, dest)

    def is_pending(self, dest: Path) -> bool:
        return self._importing().is_pending(dest)

    def check_not_kept(self, dest: Path) -> None:
        self._importing().check_not_kept(dest)

    def is_synced(self, dest: Path) -> bool:
        return layout.is_synced(dest)

    def shortfall(self, folder: Path, needed: int, what: str, where: str) -> str | None:
        return disk_space.shortfall(folder, needed, what, where)

    def write_collection_metadata(self, collection: Path, name: str | None) -> None:
        layout.write_collection_metadata(collection, name)

    def image_entry(self, name: str, local_time: str | None, source: str, extra: dict) -> dict:
        return layout.image_entry(name, local_time, source, extra)

    def write_images_file(self, folder: Path, deployment_id: str, images: list[dict], source: str = "local") -> None:
        layout.write_images_file(folder, deployment_id, images, source=source)

    def write_deployment_metadata(self, dest: Path, deployment: dict) -> None:
        layout.write_deployment_metadata(dest, deployment)

    def seal(self, source: Path, dest: Path, deployment: Deployment, **details) -> bool:
        return self._importing().seal(source, dest, deployment, **details)
