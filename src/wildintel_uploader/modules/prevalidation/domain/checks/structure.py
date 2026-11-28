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
        """The folders, other than the one chosen, that hold files.

        Any file counts, not only the images.

        Args:
            folder: The folder chosen.
            options: Not read: the check has no option.

        Returns:
            ``{"subdirectories": [str, ...]}`` — each folder that holds a file, relative to the one chosen, sorted; a
            folder that only holds other folders is not in it. Empty when every file is directly in the folder chosen.

        Example::

            {"subdirectories": ["DCIM/100RECNX", "DCIM/101RECNX"]}
        """
        return {"subdirectories": sorted({str(p.parent.relative_to(folder.root)) for p in folder.files if p.parent != folder.root})}
