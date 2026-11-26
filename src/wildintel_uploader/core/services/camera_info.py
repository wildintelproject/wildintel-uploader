"""Which camera took an image — its model and its id (serial number), read
from the image's metadata.

ExifTool is used when it's available (bundled with the executables, or installed), because the serial number of a camera
trap usually lives in the manufacturer's own MakerNotes, which only ExifTool
decodes across brands. Without it, Pillow still gives the make and model from
the standard EXIF tags (and the serial, when the camera wrote the standard
BodySerialNumber tag) — less complete, but the wizard keeps working. The
result says which one was used."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image

from wildintel_uploader.core.services import file_memo

logger = logging.getLogger(__name__)

# What ExifTool is asked for, and the order the serial number is looked for in.
_SERIAL_TAGS = ("SerialNumber", "InternalSerialNumber", "BodySerialNumber", "CameraSerialNumber")
_EXIFTOOL_TIMEOUT_SECONDS = 600
_TAG_IDS = {name: tag for tag, name in ExifTags.TAGS.items()}
_EXIF_IFD = 0x8769


@dataclass(frozen=True)
class CameraInfo:
    model: str | None = None
    camera_id: str | None = None

    @property
    def known(self) -> bool:
        return self.model is not None or self.camera_id is not None


def _bundled_exiftool() -> str | None:
    """The ExifTool shipped inside the packaged executable (see the PyInstaller
    spec), or None when running from source or when none was bundled."""
    if not getattr(sys, "frozen", False):
        return None
    candidate = Path(sys._MEIPASS) / "exiftool" / ("exiftool.exe" if os.name == "nt" else "exiftool")  # type: ignore[attr-defined]
    if not candidate.is_file():
        return None
    if os.name != "nt" and not os.access(candidate, os.X_OK):
        try:
            candidate.chmod(candidate.stat().st_mode | 0o755)
        except OSError:
            return None
    return str(candidate)


def exiftool_path() -> str | None:
    """Where ExifTool is: the bundled one first, then the one on the PATH; None
    if neither exists."""
    return _bundled_exiftool() or shutil.which("exiftool")


def _model(make: object, model: object) -> str | None:
    """"<make> <model>" — the model alone when it already starts with the make ("Canon" / "Canon EOS 5D")."""
    make_text = str(make).strip() if make else ""
    model_text = str(model).strip() if model else ""
    if make_text and model_text.lower().startswith(make_text.lower()):
        make_text = ""
    return " ".join(p for p in (make_text, model_text) if p) or None


def _clean(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _read_with_exiftool(exiftool: str, paths: list[Path]) -> dict[Path, CameraInfo]:
    """One ExifTool run over every file — the file names go in on stdin, so a
    folder of thousands of images doesn't overflow the command line."""
    args = [exiftool, "-json", "-charset", "filename=utf8", "-m", "-Make", "-Model", *(f"-{tag}" for tag in _SERIAL_TAGS), "-@", "-"]
    completed = subprocess.run(
        args, input="\n".join(str(p) for p in paths), capture_output=True, text=True, encoding="utf-8",
        timeout=_EXIFTOOL_TIMEOUT_SECONDS, check=False,
    )
    # ExifTool exits non-zero when some file can't be read, but still reports the others.
    rows = json.loads(completed.stdout) if completed.stdout.strip() else []
    by_source = {str(Path(row.get("SourceFile", ""))): row for row in rows}
    cameras: dict[Path, CameraInfo] = {}
    for path in paths:
        row = by_source.get(str(path), {})
        serial = next((s for s in (_clean(row.get(tag)) for tag in _SERIAL_TAGS) if s), None)
        cameras[path] = CameraInfo(model=_model(row.get("Make"), row.get("Model")), camera_id=serial)
    return cameras


def _read_with_pillow(path: Path) -> CameraInfo:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            make = exif.get(_TAG_IDS.get("Make", 271))
            model = exif.get(_TAG_IDS.get("Model", 272))
            serial = exif.get_ifd(_EXIF_IFD).get(_TAG_IDS.get("BodySerialNumber", 42033))
            return CameraInfo(model=_model(make, model), camera_id=_clean(serial))
    except Exception as exc:  # a corrupt/unreadable file just has no camera information
        logger.debug("No camera information in %s: %s", path, exc)
        return CameraInfo()


def _read(paths: list[Path], exiftool: str | None) -> tuple[dict[Path, CameraInfo], str]:
    if exiftool:
        try:
            return _read_with_exiftool(exiftool, paths), "exiftool"
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("ExifTool failed (%s) — falling back to Pillow for the camera information.", exc)
    return {path: _read_with_pillow(path) for path in paths}, "pillow"


_GPS_IFD = 0x8825
# The names ExifTool gives some tags that Pillow knows by another name.
_PILLOW_NAMES = {"iso": "ISOSpeedRatings", "createdate": "DateTimeDigitized", "modifydate": "DateTime", "exposurecompensation": "ExposureBiasValue"}


def _tags_with_exiftool(exiftool: str, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
    """The value of each tag in each file, in one ExifTool run (the file names on stdin): None where a file does not have it."""
    args = [exiftool, "-json", "-charset", "filename=utf8", "-m", *(f"-{tag}" for tag in tags), "-@", "-"]
    completed = subprocess.run(
        args, input="\n".join(str(p) for p in paths), capture_output=True, text=True, encoding="utf-8", timeout=_EXIFTOOL_TIMEOUT_SECONDS, check=False,
    )
    rows = json.loads(completed.stdout) if completed.stdout.strip() else []
    by_source = {str(Path(row.get("SourceFile", ""))): {k.lower(): v for k, v in row.items()} for row in rows}
    return {path: {tag: _clean(by_source.get(str(path), {}).get(tag.lower())) for tag in tags} for path in paths}


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
                out[tag] = next((v for v in (_clean(section.get(i)) for section in sections for i in ids) if v), None)
            return out
    except Exception as exc:  # an unreadable file has none of them
        logger.debug("No EXIF in %s: %s", path, exc)
        return dict.fromkeys(tags)


def read_tags(paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
    """The value of each EXIF tag asked for (by its name, as ExifTool names it: Make, ISO, GPSLatitude…) in each file — None where it has not got it —, read
    with ExifTool when there is one, and with Pillow (the standard tags only) when not, or when it fails."""
    if not tags or not paths:
        return {path: {} for path in paths}
    exiftool = exiftool_path()
    if exiftool:
        try:
            return _tags_with_exiftool(exiftool, paths, tags)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("ExifTool failed (%s) — falling back to Pillow for the EXIF fields.", exc)
    return {path: _tags_with_pillow(path, tags) for path in paths}


# The capture date of an image, by the names ExifTool gives them, the first that has one: when it was taken, else when it was digitized, else when the file
# was last changed by the camera (#227).
DATE_TAGS = ("DateTimeOriginal", "CreateDate", "ModifyDate")
_NO_DATE = {"", "0000:00:00 00:00:00", "    :  :     :  :  "}
_PILLOW_DATE_TAGS = (("exif", 36867), ("exif", 36868), ("main", 306))   # DateTimeOriginal, DateTimeDigitized, DateTime


def _parse_date(raw: object) -> datetime | None:
    text = str(raw or "").strip()
    if text in _NO_DATE:
        return None
    try:
        return datetime.strptime(text[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _date_with_pillow(path: Path) -> datetime | None:
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            sub = exif.get_ifd(_EXIF_IFD)
            for where, tag in _PILLOW_DATE_TAGS:
                found = _parse_date((sub if where == "exif" else exif).get(tag))
                if found is not None:
                    return found
    except Exception as exc:  # a corrupt or unreadable file has no date: it must not stop the rest
        logger.debug("No EXIF date in %s: %s", path, exc)
    return None


def read_dates(paths: list[Path]) -> dict[Path, datetime | None]:
    """The capture date of each image, as the camera's wall clock — None where it has none —, read with ExifTool in one run for all of them (#227):
    DateTimeOriginal, else CreateDate, else ModifyDate. Only without ExifTool, or when it fails, with Pillow, image by image."""
    if not paths:
        return {}
    if exiftool_path():
        try:
            tags = read_tags(paths, list(DATE_TAGS))
            return {p: next((d for d in (_parse_date(tags.get(p, {}).get(t)) for t in DATE_TAGS) if d is not None), None) for p in paths}
        except Exception as exc:  # noqa: BLE001 — what Pillow reads is better than nothing
            logger.warning("ExifTool could not read the dates (%s) — falling back to Pillow.", exc)
    return {p: _date_with_pillow(p) for p in paths}


def read_cameras(paths: list[Path]) -> tuple[dict[Path, CameraInfo], str]:
    """The camera model and id of each image, and which reader was used
    ("exiftool" or "pillow"). ExifTool failing for any reason falls back to Pillow.

    What is read is remembered while the image is the same one (see file_memo): the validation of the images, the preprocessing and the seal read the same images, and ExifTool
    takes seconds for a card. A reading by Pillow is made again when ExifTool is there, as it says less."""
    if not paths:
        return {}, "pillow"
    exiftool = exiftool_path()
    stamps = {path: file_memo.stamp(path) for path in paths}
    found: dict[Path, CameraInfo] = {}
    readers: set[str] = set()
    missing: list[Path] = []
    for path in paths:
        remembered = file_memo.CAMERAS.get(stamps[path])
        if remembered is not None and not (exiftool and remembered[1] != "exiftool"):
            found[path] = remembered[0]  # type: ignore[assignment]
            readers.add(remembered[1])
        else:
            missing.append(path)
    if missing:
        read, reader = _read(missing, exiftool)
        for path in missing:
            found[path] = read[path]
            file_memo.CAMERAS.put(stamps[path], (read[path], reader))
        readers.add(reader)
    return {path: found[path] for path in paths}, "exiftool" if readers == {"exiftool"} else "pillow"


def common_value(values: list[str | None]) -> str | None:
    """The one value every image has — None if any is missing or they differ."""
    distinct = set(values)
    return distinct.pop() if len(distinct) == 1 and None not in distinct else None
