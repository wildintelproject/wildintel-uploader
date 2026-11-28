"""The EXIF fields the app needs and those the settings ask for, and the images that lack them."""
from __future__ import annotations

from pathlib import Path

from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.fileinfo.domain.models import CAMERA_FIELDS

class ExifFields(ImageValidator):
    key = "exif"
    label = "EXIF fields"
    description = ("The EXIF fields the app needs — the capture date, always — and those the settings ask for, each with how many images lack it "
                   "and a few examples (all of them with detail).")

    def run(self, folder: MediaFolder, options: ImageOptions) -> dict:
        """The EXIF fields checked, and the images that lack each.

        The capture date is always checked, first; then the fields the settings ask for. The capture date is the one the
        file cache reads (when it was taken, else when it was digitized, else when the camera last changed the file), and
        Model and the serial numbers are those it read with the camera; any other field is read as a tag.

        Args:
            folder: The folder whose images are checked.
            options: What the caller says of the checks; read here: ``exif_fields`` (the fields the settings ask for) and
                ``detail`` (every image that lacks a field, not only a few examples).

        Returns:
            ``{"exif_missing": {field: {"label", "count", "examples", "files"}}}`` — one entry for each field checked,
            also for those no image lacks: how the page names it ("capture date" for DateTimeOriginal, else the field),
            how many images lack it and up to three of them, relative to the folder; ``files``, all of them, only with
            ``detail``.

        Example:
            The settings ask for Model and SerialNumber; two images say no serial number::

                {"exif_missing": {
                    "DateTimeOriginal": {"label": "capture date", "count": 0, "examples": []},
                    "Model": {"label": "Model", "count": 0, "examples": []},
                    "SerialNumber": {"label": "SerialNumber", "count": 2, "examples": ["IMG_0001.JPG", "IMG_0002.JPG"]},
                }}
        """
        cameras, taken = folder.cameras(), folder.dates()
        images = sorted(folder.images)
        fields = ["DateTimeOriginal", *(f for f in options.exif_fields if f.lower() != "datetimeoriginal")]
        others = [f for f in fields[1:] if f.lower() not in CAMERA_FIELDS]
        tags = folder.tags(images, others) if others else {}
        missing: dict[str, list[Path]] = {f: [] for f in fields}
        for path in images:
            for field in fields:
                key = field.lower()
                found = (taken[path] if key == "datetimeoriginal" else cameras[path].model if key == "model"
                         else cameras[path].camera_id if key in CAMERA_FIELDS else tags.get(path, {}).get(field))
                if found is None:
                    missing[field].append(path)
        return {"exif_missing": {
            field: {
                "label": "capture date" if field == "DateTimeOriginal" else field,
                "count": len(paths), "examples": [folder.relative(p) for p in paths[:3]],
                **({"files": [folder.relative(p) for p in paths]} if options.detail else {}),
            }
            for field, paths in missing.items()
        }}
