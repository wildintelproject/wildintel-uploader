"""Where the modules are put together (#248) — the composition root, as Dishka providers: the one place that chooses the implementation of each module's
port in (its use cases) and of its ports out (the adapters). Dishka works out the rest: to give a SettingsService it makes the SettingsStore that
SettingsUseCases asks for.

The entry points take the modules from the container made here — the web API through dishka's FastAPI integration (`web/main.py`), the command line
through `entrypoints.cli.injection` — and ask only for contracts: `FromDishka[SettingsService]`.

What is made for a request or a command is made then (Scope.REQUEST), from the settings files config points at: so a test that points them elsewhere
is heeded. What should live as long as the app — a cache, a connection — would be Scope.APP."""
from __future__ import annotations

from dishka import Container, Provider, Scope, make_container, provide

from wildintel_uploader.core import config
from wildintel_uploader.modules.settings.application.use_cases import SettingsUseCases
from wildintel_uploader.modules.settings.domain.ports import ActivityLog, Machine, RecordStorage, SettingsService, SettingsStore
from wildintel_uploader.modules.settings.infrastructure.system import AppActivityLog, AppRecordStorage, ThisMachine


class SettingsProvider(Provider):
    """The module of the settings: its use cases over the TOML files of the user's config folder, the log of the app, this computer and the backends of
    the records — those three, with nothing to read anew, for as long as the app lives."""

    @provide(scope=Scope.REQUEST)
    def store(self) -> SettingsStore:
        return config.settings_store()

    @provide(scope=Scope.APP)
    def activity_log(self) -> ActivityLog:
        return AppActivityLog()

    @provide(scope=Scope.APP)
    def machine(self) -> Machine:
        return ThisMachine()

    @provide(scope=Scope.APP)
    def record_storage(self) -> RecordStorage:
        return AppRecordStorage()

    @provide(scope=Scope.REQUEST)
    def service(self, store: SettingsStore, activity_log: ActivityLog, machine: Machine, record_storage: RecordStorage) -> SettingsService:
        return SettingsUseCases(store, config.default_data_dir(), activity_log=activity_log, machine=machine, record_storage=record_storage)


def make_app_container() -> Container:
    """The container of the app: every module's provider."""
    return make_container(SettingsProvider())
