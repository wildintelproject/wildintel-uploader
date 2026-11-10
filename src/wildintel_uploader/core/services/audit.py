"""The dates the app keeps of what it keeps — when a visit, a location, a camera, an SD card, a trapper or a role was **created** (`created_at`), when it was last
**changed** (`updated_at`) and, if it was removed, when (`deleted_at`) — as an ORM keeps them: they are written by the app, when the thing is saved, and never typed. All are
the instant, ISO 8601, UTC, with a Z (`2026-11-10T12:34:56Z`).

  * a thing that is new gets `created_at` and `updated_at`, with the same instant;
  * one that is saved again keeps its `created_at`, and gets a new `updated_at` only if something else about it changed;
  * what a thing that was kept before these dates existed has is nothing: they are not made up — it gets `updated_at` the first time it changes;
  * **nothing is deleted**: what is removed gets `deleted_at` and is no longer listed (a *logical*, or soft, deletion), but it is still kept, with everything it said. If what is
    removed is added again it comes back, with its `created_at` and without its `deleted_at`. (What is no longer used is *archived*, a status of its own: archived things are
    still listed. Deleting is for what was a mistake, or is no longer wanted in the lists.)

What a client sends for them is not taken: the dates are those the app has kept.
"""
from __future__ import annotations

from datetime import datetime, timezone

from wildintel_uploader.core.services import ids   # the id is kept with the dates: a record has both, written by the app

AUDIT_FIELDS = ("created_at", "updated_at", "deleted_at")


def now() -> str:
    """The instant, as the dates of a record are written."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _content(record: dict) -> dict:
    """What a record says, apart from its dates, and with what it leaves empty (None or "") taken as not said."""
    return {k: v for k, v in record.items() if k not in AUDIT_FIELDS and k != "id" and v not in (None, "")}


def stamped(record: dict, before: dict | None, at: str | None = None, keep_given: bool = False) -> dict:
    """`record` with its `created_at` and `updated_at`, given what was kept of it before (`before`, None when it is new).

    `keep_given` takes the dates a *new* record already has — a record that is put back from a backup — instead of the instant of now."""
    at = at or now()
    out = {k: v for k, v in record.items() if k not in AUDIT_FIELDS and k != "id"}
    out["id"] = (before or {}).get("id") or ids.new_id()   # the id is the app's too: a record keeps the one it has, and what a client sends for it is not taken
    if before is None:
        created = (record.get("created_at") if keep_given else None) or at
        out["created_at"] = created
        out["updated_at"] = (record.get("updated_at") if keep_given else None) or created
        return out
    if before.get("created_at"):
        out["created_at"] = before["created_at"]
    if before.get("deleted_at"):   # it was removed and is here again: it comes back, and that is a change
        out["updated_at"] = at
        return out
    changed = _content(record) != _content(before)
    updated = at if changed else before.get("updated_at")
    if updated:
        out["updated_at"] = updated
    return out


def is_deleted(record: dict) -> bool:
    """Whether the record was removed (logically): it has a `deleted_at`."""
    return bool(record.get("deleted_at"))


def alive(records: list[dict]) -> list[dict]:
    """The records that were not removed — what is listed."""
    return [r for r in records if not is_deleted(r)]


def deleted(record: dict, at: str | None = None) -> dict:
    """`record`, removed: it keeps everything it said, and says when it was removed. One that was removed already is left as it is."""
    if is_deleted(record):
        return dict(record)
    at = at or now()
    return {**record, "deleted_at": at, "updated_at": at}


def touched(record: dict, at: str | None = None) -> dict:
    """`record`, changed in place by the app (a visit's state, the deployment it closed): its `updated_at` is now."""
    record["updated_at"] = at or now()
    return record
