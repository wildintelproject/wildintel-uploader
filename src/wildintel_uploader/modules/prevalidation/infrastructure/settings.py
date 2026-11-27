"""The section VALIDATION of settings.toml as Pydantic reads and writes it — registered with the module of the settings, which puts the format of the
file together with it."""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from wildintel_uploader.modules.prevalidation.domain.settings import IMAGE_CHECK_DEFAULTS, IMAGE_CHECKS
from wildintel_uploader.modules.settings.domain.registry import settings_registry
from wildintel_uploader.modules.settings.domain.rules import CheckLevel, check_defaults


@settings_registry.schema("VALIDATION")
class ValidationSettings(BaseModel):
    """Which of the "Validate folder contents" checks the wizard shows — and
    so runs. Each looks at the folder alone, without knowing the deployment."""

    corrupted: bool = Field(default=True, description="Corrupted images. (VALIDATION.corrupted)")
    sequence: bool = Field(default=True, description="Shooting order vs. filename sequence. (VALIDATION.sequence)")
    structure: bool = Field(default=True, description="Folder structure (subdirectories). (VALIDATION.structure)")
    camera: bool = Field(default=True, description="Same camera on every image, as camera_levels tells it. (VALIDATION.camera)")
    camera_levels: list[list[str]] = Field(
        default_factory=lambda: [["SerialNumber"], ["Make", "Model"], ["Model"]],
        description="How two images are told to be of the same camera: levels of EXIF fields, by the names ExifTool gives them, the most reliable first — "
                    "the first level every image has is the one the images are compared by. (VALIDATION.camera_levels)",
    )

    @field_validator("camera_levels", mode="before")
    @classmethod
    def _camera_levels(cls, value):
        """Each level its fields once, as written, and each level once; a level with no field is left out, and a name that cannot be a field is refused."""
        out: list[list[str]] = []
        for level in value or []:
            fields: list[str] = []
            for name in ([level] if isinstance(level, str) else level or []):
                name = str(name).strip()
                if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*(:[A-Za-z][A-Za-z0-9_-]*)?", name):
                    raise ValueError(f"'{name}' is not the name of an EXIF field")
                if name.lower() not in (f.lower() for f in fields):
                    fields.append(name)
            if fields and [f.lower() for f in fields] not in ([f.lower() for f in o] for o in out):
                out.append(fields)
        return out
    exif: bool = Field(default=True, description="Required EXIF fields: the capture date and the ones of exif_fields. (VALIDATION.exif)")
    exif_fields: list[str] = Field(
        default_factory=lambda: ["Model"],
        description="The EXIF fields expected on every image, by the names ExifTool gives them (Make, Model, SerialNumber, ISO…), besides the capture date "
                    "(DateTimeOriginal), which is always expected: WildINTEL Uploader needs it. (VALIDATION.exif_fields)",
    )

    @field_validator("exif_fields", mode="before")
    @classmethod
    def _exif_fields(cls, value):
        """Each field once, as written; the capture date is always expected, so it is not one of them. A name ExifTool could not have is refused."""
        out: list[str] = []
        for name in value or []:
            name = str(name).strip()
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*(:[A-Za-z][A-Za-z0-9_-]*)?", name):
                raise ValueError(f"'{name}' is not the name of an EXIF field")
            if name.lower() != "datetimeoriginal" and name.lower() not in (n.lower() for n in out):
                out.append(name)
        return out
    duplicates: bool = Field(default=True, description="Duplicate images (same content). (VALIDATION.duplicates)")
    defaults: dict[str, CheckLevel] = Field(
        default_factory=lambda: dict(IMAGE_CHECK_DEFAULTS),
        description="How each check starts in an import, when it is on: required (it has to pass), warn or skip (offered unticked). (VALIDATION.defaults)",
    )

    @field_validator("defaults", mode="before")
    @classmethod
    def _defaults(cls, value):
        return check_defaults(value, IMAGE_CHECKS, IMAGE_CHECK_DEFAULTS)
