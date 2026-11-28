"""The photos of a deployment kept in the collections folder, to look at them — plain Python: which names can be a collection or a deployment,
which files are photos, their order, and the sizes they are shown at."""
from __future__ import annotations

from pathlib import PurePath

from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing

THUMBNAIL = 320
LARGE = 1280
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def is_photo(name: str) -> bool:
    return PurePath(name).suffix.lower() in IMAGE_SUFFIXES


def check_parts(*parts: str) -> None:
    """A collection and a deployment are one folder each, never a path."""
    for part in parts:
        if not part or "/" in part or "\\" in part or part in {".", ".."}:
            raise DeploymentMissing("That is not a deployment.")


def not_kept(deployment_id: str) -> DeploymentMissing:
    return DeploymentMissing(f"The deployment {deployment_id} is not in the collections folder.")


def no_photo(name: str) -> DeploymentMissing:
    return DeploymentMissing(f"The deployment doesn't have the image '{name}'.")


def cannot_show(name: str, why: object) -> DeploymentMissing:
    return DeploymentMissing(f"'{name}' can't be shown: {why}")


def in_order(names: list[str], taken: dict[str, str | None]) -> list[dict]:
    """The photos by when they were taken — the wall clock of the location, as images.json says —, then by name: {"name", "taken"}."""
    return [{"name": n, "taken": taken.get(n)} for n in sorted(names, key=lambda n: (taken.get(n) or "", n))]


def size(large: bool) -> int:
    return LARGE if large else THUMBNAIL
