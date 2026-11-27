"""The backups as the tests of before call them — by the collections folder, with each choice on its own — over the contract of the backups
(modules.backup, put together by entrypoints.wiring)."""
from pathlib import Path

from wildintel_uploader.entrypoints.wiring import build_backup
from wildintel_uploader.modules.backup.domain.archive import FORMAT  # noqa: F401
from wildintel_uploader.modules.backup.domain.ports import BackupError, Choice  # noqa: F401


def describe_project(root: Path, research_project_id: str) -> dict:
    return build_backup(root).describe(research_project_id)


def settings_snapshot(root: Path | None = None) -> dict:
    return build_backup(root).settings_snapshot()


def create_backup(root: Path, dest_dir: Path, *, settings: bool, research_project_id: str | None, project_files: bool, visits: bool,
                  deployments: list[str], images: bool, app_version: str):
    return build_backup(root, lambda: app_version).create(dest_dir, research_project_id, Choice(settings, project_files, visits, list(deployments), images))


def read_backup(root: Path, path: Path) -> dict:
    return build_backup(root).read(path)


def restore_backup(root: Path, path: Path, *, settings: bool, project_files: bool, visits: bool, deployments: list[str], images: bool, replace: bool):
    return build_backup(root).restore(path, Choice(settings, project_files, visits, list(deployments), images), replace)
