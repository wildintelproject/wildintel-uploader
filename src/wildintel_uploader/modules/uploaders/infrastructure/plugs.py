"""What the adapters of this module that are still functions of the code of before need from outside it — another module through its
contract, the settings —, plugged in where the app is put together (entrypoints.wiring; see shared.plugs)."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.ports import CatalogService
from wildintel_uploader.modules.deployments.domain.ports import DeploymentsService
from wildintel_uploader.modules.settings.domain.ports import StoredSettings
from wildintel_uploader.shared.plugs import Plug


config: Plug[StoredSettings] = Plug("the settings as settings.toml keeps them")
catalog_of: Plug[Callable[[Path], CatalogService]] = Plug("the catalog of a collections folder")
deployments: Plug[Callable[[], DeploymentsService]] = Plug("the deployments")
