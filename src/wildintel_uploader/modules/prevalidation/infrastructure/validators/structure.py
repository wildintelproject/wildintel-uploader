"""Folders other than the one chosen holding files."""
from __future__ import annotations

from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder

class Structure(ImageValidator):
    key = "structure"
    label = "Folder structure"
    description = "Folders other than the one chosen holding files — some deployments expect every image directly in one flat folder."

    def run(self, folder: MediaFolder, options: ImageOptions) -> dict:
        return {"subdirectories": sorted({str(p.parent.relative_to(folder.root)) for p in folder.files if p.parent != folder.root})}
