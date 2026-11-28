"""The images that fail to fully decode."""
from __future__ import annotations

from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder

class Corrupted(ImageValidator):
    key = "corrupted"
    label = "Corrupted images"
    description = "Files that fail to fully decode."

    def run(self, folder: MediaFolder, options: ImageOptions) -> dict:
        errors = folder.decode_errors()
        return {"corrupted": [{"path": folder.relative(p), "error": e} for p, e in errors.items() if e is not None]}
