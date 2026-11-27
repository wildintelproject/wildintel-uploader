"""What the prevalidation is told besides the images, and its error."""
from __future__ import annotations

from wildintel_uploader.modules.fileinfo.domain.models import DEFAULT_CAMERA_LEVELS


class PrevalidationError(ValueError):
    """What can't be checked at all: a folder that isn't one."""


class ImageOptions:
    """What the settings and the caller say of the checks of the images: every file of a field that lacks it (detail), the EXIF fields wanted,
    how a camera is told, and what the research project already has (by the SHA-1 of its originals) to say which images were imported before."""

    def __init__(self, *, detail: bool = False, exif_fields: list[str] | None = None, camera_levels: list[list[str]] | None = None,
                 imported: dict[str, list[dict]] | None = None) -> None:
        self.detail, self.imported = detail, imported
        self.exif_fields = exif_fields if exif_fields is not None else ["Model"]
        self.camera_levels = camera_levels if camera_levels is not None else DEFAULT_CAMERA_LEVELS
