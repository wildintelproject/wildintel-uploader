"""What the adapters of this module that are still functions of the code of before need from outside it — another module through its
contract, the settings —, plugged in where the app is put together (entrypoints.wiring; see shared.plugs)."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository
from wildintel_uploader.modules.catalog.domain.ports import CatalogService
from wildintel_uploader.modules.visits.domain.ports import VisitsService
from wildintel_uploader.shared.plugs import Plug


catalog_of: Plug[Callable[[Path], CatalogService]] = Plug("the catalog of a collections folder")
catalog_repository_of: Plug[Callable[[Path], CatalogRepository]] = Plug("where the catalog of a collections folder is kept, as the settings say")
visits_of: Plug[Callable[[Path | None], VisitsService]] = Plug("the visits of a collections folder (None: the one of the settings)")
