"""What the validators of a deployment are told of it — its fields, the collection, the location chosen, the visit, the camera of the catalog —
and what they share: the results {"ok", "message"}, the names of wildintel-tools, the dates."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import DEFAULT_CAMERA_LEVELS

DEFAULT_TOLERANCE_HOURS = 1.0

# wildintel-tools' own naming rules (see its check_collections): a deployment is "R0033-DONA_01[_suffix]" and lives in a collection "R0033[_suffix]".
DEPLOYMENT_ID_RE = re.compile(r"^R[0-9]{4}-([0-9A-Za-z_-]+)(_.+)?$")
COLLECTION_NAME_RE = re.compile(r"^R[0-9]{4}(_.+)?$")


class PostvalidationError(ValueError):
    """What can't be checked at all: a folder that isn't one, a negative tolerance."""


@dataclass(frozen=True)
class Deployment:
    """What the checks need of a deployment: its id, its dates (ISO 8601) and the model of its camera."""
    deployment_id: str
    start_date: str | None = None
    end_date: str | None = None
    camera_model: str | None = None
    camera_id: str | None = None             # the label of its camera in the catalog



@dataclass(frozen=True)
class StatisticsParameters:
    """What the statistical checks mean by a sequence and by similar: the images of a sequence are at most `sequence_gap_seconds` apart; a revision
    is judged against at least `min_revisions` before it, by their `method` (median, mean, last, range), and is similar when it is within the
    tolerance of each, in percent. The settings say them (POSTVALIDATION); these are their defaults."""
    sequence_gap_seconds: float = 60.0
    min_revisions: int = 2
    method: str = "median"
    image_count_tolerance: float = 50.0
    sequence_count_tolerance: float = 50.0
    sequence_length_tolerance: float = 50.0

    def tolerance(self, check: str) -> float:
        """The tolerance of a statistical check: "image_count", "sequence_count" or "sequence_length"."""
        return float(getattr(self, f"{check}_tolerance"))

@dataclass(frozen=True)
class DeploymentContext:
    """What the wizard knows of a deployment, for the checks of it: the collection it goes in (none: the one its id names), the location chosen,
    the leeway of the dates, the visit it is of, the record of its camera in the catalog, and how a camera is told."""
    deployment: Deployment
    collection: str | None = None
    expected_location_id: str | None = None
    tolerance_hours: float = DEFAULT_TOLERANCE_HOURS
    visit: dict | None = None
    camera: dict | None = None
    camera_levels: list[list[str]] = field(default_factory=lambda: [list(level) for level in DEFAULT_CAMERA_LEVELS])
    # the research project whose collections hold the previous revisions of the location, and what the statistical checks mean by a sequence and
    # by similar
    research_project_id: str | None = None
    statistics: StatisticsParameters = field(default_factory=StatisticsParameters)
    # the previous revisions of the location — statistics.Revision —, for the statistical checks: none, there is no history to judge by
    previous: tuple = ()


def ok(message: str) -> dict:
    return {"ok": True, "message": message}


def problem(message: str) -> dict:
    return {"ok": False, "message": message}


def natural_key(path: Path | str) -> list:
    """Sorts "IMG_2" before "IMG_10" — the order wildintel-tools walks a deployment's images in."""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", str(path))]


def parse_iso(value: str | None) -> datetime | None:
    """An ISO date as the camera's wall clock: EXIF dates are local, so the designator is dropped to compare like with like."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        return None


def collection_of(deployment_id: str) -> str | None:
    match = re.match(r"^(R[0-9]{4})-", deployment_id)
    return match.group(1) if match else None


def collection_for(context: DeploymentContext) -> str | None:
    """The collection a deployment goes in: a Trapper deployment has no folder of its own, and goes in the one its id names."""
    return context.collection if context.collection is not None else collection_of(context.deployment.deployment_id)


def same_text(a: str | None, b: str | None) -> bool:
    """Two values of a camera are the same one whatever their case and their spaces: "Browning  BTC-8A" is "browning btc-8a"."""
    norm = lambda v: " ".join(str(v or "").split()).casefold()  # noqa: E731
    return norm(a) == norm(b)
