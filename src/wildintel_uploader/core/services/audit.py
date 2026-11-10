"""The two dates the app keeps of what it keeps — when a visit, a camera or an SD card was **created** (`created_at`) and when it was last **changed**
(`updated_at`) — as an ORM keeps them: they are written by the app, when the thing is saved, and never typed. Both are the instant, ISO 8601, UTC, with a Z
(`2026-11-10T12:34:56Z`).

  * a thing that is new gets both, with the same instant;
  * one that is saved again keeps its `created_at`, and gets a new `updated_at` only if something else about it changed;
  * what a thing that was kept before these dates existed has is nothing: they are not made up — it gets `updated_at` the first time it changes.

What a client sends for them is not taken: the dates are those the app has kept.
"""
from __future__ import annotations

from datetime import datetime, timezone

AUDIT_FIELDS = ("created_at", "updated_at")


def now() -> str:
    """The instant, as the dates of a record are written."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _content(record: dict) -> dict:
    """What a record says, apart from its dates, and with what it leaves empty (None or "") taken as not said."""
    return {k: v for k, v in record.items() if k not in AUDIT_FIELDS and v not in (None, "")}


def stamped(record: dict, before: dict | None, at: str | None = None, keep_given: bool = False) -> dict:
    """`record` with its `created_at` and `updated_at`, given what was kept of it before (`before`, None when it is new).

    `keep_given` takes the dates a *new* record already has — a record that is put back from a backup — instead of the instant of now."""
    at = at or now()
    out = {k: v for k, v in record.items() if k not in AUDIT_FIELDS}
    if before is None:
        created = (record.get("created_at") if keep_given else None) or at
        out["created_at"] = created
        out["updated_at"] = (record.get("updated_at") if keep_given else None) or created
        return out
    if before.get("created_at"):
        out["created_at"] = before["created_at"]
    changed = _content(record) != _content(before)
    updated = at if changed else before.get("updated_at")
    if updated:
        out["updated_at"] = updated
    return out


def touched(record: dict, at: str | None = None) -> dict:
    """`record`, changed in place by the app (a visit's state, the deployment it closed): its `updated_at` is now."""
    record["updated_at"] = at or now()
    return record
