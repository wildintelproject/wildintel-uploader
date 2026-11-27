"""A deployment's folder as its seal reads and writes it — its images in natural file-name order, their SHA-256 a few at a time, its
deployment.json and its seal.json —, and the sections of the settings that say which checks run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from wildintel_uploader.modules.deployments.domain import naming
from wildintel_uploader.modules.deployments.domain.ports import CheckSettings, SealedFolder
from wildintel_uploader.modules.deployments.domain.seal import SEAL_FILE
from wildintel_uploader.modules.fileinfo.domain.models import IMAGE_EXTENSIONS
from wildintel_uploader.modules.settings.domain.ports import StoredSettings
from wildintel_uploader.shared import parallel


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def images_of(folder: Path) -> list[Path]:
    """The images of a folder — its subfolders' too —, in natural file-name order."""
    return sorted((p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS), key=lambda p: naming.natural_key(p.relative_to(folder)))


class DeploymentSealFolder(SealedFolder):
    def images(self, folder: Path) -> list[str]:
        return [str(p.relative_to(folder)) for p in images_of(folder)]

    def hashes(self, folder: Path, names: list[str]) -> list[str]:
        return parallel.pmap(sha256, [folder / n for n in names])

    def metadata_hash(self, folder: Path) -> str | None:
        metadata = folder / naming.DEPLOYMENT_METADATA_FILE
        return sha256(metadata) if metadata.is_file() else None

    def read_seal(self, folder: Path) -> dict | None:
        path = folder / SEAL_FILE
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(str(exc)) from exc

    def write_seal(self, folder: Path, seal: dict) -> None:
        (folder / SEAL_FILE).write_text(json.dumps(seal, indent=2, ensure_ascii=False), encoding="utf-8")


class ChecksInUse(CheckSettings):
    def __init__(self, settings: StoredSettings) -> None:
        self._settings = settings

    def validation(self) -> Any:
        return self._settings.load_settings().VALIDATION

    def postvalidation(self) -> Any:
        return self._settings.load_settings().POSTVALIDATION
