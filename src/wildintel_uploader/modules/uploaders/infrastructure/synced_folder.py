"""The collections folder as a sync with TRAPPER fills it: a collection's collection.json, a deployment's deployment.json and its images.json —
written as the deployments keep them (their contract: the layout of the collections)."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.naming import COLLECTION_METADATA_FILE, DEPLOYMENT_METADATA_FILE, IMAGES_FILE
from wildintel_uploader.modules.deployments.domain.ports import CollectionLayout
from wildintel_uploader.modules.catalog.domain.models import Location, ResearchProject, UnknownProject
from wildintel_uploader.modules.catalog.domain.ports import CatalogService
from wildintel_uploader.modules.uploaders.domain.ports import SyncedCatalog, SyncedFolder
from wildintel_uploader.shared import storage


class SyncedCollections(SyncedFolder):
    """`root` says the collections folder, asked each time; `layout` how a collection holds its deployments."""

    def __init__(self, root: Callable[[], Path], layout: Callable[[], CollectionLayout]) -> None:
        self._root, self._layout = root, layout

    def project_folder(self, project: str) -> Path:
        return self._root() / storage.valid_project_id(project)

    def _deployment(self, project: str, collection: str, deployment_id: str) -> Path:
        return self.project_folder(project) / collection / deployment_id

    def has_collection(self, project: str, collection: str) -> bool:
        return (self.project_folder(project) / collection / COLLECTION_METADATA_FILE).is_file()

    def add_collection(self, project: str, collection: str) -> None:
        self._layout().write_collection_metadata(self.project_folder(project) / collection, collection)

    def has_deployment(self, project: str, collection: str, deployment_id: str) -> bool:
        return (self._deployment(project, collection, deployment_id) / DEPLOYMENT_METADATA_FILE).is_file()

    def add_deployment(self, project: str, collection: str, deployment_id: str, record: dict) -> None:
        from pydantic import ValidationError

        from wildintel_uploader.shared.camtrap import DeploymentFields
        try:
            fields = DeploymentFields.model_validate(record)
        except ValidationError as exc:
            raise ValueError("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())) from exc
        self._layout().write_deployment_metadata(self._deployment(project, collection, deployment_id), fields.model_dump())

    def has_images(self, project: str, collection: str, deployment_id: str) -> bool:
        return (self._deployment(project, collection, deployment_id) / IMAGES_FILE).is_file()

    def add_images(self, project: str, collection: str, deployment_id: str, images: list[tuple[str, str | None, dict]]) -> None:
        layout = self._layout()
        entries = [layout.image_entry(name, taken, "trapper", extra) for name, taken, extra in images]
        layout.write_images_file(self._deployment(project, collection, deployment_id), deployment_id, entries, source="trapper")

    def images_listed(self, project: str, collection: str, deployment_id: str) -> list[str]:
        try:
            info = json.loads((self._deployment(project, collection, deployment_id) / IMAGES_FILE).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        return [i["name"] for i in info.get("images", []) if isinstance(i, dict) and i.get("name")]

    def image_path(self, project: str, collection: str, deployment_id: str, name: str) -> Path:
        return self._deployment(project, collection, deployment_id) / name

    def has_image(self, project: str, collection: str, deployment_id: str, name: str) -> bool:
        return self.image_path(project, collection, deployment_id, name).is_file()


class CatalogOfTheSync(SyncedCatalog):
    """The catalog of the collections folder as a sync reads and adds to it — through its contract, given when it is needed."""

    def __init__(self, catalog: Callable[[], CatalogService]) -> None:
        self._catalog = catalog

    def has_project(self, project: str) -> bool:
        try:
            self._catalog().require_project(project)
        except UnknownProject:
            return False
        return True

    def add_project(self, project: ResearchProject) -> None:
        self._catalog().add_project(project)

    def location_ids(self, project: str) -> set[str]:
        return {loc.location_id.lower() for loc in self._catalog().locations(project)}

    def add_location(self, project: str, location: Location) -> None:
        self._catalog().add_location(project, location)

