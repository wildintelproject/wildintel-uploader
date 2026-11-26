"""FastAPI routers — the catalog (module `modules.catalog`): the people who go to the field (trappers), adding them in the initial setup, the research
projects and their locations — at /api/catalog, and at the addresses the pages have always used (/api/deployment-import/research-projects/…,
/api/deployment-import/locations/…).

They only translate: a request into a call to the contract of the module (`domain.ports.CatalogService`), given by Dishka, and its answer or its
error into HTTP. The people are given as the files keep them: their fields, their id and their dates."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pathlib import Path
from typing import Literal

from wildintel_uploader.core.schemas.requests import (
    DeleteLocationRequest, LocalLocationsRequest, LocationRecord, ResearchProjectRecord, SaveLocationRequest, UpdateLocationRequest,
    UpdateResearchProjectRequest,
)
from wildintel_uploader.entrypoints.catalog_storage import move_catalog
from wildintel_uploader.modules.catalog.application.migration import TargetNotEmpty
from wildintel_uploader.modules.settings.domain.ports import SettingsService
from wildintel_uploader.modules.catalog.domain.models import (
    Audit, CatalogError, Location, LocationExists, LocationFromTrapper, LocationHasVisits, LocationTimeFixed, ProjectExists, ProjectNotEmpty,
    ResearchProject, Trapper, UnknownLocation, UnknownProject,
)
from wildintel_uploader.shared.storage import StorageError, valid_project_id
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


# ── where the catalog is kept ──

class MoveCatalogRequest(BaseModel):
    to: Literal["json", "sqlite"]
    database: str | None = None      # the SQLite database — else catalog.sqlite3 in the data folder
    replace: bool = False


@router.post("/migrate")
def migrate_catalog(req: MoveCatalogRequest, settings: FromDishka[SettingsService]) -> dict:
    """Moves the catalog to `to`, and keeps it there from now on: {"trappers", "projects"} copied. 409: the place holds a catalog already (replace
    it); 422: it is there already, or what was copied does not read back as it was — the catalog then stays where it was."""
    try:
        copied = move_catalog(settings, req.to, database=Path(req.database) if req.database else None, replace=req.replace)
    except TargetNotEmpty as exc:
        raise HTTPException(409, exc.message) from exc
    except CatalogError as exc:
        raise _refused(exc) from exc
    return {"trappers": copied.trappers, "projects": copied.projects}


# ── the locations ──

def _location(location: Location) -> dict:
    return _record(location)


def _new_location(body: LocationRecord) -> Location:
    """A location as the request says it — validated by its model (timezone, coordinates…), and new: its id and dates are the catalog's to give."""
    return Location(**body.model_dump())


# what the old addresses answer for each error of the locations
def _location_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (UnknownLocation, UnknownProject)):
        return HTTPException(404, str(exc))
    if isinstance(exc, (LocationExists, LocationTimeFixed, LocationHasVisits, LocationFromTrapper)):
        return HTTPException(409, exc.message)  # type: ignore[attr-defined]
    if isinstance(exc, CatalogError):
        return HTTPException(400, exc.message)
    return HTTPException(400, str(exc))


@router.get("/projects/{project}/locations")
def get_locations(project: str, catalog: Catalog, include_deleted: bool = False) -> list[dict]:
    """The locations of a research project — the removed ones only with include_deleted."""
    return [_location(loc) for loc in catalog.locations(project, include_deleted)]


@router.post("/projects/{project}/locations", status_code=201)
def add_location(project: str, location: LocationRecord, catalog: Catalog, by_hand: bool = True) -> dict:
    """A new location of a research project — by hand it starts pending or planned. 409: its id is taken; 404: no such research project."""
    try:
        return _location(catalog.add_location(project, _new_location(location), by_hand=by_hand))
    except (CatalogError, UnknownProject, StorageError) as exc:
        raise _location_error(exc) from exc


@router.patch("/projects/{project}/locations/{location_id}")
def update_location(project: str, location_id: str, changes: dict[str, Any], catalog: Catalog) -> dict:
    """Changes the fields the body names. 404: it is not kept; 409: its timezone or summer-time setting, which are fixed; 400: what the visits or
    the rules do not allow."""
    try:
        return _location(catalog.update_location(project, location_id, changes))
    except (CatalogError, UnknownLocation) as exc:
        raise _location_error(exc) from exc
    except TypeError as exc:   # a field a location does not have
        raise HTTPException(422, str(exc)) from exc


@router.delete("/projects/{project}/locations/{location_id}")
def delete_location(project: str, location_id: str, catalog: Catalog) -> dict:
    """Removes a location — logically. 404: it is not kept; 409: it has visits, or comes from TRAPPER."""
    try:
        catalog.delete_location(project, location_id)
    except (CatalogError, UnknownLocation) as exc:
        raise _location_error(exc) from exc
    return {"deleted": location_id}


# ── the locations, at the addresses of before ──

@import_router.post("/locations/list")
def list_locations_before(req: LocalLocationsRequest, catalog: Catalog) -> dict:
    """The locations kept for a research project in the collections folder."""
    try:
        valid_project_id(req.research_project_id)
    except StorageError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"results": [_location(loc) for loc in catalog.locations(req.research_project_id)]}


@import_router.post("/locations/save")
def save_location_before(req: SaveLocationRequest, catalog: Catalog) -> dict:
    """Adds a location to a research project already kept in the collections folder (by hand, or as filled in from TRAPPER) — 409 if its id is
    used."""
    try:
        return _location(catalog.add_location(req.research_project_id, _new_location(req.location), by_hand=req.by_hand))
    except LocationExists as exc:
        raise HTTPException(409, exc.message) from exc
    except (CatalogError, UnknownProject, StorageError) as exc:
        raise HTTPException(400, getattr(exc, "message", str(exc))) from exc


@import_router.post("/locations/update")
def update_location_before(req: UpdateLocationRequest, catalog: Catalog) -> dict:
    """Changes a kept location — its name, where it is, its status. Its timezone and its summer-time setting are fixed when it is created: asking
    for a different one is a 409. The fields left out stay as they are; 404 if the location isn't there."""
    changes = req.model_dump(include={"name", "latitude", "longitude", "coordinate_uncertainty", "timezone", "ignore_dst", "in_service", "status",
                                      "status_date", "status_note"}, exclude_unset=True)
    if changes.get("status") is None:
        changes.pop("status", None)
    try:
        return _location(catalog.update_location(req.research_project_id, req.location_id, changes))
    except UnknownLocation as exc:
        raise HTTPException(404, str(exc)) from exc
    except CatalogError as exc:   # what can't be changed — its timezone, the status of an archived one — is a 409, as it was
        raise HTTPException(409 if "can't be changed" in exc.message else 400, exc.message) from exc


@import_router.post("/locations/delete")
def delete_location_before(req: DeleteLocationRequest, catalog: Catalog) -> dict:
    """Deletes a kept location — 409 when visits were made to it (or it comes from TRAPPER), 404 if it isn't there."""
    try:
        found = catalog.location(req.research_project_id, req.location_id)
        catalog.delete_location(req.research_project_id, req.location_id)
    except UnknownLocation as exc:
        raise HTTPException(404, str(exc)) from exc
    except (LocationHasVisits, LocationFromTrapper) as exc:
        raise HTTPException(409, exc.message) from exc
    except CatalogError as exc:
        raise HTTPException(400, exc.message) from exc
    return {"deleted": found.location_id}
