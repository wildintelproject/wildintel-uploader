"""The container of the app: every module's provider (Dishka)."""
from __future__ import annotations

from dishka import Container, Provider, make_container

from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


def providers() -> list[Provider]:
    """Every module's provider — what the container of the app is made of, and what a test asks it all of."""
    return [w.SettingsProvider(), w.CatalogProvider(), w.FileInfoProvider(), w.ValidationProvider(), w.PreprocessingProvider(), w.SourcesProvider(),
            w.VisitsProvider(), w.DeploymentsProvider(), w.TimeFixProvider(), w.UploadersProvider(), w.BackupProvider(), w.ReportsProvider()]


def make_app_container() -> Container:
    """The container of the app: every module's provider — the runtime told of the settings first (configure_runtime)."""
    w.configure_runtime()
    return make_container(*providers())
