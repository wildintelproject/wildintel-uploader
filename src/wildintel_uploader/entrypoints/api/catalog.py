"""FastAPI routers — the catalog (module `modules.catalog`): the people who go to the field (trappers), adding them in the initial setup, and the
research projects — at /api/catalog, and at the addresses the pages have always used (/api/deployment-import/research-projects/…).

They only translate: a request into a call to the contract of the module (`domain.ports.CatalogService`), given by Dishka, and its answer or its
error into HTTP. The people are given as the files keep them: their fields, their id and their dates."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from wildintel_uploader.core.schemas.requests import LocalLocationsRequest, ResearchProjectRecord, UpdateResearchProjectRequest
from wildintel_uploader.modules.catalog.domain.models import (
    Audit, CatalogError, ProjectExists, ProjectNotEmpty, ResearchProject, Trapper, UnknownProject,
)
from wildintel_uploader.shared.storage import StorageError
from wildintel_uploader.modules.catalog.domain.ports import CatalogService

router = APIRouter(prefix="/api/catalog", tags=["catalog"], route_class=DishkaSyncRoute)
# the initial setup adds people too, at the address it always had
setup_router = APIRouter(prefix="/api/setup", tags=["setup"], route_class=DishkaSyncRoute)
# the research projects, at the addresses the pages have always used
import_router = APIRouter(prefix="/api/deployment-import", tags=["catalog"], route_class=DishkaSyncRoute)

Catalog = FromDishka[CatalogService]


def _record(record: Any) -> dict:
    """A record of the catalog as JSON, as the files keep it: what it says that this version does not know, its fields, and its id and dates."""
    fields = {k: v for k, v in asdict(record).items() if k not in ("audit", "extra")}
    return {**dict(record.extra), **fields, **{k: v for k, v in asdict(record.audit).items() if v is not None}}


_trapper = _project = _record


def _refused(exc: CatalogError) -> HTTPException:
    return HTTPException(422, {"field": exc.field, "message": exc.message})


# ── the people ──

class TrapperBody(BaseModel):
    """A trapper as the page sends it: with its id when it is one that was kept."""
    username: str
    name: str
    affiliation: str | None = None
    email: str | None = None
    status: str = "active"
    trapper_pk: int | None = None
    id: str | None = None

    def to_domain(self) -> Trapper:
        return Trapper(username=self.username, name=self.name, affiliation=self.affiliation, email=self.email, status=self.status,
                       trapper_pk=self.trapper_pk, audit=Audit(id=self.id))


@router.get("/trappers")
def get_trappers(catalog: Catalog, include_deleted: bool = False) -> list[dict]:
    """The people. The removed ones only with include_deleted: the visits they made still say who they were."""
    return [_trapper(t) for t in catalog.trappers(include_deleted)]


@router.put("/trappers")
def save_trappers(trappers: list[TrapperBody], catalog: Catalog) -> list[dict]:
    """Keeps these as all the people: one is the one kept when it says its id, or its username; an archived one stays as it was; one no longer
    listed is removed — kept, with when —, and one listed again comes back. A trapper or a list that cannot be is a 422 that names what."""
    try:
        return [_trapper(t) for t in catalog.save_trappers([t.to_domain() for t in trappers])]
    except CatalogError as exc:
        raise _refused(exc) from exc


class NewTrapper(BaseModel):
    username: str = Field(min_length=1)
    name: str = Field(min_length=1)
    affiliation: str | None = None
    email: str | None = None


class NewTrappers(BaseModel):
    trappers: list[NewTrapper]


@setup_router.post("/trappers")
def add_trappers(req: NewTrappers, catalog: Catalog) -> dict:
    """Adds the trappers that are not kept yet — one with the username of another, whatever its case, is left out. {"added": [usernames],
    "skipped": [usernames]}."""
    try:
        added = catalog.add_trappers([Trapper(username=t.username, name=t.name, affiliation=t.affiliation, email=t.email) for t in req.trappers])
    except CatalogError as exc:
        raise _refused(exc) from exc
    return {"added": added.added, "skipped": added.skipped}


# ── the research projects ──

@router.get("/projects")
def get_projects(catalog: Catalog, include_deleted: bool = False) -> list[dict]:
    """The research projects — the removed ones only with include_deleted."""
    return [_project(p) for p in catalog.projects(include_deleted)]


@router.post("/projects", status_code=201)
def add_project(req: ResearchProjectRecord, catalog: Catalog) -> dict:
    """A new research project, and its folder. 409: its acronym is taken; 422: a field it cannot have."""
    try:
        return _project(catalog.add_project(ResearchProject(**req.model_dump())))
    except ProjectExists as exc:
        raise HTTPException(409, exc.message) from exc
    except CatalogError as exc:
        raise _refused(exc) from exc
    except StorageError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{acronym}")
def get_project(acronym: str, catalog: Catalog) -> dict:
    try:
        return _project(catalog.project(acronym))
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc


@router.patch("/projects/{acronym}")
def update_project(acronym: str, changes: dict[str, Any], catalog: Catalog) -> dict:
    """Changes the fields the body names — never the acronym. 404: it is not kept; 422: it is archived, it has visits and would go back to planned,
    or a field it cannot have."""
    try:
        return _project(catalog.update_project(acronym, changes))
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc
    except CatalogError as exc:
        raise _refused(exc) from exc
    except TypeError as exc:   # a field a research project does not have
        raise HTTPException(422, {"field": None, "message": str(exc)}) from exc


@router.delete("/projects/{acronym}")
def delete_project(acronym: str, catalog: Catalog) -> dict:
    """Removes a research project — logically. 404: it is not kept; 409: its folder holds collections, deployments or images; 422: it is archived."""
    try:
        catalog.delete_project(acronym)
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc
    except ProjectNotEmpty as exc:
        raise HTTPException(409, exc.message) from exc
    except CatalogError as exc:
        raise _refused(exc) from exc
    return {"deleted": acronym}


# ── the research projects, at the addresses of before: their answers and their errors, as they were ──

@import_router.post("/research-projects/list")
def list_research_projects(catalog: Catalog) -> dict:
    """The research projects kept — the wizard's first question, "where was it taken?", is answered from them. Empty until one is added."""
    return {"results": [_project(p) for p in catalog.projects()]}


@import_router.post("/research-projects/save")
def save_research_project(req: ResearchProjectRecord, catalog: Catalog) -> dict:
    """Adds a research project to the collections folder (by hand, or as filled in from TRAPPER) — 409 if its acronym is already there."""
    try:
        return _project(catalog.add_project(ResearchProject(**req.model_dump())))
    except ProjectExists as exc:
        raise HTTPException(409, exc.message) from exc
    except (CatalogError, StorageError) as exc:
        raise HTTPException(400, getattr(exc, "message", str(exc))) from exc


@import_router.post("/research-projects/update")
def update_research_project(req: UpdateResearchProjectRequest, catalog: Catalog) -> dict:
    """Changes a kept research project — its name, description, keywords and status…; the fields left out stay as they are (its acronym names its
    folder and can't change). 404 if it isn't there."""
    changes = req.model_dump(exclude={"acronym", "trapper_pk"}, exclude_none=True, exclude_unset=True)
    try:
        return _project(catalog.update_project(req.acronym, changes))
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc
    except CatalogError as exc:
        raise HTTPException(400, exc.message) from exc


@import_router.post("/research-projects/delete")
def delete_research_project(req: LocalLocationsRequest, catalog: Catalog) -> dict:
    """Removes a research project with its locations and visits — 409 when it holds anything more (collections, deployments, images), 404 if it
    isn't there."""
    try:
        catalog.delete_project(req.research_project_id)
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc
    except ProjectNotEmpty as exc:
        raise HTTPException(409, exc.message) from exc
    except CatalogError as exc:
        raise HTTPException(400, exc.message) from exc
    return {"deleted": req.research_project_id}
