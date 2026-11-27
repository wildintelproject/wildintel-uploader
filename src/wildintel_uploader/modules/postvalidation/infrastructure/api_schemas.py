"""The web API of the postvalidation as JSON — what the requests send, for entrypoints/api/postvalidation.py."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from wildintel_uploader.shared.camtrap import DeploymentFields

DeploymentCheck = Literal[
    "deployment_id", "collection_prefix", "collection_name", "location", "time_range", "camera",
    "image_count", "sequence_count", "sequence_length", "sd_card", "photo_count",
]


class StatisticsParams(BaseModel):
    """What the statistical checks mean by a sequence and by similar (see services.statistics_service)."""

    # A sequence starts when the gap to the previous image is at least this many seconds.
    sequence_gap_seconds: float = Field(default=60.0, gt=0, le=86400)
    # How many previous revisions of the location are needed to judge at all.
    min_revisions: int = Field(default=2, ge=1, le=50)
    method: Literal["median", "mean", "last", "range"] = "median"
    # What is similar, in percent, for each statistic.
    image_count_tolerance: float = Field(default=50.0, ge=0, le=1000)
    sequence_count_tolerance: float = Field(default=50.0, ge=0, le=1000)
    sequence_length_tolerance: float = Field(default=50.0, ge=0, le=1000)


class VisitCheckInfo(BaseModel):
    """What the visit the deployment is of says, for the checks against it: the card it left, and the photos counted when it was collected."""

    left_session: Optional[str] = None  # the visit that left the camera
    left_sd: Optional[str] = None  # the card it left in it
    collected_session: Optional[str] = None  # the visit that collected the card
    counted_photos: Optional[int] = Field(default=None, ge=0)  # the photos it counted on the card
    sd_card: Optional[str] = None  # the card the images are said to come from
    # how the visit that collected the card found it: a full card or flat batteries say why the camera stopped before it was collected
    collected_card_status: Optional[str] = None  # OK or CardFull
    collected_battery_status: Optional[str] = None  # OK or NoBatteries


class ValidateDeploymentRequest(BaseModel):
    """Checks a scanned folder's images against a deployment's own declared
    fields — run once the deployment (new or existing) is known."""

    path: str
    deployment: DeploymentFields
    # None runs every check.
    checks: Optional[list[DeploymentCheck]] = None
    # The collection the deployment goes in, when it has a folder of its own (the
    # "Local folder" destination: its name). None for a Trapper deployment, whose
    # collection is the one its id names.
    collection_name: Optional[str] = None
    # The location chosen as where the images were taken, to compare the id's with.
    expected_location_id: Optional[str] = None
    # Hours of leeway around the deployment's start and end for the images' dates.
    tolerance_hours: float = Field(default=1.0, ge=0)
    # The research project whose collections hold the previous revisions of the location.
    research_project_id: Optional[str] = None
    statistics: StatisticsParams = Field(default_factory=StatisticsParams)
    # The visit the deployment is of, for the checks of the card and of the photos (none: they have nothing to compare with).
    visit: Optional[VisitCheckInfo] = None
