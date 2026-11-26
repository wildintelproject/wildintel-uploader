"""FastAPI routers — the catalog (module `modules.catalog`): the people who go to the field (trappers), and adding them in the initial setup.

They only translate: a request into a call to the contract of the module (`domain.ports.CatalogService`), given by Dishka, and its answer or its
error into HTTP. The people are given as the files keep them: their fields, their id and their dates."""
from __future__ import annotations

from dataclasses import asdict

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from wildintel_uploader.modules.catalog.domain.models import Audit, CatalogError, Trapper
from wildintel_uploader.modules.catalog.domain.ports import CatalogService

router = APIRouter(prefix="/api/catalog", tags=["catalog"], route_class=DishkaSyncRoute)
# the initial setup adds people too, at the address it always had
setup_router = APIRouter(prefix="/api/setup", tags=["setup"], route_class=DishkaSyncRoute)

Catalog = FromDishka[CatalogService]


def _trapper(trapper: Trapper) -> dict:
    """A trapper as JSON: its fields, and its id and dates beside them, as the files keep them."""
    out = {k: v for k, v in asdict(trapper).items() if k != "audit"}
    out.update({k: v for k, v in asdict(trapper.audit).items() if v is not None})
    return out


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
