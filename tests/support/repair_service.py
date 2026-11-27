"""Repairing a deployment as the tests of before call it — by the collections folder — over the use case the app uses
(modules.deployments.application.repair.Repairing), raising what the repair itself refuses (RepairError)."""
from pathlib import Path

from wildintel_uploader.modules.deployments.domain.repair import METADATA_FILES as _METADATA_FILES, RepairError  # noqa: F401


def _repairing(root: Path):
    from wildintel_uploader.entrypoints.wiring import build_reports, catalog_of, config, file_info, sealing
    from wildintel_uploader.modules.deployments.application.repair import Repairing
    from wildintel_uploader.modules.deployments.infrastructure.repair_folder import RepairFolderOnDisk
    return Repairing(RepairFolderOnDisk(lambda: root, file_info), sealing, build_reports, lambda: catalog_of(root),
                     lambda: config.load_settings().PREPROCESSING.model_dump())


def list_collections(root: Path, research_project_id: str) -> list[dict]:
    return _repairing(root).list_collections(research_project_id)


def inspect(root: Path, research_project_id: str, collection: str, deployment_id: str) -> dict:
    return _repairing(root).inspection(research_project_id, collection, deployment_id)


def repair_stream(root: Path, research_project_id: str, collection: str, deployment_id: str):
    return _repairing(root).repair_stream(research_project_id, collection, deployment_id)
