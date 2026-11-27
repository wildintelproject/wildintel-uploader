"""What the adapters of this module that are still functions of the code of before need from outside it — another module through its
contract, the settings —, plugged in where the app is put together (entrypoints.wiring; see shared.plugs)."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.ports import CatalogService
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.postvalidation.domain.ports import PostvalidationService
from wildintel_uploader.modules.prevalidation.domain.ports import PrevalidationService
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.settings.domain.ports import StoredSettings
from wildintel_uploader.shared.plugs import Plug


config: Plug[StoredSettings] = Plug("the settings as settings.toml keeps them")
catalog_of: Plug[Callable[[Path], CatalogService]] = Plug("the catalog of a collections folder")
file_info: Plug[Callable[[], FileInfoService]] = Plug("what is known of the files")
reports: Plug[Callable[[], ReportsService]] = Plug("the reports")
prevalidation: Plug[Callable[[], PrevalidationService]] = Plug("the checks of the images")
postvalidation: Plug[Callable[[], PostvalidationService]] = Plug("the checks of a deployment")
