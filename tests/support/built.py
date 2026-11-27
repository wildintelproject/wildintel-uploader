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
    from wildintel_uploader.modules.uploaders.infrastructure.synced_folder import CatalogOfTheSync, SyncedCollections
    from wildintel_uploader.modules.uploaders.infrastructure.trapper_site import TrapperSdk
    where = (lambda: root) if root is not None else (lambda: config.collections_dir())
    return TrapperSync(TrapperSdk(), lambda: CatalogOfTheSync(lambda: catalog_of(where())), SyncedCollections(where, lambda: build_deployments().layout()))


def synced(events) -> dict:
    """What a sync says when it is done — the events of TrapperSync.sync, run through."""
    result: dict = {}
    for event in events:
        if event["type"] == "done":
            result = {k: v for k, v in event.items() if k != "type"}
    return result


def status_history(root: Path):
    from wildintel_uploader.entrypoints.wiring import build_settings, catalog_repository
    from wildintel_uploader.modules.catalog.infrastructure.status_history import KeptStatusHistory
    from wildintel_uploader.modules.catalog.infrastructure.visits import VisitsAsKept
    from wildintel_uploader.shared import storage
    kept = catalog_repository(root, build_settings())
    return KeptStatusHistory(root, lambda: kept, lambda: VisitsAsKept(storage.open_store(root), lambda: kept))


def backup(root: Path | None = None, version: str | None = None):
    from wildintel_uploader.entrypoints.wiring import build_backup
    return build_backup(root) if version is None else build_backup(root, lambda: version)


def visit_files():
    from wildintel_uploader.modules.visits.application.visit_file import VisitFiles
    from wildintel_uploader.modules.visits.infrastructure.csv_file import CsvVisitFile
    return VisitFiles(CsvVisitFile())


def kept_visits(root: Path):
    from wildintel_uploader.entrypoints.wiring import catalog_records
    from wildintel_uploader.modules.visits.infrastructure.kept_visits import KeptVisits
    return KeptVisits(root, lambda: catalog_records(root))


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


def sources():
    from wildintel_uploader.entrypoints.wiring import build_sources
    return build_sources()


def prevalidation():
    from wildintel_uploader.entrypoints.wiring import build_prevalidation
    return build_prevalidation()


def postvalidation():
    from wildintel_uploader.entrypoints.wiring import build_postvalidation
    return build_postvalidation()


def deployment_checks(checks: frozenset[str] | None = None) -> list:
    """The checks of a deployment the postvalidation runs on what is known of it — the statistical ones, against the history kept, apart."""
    return [v for v in postvalidation().validators(checks) if not v.statistical]


def deployment_context(deployment, *, collection_name: str | None = None, expected_location_id: str | None = None, tolerance_hours: float | None = None,
                       visit: dict | None = None, camera: dict | None = None, camera_levels: list[list[str]] | None = None):
    """What the postvalidation knows of a deployment, from its fields as a test has them — as the API makes it of a request."""
    from wildintel_uploader.modules.postvalidation.domain import models as post
    return post.DeploymentContext(
        deployment=post.Deployment(deployment_id=deployment.deployment_id, start_date=deployment.start_date, end_date=deployment.end_date,
                                   camera_model=deployment.camera_model),
        collection=collection_name, expected_location_id=expected_location_id,
        tolerance_hours=post.DEFAULT_TOLERANCE_HOURS if tolerance_hours is None else tolerance_hours, visit=visit, camera=camera,
        **({"camera_levels": camera_levels} if camera_levels is not None else {}))


def preprocessing():
    from wildintel_uploader.entrypoints.wiring import build_preprocessing
    return build_preprocessing()


def records(root: Path):
    """The catalog of the collections folder as records, through its rules — what the other modules ask of it."""
    from wildintel_uploader.entrypoints.wiring import catalog_records
    return catalog_records(root)
