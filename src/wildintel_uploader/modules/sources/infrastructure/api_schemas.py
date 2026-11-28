"""The web API of the sources as JSON — Pydantic models of what the requests send, for the routers of entrypoints/api/sources.py."""
from __future__ import annotations

from typing import Any

from wildintel_uploader.shared.answers import Answer

from pydantic import BaseModel


class TestConnectionRequest(BaseModel):
    project_slug: str | None = None
    client_id: str | None = None
    client_secret: str | None = None


class EntriesRequest(BaseModel):
    location_id: str
    revision: int | None = None


class BatchEntriesRequest(BaseModel):
    location_ids: list[str]
    revision: int | None = None


# ── what the routes answer (#248) ──


class FormAnswer(Answer):
    """What GET /api/epicollect/form answers."""
    project: dict[str, Any] | None = None
    inputs: list[Any] | None = None


class EntriesAnswer(Answer):
    """What POST /api/epicollect/entries answers."""
    results: list[Any] | None = None


class EntriesBatchAnswer(Answer):
    """What POST /api/epicollect/entries/batch answers."""
    results: dict[str, Any] | None = None


class TestConnectionAnswer(Answer):
    """What POST /api/epicollect/test-connection answers."""
    ok: bool | None = None
    project: str | None = None
    slug: str | None = None
    forms: int | None = None
    inputs: int | None = None
