"""The collections folder as the rest of the app keeps it: where it is, whether a folder is a collection, the deployments in one, the images
already imported into a research project, the seal of a deployment kept (DeploymentSealer) and the time settings of a location, from the
catalog of that collections folder through its contract. What can't be read is DeploymentsFailed."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.models import CatalogError
from wildintel_uploader.modules.catalog.domain.ports import CatalogLocations
from wildintel_uploader.modules.deployments.domain.models import DeploymentsFailed
from wildintel_uploader.modules.deployments.domain.ports import DeploymentSealer, Folders
from wildintel_uploader.modules.deployments.infrastructure import collections as layout
from wildintel_uploader.shared.storage import StorageError


class CollectionFolders(Folders):
    """`root` says the collections folder, asked each time; `catalog_of` the catalog of a collections folder."""

    def __init__(self, root: Callable[[], Path], catalog_of: Callable[[Path], CatalogLocations], sealing: Callable[[], DeploymentSealer]) -> None:
        self._root, self._catalog_of, self._sealing = root, catalog_of, sealing

    def root(self) -> Path:
        return self._root()

    def project_of(self, collection_dir: str) -> str | None:
        folder = Path(collection_dir).expanduser().resolve().parent
        return folder.name if folder.parent == self.root().expanduser().resolve() else None

    def check_collection(self, folder: Path) -> dict:
        return layout.check_collection(folder)

    def local_deployments(self, folder: Path) -> list[dict]:
        return layout.list_deployments(folder)

    def imported(self, project: str, exclude_deployment: str | None) -> dict[str, list[dict]]:
        try:
            return layout.imported_source_hashes(self.root(), project, exclude_deployment)
        except StorageError as exc:
            raise DeploymentsFailed(str(exc)) from exc

    def seal_status(self, folder: Path) -> dict:
        return self._sealing().verify(folder)

    def location_time(self, project_dir: Path, location_id: str | None) -> dict:
        try:   # the research project of that folder, in the catalog of its collections folder
            return self._catalog_of(project_dir.parent).location_time(project_dir.name, location_id)
        except CatalogError as exc:
            raise DeploymentsFailed(exc.message) from exc
