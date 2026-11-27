"""The container of the app: every module's provider (Dishka)."""
from __future__ import annotations

from dishka import Container, make_container

from wildintel_uploader.entrypoints import wiring as w   # the other factories, asked when called


def make_app_container() -> Container:
    """The container of the app: every module's provider."""
    return make_container(w.SettingsProvider(), w.CatalogProvider(), w.FileInfoProvider(), w.ValidationProvider(), w.PreprocessingProvider(), w.SourcesProvider(), w.VisitsProvider(), w.DeploymentsProvider(), w.TimeFixProvider(), w.UploadersProvider(), w.BackupProvider(), w.ReportsProvider())
