"""The rules of the fixes of the dates — plain Python, over what the images say and what the visits say.

A camera's clock goes wrong: it is reset to its factory date when the batteries run out, someone sets it an hour or a day off, it jumps when the
settings are lost halfway. The images of a copied card, in the order the camera numbered them, are split where the time goes backwards — each
piece a *segment*, taken with one setting of the clock. Each segment is set against the deployment's period (the visits', in the cameras' clock),
and for one outside it an offset is suggested: the first segment to start at the deployment's start, a later one to go on from where the one
before ended."""
from __future__ import annotations

import datetime as dt
from typing import cast

from wildintel_uploader.modules.timefix.domain.ports import Period, TimeFixError
from wildintel_uploader.modules.visits.domain.for_the_timefix import closes_collection
from wildintel_uploader.modules.visits.domain.shapes import Visit


def _when(visit: dict) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(f"{visit['date']}T{visit['time']}")
    except (KeyError, ValueError, TypeError):
        return None


def deployment_period(visits: list[dict], research_project_id: str, location_id: str, date: str, time: str) -> Period:
    """The period of the deployment a visit started, as the cameras' clock shows it: from that visit to the next one at the same location that
    collected the card (the rules of the visits). `visits` are those of the location; their date and time are the field's wall clock.

    Raises:
        TimeFixError: the visit isn't there, or no later visit collected its card.
    """
    dated = sorted((v for v in visits if _when(v)), key=lambda v: _when(v) or dt.datetime.min)
    index = next((i for i, v in enumerate(dated) if v.get("date") == date and v.get("time") == time), None)
    if index is None:
        raise TimeFixError(f"There is no visit to {location_id} on {date} at {time} in {research_project_id}.")
    end = next((v for v in dated[index + 1:] if closes_collection(cast(Visit, v))), None)
    if end is None:
        raise TimeFixError(f"No visit to {location_id} after {date} {time} collected the card, so the deployment has no end yet.")
    return cast(dt.datetime, _when(dated[index])), cast(dt.datetime, _when(end))   # dated: each has its date and time


def segments(names: list[str], times: list[dt.datetime | None], period: Period | None, tolerance: dt.timedelta) -> list[dict]:
    """The runs of dated images whose time never goes backwards, in the camera's order; how each fits the period (widened by the tolerance) — its
    state — and the offset suggested for one that doesn't."""
    lo, hi = (period[0] - tolerance, period[1] + tolerance) if period else (None, None)
    out: list[dict] = []
    previous = None
    for index, (name, when) in enumerate(zip(names, times)):
        if when is None:
            continue
        if previous is None or when < previous:
            out.append({"first_index": index, "first": name, "first_time": when, "count": 0, "inside": 0})
        segment = out[-1]
        segment.update(last_index=index, last=name, last_time=when)
        segment["count"] += 1
        segment["inside"] += int(lo is None or hi is None or lo <= when <= hi)
        previous = when
    for i, segment in enumerate(out):
        suggestion = None
        if period and segment["inside"] < segment["count"]:
            if i == 0:
                target, why = period[0], "so that it starts when the deployment started"
            else:
                target, why = out[i - 1]["last_time"] + dt.timedelta(seconds=1), "so that it goes on from where the one before ended"
            suggestion = {"offset_seconds": int((target - segment["first_time"]).total_seconds()), "why": why}
        segment["suggestion"] = suggestion
        segment["state"] = "ok" if segment["inside"] == segment["count"] else ("outside" if segment["inside"] == 0 else "partly")
    for segment in out:
        segment["first_time"], segment["last_time"] = segment["first_time"].isoformat(), segment["last_time"].isoformat()
    return out


def timeline(folder: str, names: list[str], times: list[dt.datetime | None], period: Period | None, tolerance_hours: float,
             corrections: list[dict]) -> dict:
    """The images of a folder in the camera's order, when each says it was taken, their segments, what is wrong with them and the fixes made."""
    tolerance = dt.timedelta(hours=tolerance_hours)
    lo, hi = (period[0] - tolerance, period[1] + tolerance) if period else (None, None)
    found = segments(names, times, period, tolerance)
    undated = [n for n, t in zip(names, times) if t is None]
    outside = sum(1 for t in times if t is not None and lo is not None and hi is not None and not lo <= t <= hi)
    problems = []
    if undated:
        problems.append(f"{len(undated)} image(s) have no date.")
    if len(found) > 1:
        problems.append(f"The time goes backwards {len(found) - 1} time(s): the images make {len(found)} segments.")
    if outside:
        problems.append(f"{outside} image(s) were taken outside the deployment's period.")
    if not period:
        problems.append("No visit was chosen: the dates can't be checked against the deployment's period.")
    return {
        "folder": folder,
        "period": {"start": period[0].isoformat(), "end": period[1].isoformat()} if period else None,
        "tolerance_hours": tolerance_hours,
        "images": [{"name": n, "time": t.isoformat() if t else None} for n, t in zip(names, times)],
        "segments": found, "undated": undated, "outside": outside, "problems": problems, "ok": not problems,
        "corrections": corrections,
    }


def run_of(names: list[str], first: str, last: str | None) -> tuple[int, int]:
    """Where a run of images starts and ends, in the camera's order — to the last image when `last` is None.

    Raises:
        TimeFixError: an image that isn't there, or a run that goes backwards.
    """
    if first not in names:
        raise TimeFixError(f"There is no image {first} in the folder.")
    if last and last not in names:
        raise TimeFixError(f"There is no image {last} in the folder.")
    start, end = names.index(first), names.index(last) if last else len(names) - 1
    if end < start:
        raise TimeFixError(f"{last} comes before {first}.")
    return start, end


def images_to_remove(names: list[str], chosen: list[str]) -> list[str]:
    """The images chosen to be taken out, which must all be there.

    Raises:
        TimeFixError: none chosen, or one that isn't there.
    """
    if not chosen:
        raise TimeFixError("No image chosen to remove.")
    missing = [n for n in chosen if n not in names]
    if missing:
        raise TimeFixError(f"Not in the folder: {', '.join(missing[:5])}.")
    return chosen
