"""FallbackReader with Pillow, an image at a time — only when there is no ExifTool, or it failed: the standard EXIF tags only, with the names ExifTool
gives them where Pillow knows them by another. And Decoder: whether an image decodes in full."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image

from wildintel_uploader.modules.fileinfo.domain.models import CameraInfo, clean, model_name, parse_date
from wildintel_uploader.modules.fileinfo.domain.ports import Decoder, FallbackReader

logger = logging.getLogger(__name__)

_TAG_IDS = {name: tag for tag, name in ExifTags.TAGS.items()}
_EXIF_IFD = 0x8769
_GPS_IFD = 0x8825
# The names ExifTool gives some tags that Pillow knows by another name.
_PILLOW_NAMES = {"iso": "ISOSpeedRatings", "createdate": "DateTimeDigitized", "modifydate": "DateTime", "exposurecompensation": "ExposureBiasValue"}
_PILLOW_DATE_TAGS = (("exif", 36867), ("exif", 36868), ("main", 306))   # DateTimeOriginal, DateTimeDigitized, DateTime


def _read_with_pillow(path: Path) -> CameraInfo:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            make = exif.get(_TAG_IDS.get("Make", 271))
            model = exif.get(_TAG_IDS.get("Model", 272))
            serial = exif.get_ifd(_EXIF_IFD).get(_TAG_IDS.get("BodySerialNumber", 42033))
            return CameraInfo(model=model_name(make, model), camera_id=clean(serial))
    except Exception as exc:  # a corrupt/unreadable file just has no camera information
        logger.debug("No camera information in %s: %s", path, exc)
        return CameraInfo()


def _tags_with_pillow(path: Path, tags: list[str]) -> dict[str, str | None]:
    """The value of each tag in a file, as Pillow reads it: the standard EXIF tags only, in the image, its Exif and its GPS sections."""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            sections = [exif, exif.get_ifd(_EXIF_IFD), exif.get_ifd(_GPS_IFD)]
            gps_ids = {name.lower(): tag for tag, name in ExifTags.GPSTAGS.items()}
            out: dict[str, str | None] = {}
            for tag in tags:
                name = _PILLOW_NAMES.get(tag.lower(), tag)
                ids = [i for i in (_TAG_IDS.get(name), gps_ids.get(tag.lower()), gps_ids.get(tag.lower().removeprefix("gps"))) if i is not None]
                out[tag] = next((v for v in (clean(section.get(i)) for section in sections for i in ids) if v), None)
            return out
    except Exception as exc:  # an unreadable file has none of them
        logger.debug("No EXIF in %s: %s", path, exc)
        return dict.fromkeys(tags)


def _date_with_pillow(path: Path) -> datetime | None:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            sub = exif.get_ifd(_EXIF_IFD)
            for where, tag in _PILLOW_DATE_TAGS:
                found = parse_date((sub if where == "exif" else exif).get(tag))
                if found is not None:
                    return found
    except Exception as exc:  # a corrupt or unreadable file has no date: it must not stop the rest
        logger.debug("No EXIF date in %s: %s", path, exc)
    return None


class PillowReader(FallbackReader):
    def tags(self, path: Path, tags: list[str]) -> dict[str, str | None]:
        return _tags_with_pillow(path, tags)

    def date(self, path: Path) -> datetime | None:
        return _date_with_pillow(path)

    def camera(self, path: Path) -> CameraInfo:
        return _read_with_pillow(path)


class PillowDecoder(Decoder):
    def decode_error(self, path: Path) -> str | None:
        try:
            with Image.open(path) as img:
                img.load()
            return None
        except Exception as exc:  # noqa: BLE001 — whatever it is, the image does not decode
            return str(exc)
