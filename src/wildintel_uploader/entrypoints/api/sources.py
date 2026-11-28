"""FastAPI router — the sources (module `modules.sources`): the Epicollect5 project saved in the settings, at the addresses the pages have always
used (/api/epicollect/…). It asks only for the part of the contract each route uses — the project (SourcesProject), the entries of a deployment
(SourcesDeployments) —; what it refuses is a 400 with its words."""
from __future__ import annotations


from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException

from wildintel_uploader.modules.sources.domain.models import SourceError
from wildintel_uploader.modules.sources.domain.ports import SourcesDeployments, SourcesProject
from wildintel_uploader.modules.sources.infrastructure.api_schemas import BatchEntriesRequest, EntriesRequest, TestConnectionRequest
from wildintel_uploader.modules.sources.infrastructure.api_schemas import (  # what its routes answer
    EntriesAnswer, EntriesBatchAnswer, FormAnswer, TestConnectionAnswer,
)

router = APIRouter(prefix="/api/epicollect", tags=["sources"], route_class=DishkaSyncRoute)
Project = FromDishka[SourcesProject]
DeploymentEntries = FromDishka[SourcesDeployments]


@router.get("/form", response_model=FormAnswer, response_model_exclude_unset=True)
def form(sources: Project) -> dict:
    """The inputs of the project's forms, to map them onto the fields of a deployment."""
    try:
        return sources.project_form()
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/test-connection", response_model=TestConnectionAnswer, response_model_exclude_unset=True)
def test_connection(req: TestConnectionRequest, sources: Project) -> dict:
    """Whether the project can be read with what is typed in the settings, saved or not. Nothing is saved."""
    try:
        return sources.test_connection(req.project_slug, req.client_id, req.client_secret)
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/entries", response_model=EntriesAnswer, response_model_exclude_unset=True)
def entries(req: EntriesRequest, sources: DeploymentEntries) -> dict:
    """The entries of the project that are this location's (and this revision's), as the fields of a deployment."""
    try:
        return {"results": sources.location_entries(req.location_id, req.revision)}
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/entries/batch", response_model=EntriesBatchAnswer, response_model_exclude_unset=True)
def entries_batch(req: BatchEntriesRequest, sources: DeploymentEntries) -> dict:
    """The newest entry of each location (and this revision) — null for one that has none — reading the project once.
    {"results": {location id as sent: entry or null}}"""
    try:
        found = sources.deployment_entries(req.location_ids, req.revision)
    except SourceError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"results": {loc: (found.get(loc.strip().lower()) or [None])[0] for loc in req.location_ids}}
