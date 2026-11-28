"""What the modules share of Camtrap DP (https://camtrap-dp.tdwg.org): a row of its "deployments" table, as Pydantic validates it — the record of a
deployment that the postvalidation, the preprocessing, the deployments and the uploaders all speak of — and its kinds of place (featureType)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# Camtrap DP's own "featureType" enum — deployments-table-schema.json.
FeatureType = Literal[
    "roadPaved", "roadDirt", "trailHiking", "trailGame", "roadUnderpass", "roadOverpass", "roadBridge",
    "culvert", "burrow", "nestSite", "carcass", "waterSource", "fruitingTree",
]


class DeploymentFields(BaseModel):
    """One row of the Camtrap Data Package "deployments" table — see
    https://camtrap-dp.tdwg.org (deployments-table-schema.json), whose field
    names and constraints this mirrors (deploymentID -> deployment_id, etc.):
    deploymentID, latitude, longitude, deploymentStart and deploymentEnd are
    required; the numeric ranges, integer types and the featureType enum
    apply; and cameraHeight/cameraDepth are mutually exclusive. The two dates
    are ISO 8601 with a timezone designator (Z or ±hh:mm)."""

    deployment_id: str = Field(min_length=1)
    location_id: Optional[str] = None
    location_name: Optional[str] = None

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_uncertainty: Optional[int] = Field(default=None, ge=1)

    # ISO 8601 with timezone designator — deploymentStart/deploymentEnd.
    start_date: str
    end_date: str

    setup_by: Optional[str] = None
    camera_id: Optional[str] = None
    camera_model: Optional[str] = None
    camera_interval: Optional[int] = Field(default=None, ge=0)  # cameraDelay
    # cameraHeight and cameraDepth are mutually exclusive in the standard.
    camera_height: Optional[float] = Field(default=None, ge=0)
    camera_depth: Optional[float] = Field(default=None, ge=0)
    camera_tilt: Optional[int] = Field(default=None, ge=-90, le=90)
    camera_heading: Optional[int] = Field(default=None, ge=0, le=360)
    detection_distance: Optional[float] = Field(default=None, ge=0)

    timestamp_issues: Optional[bool] = None
    bait_use: Optional[bool] = None
    feature_type: Optional[FeatureType] = None
    habitat: Optional[str] = None
    # deploymentGroups — the standard's single field for what Trapper keeps
    # as two (session/array), e.g. "season:winter 2020 | grid:A1".
    deployment_groups: Optional[str] = None
    comments: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("start_date", "end_date")
    @classmethod
    def _iso_8601(cls, value: str) -> str:
        if not _ISO_8601.fullmatch(value):
            raise ValueError("must be an ISO 8601 date and time with timezone designator: YYYY-MM-DDThh:mm:ssZ or YYYY-MM-DDThh:mm:ss±hh:mm")
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("is not a valid date and time") from exc
        return value

    @model_validator(mode="after")
    def _starts_before_it_ends(self) -> "DeploymentFields":
        # Both dates are known to be valid ISO 8601 with a designator by now.
        if datetime.fromisoformat(self.start_date) >= datetime.fromisoformat(self.end_date):
            raise ValueError("deploymentStart must be earlier than deploymentEnd")
        return self

    @model_validator(mode="after")
    def _height_or_depth(self) -> "DeploymentFields":
        if self.camera_height is not None and self.camera_depth is not None:
            raise ValueError("camera_height and camera_depth are mutually exclusive — set only one")
        return self


_ISO_8601 = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]\d{2}:\d{2})")
