"""Importing a folder of images as the tests of before call it — by functions — over the use case the app uses
(modules.deployments.application.imports.Importing) and the rules of its domain (domain.imports)."""
from pathlib import Path

from PIL import Image  # noqa: F401 — what the tests patch to see that no image is opened

from wildintel_uploader.modules.deployments.domain.imports import collection_code, deployment_id_for, with_timezone  # noqa: F401
from wildintel_uploader.modules.deployments.domain.models import DeploymentImportError  # noqa: F401


def _importing():
    from wildintel_uploader.entrypoints.wiring import importing
    return importing()


def _image_datetime(path: Path):
    from wildintel_uploader.entrypoints.wiring import file_info
    return file_info().dates([path]).get(path)


def default_collection_dir(research_project_id: str, deployment_id: str) -> Path:
    return _importing().default_collection(research_project_id, deployment_id)


def existing_deployment_dir(research_project_id: str, deployment_id: str) -> Path | None:
    return _importing().kept(research_project_id, deployment_id)


def is_pending(dest: Path) -> bool:
    return _importing().is_pending(dest)


def check_not_kept(dest: Path) -> None:
    _importing().check_not_kept(dest)


def check_paths(source_dir: Path, dest_dir: Path) -> None:
    _importing().check_paths(source_dir, dest_dir)


def scan_folder(source_dir: Path) -> dict:
    return _importing().scan_folder(source_dir)


def guess_details(source_dir: Path) -> dict:
    return _importing().guess_details(source_dir)


def scan_session(session_dir: Path) -> dict:
    return _importing().scan_session(session_dir)


def log_entry(research_project_id: str, deployment_id: str) -> dict:
    return _importing().log_entry(research_project_id, deployment_id)


def copy_folder(source_dir: Path, dest_dir: Path):
    return _importing().copy_folder(source_dir, dest_dir)


def organize_stream(research_project_id: str, source_dir: str, deployment):
    return _importing().organize(research_project_id, source_dir, deployment)


def import_local_stream(source_dir: str, collection_dir: str, collection_name: str | None, deployment):
    return _importing().copy_as_it_is(source_dir, collection_dir, collection_name, deployment)
