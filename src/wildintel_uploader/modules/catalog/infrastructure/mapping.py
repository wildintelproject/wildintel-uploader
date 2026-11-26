"""The records of the catalog as the JSON files keep them (dicts) and as the domain has them, one into the other. A trapper kept before the ids existed
gets the same id whenever it is read (shared.ids.legacy_id), and is written with it the next time."""
from __future__ import annotations

from typing import Any

from wildintel_uploader.modules.catalog.domain.models import Audit, Location, ResearchProject, Trapper
from wildintel_uploader.shared import ids

def _extra(record: dict[str, Any], known: tuple[str, ...]) -> dict[str, Any]:
    """What a record says that the domain does not know — kept, to be written back as it was."""
    return {k: v for k, v in record.items() if k not in known and k not in _AUDIT}


_TRAPPER = ("username", "name", "affiliation", "email", "status", "trapper_pk")
_AUDIT = ("id", "created_at", "updated_at", "deleted_at")


def trapper_from_record(record: dict[str, Any]) -> Trapper:
    audit = Audit(**{k: record.get(k) for k in _AUDIT})
    if not audit.id:
        audit = Audit(id=ids.legacy_id("trapper", record.get("username") or record.get("name") or ""), created_at=audit.created_at,
                      updated_at=audit.updated_at, deleted_at=audit.deleted_at)
    return Trapper(**{k: record[k] for k in _TRAPPER if k in record and record[k] is not None}, audit=audit, extra=_extra(record, _TRAPPER))


def trapper_to_record(trapper: Trapper) -> dict[str, Any]:
    """As it is written: every field, the empty ones too, and the dates it has."""
    record: dict[str, Any] = {**trapper.extra, **{k: getattr(trapper, k) for k in _TRAPPER}}
    record.update({k: getattr(trapper.audit, k) for k in _AUDIT if getattr(trapper.audit, k) is not None})
    return record


_PROJECT = ("name", "acronym", "sampling_design", "sensor_method", "animal_types", "bait_use", "event_interval", "status", "keywords", "abstract",
            "methods", "description", "trapper_pk")


def project_from_record(record: dict[str, Any]) -> ResearchProject:
    audit = Audit(**{k: record.get(k) for k in _AUDIT})
    return ResearchProject(**{k: record[k] for k in _PROJECT if k in record and record[k] is not None}, audit=audit, extra=_extra(record, _PROJECT))


def project_to_record(project: ResearchProject) -> dict[str, Any]:
    """As it is written: every field — the empty ones too —, and the dates it has."""
    record: dict[str, Any] = {**project.extra, **{k: getattr(project, k) for k in _PROJECT}}
    record.update({k: getattr(project.audit, k) for k in _AUDIT if getattr(project.audit, k) is not None})
    return record


_LOCATION = ("location_id", "name", "timezone", "ignore_dst", "latitude", "longitude", "coordinate_uncertainty", "in_service", "trapper_pk", "status",
             "status_date", "status_note")


def location_from_record(record: dict[str, Any], project: str) -> Location:
    """A location as it is kept — one kept before the ids existed gets the same id whenever it is read; one kept as "retired" is archived."""
    values = {k: record[k] for k in _LOCATION if k in record and record[k] is not None}
    if values.get("status") == "retired":
        values["status"] = "archived"
    audit = Audit(**{k: record.get(k) for k in _AUDIT})
    if not audit.id:
        audit = Audit(id=ids.legacy_id("locations", record.get("location_id", ""), project), created_at=audit.created_at, updated_at=audit.updated_at,
                      deleted_at=audit.deleted_at)
    return Location(**values, audit=audit, extra=_extra(record, _LOCATION))


def location_to_record(location: Location) -> dict[str, Any]:
    """As it is written: every field — the empty ones too —, and the dates it has."""
    record: dict[str, Any] = {**location.extra, **{k: getattr(location, k) for k in _LOCATION}}
    record.update({k: getattr(location.audit, k) for k in _AUDIT if getattr(location.audit, k) is not None})
    return record
