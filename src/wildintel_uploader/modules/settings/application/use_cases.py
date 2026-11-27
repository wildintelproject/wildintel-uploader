"""The use cases of the settings: `SettingsUseCases` implements the port in of the module (`domain.ports.SettingsService`) — what the user does with the
settings, the same from the web app and the command line —, given the ports out it works through (`domain.ports.SettingsStore`, where the settings are
kept; `ActivityLog`, the log of the app; `Machine`, what the computer has; `RecordStorage`, the backends of the records) and the folder the data
folder falls back on. Every change is saved through the same rules (`_save`), whatever asks for it. It reads, changes and saves the settings of the domain; its errors are those of the contract, or the domain's
SettingsError — the entry points turn them into HTTP or into a message."""
from __future__ import annotations

import types
import typing
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from wildintel_uploader.modules.settings.domain import folders as folder_rules
from wildintel_uploader.modules.settings.domain.models import (
    MAX_WORKERS, DataSettings, GeneralSettings, LegacyFieldwork, Settings, SettingsError, keep_secrets, secret_fields,
)
from wildintel_uploader.modules.settings.domain.ports import (
    ActivityLog, ConfigInfo, Folders, GeneralView, Machine, NoLogFile, NoSettingsFile, Places, RecordStorage, SectionView, SettingsService, SettingsStore,
    ShownSetting, SystemInfo, UnknownConfig, UnknownSetting,
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


def _given(key: str, kind: Any, value: Any) -> Any:
    """A value as it comes from the settings page (JSON), as the setting takes it: a yes or a no, a whole number, a number, a text, a list, a table —
    anything else is refused. What the value may be (a range, a choice) is the domain's to say."""
    origin, args = typing.get_origin(kind), typing.get_args(kind)
    if isinstance(kind, types.UnionType) or origin is typing.Union:
        if value is None and type(None) in args:
            return None
        kinds = [k for k in args if k is not type(None)]
        return _given(key, kinds[0], value) if len(kinds) == 1 else value
    if kind is bool:
        if not isinstance(value, bool):
            raise SettingsError(key, "must be yes or no (true/false)")
        return value
    if kind is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SettingsError(key, "must be a whole number")
        return value
    if kind is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsError(key, "must be a number")
        return float(value)
    if kind is str:
        if not isinstance(value, str):
            raise SettingsError(key, "must be a text")
        return value
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise SettingsError(key, "must be a list")
        inner = args[0] if args else Any
        return tuple(_given(key, inner, v) if inner is not Any else v for v in value)
    if origin in (dict, typing.Mapping) or (origin is not None and getattr(origin, "__name__", "") == "Mapping"):
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            raise SettingsError(key, "must be a table of texts")
        return dict(value)
    return value


class SettingsUseCases(SettingsService):
    """What the user does with the settings, over a SettingsStore. `default_data_dir` is the folder the data folder falls back on."""

    def __init__(self, store: SettingsStore, default_data_dir: Path, *, activity_log: ActivityLog, machine: Machine, record_storage: RecordStorage) -> None:
        self.store, self.default_data_dir, self.activity_log, self.machine = store, default_data_dir, activity_log, machine
        self.record_storage = record_storage

    # ── the rules every change is saved by ──

    def check_settings(self, settings: Settings) -> None:
        name = (settings.data.storage or "").strip().lower()
        if name not in self.record_storage.available():
            raise SettingsError("DATA.storage", f"there is no storage called '{settings.data.storage}': {', '.join(self.record_storage.available())}")

    def _save(self, settings: Settings, *, blank_secrets_kept: bool = True, put_in_use: bool = False) -> Settings:
        """Saves the settings by the rules of save_settings, and gives what was kept. `blank_secrets_kept` off: a secret left blank is cleared — what
        `config set` does when it is told so. The storage and the level of the log are put in use when they change — or always, with `put_in_use`."""
        before = self.store.load()
        if blank_secrets_kept:
            settings = keep_secrets(before, settings)
        settings = replace(settings, data=folder_rules.follow_data_dir(before.data, settings.data, self.default_data_dir))
        self.check_settings(settings)
        self.store.save(settings)
        if put_in_use or settings.data.storage != before.data.storage:
            self.record_storage.use(settings.data.storage)
        if put_in_use or settings.general.log_level != before.general.log_level:
            self.activity_log.apply_level(settings.general.log_level)
        return settings

    def current(self) -> Settings:
        return self.store.load()

    def save_settings(self, settings: Settings) -> Settings:
        return self._save(settings, put_in_use=True)

    # ── each section ──

    def _attribute(self, section: str) -> str:
        attribute = _SECTIONS.get(section.upper())
        if attribute is None:
            raise UnknownSetting(section)
        return attribute

    def _section_view(self, settings: Settings, section: str) -> SectionView:
        section = section.upper()
        values = getattr(settings, self._attribute(section))
        secrets = {name for s, name in secret_fields() if s == section}
        plain = {f.name: getattr(values, f.name) for f in fields(values) if f.name not in secrets}
        return SectionView(section=section, values={k: (dict(v) if isinstance(v, typing.Mapping) else v) for k, v in plain.items()},
                           secrets={name: bool(getattr(values, name)) for name in sorted(secrets)})

    def section(self, section: str) -> SectionView:
        return self._section_view(self.store.load(), section)

    def save_section(self, section: str, values: dict[str, Any]) -> SectionView:
        settings = self.store.load()
        attribute = self._attribute(section)
        current = getattr(settings, attribute)
        hints = typing.get_type_hints(type(current))
        unknown = sorted(set(values) - set(hints))
        if unknown:
            raise UnknownSetting(f"{section.upper()}.{unknown[0]}")
        changes = {name: _given(f"{section.upper()}.{name}", hints[name], value) for name, value in values.items()}
        saved = self._save(replace(settings, **{attribute: replace(current, **changes)}))
        return self._section_view(saved, section)

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
        if not self.store.has_file(path):
            raise NoSettingsFile(config_id)
        return path

    # ── what the app changes on its own ──

    def set_show_welcome(self, show: bool) -> Settings:
        settings = self.store.load()
        return self._save(replace(settings, general=replace(settings.general, show_welcome=show)))

    def set_data_dir(self, folder: str | None) -> Path:
        """What is kept in the old data folder is not moved (see domain.folders.follow_data_dir). SettingsError: it is not an absolute path."""
        settings = self.store.load()
        changed = self._save(replace(settings, data=replace(settings.data, dir=(folder or "").strip() or None)))
        return folder_rules.data_dir(changed.data, self.default_data_dir)

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
        return self._save(replace(settings, **{attribute: replace(values, **{name: value})}), blank_secrets_kept=False)

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
        data = folder_rules.data_dir(settings.data, self.default_data_dir)
        return Places(settings_file=self.store.path_of(self.store.active_id()), data=data, collections=folder_rules.collections_dir(settings.data, data),
                      reports=folder_rules.reports_dir(settings.data, data), packages=folder_rules.packages_dir(settings.data, data),
                      catalog_storage=settings.data.catalog_storage, catalog_database=folder_rules.catalog_database(settings.data, data))

    # ── what the settings still hold of the field work ──

    def legacy_fieldwork(self) -> LegacyFieldwork:
        return self.store.load().legacy_fieldwork

    def forget_legacy_fieldwork(self, kind: str) -> None:
        self.keep_legacy_fieldwork(kind, [])

    def keep_legacy_fieldwork(self, kind: str, items: list[dict[str, Any]]) -> None:
        if kind not in {f.name for f in fields(LegacyFieldwork)}:
            raise UnknownSetting(f"FIELDWORK.{kind}")
        settings = self.store.load()
        left = tuple(dict(i) for i in items)
        if tuple(dict(i) for i in getattr(settings.legacy_fieldwork, kind)) != left:
            self.store.save(replace(settings, legacy_fieldwork=replace(settings.legacy_fieldwork, **{kind: left})))

    # ── the General section ──

    def _view(self, settings: Settings) -> GeneralView:
        data = folder_rules.data_dir(settings.data, self.default_data_dir)
        return GeneralView(
            general=settings.general,
            folders=Folders(dir=settings.data.dir, collections_dir=settings.data.collections_dir, reports_dir=settings.data.reports_dir,
                            packages_dir=settings.data.packages_dir, default_dir=self.default_data_dir,
                            default_collections_dir=data / "collections", default_reports_dir=data / "reports", default_packages_dir=data / "packages"),
            system=SystemInfo(cpu_count=self.machine.cpu_count(), max_workers=MAX_WORKERS, log_file=self.activity_log.file(),
                              log_level_override=self.activity_log.level_override()),
        )

    def general(self) -> GeneralView:
        return self._view(self.store.load())

    def save_general(self, general: GeneralSettings, folders: DataSettings) -> GeneralView:
        settings = self.store.load()
        wanted = replace(settings.data, dir=folders.dir, collections_dir=folders.collections_dir, reports_dir=folders.reports_dir,
                         packages_dir=folders.packages_dir)
        return self._view(self._save(replace(settings, general=general, data=wanted), put_in_use=True))

    def log_file(self) -> Path:
        path = self.activity_log.file()
        if not self.activity_log.has_file():
            raise NoLogFile(str(path))
        return path

    def clear_log(self) -> int:
        return self.activity_log.clear()
