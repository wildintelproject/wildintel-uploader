"""The use cases and adapters of the app, put together for a test — over a collections folder of its own when the test gives one, as
entrypoints.wiring puts them together for the app. The tests call them by their own API: this module only builds them."""
from __future__ import annotations

from pathlib import Path


def repairing(root: Path):
    from wildintel_uploader.entrypoints.wiring import build_reports, catalog_of, config, file_info, sealing
    from wildintel_uploader.modules.deployments.application.repair import Repairing
    from wildintel_uploader.modules.deployments.infrastructure.repair_folder import RepairFolderOnDisk
    return Repairing(RepairFolderOnDisk(lambda: root, file_info), sealing, build_reports, lambda: catalog_of(root),
                     lambda: config.load_settings().PREPROCESSING.model_dump())


def card_copying():
    from wildintel_uploader.modules.deployments.application.cards import CardCopying
    from wildintel_uploader.modules.deployments.infrastructure.memory_cards import CardOnDisk, CopiesInTemp
    return CardCopying(CardOnDisk(), CopiesInTemp())


def sealing():
    from wildintel_uploader.entrypoints.wiring import sealing as built
    return built()


def importing():
    from wildintel_uploader.entrypoints.wiring import importing as built
    return built()


def trapper_sync(root: Path | None = None):
    from wildintel_uploader.entrypoints.wiring import build_deployments, catalog_of, config
    from wildintel_uploader.modules.uploaders.application.sync import TrapperSync
    from wildintel_uploader.modules.uploaders.infrastructure.synced_folder import SyncedCollections
    from wildintel_uploader.modules.uploaders.infrastructure.trapper_site import TrapperSdk
    where = (lambda: root) if root is not None else (lambda: config.collections_dir())
    return TrapperSync(TrapperSdk(), lambda: catalog_of(where()).records(), SyncedCollections(where, lambda: build_deployments().layout()))


def synced(events) -> dict:
    """What a sync says when it is done — the events of TrapperSync.sync, run through."""
    result: dict = {}
    for event in events:
        if event["type"] == "done":
            result = {k: v for k, v in event.items() if k != "type"}
    return result


def status_history(root: Path):
    from wildintel_uploader.entrypoints.wiring import build_settings, build_visits, catalog_repository
    from wildintel_uploader.modules.catalog.infrastructure.status_history import KeptStatusHistory
    return KeptStatusHistory(root, lambda: catalog_repository(root, build_settings()), lambda: build_visits(root))


def backup(root: Path | None = None, version: str | None = None):
    from wildintel_uploader.entrypoints.wiring import build_backup
    return build_backup(root) if version is None else build_backup(root, lambda: version)


def visit_files():
    from wildintel_uploader.modules.visits.application.visit_file import VisitFiles
    from wildintel_uploader.modules.visits.infrastructure.csv_file import CsvVisitFile
    return VisitFiles(CsvVisitFile())


def kept_visits(root: Path):
    from wildintel_uploader.entrypoints.wiring import catalog_of
    from wildintel_uploader.modules.visits.infrastructure.kept_visits import KeptVisits
    return KeptVisits(root, lambda: catalog_of(root).records())


def upload_failures(root: Path):
    from wildintel_uploader.entrypoints.wiring import catalog_of
    from wildintel_uploader.modules.uploaders.infrastructure.failures import UploadFailures
    return UploadFailures(lambda: root, catalog_of)


def file_info():
    from wildintel_uploader.entrypoints.wiring import file_info as built
    return built()


def trapper_uploads():
    from wildintel_uploader.entrypoints.wiring import trapper_uploads as built
    return built()
