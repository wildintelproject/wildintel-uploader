"""The rules of the catalog over its records, pure functions: what a list of them may hold, and how a list that is saved becomes what is kept — who is
who, what is new, what changed, what was removed —, with the dates of each (#248). The instant and the new ids are given, so that the rules decide
nothing about the clock."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import fields, replace
from typing import Any, TypeVar

from wildintel_uploader.modules.catalog.domain.models import Audit, CatalogError, Trapper

R = TypeVar("R", bound=Any)  # a record of the catalog: a dataclass with an `audit`


def _content(record) -> dict:
    """What a record says, apart from its audit, with what it leaves empty taken as not said."""
    return {f.name: getattr(record, f.name) for f in fields(record) if f.name != "audit" and getattr(record, f.name) not in (None, "")}


def stamped(record: R, before: R | None, at: str, new_id: Callable[[], str]) -> R:
    """`record` — any record of the catalog — with its audit, given what was kept of it (`before`, None when it is new): a new one gets an id and is created and updated now; one
    kept before keeps its id and its creation, and is updated now if it says something else — or if it was removed and is here again."""
    if before is None:
        return replace(record, audit=Audit(id=new_id(), created_at=at, updated_at=at))
    if before.audit.deleted:
        return replace(record, audit=Audit(id=before.audit.id or new_id(), created_at=before.audit.created_at, updated_at=at))
    updated = at if _content(record) != _content(before) else before.audit.updated_at
    return replace(record, audit=Audit(id=before.audit.id or new_id(), created_at=before.audit.created_at, updated_at=updated))


def removed(record: R, at: str) -> R:
    """`record`, removed: it keeps everything it said and says when it was removed. One removed already is left as it is."""
    if record.deleted:
        return record
    return replace(record, audit=replace(record.audit, deleted_at=at, updated_at=at))


# ── the people ──

def checked_trappers(trappers: Iterable[Trapper]) -> list[Trapper]:
    """A list of people as it may be kept: a full name is listed once among those not removed (the first one stays; a removed one is kept as it is),
    and a username is one trapper's only, whatever its case — two with it are refused."""
    seen_names: set[str] = set()
    out: list[Trapper] = []
    for t in trappers:
        if not t.deleted:
            if t.name in seen_names:
                continue
            seen_names.add(t.name)
        out.append(t)
    usernames: dict[str, str] = {}
    for t in out:
        key = t.username.lower()
        if key in usernames:
            raise CatalogError("trappers", f"The username '{t.username}' is used by more than one trapper ({usernames[key]} and {t.name}): it is unique.")
        usernames[key] = t.name
    return out


def saved_trappers(kept: list[Trapper], wanted: list[Trapper], at: str, new_id: Callable[[], str]) -> list[Trapper]:
    """The people as they are kept once `wanted` is saved as all of them. A trapper is the one kept when it says its id — so one renamed, or whose
    username is corrected, is the same one, and what points to it still does — or, saying none, when it has the same username. An archived one is out
    of use for good: it stays as it was. One the list no longer has is removed — kept, with when it was —, and one listed again comes back."""
    by_id = {t.audit.id: t for t in kept if t.audit.id}
    by_username = {t.username.lower(): t for t in kept}
    out: list[Trapper] = []
    listed: set[str | None] = set()
    for trapper in wanted:
        before = by_id.get(trapper.audit.id) if trapper.audit.id else None
        before = before or by_username.get(trapper.username.lower())
        if before is not None:
            listed.add(before.audit.id)
            if before.status == "archived":
                out.append(before)
                continue
        out.append(stamped(trapper, before, at, new_id))
    out += [removed(t, at) for t in kept if t.audit.id not in listed]
    return out
