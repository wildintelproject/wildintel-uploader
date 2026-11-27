"""The settings of the postvalidation — the section POSTVALIDATION of settings.toml —: which checks of a deployment an import offers (its statistical
ones too), how they start, and the parameters of those that take one. Registered with the module of the settings."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from wildintel_uploader.modules.settings.domain.registry import settings_registry
from wildintel_uploader.modules.settings.domain.rules import _check_levels, _in_range, _one_of, _set


DEPLOYMENT_CHECKS = ("deployment_id", "collection_prefix", "collection_name", "location", "time_range", "camera", "image_count", "sequence_count",
                     "sequence_length", "sd_card", "photo_count")
# As they started before they could be set: the dates of the images and the SD card have to pass, the rest warn.
DEPLOYMENT_CHECK_DEFAULTS: Mapping[str, str] = {c: ("required" if c in ("time_range", "sd_card") else "warn") for c in DEPLOYMENT_CHECKS}


SIMILARITY_METHODS = ("median", "mean", "last", "range")


@settings_registry.section("POSTVALIDATION", "postvalidation", order=80)
@dataclass(frozen=True)
class PostvalidationSettings:
    """Which checks of a deployment an import offers, how they start, and the parameters those that take one start from."""
    deployment_id: bool = True
    collection_prefix: bool = True
    collection_name: bool = True
    location: bool = True
    time_range: bool = True
    camera: bool = True
    image_count: bool = True
    sequence_count: bool = True
    sequence_length: bool = True
    sd_card: bool = True
    photo_count: bool = True
    defaults: Mapping[str, str] = field(default_factory=lambda: dict(DEPLOYMENT_CHECK_DEFAULTS))
    sequence_gap_seconds: float = 60.0      # a new sequence starts when the gap to the image before is at least this
    min_revisions: int = 2                  # how many previous revisions the statistical checks need to judge
    similarity_method: str = "median"       # what this revision is compared to: the median, the mean, the last one or the range of the previous ones
    image_count_tolerance: float = 50.0     # percent
    sequence_count_tolerance: float = 50.0
    sequence_length_tolerance: float = 50.0
    tolerance_hours: float = 1.0            # leeway around the start and the end when the dates of the images are checked

    def __post_init__(self) -> None:
        _set(self, "defaults", _check_levels("POSTVALIDATION.defaults", self.defaults, DEPLOYMENT_CHECKS, DEPLOYMENT_CHECK_DEFAULTS))
        _in_range("POSTVALIDATION.sequence_gap_seconds", self.sequence_gap_seconds, 0, 86400, low_open=True)
        _in_range("POSTVALIDATION.min_revisions", self.min_revisions, 1, 50)
        _one_of("POSTVALIDATION.similarity_method", self.similarity_method, SIMILARITY_METHODS)
        for name in ("image_count_tolerance", "sequence_count_tolerance", "sequence_length_tolerance"):
            _in_range(f"POSTVALIDATION.{name}", getattr(self, name), 0, 1000)
        _in_range("POSTVALIDATION.tolerance_hours", self.tolerance_hours, 0, 8760)
