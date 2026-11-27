"""The settings of the prevalidation — the section VALIDATION of settings.toml —: which checks of the images an import offers, how they start, how
a camera is told and the EXIF fields every image should have. Registered with the module of the settings, which puts them together with the rest."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from wildintel_uploader.modules.settings.domain.registry import settings_registry
from wildintel_uploader.modules.settings.domain.rules import check_levels, exif_name, tidy_field


IMAGE_CHECKS = ("corrupted", "sequence", "structure", "camera", "exif", "duplicates")
# As they started before they could be set: they all warn.
IMAGE_CHECK_DEFAULTS: Mapping[str, str] = {c: "warn" for c in IMAGE_CHECKS}


@settings_registry.section("VALIDATION", "validation", order=70)
@dataclass(frozen=True)
class ValidationSettings:
    """Which checks of the images an import offers — each looks at the folder alone —, and how they start."""
    corrupted: bool = True
    sequence: bool = True
    structure: bool = True
    camera: bool = True
    # How two images are told to be of the same camera: levels of EXIF fields, the most reliable first — the first level every image has is used.
    camera_levels: tuple[tuple[str, ...], ...] = (("SerialNumber",), ("Make", "Model"), ("Model",))
    exif: bool = True
    # The EXIF fields expected on every image besides the capture date (DateTimeOriginal), which is always expected.
    exif_fields: tuple[str, ...] = ("Model",)
    duplicates: bool = True
    defaults: Mapping[str, str] = field(default_factory=lambda: dict(IMAGE_CHECK_DEFAULTS))

    def __post_init__(self) -> None:
        # each level its fields once, as written, and each level once; a level with no field is left out
        levels: list[tuple[str, ...]] = []
        for level in self.camera_levels:
            names: list[str] = []
            for name in ((level,) if isinstance(level, str) else level):
                name = exif_name("VALIDATION.camera_levels", name)
                if name.lower() not in (n.lower() for n in names):
                    names.append(name)
            if names and [n.lower() for n in names] not in ([n.lower() for n in kept] for kept in levels):
                levels.append(tuple(names))
        tidy_field(self, "camera_levels", tuple(levels))
        # each field once, as written; the capture date is always expected, so it is not one of them
        exif: list[str] = []
        for name in self.exif_fields:
            name = exif_name("VALIDATION.exif_fields", name)
            if name.lower() != "datetimeoriginal" and name.lower() not in (n.lower() for n in exif):
                exif.append(name)
        tidy_field(self, "exif_fields", tuple(exif))
        tidy_field(self, "defaults", check_levels("VALIDATION.defaults", self.defaults, IMAGE_CHECKS, IMAGE_CHECK_DEFAULTS))
