"""What is known of a file of an image, and how its metadata are understood — plain Python, with no reader nor store.

A file is known by its stamp: its path, its size and its modification time in nanoseconds. One that was changed, or replaced by another, has another
stamp: what is remembered of a stamp is never what an earlier file said."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# What a file is, for this: where it is, how big, when its content was last modified, and when the file last changed (ctime) — in
# nanoseconds, to tell two writes in the same second. The ctime tells a file replaced by another of the same size whose modification time was kept
# (cp -p, rsync -a): no copy can keep it, any write changes it (on Windows it is when the file was made, which a file put in place of another
# changes too).
Stamp = tuple[str, int, int, int]
# The tags of an image, by their names in lowercase (as ExifTool names them), None where it has not got one.
Tags = dict[str, str | None]

# What is remembered of a file besides its tags.
DECODED, SHA1, SHA256 = "decoded", "sha1", "sha256"
FACTS = (DECODED, SHA1, SHA256)

# The files that are images.
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff"})
# The EXIF fields the camera of an image already says: the model — the make with it — and the serial number, under any of its names.
CAMERA_FIELDS = frozenset({"model", "serialnumber", "internalserialnumber", "bodyserialnumber", "cameraserialnumber"})
SERIAL_FIELDS = CAMERA_FIELDS - {"model"}
# How two images are told to be of the same camera when the settings do not say it (VALIDATION.camera_levels): by the serial number, else by the make
# and the model, else by the model alone.
DEFAULT_CAMERA_LEVELS = [["SerialNumber"], ["Make", "Model"], ["Model"]]

# Where the serial number of a camera is, the first that has one.
SERIAL_TAGS = ("SerialNumber", "InternalSerialNumber", "BodySerialNumber", "CameraSerialNumber")
# The capture date of an image, the first that has one: when it was taken, else when it was digitized, else when the camera last changed the file (#227).
DATE_TAGS = ("DateTimeOriginal", "CreateDate", "ModifyDate")
# What every reading asks for, whatever it is for: the camera and the capture date, which every step of an import needs — so that one reading reads
# what the next ones will ask for (#140).
BASE_TAGS = ("Make", "Model", *SERIAL_TAGS, *DATE_TAGS)
_NO_DATE = {"", "0000:00:00 00:00:00", "    :  :     :  :  "}


@dataclass(frozen=True)
class CameraInfo:
    """The camera that took an image: its make and model, and its id (its serial number)."""
    model: str | None = None
    camera_id: str | None = None

    @property
    def known(self) -> bool:
        return self.model is not None or self.camera_id is not None


def clean(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def model_name(make: object, model: object) -> str | None:
    """"<make> <model>" — the model alone when it already starts with the make ("Canon" / "Canon EOS 5D")."""
    make_text = str(make).strip() if make else ""
    model_text = str(model).strip() if model else ""
    if make_text and model_text.lower().startswith(make_text.lower()):
        make_text = ""
    return " ".join(p for p in (make_text, model_text) if p) or None


def parse_date(raw: object) -> datetime | None:
    """An EXIF date ("2024:09:04 10:00:00"), as the camera's wall clock; None when there is none, or it is not one."""
    text = str(raw or "").strip()
    if text in _NO_DATE:
        return None
    try:
        return datetime.strptime(text[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def date_of(tags: Tags) -> datetime | None:
    """The capture date the tags of an image say: the first of DATE_TAGS that has one."""
    return next((d for d in (parse_date(tags.get(t.lower())) for t in DATE_TAGS) if d is not None), None)


def camera_of(tags: Tags) -> CameraInfo:
    """The camera the tags of an image say: the model with its make, and the first serial number there is, in the order of SERIAL_TAGS."""
    serial = next((s for s in (clean(tags.get(t.lower())) for t in SERIAL_TAGS) if s), None)
    return CameraInfo(model=model_name(tags.get("make"), tags.get("model")), camera_id=serial)


def common_value(values: list[str | None]) -> str | None:
    """The one value every image has — None if any is missing or they differ."""
    distinct = set(values)
    return distinct.pop() if len(distinct) == 1 and None not in distinct else None
