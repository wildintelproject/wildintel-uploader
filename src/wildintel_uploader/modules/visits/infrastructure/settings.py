"""The section FIELDLOG of settings.toml as Pydantic reads and writes it — registered with the module of the settings."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from wildintel_uploader.modules.settings.domain.registry import settings_registry


@settings_registry.schema("FIELDLOG")
class FieldlogSettings(BaseModel):
    """Field records: how the visits of a field trip are read from the file of the field app (an Epicollect download) and what is made of them
    (see services.visits_csv and services.visit_deployments)."""

    time_source: Literal["created_at", "hour"] = Field(
        default="created_at",
        description="When a visit happened: created_at, the time its entry was created (UTC); or hour, the date and the hour typed in the form (the wall clock of its location). (FIELDLOG.time_source)",
    )
    keep_seconds: bool = Field(
        default=False, description="Keep the seconds of the visits in the deployments' start and end written in the logs; off, they are cut to the minute. (FIELDLOG.keep_seconds)",
    )
