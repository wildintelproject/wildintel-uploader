"""FastAPI routers — the catalog (module `modules.catalog`): the people who go to the field (trappers), the research projects and their locations,
cameras, SD cards, roles and the history of their states — at /api/catalog, and at the addresses the pages have always used
(/api/deployment-import/…, /api/setup/…, /api/settings/field-item-status, /api/settings/status-history…, /api/settings/default-research-project).

They only translate: a request into a call to the contract of the module (`domain.ports.CatalogService`), given by Dishka, and its answer or its
error into HTTP. The people are given as the files keep them: their fields, their id and their dates."""
from __future__ import annotations

from typing import Any

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException

from pathlib import Path

from wildintel_uploader.modules.catalog.infrastructure.api_schemas import (
    record_shown,
    CameraIdentityRequest, DefaultResearchProjectRequest, DeleteLocationRequest, FieldItemsRequest, FieldItemStatusRequest, LocalLocationsRequest,
    LocationRecord, MoveCatalogRequest, NewTrappers, RebuildStatusHistoryRequest, ResearchProjectRecord, RoleBody, RolesRequest, SaveLocationRequest,
    StatusHistoryRequest, TrapperBody, UpdateLocationRequest, UpdateResearchProjectRequest,
)
from wildintel_uploader.entrypoints.catalog_storage import move_catalog
from wildintel_uploader.modules.catalog.application.migration import TargetNotEmpty
from wildintel_uploader.modules.settings.domain.ports import SettingsService
from wildintel_uploader.modules.catalog.domain.models import (
    Audit, Camera, CatalogError, Location, LocationExists, LocationFromTrapper, LocationHasVisits, LocationTimeFixed, ProjectExists, ProjectNotEmpty,
    ResearchProject, Role, SdCard, Trapper, UnknownCamera, UnknownLocation, UnknownProject, UnknownTrapper,
)
from wildintel_uploader.shared.storage import StorageError, valid_project_id
from wildintel_uploader.modules.catalog.domain.ports import CatalogService

router = APIRouter(prefix="/api/catalog", tags=["catalog"], route_class=DishkaSyncRoute)
# the initial setup adds people too, at the address it always had
setup_router = APIRouter(prefix="/api/setup", tags=["setup"], route_class=DishkaSyncRoute)
# the research projects, at the addresses the pages have always used
import_router = APIRouter(prefix="/api/deployment-import", tags=["catalog"], route_class=DishkaSyncRoute)
# what the settings page does with the catalog, at the addresses it has always used
settings_router = APIRouter(prefix="/api/settings", tags=["catalog"], route_class=DishkaSyncRoute)

Catalog = FromDishka[CatalogService]


_record = _trapper = _project = record_shown


def _refused(exc: CatalogError) -> HTTPException:
    return HTTPException(422, {"field": exc.field, "message": exc.message})


# ── the people ──

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


# ── the cameras, the SD cards and the roles ──

_EQUIPMENT = {"cameras": ("cameras", Camera), "sd-cards": ("sd_cards", SdCard)}


def _item_json(item: Any, project: str | None) -> dict:
    return {**_record(item), "research_project": project}


def _role_json(role: Role, project: str | None) -> dict:
    out = {k: v for k, v in _record(role).items() if k != "trapper_ref"}
    return {**out, "trapper": role.trapper, "research_project": project}


def _get_equipment(project: str, kind: str, catalog: CatalogService, include_deleted: bool) -> list[dict]:
    return [_item_json(i, project) for i in catalog.equipment(project, _EQUIPMENT[kind][0], include_deleted)]


def _save_equipment(project: str, kind: str, items: list[dict[str, Any]], catalog: CatalogService) -> list[dict]:
    """Keeps these as all the cameras or SD cards of a research project — by hand: their status changes only as the visits allow. One is the one
    kept when it says its id, or its label. 404: no such research project; 422: what can't be."""
    domain_kind, model = _EQUIPMENT[kind]
    try:
        wanted = [model(**{k: v for k, v in i.items() if k not in ("id", "created_at", "updated_at", "deleted_at", "research_project")},
                        audit=Audit(id=i.get("id"))) for i in items]
        return [_item_json(i, project) for i in catalog.save_equipment(project, domain_kind, wanted, by_hand=True)]
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc
    except CatalogError as exc:
        raise _refused(exc) from exc
    except TypeError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/projects/{project}/cameras")
def get_cameras(project: str, catalog: Catalog, include_deleted: bool = False) -> list[dict]:
    """The cameras of a research project — the removed ones only with include_deleted."""
    return _get_equipment(project, "cameras", catalog, include_deleted)


@router.put("/projects/{project}/cameras")
def save_cameras(project: str, items: list[dict[str, Any]], catalog: Catalog) -> list[dict]:
    """Keeps these as all the cameras of a research project — see _save_equipment."""
    return _save_equipment(project, "cameras", items, catalog)


@router.get("/projects/{project}/sd-cards")
def get_sd_cards(project: str, catalog: Catalog, include_deleted: bool = False) -> list[dict]:
    """The SD cards of a research project — the removed ones only with include_deleted."""
    return _get_equipment(project, "sd-cards", catalog, include_deleted)


@router.put("/projects/{project}/sd-cards")
def save_sd_cards(project: str, items: list[dict[str, Any]], catalog: Catalog) -> list[dict]:
    """Keeps these as all the SD cards of a research project — see _save_equipment."""
    return _save_equipment(project, "sd-cards", items, catalog)


@router.get("/projects/{project}/roles")
def get_roles(project: str, catalog: Catalog, include_deleted: bool = False) -> list[dict]:
    """The roles of the people in a research project, each told with the name its trapper has now."""
    return [_role_json(r, project) for r in catalog.roles(project, include_deleted)]


@router.put("/projects/{project}/roles")
def save_roles(project: str, roles: list[RoleBody], catalog: Catalog) -> list[dict]:
    """Keeps these as all the roles of a research project, each by the id of its trapper."""
    try:
        return [_role_json(r, project) for r in catalog.save_roles(project, [Role(trapper=r.trapper, role=r.role, audit=Audit(id=r.id)) for r in roles])]
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc
    except CatalogError as exc:
        raise _refused(exc) from exc


@router.get("/projects/{project}/history")
def get_history(project: str, catalog: Catalog, kind: str | None = None, name: str | None = None) -> list[dict]:
    """The history of the states of the locations, cameras and SD cards of a research project, the oldest first."""
    try:
        return catalog.status_history(project, kind, name)
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/projects/{project}/history/rebuild")
def rebuild_history(project: str, catalog: Catalog) -> dict:
    """Adds to the history what the visits say and it lacks: {"added"}."""
    try:
        return {"added": catalog.rebuild_status_history(project)}
    except UnknownProject as exc:
        raise HTTPException(404, str(exc)) from exc


# ── at the addresses of before ──

@import_router.post("/camera-identity")
def camera_identity(req: CameraIdentityRequest, catalog: Catalog) -> dict:
    """Keeps in a camera's record the make and the model its images say — what Camera consistency compares them with from then on."""
    try:
        return _item_json(catalog.set_camera_identity(req.research_project_id, req.label, req.make, req.model), req.research_project_id)
    except (UnknownCamera, CatalogError, StorageError) as exc:
        raise HTTPException(400, getattr(exc, "message", str(exc))) from exc


@setup_router.post("/roles")
def add_roles(req: RolesRequest, catalog: Catalog) -> dict:
    """Gives trappers a role in a research project: the ones it has already are left as they are, and a trapper that is not kept is refused.
    {"added": [[trapper, role]]}."""
    try:
        added = catalog.add_roles(req.research_project_id, [(r.trapper, r.role) for r in req.roles])
    except UnknownTrapper as exc:
        raise HTTPException(404, str(exc)) from exc
    except (UnknownProject, CatalogError, StorageError) as exc:
        raise HTTPException(400, getattr(exc, "message", str(exc))) from exc
    return {"added": [list(a) for a in added]}


@setup_router.post("/field-items")
def add_field_items(req: FieldItemsRequest, catalog: Catalog) -> dict:
    """Adds cameras or SD cards to a research project, active: one with the label of another is left out. {"added": [labels], "skipped": [labels]}."""
    own = ("camera_id", "camera_make", "camera_model") if req.kind == "cameras" else ("brand", "capacity")
    model = Camera if req.kind == "cameras" else SdCard
    try:
        items = [model(label=i.label, **{k: getattr(i, k) for k in own}) for i in req.items]
        added = catalog.add_equipment(req.research_project_id, req.kind, items)
    except (UnknownProject, CatalogError, StorageError) as exc:
        raise HTTPException(400, getattr(exc, "message", str(exc))) from exc
    return {"added": added.added, "skipped": added.skipped}


@settings_router.post("/field-item-status")
def set_field_item_status(req: FieldItemStatusRequest, catalog: Catalog) -> dict:
    """Marks a camera or an SD card of a research project as no longer available (stolen, lost…) — what a visit that finds a camera stolen says of
    it and of its card. Nothing happens, and `updated` is false, when the research project does not keep one called that — or when it is archived,
    which is for good and is never changed."""
    try:
        return {"updated": catalog.retire_equipment(req.research_project_id, req.kind, req.key, req.status, req.status_date, req.status_note)}
    except (UnknownProject, CatalogError, StorageError) as exc:
        raise HTTPException(400, getattr(exc, "message", str(exc))) from exc


@settings_router.post("/status-history")
def status_history_of(req: StatusHistoryRequest, catalog: Catalog) -> dict:
    """The history of the status of the locations, the cameras and the SD cards of a research project — of one kind, and of one of them, when they
    are given — the oldest first."""
    try:
        return {"results": catalog.status_history(req.research_project_id, req.kind, req.name)}
    except (UnknownProject, StorageError) as exc:
        raise HTTPException(400, str(exc)) from exc


@settings_router.post("/status-history/rebuild")
def rebuild_status_history(req: RebuildStatusHistoryRequest, catalog: Catalog) -> dict:
    """Rebuilds the history of the status of a research project from its visits, adding the lines it lacks — nothing of it is overwritten nor
    deleted. Says how many it added."""
    try:
        return {"added": catalog.rebuild_status_history(req.research_project_id)}
    except (UnknownProject, StorageError) as exc:
        raise HTTPException(400, str(exc)) from exc


@settings_router.put("/default-research-project")
def set_default_research_project(req: DefaultResearchProjectRequest, catalog: Catalog, settings: FromDishka[SettingsService]) -> dict:
    """Changes only the research project that comes filled in everywhere — what the selector of the header does. It must be one of the catalog: the
    catalog says it is, and the settings keep it."""
    found = next((p.acronym for p in catalog.projects() if p.acronym.lower() == req.acronym.strip().lower()), None)
    if found is None:
        raise HTTPException(404, f"There is no research project called {req.acronym!r} in the collections folder.")
    settings.save_section("GENERAL", {"default_research_project": found})
    return {"default_research_project": found}
