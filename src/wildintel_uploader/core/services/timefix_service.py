"""Fixing the dates and times of the images in a folder — between copying a card and importing it.

A camera's clock goes wrong: it is reset to its factory date when the batteries run out, someone sets it an hour or a
day off, it jumps when the settings are lost halfway. timeline() reads the images of a copied card in the order the
camera numbered them, with when each one says it was taken, and splits them where the time goes backwards — each
piece a "segment" taken with one setting of the clock. Each segment is set against the deployment's period (the visits', in the
cameras' clock), and for one outside it an offset is suggested: the first
segment to start at the deployment's start, a later one to go on from where the one before ended.

The folder is the one the card was copied to: its images, and nothing else is read. What it should hold is told by the
visits kept in the research project's visits.json (see visit_period): a deployment goes from the visit that left the camera to the
next one at the same location that collected its card, in the cameras' clock.

The fixes are made on the images of that folder, never on the card itself:

  * shift() moves the date and time of a run of images (from one image to another, in the camera's order) by an
    offset, with ExifTool — every date of the image: DateTimeOriginal, CreateDate and ModifyDate;
  * remove() takes out images whose time can't be made right — nothing goes on without a time to trust.

No second copy of the card is kept: every fix is written down in the deployment's time_corrections.json — what, to
which images, by how much, why, when and by whom — so a shift can be undone by shifting back. Nothing is changed
without a record of it. 
"""
from __future__ import annotations

import datetime as dt
import getpass
import json
import logging
import subprocess
from pathlib import Path

from wildintel_uploader.core import config, parallel
from wildintel_uploader.core.services import camera_info, local_folder_service
from wildintel_uploader.core.services import deployment_import_service as dis

logger = logging.getLogger(__name__)

CORRECTIONS_FILE = "time_corrections.json"


class TimeFixError(Exception):
    """A deployment's images can't be read or fixed."""


def _dir(folder: str) -> Path:
    path = Path(folder).expanduser() if folder else None
    if path is None or not path.is_dir():
        raise TimeFixError(f"'{folder}' is not a folder.")
    return path


def _images(folder: Path) -> list[Path]:
    return sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in dis.IMAGE_EXTENSIONS), key=lambda p: dis._natural_key(Path(p.name)))


def read_corrections(folder: Path) -> list[dict]:
    try:
        data = json.loads((folder / CORRECTIONS_FILE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _record(folder: Path, entry: dict) -> None:
    try:
        user = getpass.getuser()
    except Exception:
        user = None
    entries = read_corrections(folder)
    entries.append({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "by": user, **entry})
    (folder / CORRECTIONS_FILE).write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")


def _when(visit: dict) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(f"{visit['date']}T{visit['time']}")
    except (KeyError, ValueError, TypeError):
        return None


def visit_period(research_project_id: str, location_id: str, date: str, time: str, settings: config.Settings | None = None) -> tuple[dt.datetime, dt.datetime]:
    """The period of the deployment a visit started, as the cameras' clock shows it: from that visit to the next one at the same
    location that collected the card (local_folder_service.closes_collection). The visits' own date and time are the field's wall clock.

    Raises:
        TimeFixError: the visit isn't in the research project, or no later visit collected its card.
    """
    try:
        visits = local_folder_service.list_visits(config.collections_dir(settings), research_project_id, location_id)
    except local_folder_service.LocalFolderError as exc:
        raise TimeFixError(str(exc)) from exc
    visits = sorted((v for v in visits if _when(v)), key=_when)
    index = next((i for i, v in enumerate(visits) if v.get("date") == date and v.get("time") == time), None)
    if index is None:
        raise TimeFixError(f"There is no visit to {location_id} on {date} at {time} in {research_project_id}.")
    end = next((v for v in visits[index + 1:] if local_folder_service.closes_collection(v)), None)
    if end is None:
        raise TimeFixError(f"No visit to {location_id} after {date} {time} collected the card, so the deployment has no end yet.")
    return _when(visits[index]), _when(end)


def timeline(folder: str, period: tuple[dt.datetime, dt.datetime] | None = None, settings: config.Settings | None = None) -> dict:
    """The images of a folder in the camera's order, when each says it was taken, the segments they make and how each
    fits the deployment's period — with an offset suggested for those that don't — and the fixes made so far.

    Raises:
        TimeFixError: the folder doesn't exist.
    """
    settings = settings or config.load_settings()
    folder = _dir(folder)
    images = _images(folder)
    times = parallel.pmap(dis._image_datetime, images, settings.GENERAL.workers)
    tolerance = dt.timedelta(hours=settings.POSTVALIDATION.tolerance_hours)
    lo, hi = (period[0] - tolerance, period[1] + tolerance) if period else (None, None)

    def inside(t: dt.datetime) -> bool:
        return lo is None or lo <= t <= hi

    # Segments: runs of dated images whose time never goes backwards, in the camera's order.
    segments: list[dict] = []
    previous = None
    for index, (path, when) in enumerate(zip(images, times)):
        if when is None:
            continue
        if previous is None or when < previous:
            segments.append({"first_index": index, "first": path.name, "first_time": when, "count": 0, "inside": 0})
        segment = segments[-1]
        segment.update(last_index=index, last=path.name, last_time=when)
        segment["count"] += 1
        segment["inside"] += inside(when)
        previous = when
    for i, segment in enumerate(segments):
        suggestion = None
        if period and segment["inside"] < segment["count"]:
            if i == 0:
                target, why = period[0], "so that it starts when the deployment started"
            else:
                target, why = segments[i - 1]["last_time"] + dt.timedelta(seconds=1), "so that it goes on from where the one before ended"
            offset = int((target - segment["first_time"]).total_seconds())
            suggestion = {"offset_seconds": offset, "why": why}
        segment["suggestion"] = suggestion
        segment["state"] = "ok" if segment["inside"] == segment["count"] else ("outside" if segment["inside"] == 0 else "partly")
    for segment in segments:
        segment["first_time"] = segment["first_time"].isoformat()
        segment["last_time"] = segment["last_time"].isoformat()
    undated = [p.name for p, t in zip(images, times) if t is None]
    outside = sum(1 for t in times if t is not None and not inside(t))
    problems = []
    if undated:
        problems.append(f"{len(undated)} image(s) have no date.")
    if len(segments) > 1:
        problems.append(f"The time goes backwards {len(segments) - 1} time(s): the images make {len(segments)} segments.")
    if outside:
        problems.append(f"{outside} image(s) were taken outside the deployment's period.")
    if not period:
        problems.append("No visit was chosen: the dates can't be checked against the deployment's period.")
    return {
        "folder": str(folder),
        "period": {"start": period[0].isoformat(), "end": period[1].isoformat()} if period else None,
        "tolerance_hours": settings.POSTVALIDATION.tolerance_hours,
        "images": [{"name": p.name, "time": t.isoformat() if t else None} for p, t in zip(images, times)],
        "segments": segments, "undated": undated, "outside": outside, "problems": problems, "ok": not problems,
        "corrections": read_corrections(folder),
    }


def _run(images: list[Path], first: str, last: str | None) -> list[Path]:
    names = [p.name for p in images]
    if first not in names:
        raise TimeFixError(f"There is no image {first} in the folder.")
    end = names.index(last) if last else len(names) - 1
    if last and last not in names:
        raise TimeFixError(f"There is no image {last} in the folder.")
    start = names.index(first)
    if end < start:
        raise TimeFixError(f"{last} comes before {first}.")
    return images[start:end + 1]


def _shift_argument(offset_seconds: int) -> str:
    """ExifTool's shift, "Y:M:D h:m:s", for an offset in seconds: "-AllDates+=0:0:400 5:30:15"."""
    sign = "+" if offset_seconds >= 0 else "-"
    days, rest = divmod(abs(offset_seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"-AllDates{sign}=0:0:{days} {hours}:{minutes}:{seconds}"


def shift(folder: str, period: tuple[dt.datetime, dt.datetime] | None, first: str, last: str | None, offset_seconds: int,
          reason: str = "", settings: config.Settings | None = None) -> dict:
    """Moves the date and time of the images from first to last (to the end when last is None), in the camera's order,
    by offset_seconds. Returns the timeline after it.

    Raises:
        TimeFixError: no such images, no ExifTool, or ExifTool fails.
    """
    settings = settings or config.load_settings()
    path = _dir(folder)
    if not offset_seconds:
        raise TimeFixError("An offset of 0 changes nothing.")
    exiftool = camera_info.exiftool_path()
    if exiftool is None:
        raise TimeFixError("Fixing the dates needs ExifTool, and it isn't installed.")
    run = _run(_images(path), first, last)
    argfile = path / ".timefix-args.txt"
    argfile.write_text("\n".join(str(p) for p in run) + "\n", encoding="utf-8")
    try:
        result = subprocess.run([exiftool, "-charset", "filename=utf8", "-overwrite_original", "-P", _shift_argument(offset_seconds), "-@", str(argfile)],
                                capture_output=True, text=True, check=False)
    finally:
        argfile.unlink(missing_ok=True)
    if result.returncode != 0:
        raise TimeFixError(f"ExifTool could not change the dates: {(result.stderr or result.stdout).strip()}")
    _record(path, {"action": "shift", "first": run[0].name, "last": run[-1].name, "count": len(run), "offset_seconds": offset_seconds, "reason": reason.strip() or None})
    logger.info("%s: %d image(s) from %s shifted by %d s", path.name, len(run), run[0].name, offset_seconds)
    return timeline(folder, period, settings)


def remove(folder: str, period: tuple[dt.datetime, dt.datetime] | None, names: list[str], reason: str = "",
           settings: config.Settings | None = None) -> dict:
    """Takes images whose time can't be made right out of the folder: they are deleted, and their names written down.
    Returns the timeline after it.

    Raises:
        TimeFixError: an image isn't in the deployment, or none is given.
    """
    settings = settings or config.load_settings()
    path = _dir(folder)
    present = {p.name: p for p in _images(path)}
    missing = [n for n in names if n not in present]
    if not names:
        raise TimeFixError("No image chosen to remove.")
    if missing:
        raise TimeFixError(f"Not in the folder: {', '.join(missing[:5])}.")
    for name in names:
        present[name].unlink()
    _record(path, {"action": "remove", "names": names, "count": len(names), "reason": reason.strip() or None})
    logger.info("%s: %d image(s) removed for their time", path.name, len(names))
    return timeline(folder, period, settings)

