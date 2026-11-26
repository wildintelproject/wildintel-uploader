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
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image

from wildintel_uploader.core.services import exif_store, file_memo

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


_GPS_IFD = 0x8825
# The names ExifTool gives some tags that Pillow knows by another name.
_PILLOW_NAMES = {"iso": "ISOSpeedRatings", "createdate": "DateTimeDigitized", "modifydate": "DateTime", "exposurecompensation": "ExposureBiasValue"}


def _tags_with_exiftool(exiftool: str, paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
    """The value of each tag in each file, in one ExifTool run (the file names on stdin): None where a file does not have it. A file ExifTool says nothing
    of — one it could not read — is not in what is returned."""
    args = [exiftool, "-json", "-charset", "filename=utf8", "-m", *(f"-{tag}" for tag in tags), "-@", "-"]
    completed = subprocess.run(
        args, input="\n".join(str(p) for p in paths), capture_output=True, text=True, encoding="utf-8", timeout=_EXIFTOOL_TIMEOUT_SECONDS, check=False,
    )
    rows = json.loads(completed.stdout) if completed.stdout.strip() else []
    by_source = {str(Path(row.get("SourceFile", ""))): {k.lower(): v for k, v in row.items()} for row in rows}
    return {path: {tag: _clean(by_source[str(path)].get(tag.lower())) for tag in tags} for path in paths if str(path) in by_source}


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
    read = _metadata(paths, tags)
    if read is not None:
        return {path: {tag: read[path].get(tag.lower()) for tag in tags} for path in paths}
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
    read = _metadata(paths, list(DATE_TAGS))
    if read is not None:
        return {p: next((d for d in (_parse_date(read[p].get(t.lower())) for t in DATE_TAGS) if d is not None), None) for p in paths}
    return {p: _date_with_pillow(p) for p in paths}


def read_cameras(paths: list[Path]) -> tuple[dict[Path, CameraInfo], str]:
    """The camera model and id of each image, and which reader was used ("exiftool" or "pillow"). With ExifTool it is what _metadata read — once for every
    step that asks —; without it, or when it fails, Pillow reads it, and that too is remembered while the image is the same (see file_memo), but only as long as
    there is no ExifTool: it says less."""
    if not paths:
        return {}, "pillow"
    read = _metadata(paths, [])
    if read is not None:
        return {p: _camera_of(read[p]) for p in paths}, "exiftool"
    found: dict[Path, CameraInfo] = {}
    for path in paths:
        key = file_memo.stamp(path)
        remembered = file_memo.CAMERAS.get(key)
        if remembered is None:
            remembered = (_read_with_pillow(path), "pillow")
            file_memo.CAMERAS.put(key, remembered)
        found[path] = remembered[0]  # type: ignore[assignment]
    return found, "pillow"


def _camera_of(tags: dict[str, str | None]) -> CameraInfo:
    """The camera, from the tags ExifTool read of an image: the model with its make, and the first serial number there is, in the order of _SERIAL_TAGS."""
    serial = next((s for s in (_clean(tags.get(t.lower())) for t in _SERIAL_TAGS) if s), None)
    return CameraInfo(model=_model(tags.get("make"), tags.get("model")), camera_id=serial)


# Only one ExifTool reading runs at a time (see _metadata).
_reading = threading.Lock()
# Whether prefetch reads ahead at all: the tests turn it off (conftest), so that no reading started by one test is still running in the next.
PREFETCH = True


def prefetch(paths: list[Path], tags: list[str] | None = None) -> threading.Thread | None:
    """Starts reading, in the background, what the steps of an import will ask of these images — the camera, the dates, and `tags` (the EXIF fields the
    settings ask for) —, so that it is remembered by the time they ask (#140): a step that asks meanwhile waits for it rather than reading them again.
    Nothing is started without ExifTool — Pillow reads each image as it is asked for — or with no images. Returns the thread, for the tests to wait on."""
    if not PREFETCH or not paths or not exiftool_path():
        return None

    def run() -> None:
        try:
            _metadata(paths, list(tags or []))
        except Exception as exc:  # noqa: BLE001 — a reading ahead that fails only means the steps read the images themselves
            logger.debug("Reading the EXIF ahead failed: %s", exc)
    thread = threading.Thread(target=run, name="exif-prefetch", daemon=True)
    thread.start()
    return thread


# What every reading of an image with ExifTool asks for, whatever step it is for: the camera and the capture date, which every step of an import needs — so that
# one run reads what the next ones will ask for (#140).
_BASE_TAGS = ("Make", "Model", *_SERIAL_TAGS, *DATE_TAGS)


def _metadata(paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]] | None:
    """The tags of each image (by their names in lowercase, None where it has not got one) as ExifTool reads them — None when there is no ExifTool, or it
    failed: the caller reads with Pillow then.

    Each image is read once while it is the same file (its path, size and modification time, see file_memo): what was read is remembered in memory and kept on
    disk (exif_store), so that neither the next step nor a restart of the app reads it again. Only the images not remembered, or remembered without one of the
    tags asked for, are read — all of them in one run, asking for _BASE_TAGS besides the tags asked for, so that the next steps find them."""
    exiftool = exiftool_path()
    if not exiftool:
        return None
    wanted = {t.lower() for t in tags}
    stamps = {path: file_memo.stamp(path) for path in paths}
    found: dict[Path, dict[str, str | None]] = {}
    for path in paths:
        known = file_memo.EXIF.get(stamps[path])
        if known is not None and wanted <= known.keys():
            found[path] = known
    kept = exif_store.get_many([stamps[p] for p in paths if p not in found and stamps[p] is not None])
    for path in paths:
        known = kept.get(stamps[path]) if path not in found and stamps[path] is not None else None
        if known is not None and wanted <= known.keys():
            file_memo.EXIF.put(stamps[path], known)
            found[path] = known
    missing = [p for p in paths if p not in found]
    if not missing:
        return found
    # One reading at a time: a step that asks while another reading is under way — the one started when the folder was scanned — waits for it, and
    # then finds what it read instead of reading the same images again.
    with _reading:
        return _read_missing(exiftool, paths, missing, tags, wanted, stamps, found)


def _read_missing(exiftool: str, paths: list[Path], missing: list[Path], tags: list[str], wanted: set[str],
                  stamps: dict[Path, file_memo.Stamp | None], found: dict[Path, dict[str, str | None]]) -> dict[Path, dict[str, str | None]] | None:
    """The part of _metadata that runs ExifTool, under its lock: what another reading left in memory meanwhile is taken first."""
    still = []
    for path in missing:
        known = file_memo.EXIF.get(stamps[path])
        if known is not None and wanted <= known.keys():
            found[path] = known
        else:
            still.append(path)
    missing = still
    if not missing:
        return found
    ask = list({t.lower(): t for t in (*_BASE_TAGS, *tags)}.values())
    try:
        read = _tags_with_exiftool(exiftool, missing, ask)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("ExifTool failed (%s) — falling back to Pillow.", exc)
        return None
    fresh: dict[file_memo.Stamp, dict[str, str | None]] = {}
    for path in missing:
        if path not in read:   # ExifTool could not read it: it has none of them, and it is looked at again next time
            found[path] = dict.fromkeys((t.lower() for t in ask), None)
            continue
        values = {**(file_memo.EXIF.get(stamps[path]) or {}), **{t.lower(): v for t, v in read[path].items()}}
        found[path] = values
        if stamps[path] is not None:
            file_memo.EXIF.put(stamps[path], values)
            fresh[stamps[path]] = values  # type: ignore[index]
    exif_store.put_many(fresh)
    return found


def common_value(values: list[str | None]) -> str | None:
    """The one value every image has — None if any is missing or they differ."""
    distinct = set(values)
    return distinct.pop() if len(distinct) == 1 and None not in distinct else None
