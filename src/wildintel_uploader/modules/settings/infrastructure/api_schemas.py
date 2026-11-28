"""The web API of the settings as JSON — Pydantic models of what the requests send and of what the answers say, part of the module's adapter of
entry (#248): the routers of `entrypoints/api/settings.py` take them from here, and never answer with a view of the domain as it is. What a setting may be is the domain's to say (modules.settings.domain.models): the settings the page sends are turned into it here."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wildintel_uploader.modules.settings.domain import models
from wildintel_uploader.modules.settings.domain.ports import ConfigInfo, GeneralView, SectionView
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


# ── what the answers say ──

class ConfigShown(BaseModel):
    """A config: its id, its name, its file, and whether it is the one in use."""
    id: str
    name: str
    path: str
    active: bool

    @classmethod
    def of(cls, config: ConfigInfo) -> "ConfigShown":
        return cls(id=config.id, name=config.name, path=config.path, active=config.active)


class GeneralSettingsShown(BaseModel):
    log_level: str
    workers: int
    default_research_project: str | None
    show_welcome: bool


class FoldersShown(BaseModel):
    """The folders the settings say — none: the default — and the default of each, where the settings say none."""
    dir: str | None
    collections_dir: str | None
    reports_dir: str | None
    packages_dir: str | None
    default_dir: str
    default_collections_dir: str
    default_reports_dir: str
    default_packages_dir: str


class SystemShown(BaseModel):
    cpu_count: int
    max_workers: int
    log_file: str
    log_level_override: str | None


class GeneralShown(BaseModel):
    """The General section: its settings, the folders and what the system says."""
    general: GeneralSettingsShown
    folders: FoldersShown
    system: SystemShown

    @classmethod
    def of(cls, view: GeneralView) -> "GeneralShown":
        g, f, s = view.general, view.folders, view.system
        return cls(general=GeneralSettingsShown(log_level=g.log_level, workers=g.workers, default_research_project=g.default_research_project,
                                                show_welcome=g.show_welcome),
                   folders=FoldersShown(dir=f.dir, collections_dir=f.collections_dir, reports_dir=f.reports_dir, packages_dir=f.packages_dir,
                                        default_dir=str(f.default_dir), default_collections_dir=str(f.default_collections_dir),
                                        default_reports_dir=str(f.default_reports_dir), default_packages_dir=str(f.default_packages_dir)),
                   system=SystemShown(cpu_count=s.cpu_count, max_workers=s.max_workers, log_file=str(s.log_file), log_level_override=s.log_level_override))


class SectionShown(BaseModel):
    """One section: its settings — the secrets left out — and, of each secret, whether one is saved."""
    section: str
    values: dict[str, Any]
    secrets: dict[str, bool]

    @classmethod
    def of(cls, view: SectionView) -> "SectionShown":
        return cls(section=view.section, values=dict(view.values), secrets=dict(view.secrets))


class LogDeleted(BaseModel):
    deleted: int

