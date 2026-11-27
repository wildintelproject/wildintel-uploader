"""The history of the states as the tests of before call it — by the collections folder — over the class the app uses (KeptStatusHistory, as
entrypoints.wiring puts the catalog together)."""
from pathlib import Path

from wildintel_uploader.modules.catalog.domain.history import BY_HAND, KINDS, UNKNOWN, because  # noqa: F401


def _history(root: Path):
    from wildintel_uploader.entrypoints.wiring import build_settings, build_visits, catalog_repository
    from wildintel_uploader.modules.catalog.infrastructure.status_history import KeptStatusHistory
    return KeptStatusHistory(root, lambda: catalog_repository(root, build_settings()), lambda: build_visits(root))


def record_changes(root: Path, research_project_id: str, kind: str, before: list[dict], after: list[dict], name_of, match) -> int:
    return _history(root).record_changes(research_project_id, kind, before, after, name_of, match)


def list_history(root: Path, research_project_id: str, kind: str | None = None, name: str | None = None) -> list[dict]:
    return _history(root).lines(research_project_id, kind, name)


def rebuild(root: Path, research_project_id: str, only_if_missing: bool = False) -> int:
    return _history(root).rebuild(research_project_id, only_if_missing)
