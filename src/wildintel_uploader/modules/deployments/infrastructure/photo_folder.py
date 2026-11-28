"""The folder of a deployment in the collections folder, as its photos are looked at: the files in it, when images.json says each was taken, and
one of them as a JPEG, turned as its EXIF says."""
from __future__ import annotations

import io
import json
from collections.abc import Callable
from pathlib import Path

from wildintel_uploader.modules.deployments.domain import photos as rules
from wildintel_uploader.modules.deployments.domain.naming import IMAGES_FILE
from wildintel_uploader.modules.deployments.domain.ports import PhotoFolder
from wildintel_uploader.modules.deployments.infrastructure import collections as layout


class PhotosOnDisk(PhotoFolder):
    """`root` says the collections folder, asked each time."""

    def __init__(self, root: Callable[[], Path]) -> None:
        self._root = root

    def _folder(self, project: str, collection: str, deployment_id: str) -> Path:
        try:
            project_dir = layout.project_dir(self._root(), project)
        except layout.LocalFolderError as exc:
            raise rules.DeploymentMissing(str(exc)) from exc
        folder = (project_dir / collection / deployment_id).resolve()
        if project_dir.resolve() not in folder.parents or not folder.is_dir():
            raise rules.not_kept(deployment_id)
        return folder

    def names(self, project: str, collection: str, deployment_id: str) -> list[str]:
        return [p.name for p in self._folder(project, collection, deployment_id).iterdir() if p.is_file()]

    def taken(self, project: str, collection: str, deployment_id: str) -> dict[str, str | None]:
        folder = self._folder(project, collection, deployment_id)
        try:
            return {image["name"]: image.get("local_time") for image in json.loads((folder / IMAGES_FILE).read_text(encoding="utf-8")).get("images", [])}
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return {}

    def jpeg(self, project: str, collection: str, deployment_id: str, name: str, size: int) -> bytes:
        from PIL import Image, ImageOps

        folder = self._folder(project, collection, deployment_id)
        path = (folder / name).resolve()
        if path.parent != folder or not path.is_file():
            raise rules.no_photo(name)
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((size, size))
                out = io.BytesIO()
                img.convert("RGB").save(out, "JPEG", quality=75)
                return out.getvalue()
        except Exception as exc:  # noqa: BLE001 — what Pillow can't open is said, not raised
            raise rules.cannot_show(name, exc) from exc
