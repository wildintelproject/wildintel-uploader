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
