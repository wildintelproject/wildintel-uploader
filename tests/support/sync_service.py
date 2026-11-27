"""The sync with TRAPPER as the tests of before call it — by the collections folder — over the use cases and the adapters the app uses
(modules.uploaders: TrapperSync)."""
from pathlib import Path

from wildintel_uploader.modules.uploaders.domain.sync import wall_clock  # noqa: F401


def _sync(root: Path | None = None):
    from wildintel_uploader.entrypoints.wiring import build_deployments, catalog_of, config
    from wildintel_uploader.modules.uploaders.application.sync import TrapperSync
    from wildintel_uploader.modules.uploaders.infrastructure.synced_folder import SyncedCollections
    from wildintel_uploader.modules.uploaders.infrastructure.trapper_site import TrapperSdk
    where = (lambda: root) if root is not None else (lambda: config.collections_dir())
    return TrapperSync(TrapperSdk(), lambda: catalog_of(where()).records(), SyncedCollections(where, lambda: build_deployments().layout()))


def collection_names(credentials, classification_project_pk: int) -> list[str]:
    return _sync().collection_names(credentials, classification_project_pk)


def sync_stream(credentials, root: Path, research_project: dict, classification_project_pk: int, only=None, only_deployments=None, download_images=False):
    return _sync(root).sync(credentials, research_project, classification_project_pk, only, only_deployments, download_images)


def sync(credentials, root: Path, research_project: dict, classification_project_pk: int, only=None, only_deployments=None, download_images=False) -> dict:
    result: dict = {}
    for event in sync_stream(credentials, root, research_project, classification_project_pk, only, only_deployments, download_images):
        if event["type"] == "done":
            result = {k: v for k, v in event.items() if k != "type"}
    return result
