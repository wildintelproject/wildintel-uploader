"""The section PREPROCESSING of settings.toml as Pydantic reads and writes it — registered with the module of the settings."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator



class PreprocessingSettings(BaseModel):
    """What is done to the images as they are imported into their collection —
    which preprocessing steps a new run starts with, and the values they use.
    The wizard lists them before the import, and a run can still switch each off."""

    rename: bool = Field(default=True, description="Rename the images <DEPLOYMENT>__<YYYYMMDD>_<n>.<EXT>. (PREPROCESSING.rename)")
    resize: bool = Field(default=True, description="Resize the images to a width, keeping their proportions. (PREPROCESSING.resize)")
    resize_width: int = Field(
        default=2400, ge=100, le=20000,
        description="The width, in pixels, images wider than it are resized to. Smaller ones are left as they are. (PREPROCESSING.resize_width)",
    )
    metadata: bool = Field(default=True, description="Add authorship, rights and license metadata (XMP, with ExifTool). (PREPROCESSING.metadata)")
    owner: str = Field(default="", description="Who owns the images — the rights holder. (PREPROCESSING.owner)")
    publisher: str = Field(default="", description="Who publishes the images. (PREPROCESSING.publisher)")
    coverage: str = Field(
        default="", description="Where the images were taken, in the coverage text (e.g. Doñana National Park). Blank: the deployment's location. (PREPROCESSING.coverage)",
    )
    license_url: str = Field(
        default="https://creativecommons.org/licenses/by-nc/4.0/", description="The license the images are shared under. (PREPROCESSING.license_url)",
    )
    ignore_dst: bool = Field(
        default=True,
        description="Read the camera's clock as if it never changed to summer time, using the timezone's standard offset. (PREPROCESSING.ignore_dst)",
    )
    convert_to_utc: bool = Field(default=True, description="Give the capture dates (in names and metadata) in UTC. (PREPROCESSING.convert_to_utc)")

    @field_validator("owner", "publisher", "coverage", "license_url")
    @classmethod
    def _stripped(cls, value: str) -> str:
        return value.strip()


# The format in settings.toml of the sections this module owns — put together with the others by infrastructure.schema.
SCHEMAS = {
    "PREPROCESSING": PreprocessingSettings,
}
