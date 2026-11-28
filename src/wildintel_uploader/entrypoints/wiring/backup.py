"""The backups of the collections folder and of the settings."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from dishka import Provider, Scope, provide

from wildintel_uploader.entrypoints import config
from wildintel_uploader.modules.backup.application.use_cases import BackupUseCases
from wildintel_uploader.modules.backup.domain.ports import BackupService
from wildintel_uploader.modules.backup.infrastructure.folders import CollectionsFolder as ProjectFoldersOnDisk
from wildintel_uploader.modules.backup.infrastructure.outside import RecordsOfTheProject, SettingsOfTheApp
from wildintel_uploader.modules.backup.infrastructure.zip_files import ZipBackups
from wildintel_uploader.shared.version import current_version
from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


def build_backup(collections_dir: Path | None = None, version: Callable[[], str] = current_version) -> BackupService:
    """The backups, as zip files, of the collections folder — the settings' by default —: the catalog and the visits through their contracts."""
    def root() -> Path:
        return collections_dir or config.collections_dir()
    return BackupUseCases(RecordsOfTheProject(root, w.catalog_of, w.catalog_record_store, lambda r: w.build_visits(r)), ProjectFoldersOnDisk(root), ZipBackups(),
                          SettingsOfTheApp(config), version)


class BackupProvider(Provider):
    @provide(scope=Scope.APP)
    def service(self) -> BackupService:
        return build_backup()
