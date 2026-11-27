"""The catalog as the visits see it — the research projects, their locations, cameras, SD cards and people as the dicts the rules of the visits
read (domain.references, domain.rules) —, made from the catalog's own models (catalog.domain.models), asked of it through its contract. The
visits' view, not the shape the catalog keeps its records in: what the catalog keeps, and how, is its own.

Each field of a model is a key; its dates and its id (its audit) too, when it has them; and what the catalog keeps that this version does not
know (`extra`) as it is. What the visits give back — a location a file makes, the cameras and SD cards it makes or completes, the people it
names — is made into the catalog's models the same way."""
from __future__ import annotations

from dataclasses import fields
from typing import Any

from wildintel_uploader.modules.catalog.domain.models import Audit, Camera, Location, SdCard, Trapper

_AUDIT = ("id", "created_at", "updated_at", "deleted_at")
EQUIPMENT = {"cameras": Camera, "sd_cards": SdCard}


def _own(model_class) -> tuple[str, ...]:
    return tuple(f.name for f in fields(model_class) if f.name not in ("audit", "extra"))


def seen(model: Any) -> dict[str, Any]:
    """A model of the catalog as the visits read it."""
    seen = {**dict(model.extra), **{name: getattr(model, name) for name in _own(type(model))}}
    seen.update({k: getattr(model.audit, k) for k in _AUDIT if getattr(model.audit, k) is not None})
    return seen


def _made(model_class, given: dict[str, Any], *, new: bool, ignore: tuple[str, ...] = ()) -> Any:
    own = _own(model_class)
    values = {k: given[k] for k in own if given.get(k) is not None}
    audit = Audit() if new else Audit(**{k: given.get(k) for k in _AUDIT})
    extra = {k: v for k, v in given.items() if k not in own and k not in _AUDIT and k not in ignore}
    return model_class(**values, audit=audit, extra=extra)


def new_location(given: dict[str, Any]) -> Location:
    """A location a visit makes: its id and its dates are the catalog's to give."""
    return _made(Location, given, new=True)


def equipment(given: dict[str, Any], kind: str) -> Camera | SdCard:
    """A camera or an SD card as the visits give it back: with the id it has — none for a new one, which the catalog gives."""
    return _made(EQUIPMENT[kind], {"label": "", **given}, new=not given.get("id"), ignore=("research_project",))


def trapper(given: dict[str, Any]) -> Trapper:
    """A person as the visits give them back: with the id they have — none for a new one."""
    return _made(Trapper, given, new=not given.get("id"))
