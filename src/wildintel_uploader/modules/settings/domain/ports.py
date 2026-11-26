"""The contracts of the module of the settings (#248), on both sides of it:

- **In** — `SettingsService`: what the module offers, which the entry points (the web API, the command line) call. Implemented by the use cases
  (`application.use_cases.SettingsUseCases`); its answers and its errors, below, are part of it.
- **Out** — `SettingsStore`: what the module needs from outside, which the infrastructure gives: where the settings are kept — the TOML files of the
  user's config folder today (`infrastructure.toml_files.TomlSettingsStore`), anything else tomorrow, or a folder of its own in a test.

Both speak the settings of the domain (`models.Settings`)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from wildintel_uploader.modules.settings.domain.models import Settings


# ── what both sides speak of ──

@dataclass(frozen=True)
class ConfigInfo:
    """One set of settings the user can switch to."""
    id: str
    name: str
    path: str
    active: bool


@dataclass(frozen=True)
class ShownSetting:
    """A setting as it is shown: a secret only says whether it is saved."""
    key: str           # SECTION.field, as settings.toml names it
    value: Any         # None for a secret
    secret: bool
    saved: bool        # a secret: whether there is one


@dataclass(frozen=True)
class Places:
    """Where the app keeps its files."""
    settings_file: Path
    data: Path
    collections: Path
    reports: Path
    packages: Path


class UnknownConfig(LookupError):
    """There is no config with that id."""


class NoSettingsFile(LookupError):
    """The config exists, but its file has not been written yet."""


class UnknownSetting(LookupError):
    """There is no setting by that name."""


# ── in: what the module offers ──

class SettingsService(Protocol):
    """What the user can do with the settings, from the web app or the command line. Besides the errors each method names, a value that cannot be is
    the domain's SettingsError."""

    # the configs
    def list_configs(self) -> list[ConfigInfo]:
        """Every config, the default one first, the one in use flagged."""

    def create_config(self, name: str) -> list[ConfigInfo]:
        """A new config with the default settings — not the one in use —, and the list of them. ValueError: `name` has nothing to name it after."""

    def activate_config(self, config_id: str) -> list[ConfigInfo]:
        """From now on the whole app reads and saves that config. UnknownConfig."""

    def config_file(self, config_id: str) -> Path:
        """The file of a config, to download it or open its folder. UnknownConfig, NoSettingsFile."""

    # what the app changes on its own
    def set_show_welcome(self, show: bool) -> Settings:
        """Whether the welcome page is shown when the app opens."""

    def set_data_dir(self, folder: str | None) -> Path:
        """The data folder — blank, the default one —, and the folder it is now: the folders that were inside the old one go inside the new one."""

    # one setting by its name
    def change_setting(self, key: str, text: str | None) -> Settings:
        """One setting, named as settings.toml names it — TRAPPER.base_url —, to a value typed as text. UnknownSetting."""

    def is_secret(self, key: str) -> bool:
        """Whether a setting, named SECTION.field, is a secret: never shown, hidden while it is typed."""

    # what the settings are
    def shown_settings(self) -> dict[str, list[ShownSetting]]:
        """Every setting of the config in use, section by section, the secrets kept out of sight."""

    def places(self) -> Places:
        """Where the app keeps its files."""


# ── out: what the module needs ──

class SettingsStore(Protocol):
    """Several sets of settings ("configs"), one of them active: the one load and save work on."""

    def list(self) -> list[ConfigInfo]:
        """Every config, the default one first."""

    def active_id(self) -> str:
        """The id of the config in use."""

    def set_active(self, config_id: str) -> None:
        """Raises KeyError: there is no config with that id."""

    def create(self, name: str) -> str:
        """A new config with the default settings, named after `name`, and its id: it does not become the active one.
        Raises ValueError: `name` has nothing to name it after."""

    def path_of(self, config_id: str) -> Path:
        """Where a config is kept, to download it or open its folder. Raises KeyError: there is no config with that id."""

    def load(self) -> Settings:
        """The settings of the active config — its defaults, the first time."""

    def save(self, settings: Settings) -> None:
        """Keeps them as the settings of the active config, all at once."""
