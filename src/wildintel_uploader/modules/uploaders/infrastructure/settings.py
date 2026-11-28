"""The sections TRAPPER and AGOUTI of settings.toml as Pydantic reads and writes them — registered with the module of the settings."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator



class TrapperSettings(BaseModel):
    enabled: bool = Field(default=True, description="Whether TRAPPER is used as a place to upload deployments to. (TRAPPER.enabled)")
    base_url: Optional[str] = Field(default=None, description="TRAPPER server URL. (TRAPPER.base_url)")
    user_name: Optional[str] = Field(default=None, description="TRAPPER username (its email — the import form only accepts that). (TRAPPER.user_name)")
    user_password: Optional[str] = Field(
        default=None, description="TRAPPER password. (TRAPPER.user_password)", json_schema_extra={"secret": True}, repr=False,
    )
    max_zip_mb: int = Field(
        default=500,
        description="The images of each deployment are uploaded in packages of at most this many megabytes. (TRAPPER.max_zip_mb)",
    )


class AgoutiSettings(BaseModel):
    """What an upload to Agouti needs (its public API: https://docs.agouti.eu/api/endpoints.html) — kept here; nothing is uploaded to Agouti yet."""

    enabled: bool = Field(default=False, description="Whether Agouti is used as a place to upload deployments to. (AGOUTI.enabled)")
    base_url: Optional[str] = Field(default=None, description="The address of Agouti's API (https://api.agouti.eu). (AGOUTI.base_url)")
    api_key: Optional[str] = Field(
        default=None, description="The API key Agouti's support gives, sent as X-API-KEY. (AGOUTI.api_key)", json_schema_extra={"secret": True}, repr=False,
    )
    project_id: Optional[str] = Field(default=None, description="The id of the Agouti project the deployments are uploaded to. (AGOUTI.project_id)")

    @field_validator("base_url", "project_id")
    @classmethod
    def _stripped(cls, value: Optional[str]) -> Optional[str]:
        return (value.strip() or None) if isinstance(value, str) else value


# The format in settings.toml of the sections this module owns — put together with the others by infrastructure.schema.
SCHEMAS = {
    "TRAPPER": TrapperSettings,
    "AGOUTI": AgoutiSettings,
}
