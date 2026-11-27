"""The web API of the settings as JSON — Pydantic models of what the requests send, part of the module's adapter of entry (#248): the routers of
`entrypoints/api/settings.py` take them from here. What a setting may be is the domain's to say (modules.settings.domain.models): the settings the page sends are turned into it here."""
from __future__ import annotations

from pydantic import BaseModel

from wildintel_uploader.modules.settings.domain import models
from wildintel_uploader.modules.settings.infrastructure import schema
from wildintel_uploader.modules.settings.infrastructure.mapping import to_domain


class NewConfigRequest(BaseModel):
    name: str


class ShowWelcomeRequest(BaseModel):
    show: bool


class DataDirRequest(BaseModel):
    dir: str | None = None


class FoldersRequest(BaseModel):
    dir: str | None = None
    collections_dir: str | None = None
    reports_dir: str | None = None
    packages_dir: str | None = None


class GeneralRequest(BaseModel):
    log_level: str
    workers: int
    default_research_project: str | None = None
    show_welcome: bool = True
    # left out, the folders stay as they are
    folders: FoldersRequest | None = None


def settings_of(page: schema.Settings) -> models.Settings:
    """The settings the page sends — all of them, validated as settings.toml keeps them —, as the domain of the settings has them."""
    return to_domain(page)
