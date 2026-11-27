"""Epicollect5 as a source of visits and of the details of a deployment — now the module `modules.sources` (#248). What is left here are the names
the code of before calls, each asking that module; EpicollectError is its SourceError."""
from __future__ import annotations

from wildintel_uploader.entrypoints import config
from wildintel_uploader.modules.sources.domain.models import (  # noqa: F401 — the names of before
    VISIT_COLUMNS, VISIT_QUESTIONS, SourceError as EpicollectError, entry_fields, parse_project, unmapped_notes, visit_actions, visit_row,
)
from wildintel_uploader.modules.sources.domain.settings import Epicollect5Settings
from wildintel_uploader.modules.sources.infrastructure.epicollect5 import forget_tokens  # noqa: F401
from wildintel_uploader.modules.sources.infrastructure.sources.epicollect_csv import form_columns, form_error, visits_from_csv  # noqa: F401


def _sources():
    from wildintel_uploader.entrypoints import wiring
    return wiring.build_sources()


def _epicollect5(settings: config.Settings | None) -> Epicollect5Settings | None:
    """The section of the settings given — as the file has it — as the module of the sources takes it; none, the settings in use."""
    return None if settings is None else Epicollect5Settings(**settings.EPICOLLECT5.model_dump())


def fetch_form(settings: config.Settings | None = None) -> dict:
    return _sources().project_form(_epicollect5(settings))


def test_connection(slug: str | None, client_id: str | None, client_secret: str | None, settings: config.Settings | None = None) -> dict:
    return _sources().test_connection(slug, client_id, client_secret, _epicollect5(settings))


def find_entries(location_id: str, revision: int | None, settings: config.Settings | None = None) -> list[dict]:
    """The entries that are this location's — and this revision's, when the form asks it —, newest first."""
    wanted = location_id.strip().lower()
    if not wanted:
        raise EpicollectError("Choose the location first.")
    return find_entries_of([wanted], revision, settings)[wanted]


def find_entries_of(location_ids: list[str], revision: int | None, settings: config.Settings | None = None) -> dict[str, list[dict]]:
    return _sources().deployment_entries(location_ids, revision, _epicollect5(settings))


def visits_csv(settings: config.Settings | None = None) -> str:
    return _sources().visits("epicollect-api", settings=_epicollect5(settings)).csv


def is_form_csv(text: str) -> bool:
    return form_error(text) is None
