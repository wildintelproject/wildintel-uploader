"""The statistics of the postvalidation, in plain Python: is this revision of a location like the ones before it? About as many photos, about as many
sequences, sequences about as long. "What is a sequence" and "what is similar" are parameters: a sequence starts when the gap to the previous image
is at least `sequence_gap_seconds`; a value is similar when it is within `tolerance_percent` of the reference — the median, the mean or the last of
the previous revisions — or, with the "range" method, within the range they span, each end widened by the tolerance."""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from typing import Literal

from wildintel_uploader.modules.postvalidation.domain.models import PostvalidationError

Method = Literal["median", "mean", "last", "range"]
METHODS: tuple[str, ...] = ("median", "mean", "last", "range")
_DEPLOYMENT_RE = re.compile(r"^R(\d{4})-(.+)$")


@dataclass(frozen=True)
class DeploymentTimes:
    """One deployment's images: how many there are, and when each dated one was taken."""

    image_count: int
    times: list[float]  # seconds since the epoch, sorted

    def sequences(self, gap_seconds: float) -> list[int]:
        """The images in each sequence — a new one starts when the gap to the previous image is at least gap_seconds."""
        return sequence_lengths(self.times, gap_seconds)


def sequence_lengths(times: list[float], gap_seconds: float) -> list[int]:
    """The number of images in each sequence of the (sorted) times. A gap of exactly
    gap_seconds starts a new one: "at least X seconds"."""
    lengths: list[int] = []
    previous: float | None = None
    for t in sorted(times):
        if previous is None or t - previous >= gap_seconds:
            lengths.append(1)
        else:
            lengths[-1] += 1
        previous = t
    return lengths


@dataclass(frozen=True)
class Revision:
    """A previous revision of the location: its number, its deployment, and when its images were taken."""
    revision: int
    deployment_id: str
    times: DeploymentTimes


def fmt(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") if value != int(value) else str(int(value))


def compare(value: float, previous: list[float], *, method: str, tolerance_percent: float, min_revisions: int) -> dict:
    """Whether `value` is similar to the `previous` revisions' values, and why.

    Returns {"ok", "skipped", "value", "reference", "lower", "upper", "previous"}: skipped
    (and ok) when there aren't min_revisions previous values to go by.
    """
    if method not in METHODS:
        raise PostvalidationError(f"Unknown method '{method}' — use one of {', '.join(METHODS)}.")
    base = {"value": value, "previous": len(previous), "reference": None, "lower": None, "upper": None}
    if len(previous) < max(min_revisions, 1):
        return {**base, "ok": True, "skipped": True}
    tolerance = tolerance_percent / 100
    reference = {
        "median": lambda: statistics.median(previous), "mean": lambda: statistics.fmean(previous),
        "last": lambda: previous[-1], "range": lambda: statistics.median(previous),
    }[method]()
    if method == "range":
        lower, upper = min(previous) * (1 - tolerance), max(previous) * (1 + tolerance)
    else:
        lower, upper = reference * (1 - tolerance), reference * (1 + tolerance)
    return {**base, "ok": lower <= value <= upper, "skipped": False, "reference": reference, "lower": lower, "upper": upper}


def describe(label: str, unit: str, result: dict, *, method: str, tolerance_percent: float, min_revisions: int, location: str) -> str:
    if result["skipped"]:
        return (f"Not enough history to judge the {label}: {result['previous']} previous revision(s) of {location} found, "
                f"{max(min_revisions, 1)} needed.")
    allowed = f"{fmt(result['lower'])}–{fmt(result['upper'])}"
    how = {"median": "the median of", "mean": "the mean of", "last": "the last of", "range": "the range of"}[method]
    verb = "is similar to" if result["ok"] else "is not similar to"
    return (f"The {label} ({fmt(result['value'])}{unit}) {verb} {how} the {result['previous']} previous revision(s) of {location} "
            f"(allowed {allowed}, ±{fmt(tolerance_percent)}%).")


STATISTIC_CHECKS = ("image_count", "sequence_count", "sequence_length")
LABELS = {"image_count": "number of images", "sequence_count": "number of sequences", "sequence_length": "length of the sequences"}
UNITS = {"image_count": "", "sequence_count": "", "sequence_length": " images per sequence"}


def metrics(times: DeploymentTimes, gap_seconds: float) -> dict[str, float]:
    lengths = times.sequences(gap_seconds)
    return {
        "image_count": float(times.image_count),
        "sequence_count": float(len(lengths)),
        "sequence_length": (sum(lengths) / len(lengths)) if lengths else 0.0,  # the mean number of images per sequence
    }


def judge(current: DeploymentTimes, previous: list[Revision], deployment_id: str, checks: frozenset[str], *, sequence_gap_seconds: float,
          min_revisions: int, method: str, tolerances: dict[str, float]) -> dict[str, dict]:
    """The statistical checks asked for, by name — each as compare() gives it plus "message" and "history" (the value in each previous revision
    that has images)."""
    wanted = [c for c in STATISTIC_CHECKS if c in checks]
    if not wanted:
        return {}
    match = _DEPLOYMENT_RE.match(deployment_id)
    location = match.group(2) if match else deployment_id
    histories = [(r, metrics(r.times, sequence_gap_seconds)) for r in previous if r.times.image_count > 0]
    now = metrics(current, sequence_gap_seconds)
    out: dict[str, dict] = {}
    for key in wanted:
        values = [m[key] for _, m in histories]
        tolerance = tolerances[key]
        result = compare(now[key], values, method=method, tolerance_percent=tolerance, min_revisions=min_revisions)
        result["message"] = describe(LABELS[key], UNITS[key], result, method=method, tolerance_percent=tolerance, min_revisions=min_revisions, location=location)
        result["history"] = [{"revision": r.revision, "deployment_id": r.deployment_id, "value": m[key]} for r, m in histories]
        out[key] = result
    return out
