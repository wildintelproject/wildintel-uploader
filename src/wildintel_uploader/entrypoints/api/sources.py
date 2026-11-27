"""FastAPI router — the sources (module `modules.sources`): the Epicollect5 project saved in the settings, at the addresses the pages have always
used (/api/epicollect/…). It asks only for the contract, SourcesService; what it refuses is a 400 with its words."""
from __future__ import annotations


from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException

from wildintel_uploader.modules.sources.domain.models import SourceError
from wildintel_uploader.modules.sources.domain.ports import SourcesService
from wildintel_uploader.modules.sources.infrastructure.api_schemas import BatchEntriesRequest, EntriesRequest, TestConnectionRequest

router = APIRouter(prefix="/api/epicollect", tags=["sources"], route_class=DishkaSyncRoute)
Sources = FromDishka[SourcesService]


@router.get("/form")
def form(sources: Sources) -> dict:
    """The inputs of the project's forms, to map them onto the fields of a deployment."""
    try:
        return sources.project_form()
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/test-connection")
def test_connection(req: TestConnectionRequest, sources: Sources) -> dict:
    """Whether the project can be read with what is typed in the settings, saved or not. Nothing is saved."""
    try:
        return sources.test_connection(req.project_slug, req.client_id, req.client_secret)
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/entries")
def entries(req: EntriesRequest, sources: Sources) -> dict:
    """The entries of the project that are this location's (and this revision's), as the fields of a deployment."""
    wanted = req.location_id.strip().lower()
    try:
        if not wanted:
            raise SourceError("Choose the location first.")
        return {"results": sources.deployment_entries([wanted], req.revision)[wanted]}
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/entries/batch")
def entries_batch(req: BatchEntriesRequest, sources: Sources) -> dict:
    """The newest entry of each location (and this revision) — null for one that has none — reading the project once.
    {"results": {location id as sent: entry or null}}"""
    try:
        found = sources.deployment_entries(req.location_ids, req.revision)
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"results": {loc: (found.get(loc.strip().lower()) or [None])[0] for loc in req.location_ids}}
