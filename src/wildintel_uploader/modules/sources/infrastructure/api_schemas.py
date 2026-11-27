"""The web API of the sources as JSON — Pydantic models of what the requests send, for the routers of entrypoints/api/sources.py."""
from __future__ import annotations

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
