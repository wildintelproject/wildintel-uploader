"""Statistical postvalidation of the deployments kept: is this revision of a location like the ones before it? — plain Python.

A location is visited again and again — R0001-DONA_0006_B, R0002-DONA_0006_B… — so what the previous revisions of it looked like says what
this one should: about as many photos, about as many sequences, sequences about as long. A revision that departs a lot (a camera that fired
nonstop, one that died early) is worth a look before it's uploaded. What is a sequence and what is similar are parameters (see
modules.postvalidation.domain.statistics, which judges them)."""
from __future__ import annotations

import collections
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from wildintel_uploader.modules.postvalidation.domain.statistics import DeploymentTimes, metrics as compared_metrics

_DEPLOYMENT_RE = re.compile(r"^R(\d{4})-(.+)$")
_COLLECTION_RE = re.compile(r"^R\d{4}(_.+)?$")
COMPARED = ("image_count", "images_per_day", "sequence_count", "sequence_length", "sequence_median", "sequence_max")


@dataclass(frozen=True)
class KeptDeployment:
    """A deployment kept in a collection of a research project: its revision and its location by its id."""
    revision: int
    deployment_id: str
    location: str
    where: object   # what the folders tell it by


def is_collection(name: str) -> bool:
    return bool(_COLLECTION_RE.match(name))


def revision_of(deployment_id: str) -> tuple[int, str] | None:
    """The revision and the location of a deployment's id (R0003-DONA_01 → 3, DONA_01), or None when it is not one's."""
    match = _DEPLOYMENT_RE.match(deployment_id)
    return (int(match.group(1)), match.group(2)) if match else None


def earlier(kept: list[KeptDeployment], deployment_id: str) -> list[KeptDeployment]:
    """The deployments of the same location with a lower revision — oldest first."""
    found = revision_of(deployment_id)
    if not found:
        return []
    revision, location = found[0], found[1].lower()
    return sorted((k for k in kept if k.revision < revision and k.location.lower() == location), key=lambda k: (k.revision, k.deployment_id))


def next_revision(kept: list[KeptDeployment], location_id: str) -> dict:
    """The revision a new deployment at this location is expected to be: one after the highest kept for it, or 1 if there is none. {"last", "next"}."""
    wanted = location_id.strip().lower()
    revisions = [k.revision for k in kept if wanted and k.location.lower() == wanted]
    last = max(revisions) if revisions else None
    return {"last": last, "next": (last or 0) + 1}


def sequence_length_counts(lengths: list[int]) -> list[list[int]]:
    """How many sequences have each number of images — [[1, 180], [2, 138]…], by length."""
    return [[length, n] for length, n in sorted(collections.Counter(lengths).items())]


def longest_sequence(times: list[float], gap_seconds: float) -> dict | None:
    """The longest sequence (the first, if several tie): {"images", "start", "end", "seconds"} — the start and the end as the camera's wall clock."""
    ordered = sorted(times)
    best: tuple[int, float, float] | None = None
    start = 0
    for i in range(1, len(ordered) + 1):
        if i == len(ordered) or ordered[i] - ordered[i - 1] >= gap_seconds:
            if best is None or i - start > best[0]:
                best = (i - start, ordered[start], ordered[i - 1])
            start = i
    if best is None:
        return None
    count, first, last = best
    wall = lambda t: datetime.fromtimestamp(t, timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")  # noqa: E731
    return {"images": count, "start": wall(first), "end": wall(last), "seconds": last - first}


def images_per_calendar_day(times: list[float]) -> list[dict]:
    """The images of each calendar day from the first image's to the last's — [{"date", "images"}] —, a day with none counting 0. The times are the
    camera's wall clock (stood as UTC), so the date is the one the camera showed."""
    if not times:
        return []
    counts: dict = {}
    for t in times:
        day = datetime.fromtimestamp(t, timezone.utc).date()
        counts[day] = counts.get(day, 0) + 1
    first, last = min(counts), max(counts)
    return [{"date": (first + timedelta(days=i)).isoformat(), "images": counts.get(first + timedelta(days=i), 0)} for i in range((last - first).days + 1)]


def sequences_per_calendar_day(times: list[float], gap_seconds: float) -> list[dict]:
    """The sequences that began each calendar day from the first image's to the last's — [{"date", "sequences"}] —, a day with none counting 0."""
    ordered = sorted(times)
    if not ordered:
        return []
    starts = [t for i, t in enumerate(ordered) if i == 0 or t - ordered[i - 1] >= gap_seconds]
    first = datetime.fromtimestamp(ordered[0], timezone.utc).date()
    last = datetime.fromtimestamp(ordered[-1], timezone.utc).date()
    counts = [0] * ((last - first).days + 1)
    for t in starts:
        counts[(datetime.fromtimestamp(t, timezone.utc).date() - first).days] += 1
    return [{"date": d["date"], "sequences": n} for d, n in zip(images_per_calendar_day(ordered), counts)]


def deployment_metrics(times: DeploymentTimes, gap_seconds: float) -> dict:
    """What a deployment's images look like: the three compared metrics (image_count, sequence_count, sequence_length) plus the days it covers,
    images_per_day, the median and the longest sequence, the first and last image, and the histograms: "daily", "sequences_daily",
    "sequence_lengths" and "longest_sequence"."""
    lengths = times.sequences(gap_seconds)
    days = (times.times[-1] - times.times[0]) / 86400 if len(times.times) > 1 else 0.0
    return {
        **compared_metrics(times, gap_seconds),
        "days": days if days > 0 else None,
        "images_per_day": (times.image_count / days) if days > 0 else None,
        "daily": images_per_calendar_day(times.times),
        "sequences_daily": sequences_per_calendar_day(times.times, gap_seconds),
        "sequence_lengths": sequence_length_counts(lengths),
        "longest_sequence": longest_sequence(times.times, gap_seconds),
        "sequence_median": float(statistics.median(lengths)) if lengths else 0.0,
        "sequence_max": float(max(lengths)) if lengths else 0.0,
        "first_image": times.times[0] if times.times else None,
        "last_image": times.times[-1] if times.times else None,
    }


def without_daily(metrics: dict) -> dict:
    """The metrics of a revision beside another: the histograms by day are of the deployment of the row only."""
    return {k: v for k, v in metrics.items() if k not in ("daily", "sequences_daily", "longest_sequence")}


def side_by_side(first: str, second: str, a: dict, b: dict) -> dict:
    """Two deployments side by side: {"first", "second", "metrics": {name: {"first", "second", "change_percent"}}} — change_percent None when the
    first is 0 or a value is missing."""
    out = {}
    for key in COMPARED:
        x, y = a[key], b[key]
        out[key] = {"first": x, "second": y, "change_percent": ((y - x) / x * 100) if x and y is not None else None}
    return {"first": first, "second": second, "metrics": out}
