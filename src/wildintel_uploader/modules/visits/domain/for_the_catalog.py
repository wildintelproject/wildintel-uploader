"""What the visits offer the catalog — the one door of the module of the visits the catalog goes through (#248), narrow and kept stable: how a visit
is ordered and what it does to the cameras, the SD cards and the sites (for the history of their states), how the visits kept are read and told,
and why a status cannot be set by hand. The catalog needs them without the module of the visits, which needs the catalog; the rest of the domain of
the visits may change without the catalog knowing — an architecture test keeps the catalog to this module.

    >>> stamp({"when": "2026-06-10T09:00:00Z", "date": "2026-06-10", "time": "11:00:00"})
    '2026-06-10T09:00:00Z'
"""
from __future__ import annotations

from wildintel_uploader.modules.visits.domain import references, refusals, rules
from wildintel_uploader.modules.visits.domain.shapes import Camera, Location, SdCard, Trapper, UnknownVisit, Visit

__all__ = ["stamp", "entity_changes", "told", "unknown_told", "site_status_refusal", "camera_status_refusal", "card_status_refusal"]


def stamp(visit: Visit) -> str:
    """When a visit was, to order visits: its instant — the wall clock of its location only when it has none."""
    return rules.visit_stamp(visit)


def entity_changes(visit: Visit, before: list[Visit]) -> list[dict]:
    """What a visit does to the cameras, the SD cards and the site, given the visits before it: {"kind", "name", "status", "reason"} each."""
    return rules.entity_changes(visit, before)


def told(kept: list[Visit], locations: list[Location], cameras: list[Camera], sd_cards: list[SdCard], trappers: list[Trapper], project: str) -> list[Visit]:
    """The visits of a research project as they are kept, told with the names of what they point to (the catalog's records, as the visits see them)."""
    return references.read_kept(kept, references.Refs(locations, cameras, sd_cards, trappers), project)[1]


def unknown_told(kept: list[UnknownVisit], locations: list[Location]) -> list[UnknownVisit]:
    """The visits a revision lacks, as they are told — {"location_id", "session"} —, from how they are kept."""
    return references.unknown_told(kept, locations)


def site_status_refusal(visits: list[Visit], unknown: list[UnknownVisit], locations: list[Location], location: Location, wanted: str) -> str | None:
    """Why the status of a site cannot be set by hand to `wanted` — None when it can."""
    return refusals.site_status_refusal(visits, unknown, locations, location, wanted)


def camera_status_refusal(camera: Camera, wanted: str, visits: list[Visit]) -> str | None:
    """Why the status of a camera cannot be set by hand to `wanted` — None when it can."""
    return refusals.camera_status_refusal(camera, wanted, visits)


def card_status_refusal(card: SdCard, wanted: str, visits: list[Visit]) -> str | None:
    """Why the status of an SD card cannot be set by hand to `wanted` — None when it can."""
    return refusals.card_status_refusal(card, wanted, visits)
