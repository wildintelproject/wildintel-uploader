"""The web API of the reports as JSON — what its routes answer (#248), for the routers of `entrypoints/api/reports.py`."""
from __future__ import annotations

from typing import Any
from pydantic import Field

from wildintel_uploader.shared.answers import Answer


# ── what the routes answer (#248) ──


class DeleteReportAnswer(Answer):
    """What DELETE /api/reports/{report_id} answers."""
    status: str | None = None


class ListReportsItem(Answer):
    """One of what GET /api/reports answers."""
    id: str | None = None
    kind: str | None = None
    title: str | None = None
    created_at: str | None = None
    source_dir: str | None = None
    deployment_id: Any = None
    checked: int | None = None
    totals: dict[str, Any] | None = None


class GetReportAnswer(Answer):
    """What GET /api/reports/{report_id} answers."""
    kind: str | None = None
    title: str | None = None
    created_at: str | None = None
    source_dir: str | None = None
    deployment_id: Any = None
    parameters: dict[str, Any] | None = None
    checked: int | None = None
    checks: dict[str, Any] | None = None
    totals: dict[str, Any] | None = None
    entries: list[Any] | None = None
    id: str | None = None
