"""The uploaders: TRAPPER, the uploads kept in the collections folder and the sync."""
from __future__ import annotations

from pathlib import Path

from dishka import Provider, Scope, alias, provide

from wildintel_uploader.entrypoints import config
from wildintel_uploader.modules.uploaders.application.sync import TrapperSync
from wildintel_uploader.modules.uploaders.application.upload import TrapperUploads
from wildintel_uploader.modules.uploaders.application.use_cases import UploadersUseCases
from wildintel_uploader.modules.uploaders.domain.ports import UploadersAccount, UploadersImport, UploadersService, UploadersState, UploadersSync, UploadersTrapper, UploadersUpload
from wildintel_uploader.modules.uploaders.infrastructure.failures import UploadFailures
from wildintel_uploader.modules.uploaders.infrastructure.packages import DeploymentFolder, PackagesOnDisk
from wildintel_uploader.modules.uploaders.infrastructure.synced_folder import CatalogOfTheSync, SyncedCollections
from wildintel_uploader.modules.uploaders.infrastructure.trapper import CollectionsFolder, PlacesInUse, SavedUploadReports, TrapperClient
from wildintel_uploader.modules.uploaders.infrastructure.trapper_site import TrapperSdk
from wildintel_uploader.modules.uploaders.infrastructure.uploads import FolderUploads
from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


def build_uploaders(collections_dir: Path | None = None) -> UploadersService:
    """The uploaders: TRAPPER through its client, the collections folder — the one of the settings by default — with the uploads kept in it."""
    def root() -> Path:   # asked each time: the uploaders are made once for the app, and the collections folder may change while it runs
        return collections_dir or w.catalog_collections_dir()
    failures = UploadFailures(root, w.catalog_of)
    return UploadersUseCases(TrapperClient(w.section("TRAPPER"), w.keep_trapper_account, TrapperSdk()), CollectionsFolder(root, w.catalog_of, failures),
                             SavedUploadReports(w.build_reports()), FolderUploads(root, w.section("TRAPPER"), w.section("AGOUTI"), lambda: w.build_deployments().layout(), failures),
                             deployments=w.build_deployments,
                             sending=trapper_uploads(), places=PlacesInUse(lambda: config.packages_dir(), lambda: config.max_zip_mb()),
                             syncing=TrapperSync(TrapperSdk(), lambda: CatalogOfTheSync(lambda: w.catalog_of(config.collections_dir())),
                                                 SyncedCollections(lambda: config.collections_dir(), lambda: w.build_deployments().layout())))


def trapper_uploads() -> TrapperUploads:
    """Uploading to TRAPPER: its API through its SDK, the deployments kept and the packages on disk."""
    return TrapperUploads(TrapperSdk(), DeploymentFolder(), PackagesOnDisk())


class UploadersProvider(Provider):
    @provide(scope=Scope.APP)
    def service(self) -> UploadersService:
        return build_uploaders()

    # each part of the contract, for whoever needs only that one: the same service
    account = alias(source=UploadersService, provides=UploadersAccount)
    trapper = alias(source=UploadersService, provides=UploadersTrapper)
    importing = alias(source=UploadersService, provides=UploadersImport)
    uploading = alias(source=UploadersService, provides=UploadersUpload)
    state = alias(source=UploadersService, provides=UploadersState)
    syncing = alias(source=UploadersService, provides=UploadersSync)
