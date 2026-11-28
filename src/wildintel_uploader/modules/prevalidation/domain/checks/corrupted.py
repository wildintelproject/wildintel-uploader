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
        """The images that do not fully decode.

        Every image is decoded, in parallel; what is found is kept in the folder for the checks that run after it (the
        order of the shots leaves those images out).

        Args:
            folder: The folder whose images are checked.
            options: Not read: the check has no option.

        Returns:
            ``{"corrupted": [{"path": str, "error": str}, ...]}`` — each image that does not decode, relative to the
            folder, and why, in the order the folder lists them. Empty when every image decodes.

        Example::

            {"corrupted": [{"path": "IMG_0042.JPG", "error": "image file is truncated (12 bytes not processed)"}]}
        """
        errors = folder.decode_errors()
        return {"corrupted": [{"path": folder.relative(p), "error": e} for p, e in errors.items() if e is not None]}
