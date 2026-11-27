"""The settings of the preprocessing — the section PREPROCESSING of settings.toml —: the steps a new import starts with, and their values. Registered
with the module of the settings."""
from __future__ import annotations

from dataclasses import dataclass

from wildintel_uploader.modules.settings.domain.registry import settings_registry
from wildintel_uploader.modules.settings.domain.rules import in_range, tidy_field


@settings_registry.section("PREPROCESSING", "preprocessing", order=90)
@dataclass(frozen=True)
class PreprocessingSettings:
    """What is done to the images as they go into their collection: the steps a new import starts with, and their values."""
    rename: bool = True                     # <DEPLOYMENT>__<YYYYMMDD>_<n>.<EXT>
    resize: bool = True
    resize_width: int = 2400                # images wider than this are resized to it
    metadata: bool = True                   # authorship, rights and license as XMP
    owner: str = ""
    publisher: str = ""
    coverage: str = ""                      # where the images were taken; blank, the location of the deployment
    license_url: str = "https://creativecommons.org/licenses/by-nc/4.0/"
    ignore_dst: bool = True                 # the camera's clock read as if it never changed to summer time
    convert_to_utc: bool = True             # the capture dates, in names and metadata, in UTC

    def __post_init__(self) -> None:
        in_range("PREPROCESSING.resize_width", self.resize_width, 100, 20000)
        for name in ("owner", "publisher", "coverage", "license_url"):
            tidy_field(self, name, (getattr(self, name) or "").strip())
