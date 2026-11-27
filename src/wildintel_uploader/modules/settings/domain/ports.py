"""The contracts of the module of the settings (#248), on both sides of it:

- **In** — `SettingsService`: what the module offers, which the entry points (the web API, the command line) call. Implemented by the use cases
  (`application.use_cases.SettingsUseCases`); its answers and its errors, below, are part of it.
- **Out** — what the module needs from outside, which the infrastructure gives: `SettingsStore`, where the settings are kept — the TOML files of the
  user's config folder today (`infrastructure.toml_files.TomlSettingsStore`), anything else tomorrow, or a folder of its own in a test —;
  `ActivityLog`, the log of the app (its file, its level), `Machine`, what the computer has, and `RecordStorage`, the backends the records of the
  research projects can be kept in (`infrastructure.system`).

Both speak the settings of the domain (`models.Settings`)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from wildintel_uploader.modules.settings.domain.models import DataSettings, GeneralSettings, LegacyFieldwork, Settings


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
    catalog_storage: str           # where the catalog is kept: "json" (the collections folder) or "sqlite"
    catalog_database: Path         # the SQLite database it is in, when it is


@dataclass(frozen=True)
class Folders:
    """The folders of the app as the settings say them — None, the default one — and the default each one has now."""
    dir: str | None
    collections_dir: str | None
    reports_dir: str | None
    packages_dir: str | None
    default_dir: Path              # the data folder when DATA.dir says none
    default_collections_dir: Path  # inside the data folder the settings say
    default_reports_dir: Path
    default_packages_dir: Path


@dataclass(frozen=True)
class SystemInfo:
    """What the settings of the General section are shown with: what the computer has and where the log is."""
    cpu_count: int
    max_workers: int
    log_file: Path
    log_level_override: str | None   # a level the environment forces, which wins over the setting


@dataclass(frozen=True)
class GeneralView:
    """The General section of the settings, as it is shown: its settings, the folders, and what the system says."""
    general: GeneralSettings
    folders: Folders
    system: SystemInfo


class UnknownConfig(LookupError):
    """There is no config with that id."""


class BadConfigName(ValueError):
    """A name a config cannot be given: it has no letter or digit to name its file after."""


class UnreadableSettings(ValueError):
    """A settings file that cannot be read: it is not TOML, or what it says is not settings. `path` names it; the message says why."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path, self.message = path, message


class NoSettingsFile(LookupError):
    """The config exists, but its file has not been written yet."""


class UnknownSetting(LookupError):
    """There is no setting by that name."""


@dataclass(frozen=True)
class SectionView:
    """One section of the settings, as it is shown: its settings — the secrets left out — and, of each secret, whether one is saved."""
    section: str                       # as settings.toml names it: TRAPPER
    values: dict[str, Any]
    secrets: dict[str, bool]


class NoLogFile(LookupError):
    """Nothing has been logged yet: there is no log file."""


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

    # all the settings, and each section
    def current(self) -> Settings:
        """The settings of the config in use."""

    def check_settings(self, settings: Settings) -> None:
        """Whether they could be saved — what only the outside knows: that the storage they name exists. SettingsError."""

    def save_settings(self, settings: Settings) -> Settings:
        """Saves all the settings, as the settings page does, and gives what was kept: a secret left blank keeps the one saved; when the data folder
        changes, the folders that were inside it go inside the new one; the storage of the records has to exist, and is the one in use from then on;
        the level of the log applies at once. SettingsError."""

    def section(self, section: str) -> SectionView:
        """One section, named as settings.toml names it — TRAPPER, VALIDATION… UnknownSetting."""

    def save_section(self, section: str, values: dict[str, Any]) -> SectionView:
        """Changes the settings of one section that `values` names — the others stay —, with the rules of save_settings. UnknownSetting: a section or a
        setting that is not one; SettingsError: a value it does not take."""

    # what the settings still hold of the field work
    def legacy_fieldwork(self) -> LegacyFieldwork:
        """The cameras, SD cards, trappers and roles versions before kept in the settings — not settings: they go to the catalog."""

    def forget_legacy_fieldwork(self, kind: str) -> None:
        """Takes one kind of them out of the settings — "trappers", "cameras", "sd_cards", "roles" — once the catalog keeps them."""

    def keep_legacy_fieldwork(self, kind: str, items: list[dict[str, Any]]) -> None:
        """What is left of one kind once the catalog took what it could — the rest is no longer in the settings."""

    # the General section
    def general(self) -> GeneralView:
        """The General section: its settings, the folders and what the system says."""

    def save_general(self, general: GeneralSettings, folders: DataSettings) -> GeneralView:
        """Saves the General section — its settings and the folders —, and the level of the log applies at once. When the data folder changes, the
        folders that were inside the old one go inside the new one. What DATA says besides the folders (the storage) is kept as it was."""

    def log_file(self) -> Path:
        """The log file, to download it. NoLogFile."""

    def clear_log(self) -> int:
        """Deletes the log file and its older copies — logging goes on, into a new one —, and says how many."""


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

    def has_file(self, path: Path) -> bool:
        """Whether the file of a config is there."""

    def load(self) -> Settings:
        """The settings of the active config — its defaults, the first time."""

    def save(self, settings: Settings) -> None:
        """Keeps them as the settings of the active config, all at once."""


class ActivityLog(Protocol):
    """The log of the app."""

    def file(self) -> Path:
        """Where it is written."""

    def has_file(self) -> bool:
        """Whether anything has been written to it yet."""

    def level_override(self) -> str | None:
        """A level the environment forces, if any: it wins over the setting."""

    def apply_level(self, level: str) -> None:
        """From now on, log at this level — unless the environment forces another."""

    def clear(self) -> int:
        """Deletes the log file and its older copies, and says how many."""


class Machine(Protocol):
    """What the computer has."""

    def cpu_count(self) -> int:
        """How many CPUs."""


class RecordStorage(Protocol):
    """The backends the records of the research projects can be kept in."""

    def available(self) -> tuple[str, ...]:
        """Their names."""

    def use(self, name: str) -> None:
        """From now on, the records are kept in that one."""


class StoredSettings(Protocol):
    """The settings as `settings.toml` keeps them, by section (`.VALIDATION`, `.TRAPPER`…), and the folders they say. Only what keeps the
    settings whole — the backup of the settings — is given them all (entrypoints.config); every other adapter is given the section or the
    folder it reads, by entrypoints.wiring."""

    def load_settings(self) -> Any:
        ...

    def save_settings(self, settings: Any) -> None:
        ...

    def collections_dir(self, settings: Any = None) -> Path:
        ...

    def reports_dir(self, settings: Any = None) -> Path:
        ...

    def packages_dir(self, settings: Any = None) -> Path:
        ...

    def max_zip_mb(self, settings: Any = None) -> int:
        ...

    def get_sessions_dir(self) -> Path:
        ...

    def legacy_sessions_dir(self) -> Path:
        ...

    def get_logs_dir(self) -> Path:
        ...

    def legacy_logs_dir(self) -> Path:
        ...

    def secret_fields(self) -> Any:
        ...
