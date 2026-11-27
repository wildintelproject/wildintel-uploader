"""What the preprocessing is told, and what it works out without touching a file: the dates in a timezone, the new names, the XMP of an image,
what resizing did."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# What records, beside the images, what was done to each one.
PREPROCESSING_LOG_FILE = "preprocessing.json"
# Where a deployment is prepared: <collection>/.staging/<deployment id>, inside its own collection so that moving it to its place is one rename on
# the same volume — atomic, and instant however many images it has.
STAGING_DIR = ".staging"


class PreprocessingError(ValueError):
    """What stops the preprocessing: bad paths, an unknown timezone, metadata without ExifTool, no room, a deployment already there…"""


@dataclass(frozen=True)
class PreprocessOptions:
    """What to do to the images, and the values it uses."""

    rename: bool = True
    resize: bool = True
    resize_width: int = 2400
    metadata: bool = True
    owner: str = ""
    publisher: str = ""
    coverage: str = ""
    license_url: str = "https://creativecommons.org/licenses/by-nc/4.0/"
    # The research project's name, for the creator metadata.
    research_project: str = ""
    timezone: str = "UTC"
    ignore_dst: bool = True
    convert_to_utc: bool = True


class DeploymentLike(Protocol):
    """What the steps of the preprocessing read of a deployment: its id and where it is. Read only — the record of a deployment (DeploymentRecord)
    is one."""

    @property
    def deployment_id(self) -> str: ...
    @property
    def location_id(self) -> str | None: ...
    @property
    def location_name(self) -> str | None: ...


@dataclass
class ImageWork:
    """One image as the steps go through it: where it is and where it goes, and its record — what each step found out or did, by the keys of
    preprocessing.json (original, name, date, date_source, resized, sizes, hashes, camera); what starts with "_" is only for the steps after it."""
    index: int                 # its place in natural file-name order, from 1
    source: Path
    source_dir: Path
    work_dir: Path
    record: dict[str, Any] = field(default_factory=dict)

    @property
    def relative(self) -> Path:
        return self.source.relative_to(self.source_dir)


def natural_key(path: Path | str) -> list:
    """Sorts "IMG_2" before "IMG_10" — the order the images are numbered in."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(path))]


def zone_of(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise PreprocessingError(f"Unknown timezone: {name}") from exc


def localize(naive: datetime, zone: ZoneInfo, *, ignore_dst: bool) -> datetime:
    """A camera's wall-clock time in a timezone. Ignoring summer time uses the zone's standard offset all year, as for a camera whose clock was
    never changed."""
    if ignore_dst:
        offset, dst = zone.utcoffset(naive), zone.dst(naive)
        if offset is None or dst is None:
            raise ValueError(f"Invalid timezone information for {zone}")
        return naive.replace(tzinfo=datetime_timezone(offset - dst))
    return naive.replace(tzinfo=zone)


def as_kept(aware: datetime, options: PreprocessOptions) -> datetime:
    """The date an image keeps: in UTC, if asked."""
    return aware.astimezone(datetime_timezone.utc) if options.convert_to_utc else aware


def new_name(deployment_id: str, date: datetime, index: int, suffix: str) -> str:
    """<DEPLOYMENT>__<YYYYMMDD>_<n>.<EXT>, upper case, .jpg as .jpeg."""
    suffix = suffix.lower()
    if suffix == ".jpg":
        suffix = ".jpeg"
    return f"{deployment_id}__{date.strftime('%Y%m%d')}_{index}{suffix}".upper()


def xmp_tags(options: PreprocessOptions, deployment: DeploymentLike, *, camera: str | None, date: datetime, mime: str,
             source_hash: str, image_hash: str, year: int | None = None) -> dict[str, str]:
    """The XMP tags one image gets. A blank owner or publisher is "Unknown", and a blank coverage is the deployment's location."""
    owner = options.owner or "Unknown"
    publisher = options.publisher or "Unknown"
    place = options.coverage or deployment.location_name or deployment.location_id or "an unspecified place"
    # As wildintel-tools wrote it: the camera's make and model in lower case, then the research project's name.
    creator = f"CT ({camera.lower() if camera else '(unknown) (unknown)'} {options.research_project or 'Unknown'})"
    return {
        "XMP-dc:Creator": creator,
        "XMP-dc:Date": date.isoformat(),
        "XMP-dc:Format": mime,
        "XMP-dc:Identifier": f"WildINTEL:{image_hash}",
        "XMP-dc:Source": f"WildINTEL:{source_hash}",
        "XMP-dc:Publisher": publisher,
        "XMP-dc:Rights": f"© {owner}, {year or datetime.now().year}. All rights reserved.",
        "XMP-dc:Coverage": f"This image was taken at {place}, as part of the WildINTEL project. https://wildintel.eu/",
        "XMP-xmpRights:Marked": "true",
        "XMP-xmpRights:Owner": owner,
        "XMP-xmpRights:WebStatement": options.license_url,
    }


# The keys of an image in preprocessing.json, in the order they have always been written in.
RECORD_KEYS = ("original", "name", "date", "date_source", "resized", "original_width", "original_height", "original_bytes", "width", "height", "bytes",
               "source_hash", "hash", "camera", "camera_id")


def public_record(record: dict) -> dict:
    """What preprocessing.json keeps of an image: without what was only for the steps, in the order of RECORD_KEYS."""
    ordered = {k: record[k] for k in RECORD_KEYS if k in record}
    return {**ordered, **{k: v for k, v in record.items() if not k.startswith("_") and k not in ordered}}


def resize_summary(records: list[dict]) -> dict:
    """What resizing did to the images of a deployment, to see it at a glance: how many were resized of how many, the most common size before and
    after, and how much they weighed before and after — all the images, the ones not resized too."""
    def common(keys: tuple[str, str]) -> str | None:
        sizes = Counter(f"{r[keys[0]]}×{r[keys[1]]}" for r in records if r.get(keys[0]) and r.get(keys[1]))
        return sizes.most_common(1)[0][0] if sizes else None
    resized = [r for r in records if r.get("resized")]
    return {
        "resized": len(resized), "images": len(records),
        "before": common(("original_width", "original_height")), "after": common(("width", "height")),
        "before_bytes": sum(r.get("original_bytes") or 0 for r in records), "after_bytes": sum(r.get("bytes") or 0 for r in records),
    }
