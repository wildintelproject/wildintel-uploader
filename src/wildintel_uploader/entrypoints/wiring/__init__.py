"""Where the modules are put together (#248) — the composition root: the one place that chooses the implementation of each module's port in (its use
cases) and of its ports out (the adapters).

Each module is built by a function here (`build_…`), in the factory of its context — common, settings, catalog, files, deployments, visits, uploaders,
backup —, with the Dishka provider that gives it (container makes them one container); the entry points that build one on their own use the same
functions, so that there is one way of putting a module together. A factory asks another's through this package (`w.build_catalog(…)`), when it is
called: so the factories do not import each other, and what a test puts in place here is heeded by all of them. Dishka works out the rest: to give a
CatalogService it gives the SettingsService the catalog asks for.

The entry points take the modules from the container made here — the web API through dishka's FastAPI integration (`web/main.py`), the command line
through `entrypoints.cli.injection` — and ask only for contracts: `FromDishka[SettingsService]`, `FromDishka[CatalogService]`.

What is resolved when
---------------------
- Scope.REQUEST — the settings, the catalog, the sources, the visits and the deployments: made for each request or command, from the settings files
  config points at then; a test that points them elsewhere is heeded.
- Scope.APP — the log, the machine, the storage of the records, the clock, what is known of the files, the checks, the preprocessing, the fixes of
  the dates, the uploaders, the backups and the reports: made once. None of them keeps a folder or a setting from when it was made: each asks for
  them when it needs them — `section("…")`, `lambda: config.collections_dir()`, a `root()` — so a change to the settings while the app runs (the
  data folder moved, an account kept) is heeded at once. An adapter given a Path where it should be given a function that says it would keep the
  folder of the start: that is the mistake to look for here.
- What is known of the files (file_info) is one for the whole process, on purpose — see it."""
from __future__ import annotations

from wildintel_uploader.entrypoints.wiring.common import section, keep_trapper_account, app_log, error_words, catalog_collections_dir, configure_runtime  # noqa: E402,F401
from wildintel_uploader.entrypoints.wiring.settings import build_settings, SettingsProvider  # noqa: E402,F401
from wildintel_uploader.entrypoints.wiring.catalog import catalog_of, build_catalog, catalog_record_store, catalog_repository, CatalogProvider  # noqa: E402,F401
from wildintel_uploader.entrypoints.wiring.files import file_info, build_reports, build_prevalidation, build_postvalidation, build_preprocessing, FileInfoProvider, ValidationProvider, PreprocessingProvider, ReportsProvider  # noqa: E402,F401
from wildintel_uploader.entrypoints.wiring.deployments import build_deployments, importing, sealing, repairing, revision_statistics, DeploymentsProvider  # noqa: E402,F401
from wildintel_uploader.entrypoints.wiring.visits import build_sources, build_visits, build_timefix, SourcesProvider, VisitsProvider, TimeFixProvider  # noqa: E402,F401
from wildintel_uploader.entrypoints.wiring.uploaders import build_uploaders, trapper_uploads, UploadersProvider  # noqa: E402,F401
from wildintel_uploader.entrypoints.wiring.backup import build_backup, BackupProvider  # noqa: E402,F401
from wildintel_uploader.entrypoints.wiring.container import make_app_container  # noqa: E402,F401

__all__ = [
    "configure_runtime",
    "section",
    "keep_trapper_account",
    "app_log",
    "error_words",
    "catalog_collections_dir",
    "build_settings",
    "SettingsProvider",
    "catalog_of",
    "build_catalog",
    "catalog_record_store",
    "catalog_repository",
    "CatalogProvider",
    "file_info",
    "build_reports",
    "build_prevalidation",
    "build_postvalidation",
    "build_preprocessing",
    "FileInfoProvider",
    "ValidationProvider",
    "PreprocessingProvider",
    "ReportsProvider",
    "build_deployments",
    "importing",
    "sealing",
    "repairing",
    "revision_statistics",
    "DeploymentsProvider",
    "build_sources",
    "build_visits",
    "build_timefix",
    "SourcesProvider",
    "VisitsProvider",
    "TimeFixProvider",
    "build_uploaders",
    "trapper_uploads",
    "UploadersProvider",
    "build_backup",
    "BackupProvider",
    "make_app_container",
]
