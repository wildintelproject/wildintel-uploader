"""The use cases of the settings: `SettingsUseCases` implements the port in of the module (`domain.ports.SettingsService`) — what the user does with the
settings, the same from the web app and the command line —, given the port out it keeps them through (`domain.ports.SettingsStore`) and the folder the
data folder falls back on. It reads, changes and saves the settings of the domain; its errors are those of the contract, or the domain's
SettingsError — the entry points turn them into HTTP or into a message."""
from __future__ import annotations

import types
import typing
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from wildintel_uploader.modules.settings.domain import folders
from wildintel_uploader.modules.settings.domain.models import Settings, SettingsError, secret_fields
from wildintel_uploader.modules.settings.domain.ports import (
    ConfigInfo, NoSettingsFile, Places, SettingsService, SettingsStore, ShownSetting, UnknownConfig, UnknownSetting,
)

# The sections that are settings, as settings.toml names them, and their attribute in the domain: what the file still holds of the field work is not one.
_SECTIONS = {section: name for name, section in Settings.SECTIONS.items() if name != "legacy_fieldwork"}
_TRUE, _FALSE = {"true", "yes", "on", "1"}, {"false", "no", "off", "0"}


def _parsed(key: str, kind: Any, text: str | None) -> Any:
    """A value typed as text, as the setting takes it: a yes or a no, a number, a text — blank is none."""
    if text is None or text.strip() == "":
        return None
    if isinstance(kind, types.UnionType) or typing.get_origin(kind) is typing.Union:
        kinds = [k for k in typing.get_args(kind) if k is not type(None)]
        kind = kinds[0] if len(kinds) == 1 else str
    text = text.strip()
    if kind is bool:
        if text.lower() in _TRUE:
            return True
        if text.lower() in _FALSE:
            return False
        raise SettingsError(key, "must be yes or no (true/false)")
    if kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            raise SettingsError(key, f"must be {'a whole number' if kind is int else 'a number'}") from None
    if kind is str:
        return text
    raise SettingsError(key, "is a list or a table: change it on the settings page, or in settings.toml")


class SettingsUseCases(SettingsService):
    """What the user does with the settings, over a SettingsStore. `default_data_dir` is the folder the data folder falls back on."""

    def __init__(self, store: SettingsStore, default_data_dir: Path) -> None:
        self.store, self.default_data_dir = store, default_data_dir

    # ── the configs ──

    def list_configs(self) -> list[ConfigInfo]:
        return self.store.list()

    def create_config(self, name: str) -> list[ConfigInfo]:
        self.store.create(name)
        return self.store.list()

    def activate_config(self, config_id: str) -> list[ConfigInfo]:
        try:
            self.store.set_active(config_id)
        except KeyError:
            raise UnknownConfig(config_id) from None
        return self.store.list()

    def config_file(self, config_id: str) -> Path:
        try:
            path = self.store.path_of(config_id)
        except KeyError:
            raise UnknownConfig(config_id) from None
        if not path.is_file():
            raise NoSettingsFile(config_id)
        return path

    # ── what the app changes on its own ──

    def set_show_welcome(self, show: bool) -> Settings:
        settings = self.store.load()
        changed = replace(settings, general=replace(settings.general, show_welcome=show))
        self.store.save(changed)
        return changed

    def set_data_dir(self, folder: str | None) -> Path:
        """What is kept in the old data folder is not moved (see domain.folders.follow_data_dir). SettingsError: it is not an absolute path."""
        settings = self.store.load()
        wanted = replace(settings.data, dir=(folder or "").strip() or None)
        changed = replace(settings, data=folders.follow_data_dir(settings.data, wanted, self.default_data_dir))
        self.store.save(changed)
        return folders.data_dir(changed.data, self.default_data_dir)

    # ── one setting by its name ──

    def change_setting(self, key: str, text: str | None) -> Settings:
        settings = self.store.load()
        section, _, name = key.partition(".")
        attribute = _SECTIONS.get(section.upper())
        if attribute is None or name not in {f.name for f in fields(getattr(settings, attribute))}:
            raise UnknownSetting(key)
        values = getattr(settings, attribute)
        kind = typing.get_type_hints(type(values))[name]
        value = _parsed(f"{section.upper()}.{name}", kind, text)
        if value is None and kind in (bool, int, float, str):
            raise SettingsError(key, "can't be blank")
        changed = replace(settings, **{attribute: replace(values, **{name: value})})
        self.store.save(changed)
        return changed

    def is_secret(self, key: str) -> bool:
        section, _, name = key.partition(".")
        return (section.upper(), name) in secret_fields()

    # ── what the settings are ──

    def shown_settings(self) -> dict[str, list[ShownSetting]]:
        settings = self.store.load()
        secrets = set(secret_fields())
        out: dict[str, list[ShownSetting]] = {}
        for section, attribute in _SECTIONS.items():
            values = getattr(settings, attribute)
            out[section] = [
                ShownSetting(key=f"{section}.{f.name}", value=None if (section, f.name) in secrets else getattr(values, f.name),
                             secret=(section, f.name) in secrets, saved=bool(getattr(values, f.name)))
                for f in fields(values)
            ]
        return out

    def places(self) -> Places:
        settings = self.store.load()
        data = folders.data_dir(settings.data, self.default_data_dir)
        return Places(settings_file=self.store.path_of(self.store.active_id()), data=data, collections=folders.collections_dir(settings.data, data),
                      reports=folders.reports_dir(settings.data, data), packages=folders.packages_dir(settings.data, data))
