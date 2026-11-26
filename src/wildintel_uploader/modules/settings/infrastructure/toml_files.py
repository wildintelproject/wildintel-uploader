"""The settings kept as TOML files of the user's config folder: settings.toml (the default config), one more file for each config in configs/, and the
id of the one in use in active-config. Read with Dynaconf — so that WILDINTEL_UPLOADER_* variables of the environment override them — and validated
by the schema (`infrastructure.schema`), and given as the settings of the domain; written with its TOML loader, all at once."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from dynaconf import Dynaconf, loaders

from wildintel_uploader.modules.settings.domain.ports import ConfigInfo, SettingsStore
from wildintel_uploader.modules.settings.domain import models
from wildintel_uploader.modules.settings.infrastructure.mapping import to_domain, to_schema
from wildintel_uploader.modules.settings.infrastructure.schema import Settings

DEFAULT_CONFIG_ID = "default"
ENV_PREFIX = "WILDINTEL_UPLOADER"


def read_settings_file(config_file: Path) -> Settings:
    """The settings of a file — written with the defaults first if there is none —, as the schema validates them: what was kept before a field existed
    gets it."""
    if not config_file.exists():
        write_settings_file(Settings(), config_file)
    dynaconf_settings = Dynaconf(settings_files=[str(config_file)], envvar_prefix=ENV_PREFIX)
    return Settings.model_validate(dynaconf_settings.to_dict(), context={"migrate": True})


def write_settings_file(settings: Settings, config_file: Path) -> None:
    """Writes the settings to a file of their own and puts it in place at once: two saves at the same time (or a read in the middle of one) never
    leave a half-written settings file, which the app could not read again."""
    config_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config_file.parent, prefix=f".{config_file.name}.", suffix=".tmp")
    os.close(fd)
    try:
        loaders.toml_loader.write(tmp, settings.model_dump(mode="json", exclude_none=True), merge=False)
        os.replace(tmp, config_file)
    finally:
        Path(tmp).unlink(missing_ok=True)


class TomlSettingsStore(SettingsStore):
    """A SettingsStore over the TOML files: `default_file` is the default config, `configs_dir` holds the others (<id>.toml), and `pointer` names the
    one in use."""

    def __init__(self, default_file: Path, configs_dir: Path, pointer: Path) -> None:
        self.default_file, self.configs_dir, self.pointer = default_file, configs_dir, pointer

    def _path(self, config_id: str) -> Path:
        return self.default_file if config_id == DEFAULT_CONFIG_ID else self.configs_dir / f"{config_id}.toml"

    def _ids(self) -> list[str]:
        extra = sorted(p.stem for p in self.configs_dir.glob("*.toml")) if self.configs_dir.is_dir() else []
        return [DEFAULT_CONFIG_ID, *(config_id for config_id in extra if config_id != DEFAULT_CONFIG_ID)]

    def active_id(self) -> str:
        """The one the pointer names — the default one if it is missing, empty or names a file that is gone."""
        try:
            config_id = self.pointer.read_text(encoding="utf-8").strip()
        except OSError:
            return DEFAULT_CONFIG_ID
        return config_id if config_id in self._ids() else DEFAULT_CONFIG_ID

    def active_path(self) -> Path:
        return self._path(self.active_id())

    def list(self) -> list[ConfigInfo]:
        active = self.active_id()
        return [ConfigInfo(id=config_id, name="Default config" if config_id == DEFAULT_CONFIG_ID else config_id, path=str(self._path(config_id)),
                           active=config_id == active) for config_id in self._ids()]

    def create(self, name: str) -> str:
        """Named after `name`, made file-name safe and unique among the others."""
        base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        if not base:
            raise ValueError("A config needs a name with at least one letter or digit.")
        existing = set(self._ids())
        config_id, suffix = base, 2
        while config_id in existing:
            config_id, suffix = f"{base}-{suffix}", suffix + 1
        self.configs_dir.mkdir(parents=True, exist_ok=True)
        loaders.toml_loader.write(str(self._path(config_id)), Settings().model_dump(mode="json", exclude_none=True), merge=False)
        return config_id

    def set_active(self, config_id: str) -> None:
        if config_id not in self._ids():
            raise KeyError(config_id)
        self.pointer.parent.mkdir(parents=True, exist_ok=True)
        self.pointer.write_text(config_id, encoding="utf-8")

    def path_of(self, config_id: str) -> Path:
        if config_id not in self._ids():
            raise KeyError(config_id)
        return self._path(config_id)

    def load(self) -> models.Settings:
        return to_domain(read_settings_file(self.active_path()))

    def save(self, settings: models.Settings) -> None:
        write_settings_file(to_schema(settings), self.active_path())
