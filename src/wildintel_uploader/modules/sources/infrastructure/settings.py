"""The sections EPICOLLECT5 and EPICOLLECTCSV of settings.toml as Pydantic reads and writes them — registered with the module of the settings."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from wildintel_uploader.modules.settings.domain.registry import settings_registry


@settings_registry.schema("EPICOLLECT5")
class Epicollect5Settings(BaseModel):
    enabled: bool = Field(default=False, description="Whether Epicollect5 is used as a source: of visits (its entries are downloaded as a CSV), and of the details of a deployment when it is imported. (EPICOLLECT5.enabled)")
    unmapped_to_comments: bool = Field(
        default=False,
        description="What an entry says in an input that is not mapped to any field goes to the comments of the deployment. (EPICOLLECT5.unmapped_to_comments)",
    )
    project_slug: Optional[str] = Field(default=None, description="Slug of the Epicollect5 project — the name in its URL (five.epicollect.net/project/<slug>). (EPICOLLECT5.project_slug)")
    client_id: Optional[str] = Field(default=None, description="Client id of the Epicollect5 API client app, for private projects. (EPICOLLECT5.client_id)")
    client_secret: Optional[str] = Field(
        default=None, description="Client secret of the Epicollect5 API client app. (EPICOLLECT5.client_secret)", json_schema_extra={"secret": True},
    )
    mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Which input of the Epicollect5 form (its ref) gives each field of a deployment: deployment field -> input ref. (EPICOLLECT5.mapping)",
    )


@settings_registry.schema("EPICOLLECTCSV")
class EpicollectCsvSettings(BaseModel):
    enabled: bool = Field(default=True, description="Whether the CSV downloaded from the new WildINTEL Epicollect project can be read for visits. (EPICOLLECTCSV.enabled)")
