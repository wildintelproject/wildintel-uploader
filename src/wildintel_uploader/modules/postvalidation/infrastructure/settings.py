"""The section POSTVALIDATION of settings.toml as Pydantic reads and writes it — registered with the module of the settings."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from wildintel_uploader.modules.postvalidation.domain.settings import DEPLOYMENT_CHECK_DEFAULTS, DEPLOYMENT_CHECKS
from wildintel_uploader.modules.settings.domain.registry import settings_registry
from wildintel_uploader.modules.settings.domain.rules import CheckLevel, check_defaults


@settings_registry.schema("POSTVALIDATION")
class PostvalidationSettings(BaseModel):
    """Which of the postvalidation checks the wizard shows — and so runs — and
    the parameters those that take one start from. They need what the wizard
    knows of the deployment: its id, collection, location and dates."""

    deployment_id: bool = Field(default=True, description="Deployment id format. (POSTVALIDATION.deployment_id)")
    collection_prefix: bool = Field(default=True, description="Deployment id starts with its collection. (POSTVALIDATION.collection_prefix)")
    collection_name: bool = Field(default=True, description="Collection name. (POSTVALIDATION.collection_name)")
    location: bool = Field(default=True, description="The id's location is the one chosen. (POSTVALIDATION.location)")
    time_range: bool = Field(default=True, description="Image dates fit the deployment. (POSTVALIDATION.time_range)")
    camera: bool = Field(default=True, description="Camera consistency. (POSTVALIDATION.camera)")
    image_count: bool = Field(default=True, description="The number of images is like the previous revisions'. (POSTVALIDATION.image_count)")
    sequence_count: bool = Field(default=True, description="The number of sequences is like the previous revisions'. (POSTVALIDATION.sequence_count)")
    sequence_length: bool = Field(default=True, description="The length of the sequences is like the previous revisions'. (POSTVALIDATION.sequence_length)")
    sd_card: bool = Field(default=True, description="The SD card is the one the visit left in the camera. (POSTVALIDATION.sd_card)")
    photo_count: bool = Field(default=True, description="The folder has the number of images the visit counted on the card. (POSTVALIDATION.photo_count)")
    defaults: dict[str, CheckLevel] = Field(
        default_factory=lambda: dict(DEPLOYMENT_CHECK_DEFAULTS),
        description="How each check starts in an import, when it is on: required (it has to pass), warn or skip (offered unticked). (POSTVALIDATION.defaults)",
    )

    @field_validator("defaults", mode="before")
    @classmethod
    def _defaults(cls, value):
        return check_defaults(value, DEPLOYMENT_CHECKS, DEPLOYMENT_CHECK_DEFAULTS)
    sequence_gap_seconds: float = Field(
        default=60.0, gt=0, le=86400,
        description="What a sequence is: a new one starts when the gap to the previous image is at least this many seconds. (POSTVALIDATION.sequence_gap_seconds)",
    )
    min_revisions: int = Field(
        default=2, ge=1, le=50,
        description="How many previous revisions of the location the statistical checks need to have to judge — with fewer they are skipped. (POSTVALIDATION.min_revisions)",
    )
    similarity_method: Literal["median", "mean", "last", "range"] = Field(
        default="median",
        description="What this revision is compared to: the median or mean of the previous ones, the last one, or the range they span. (POSTVALIDATION.similarity_method)",
    )
    image_count_tolerance: float = Field(default=50.0, ge=0, le=1000, description="What is similar for the number of images, in percent. (POSTVALIDATION.image_count_tolerance)")
    sequence_count_tolerance: float = Field(default=50.0, ge=0, le=1000, description="What is similar for the number of sequences, in percent. (POSTVALIDATION.sequence_count_tolerance)")
    sequence_length_tolerance: float = Field(default=50.0, ge=0, le=1000, description="What is similar for the length of the sequences, in percent. (POSTVALIDATION.sequence_length_tolerance)")
    tolerance_hours: float = Field(
        default=1.0, ge=0, le=8760,
        description="Hours of leeway around the deployment's start and end when checking the image dates — the default of the tolerance the wizard asks for. (POSTVALIDATION.tolerance_hours)",
    )
