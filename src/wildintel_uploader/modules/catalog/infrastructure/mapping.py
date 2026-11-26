"""The records of the catalog as the JSON files keep them (dicts) and as the domain has them, one into the other. What was kept before the ids existed
gets the same id whenever it is read (shared.ids.legacy_id), and is written with it the next time."""
from __future__ import annotations

from typing import Any

from wildintel_uploader.modules.catalog.domain.models import Audit, Trapper
from wildintel_uploader.shared import ids

_TRAPPER = ("username", "name", "affiliation", "email", "status", "trapper_pk")
_AUDIT = ("id", "created_at", "updated_at", "deleted_at")


def trapper_from_record(record: dict[str, Any]) -> Trapper:
    audit = Audit(**{k: record.get(k) for k in _AUDIT})
    if not audit.id:
        audit = Audit(id=ids.legacy_id("trapper", record.get("username") or record.get("name") or ""), created_at=audit.created_at,
                      updated_at=audit.updated_at, deleted_at=audit.deleted_at)
    return Trapper(**{k: record[k] for k in _TRAPPER if k in record and record[k] is not None}, audit=audit)


def trapper_to_record(trapper: Trapper) -> dict[str, Any]:
    """As it is written: every field, the empty ones too, and the dates it has."""
    record: dict[str, Any] = {k: getattr(trapper, k) for k in _TRAPPER}
    record.update({k: getattr(trapper.audit, k) for k in _AUDIT if getattr(trapper.audit, k) is not None})
    return record
