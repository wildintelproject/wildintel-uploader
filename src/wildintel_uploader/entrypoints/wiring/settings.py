"""The settings: their store, the log, the machine and the storage of the records."""
from __future__ import annotations

from dishka import Provider, Scope, alias, provide

from wildintel_uploader.entrypoints import config
from wildintel_uploader.modules.settings.application.use_cases import SettingsUseCases
from wildintel_uploader.modules.settings.domain.ports import (
    ActivityLog, Machine, RecordStorage, SettingsConfigs, SettingsEditing, SettingsOfBefore, SettingsReading, SettingsService, SettingsStore,
)
from wildintel_uploader.modules.settings.infrastructure.system import AppRecordStorage, ThisMachine
from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


def build_settings(store: SettingsStore | None = None, *, activity_log: ActivityLog | None = None, machine: Machine | None = None,
                   record_storage: RecordStorage | None = None) -> SettingsService:
    """The settings: their use cases over the TOML files of the user's config folder, the log of the app, this computer and the backends of the
    records."""
    return SettingsUseCases(store or config.settings_store(), config.default_data_dir(), activity_log=activity_log or w.app_log(),
                            machine=machine or ThisMachine(), record_storage=record_storage or AppRecordStorage())


class SettingsProvider(Provider):
    """The module of the settings."""

    @provide(scope=Scope.REQUEST)
    def store(self) -> SettingsStore:
        return config.settings_store()

    @provide(scope=Scope.APP)
    def activity_log(self) -> ActivityLog:
        return w.app_log()

    @provide(scope=Scope.APP)
    def machine(self) -> Machine:
        return ThisMachine()

    @provide(scope=Scope.APP)
    def record_storage(self) -> RecordStorage:
        return AppRecordStorage()

    @provide(scope=Scope.REQUEST)
    def service(self, store: SettingsStore, activity_log: ActivityLog, machine: Machine, record_storage: RecordStorage) -> SettingsService:
        return build_settings(store, activity_log=activity_log, machine=machine, record_storage=record_storage)

    # each part of the contract, for whoever needs only that one: the same service of the request
    reading = alias(source=SettingsService, provides=SettingsReading)
    editing = alias(source=SettingsService, provides=SettingsEditing)
    configs = alias(source=SettingsService, provides=SettingsConfigs)
    of_before = alias(source=SettingsService, provides=SettingsOfBefore)
