"""The settings file of the app, for where the app is put together (entrypoints.wiring) and the settings page — `config.load_settings()`,
`config.collections_dir()`, `config.Settings`… —, over the module `modules.settings`: the settings as the app understands them are the dataclasses
of its `domain.models`, the folders follow the rules of its `domain.folders`, and they are kept through the port `domain.ports.SettingsStore`,
whose adapter is the TOML files of `infrastructure.toml_files`; `Settings` is the Pydantic model of the files (`infrastructure.schema`).

No module asks for it: the wiring gives each adapter the section or the folder it reads (see entrypoints.wiring), and the routers ask the
contract of the settings (SettingsService). The tests use it to point the files elsewhere.

The files are where they always were: settings.toml in the user's config folder, the other configs in configs/, the one in use named by active-config.
The adapter is made from DEFAULT_CONFIG_FILE, CONFIGS_DIR and ACTIVE_CONFIG_POINTER each time it is asked for, so that a test can point them elsewhere."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from wildintel_uploader.modules.settings.domain.ports import ConfigInfo  # noqa: F401
from wildintel_uploader.modules.settings.domain import folders
from wildintel_uploader.modules.settings.domain import models as domain
from wildintel_uploader.modules.settings.infrastructure import app_dirs
from wildintel_uploader.modules.postvalidation.infrastructure.settings import PostvalidationSettings  # noqa: F401
from wildintel_uploader.modules.preprocessing.infrastructure.settings import PreprocessingSettings  # noqa: F401
from wildintel_uploader.modules.prevalidation.infrastructure.settings import ValidationSettings  # noqa: F401
from wildintel_uploader.modules.settings.infrastructure.schema import (  # noqa: F401
    DataSettings, FieldworkSettings, GeneralSettings, Settings, Trapper, default_workers, secret_fields,
)
from wildintel_uploader.modules.settings.infrastructure.toml_files import TomlSettingsStore, read_settings_file, write_settings_file  # noqa: F401

APP_NAME = app_dirs.APP_NAME
DEFAULT_CONFIG_FILE = app_dirs.config_dir() / "settings.toml"
# More settings files besides the default one: every .toml in CONFIGS_DIR. Which one is in use is named by ACTIVE_CONFIG_POINTER.
CONFIGS_DIR = DEFAULT_CONFIG_FILE.parent / "configs"
ACTIVE_CONFIG_POINTER = DEFAULT_CONFIG_FILE.parent / "active-config"


def settings_store() -> TomlSettingsStore:
    """The adapter the settings are kept through."""
    return TomlSettingsStore(DEFAULT_CONFIG_FILE, CONFIGS_DIR, ACTIVE_CONFIG_POINTER)


# ── the folders of the app (see modules.settings.infrastructure.app_dirs) ──

def get_app_documents_dir() -> Path:
    return app_dirs.documents_dir()


def get_logs_dir() -> Path:
    """Where the app's log files go — the log folder of the system. Not configurable."""
    return app_dirs.logs_dir()


def legacy_logs_dir() -> Path:
    """Where the log files were kept before: next to settings.toml."""
    return DEFAULT_CONFIG_FILE.parent / "logs"


def legacy_sessions_dir() -> Path:
    return app_dirs.legacy_sessions_dir()


def get_sessions_dir() -> Path:
    """Where in-progress and interrupted wizard runs persist. Not configurable — see modules.deployments (domain.sessions)."""
    return app_dirs.sessions_dir()


def default_data_dir() -> Path:
    """The data folder unless DATA.dir says another: <documents>/wildintel-uploader."""
    return get_app_documents_dir()


# ── the configs (see modules.settings.domain.ports.SettingsStore) ──

def active_config_id() -> str:
    return settings_store().active_id()


def active_config_file() -> Path:
    """The settings file load_settings()/save_settings() work on when not given one."""
    return settings_store().active_path()


def list_configs() -> list[ConfigInfo]:
    return settings_store().list()


def create_config(name: str) -> str:
    """Raises:
        ValueError: if `name` has no letters or digits to name a file after.
    """
    return settings_store().create(name)


def set_active_config(config_id: str) -> None:
    """Raises:
        KeyError: if there's no config with that id.
    """
    settings_store().set_active(config_id)


def config_file_for(config_id: str) -> Path:
    """Raises:
        KeyError: if there's no config with that id.
    """
    return settings_store().path_of(config_id)


def load_settings(config_file: Optional[Path] = None) -> Settings:
    """The settings of the active config, in the format of the file (see the note above)."""
    return read_settings_file(config_file or settings_store().active_path())


def save_settings(settings: Settings, config_file: Optional[Path] = None) -> None:
    write_settings_file(settings, config_file or settings_store().active_path())


# ── what the settings say (see modules.settings.domain.folders) ──

def _data(settings: Settings) -> domain.DataSettings:
    """The DATA section of the file's settings, as the domain has it."""
    return domain.DataSettings(**settings.DATA.model_dump())

def workers(settings: Settings | None = None) -> int:
    """How many images are validated or preprocessed at once — GENERAL.workers."""
    return (settings or load_settings()).GENERAL.workers


def max_zip_mb(settings: Settings | None = None) -> int:
    """The largest zip an upload makes, in megabytes — TRAPPER.max_zip_mb."""
    return (settings or load_settings()).TRAPPER.max_zip_mb


def data_dir(settings: Settings | None = None) -> Path:
    """The effective data directory — DATA.dir if set, else the default."""
    return folders.data_dir(_data(settings or load_settings()), default_data_dir())


def collections_dir(settings: Settings | None = None) -> Path:
    """Where every collection is kept locally: <research project id>/<collection, e.g. R0003>/<deployment id>/ inside it."""
    settings = settings or load_settings()
    return folders.collections_dir(_data(settings), data_dir(settings))


def reports_dir(settings: Settings | None = None) -> Path:
    """Where the reports of the validations, postvalidations and preprocessings are kept (see modules.reports)."""
    settings = settings or load_settings()
    return folders.reports_dir(_data(settings), data_dir(settings))


def packages_dir(settings: Settings | None = None) -> Path:
    """Where the packages made to upload to Trapper are written (see modules.uploaders)."""
    settings = settings or load_settings()
    return folders.packages_dir(_data(settings), data_dir(settings))
