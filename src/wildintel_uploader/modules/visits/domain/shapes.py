"""The shapes the visits work with — plain Python: a visit, a visit not known, and what the visits see of the catalog (a location, a camera, an SD
card, a person). Typed dicts: what each holds, by name and kind, while it is still the dict the rules read and the records keep — so the rules
say what they take and give, and a type checker can hold them to it, without turning each into an object.

A visit is told (domain.references.as_told) with what it points to said by its name — `location_id`, `camera_id`, `sd`, `setup_by`, `trappers` —,
and kept (as_kept) by the ids of the records it points to — `location_ref`, `camera_ref`, `sd_ref`, `setup_by_ref`, `trapper_refs` —: a Visit
has both, and only one of each pair is there at a time."""
from __future__ import annotations

from typing import TypedDict


class Visit(TypedDict, total=False):
    """A visit to a camera trap, as the fieldwork datasheet keeps it (see infrastructure.records.VisitRecord, which checks it)."""
    id: str
    location_id: str                  # told: the location, by its id — kept: location_ref
    location_ref: str
    session: str                      # the revision: R0001, R0002…
    date: str                         # the wall clock of the location: YYYY-MM-DD
    time: str                         # HH:MM:SS
    when: str | None                  # the instant, in UTC
    actions: list[str]                # SiteStart, Installation, Revision, Desinstallation, Stolen, Archive
    trappers: str | None              # told: who went, by name, separated by commas — kept: trapper_refs
    trapper_refs: list[str]
    camera_status: str | None
    battery_status: str | None        # OK, NoBatteries
    card_status: str | None           # OK, CardFull
    num_photos: int | None
    sd: str | None                    # told: the SD card left, by its label — kept: sd_ref
    sd_ref: str
    date_time_ok: str | None
    calibration: bool | None
    latitude: float | None
    longitude: float | None
    deployment_id: str | None         # the deployment it started, once its images are imported
    state: str | None                 # deployed, collected, stolen, not_visited, no_camera
    created_at: str | None
    updated_at: str | None
    setup_by: str | None              # told: who set it up, by name — kept: setup_by_ref
    setup_by_ref: str
    camera_ref: str                   # the record of the camera, by its id (#231)
    camera_id: str | None             # its label
    camera_model: str | None
    camera_serial: str | None
    camera_interval: int | None
    camera_height: float | None
    camera_depth: float | None
    camera_tilt: int | None
    camera_heading: int | None
    detection_distance: float | None
    timestamp_issues: bool | None
    bait_use: bool | None
    feature_type: str | None
    habitat: str | None
    deployment_groups: str | None
    comments: str | None
    tags: list[str]
    card_batteries_ok: str | None     # kept by an earlier version: the batteries and the card in one field (see references.two_fields)


class ClosedVisit(TypedDict):
    """A visit that left a camera whose card a later visit collected — that later one, `end` —, with no deployment linked yet."""
    visit: Visit
    end: Visit


class Whereabouts(TypedDict, total=False):
    """Where a camera or an SD card is at a moment, as the visits before it say: the site, and the day and the revision of the visit that left it —
    with what was left (`camera`, or the card's `label`) while it is being worked out."""
    site: str
    date: str
    session: str | None
    camera: str
    label: str


class UnknownVisit(TypedDict, total=False):
    """A visit a revision lacks, whose day nobody knows: its site — told by location_id, kept by location_ref — and its revision."""
    location_id: str
    location_ref: str
    session: str


class Location(TypedDict, total=False):
    """A location as the visits see it (infrastructure.catalog_view)."""
    id: str
    location_id: str
    name: str | None
    timezone: str | None
    ignore_dst: bool | None
    latitude: float | None
    longitude: float | None
    coordinate_uncertainty: int | None
    in_service: str | None
    trapper_pk: int | None
    status: str                       # pending, ready, active, planned, archived
    status_date: str | None
    status_note: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None


class Camera(TypedDict, total=False):
    """A camera as the visits see it: its label, and its serial number (camera_id), make and model."""
    id: str
    label: str
    camera_id: str | None
    camera_make: str | None
    camera_model: str | None
    status: str
    status_date: str | None
    status_note: str | None
    archive_reason: str | None
    research_project: str
    deleted_at: str | None


class SdCard(TypedDict, total=False):
    """An SD card as the visits see it."""
    id: str
    label: str
    brand: str | None
    capacity: str | None
    status: str
    status_date: str | None
    status_note: str | None
    archive_reason: str | None
    research_project: str
    deleted_at: str | None


class Trapper(TypedDict, total=False):
    """A person, as the visits see them: their username and their name, which a visit says who went by."""
    id: str
    username: str
    name: str
    status: str
    deleted_at: str | None
