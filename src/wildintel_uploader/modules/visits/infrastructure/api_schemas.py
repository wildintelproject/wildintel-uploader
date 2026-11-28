"""The web API of the visits as JSON — Pydantic models of what the requests send, for the routers of entrypoints/api/visits.py, with their fields
and their checks as they were, so that the API did not change."""
from __future__ import annotations

from typing import Any

from wildintel_uploader.shared.answers import Answer

from datetime import date as date_type, time as time_type
from typing import Literal, Optional

from pydantic import BaseModel, Field

from wildintel_uploader.modules.visits.infrastructure.records import VisitRecord


class LocalLocationsRequest(BaseModel):
    research_project_id: str = Field(min_length=1)


class ListVisitsRequest(LocalLocationsRequest):
    """The visits of a research project — only those to one location when it is given."""

    location_id: Optional[str] = None


class CreateRevisionRequest(LocalLocationsRequest):
    """Plan the next revision: a visit to each location that is ready, planned."""


class MarkNotVisitedRequest(LocalLocationsRequest):
    """Finish a revision: the locations with no visit in it are marked as not visited."""

    session: str = Field(pattern=r"^R\d+$")


class SaveVisitRequest(LocalLocationsRequest):
    visit: VisitRecord


class UpdateVisitRequest(LocalLocationsRequest):
    """Edit a visit kept: its site and its revision are its key — they say which one it is, and do not change."""

    location_id: str = Field(min_length=1)
    session: str = Field(pattern=r"^R\d+$")
    visit: VisitRecord


class LinkVisitRequest(LocalLocationsRequest):
    """The visit that closed a deployment (found by its location, day and time), and the deployment."""

    location_id: str = Field(min_length=1)
    date: date_type
    time: time_type
    deployment_id: str = Field(min_length=1)


class CloseAfter(BaseModel):
    """The day a revision is closed on: so many days, weeks or months after its last visit (`after_last`), or before the first visit of the revision after it (`before_next`)."""
    amount: int = Field(ge=0)
    unit: Literal["days", "weeks", "months"] = "days"
    anchor: Literal["after_last", "before_next"] = "after_last"


class ImportVisitsCsvRequest(LocalLocationsRequest):
    """The text of a CSV file with visits — only read and checked unless `save` is set, then the visits that can be kept are."""

    csv: str = ""
    save: bool = False
    # How the file is read: with the column of each field said in `mapping`, as the download of the new Epicollect5 project, or as the entries of the Epicollect5
    # project of the settings (`csv` is then not used: they are read from Epicollect5).
    format: Literal["mapped", "epicollect-api", "epicollect-csv"] = "mapped"
    mapping: Optional[dict[str, str]] = None
    # What to create when the file names a location, a camera or an SD card that does not exist: {"locations": bool, "cameras": bool, "sd_cards": bool}. The fields each one
    # needs become required (see domain.visit_file.CREATABLE).
    create: Optional[dict[str, bool]] = None
    # The revision before the ones the file starts is closed when it has locations still planned: each is marked as not visited (an unknown one is not).
    close_revisions: bool = False
    # The day a revision that is closed is closed on — so long after its last visit, or before the first visit of the revision after it —: the locations still to be visited in
    # it are marked as not visited on that day. The same for every revision the file closes; none closes them on the day of their last visit.
    close_after: Optional[CloseAfter] = None
    # A row with no coordinates of the visit takes those of its location — unless this is off: then it is refused.
    coordinates_from_location: bool = True
    # The photos on the cards were not counted (an old datasheet): a Revision or a Desinstallation with no count is accepted, and the deployment is not checked against a count it has not.
    photos_not_counted: bool = False
    # The value of a field that the file has no column for, or whose cell is empty: {field: value}.
    defaults: Optional[dict[str, str]] = None


class VisitsCsvColumnsRequest(BaseModel):
    """The text of a CSV file whose columns are asked for, to map them to the fields of a visit."""

    csv: str


# ── what the routes answer (#248) ──


class VisitBookAnswer(Answer):
    """What POST /api/visits/book answers."""
    results: list[Any] | None = None


class ClosedVisitsAnswer(Answer):
    """What POST /api/visits/closed answers."""
    results: list[Any] | None = None


class CreateRevisionAnswer(Answer):
    """What POST /api/visits/create-revision answers."""
    session: str | None = None
    planned: list[Any] | None = None
    previous: dict[str, Any] | None = None


class CsvColumnsAnswer(Answer):
    """What POST /api/visits/csv-columns answers."""
    columns: list[Any] | None = None
    sample: list[Any] | None = None
    mapping: dict[str, Any] | None = None
    f_fields: list[Any] | None = Field(default=None, alias="fields")
    kind: str | None = None
    form_columns: dict[str, Any] | None = None
    form_error: str | None = None


class DeploymentsAnswer(Answer):
    """What POST /api/visits/deployments answers."""
    results: list[Any] | None = None


class EpicollectDownloadAnswer(Answer):
    """What POST /api/visits/epicollect-download answers."""
    csv: str | None = None
    count: int | None = None


class ImportVisitsCsvAnswer(Answer):
    """What POST /api/visits/import-csv answers."""
    visits: list[Any] | None = None
    problems: list[Any] | None = None
    rows: list[Any] | None = None
    skipped: int | None = None
    new_sites: list[Any] | None = None
    create: dict[str, Any] | None = None
    warnings: list[Any] | None = None
    loose_warnings: list[Any] | None = None
    notes: list[Any] | None = None
    unknown: list[Any] | None = None
    closed: list[Any] | None = None
    blocking: dict[str, Any] | None = None
    saved: int | None = None
    collection_folders: dict[str, Any] | None = None
    report: str | None = None


class LinkVisitAnswer(Answer):
    """What POST /api/visits/link answers."""
    session: str | None = None
    when: str | None = None
    actions: list[Any] | None = None
    camera_status: Any = None
    battery_status: Any = None
    card_status: Any = None
    num_photos: int | None = None
    sd: str | None = None
    date_time_ok: Any = None
    calibration: Any = None
    latitude: Any = None
    longitude: Any = None
    deployment_id: str | None = None
    state: str | None = None
    camera_id: str | None = None
    camera_model: str | None = None
    camera_serial: Any = None
    camera_interval: Any = None
    camera_height: float | None = None
    camera_depth: Any = None
    camera_tilt: Any = None
    camera_heading: Any = None
    detection_distance: Any = None
    timestamp_issues: Any = None
    bait_use: bool | None = None
    feature_type: Any = None
    habitat: str | None = None
    deployment_groups: Any = None
    comments: str | None = None
    tags: list[Any] | None = None
    id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    location_id: str | None = None
    setup_by: str | None = None
    trappers: str | None = None
    date: str | None = None
    time: str | None = None


class ListVisitsAnswer(Answer):
    """What POST /api/visits/list answers."""
    results: list[Any] | None = None


class MarkNotVisitedAnswer(Answer):
    """What POST /api/visits/mark-not-visited answers."""
    session: str | None = None
    marked: list[Any] | None = None


class SaveVisitAnswer(Answer):
    """What POST /api/visits/save answers."""
    session: str | None = None
    when: str | None = None
    actions: list[Any] | None = None
    trappers: str | None = None
    camera_status: str | None = None
    battery_status: str | None = None
    card_status: str | None = None
    num_photos: int | None = None
    date_time_ok: Any = None
    calibration: bool | None = None
    latitude: Any = None
    longitude: Any = None
    deployment_id: Any = None
    state: Any = None
    setup_by: str | None = None
    camera_ref: str | None = None
    camera_model: str | None = None
    camera_interval: Any = None
    camera_height: float | None = None
    camera_depth: Any = None
    camera_tilt: int | None = None
    camera_heading: Any = None
    detection_distance: Any = None
    timestamp_issues: Any = None
    bait_use: bool | None = None
    feature_type: str | None = None
    habitat: Any = None
    deployment_groups: Any = None
    comments: str | None = None
    tags: list[Any] | None = None
    id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    location_id: str | None = None
    camera_id: str | None = None
    camera_serial: str | None = None
    sd: str | None = None
    date: str | None = None
    time: str | None = None
    collection_folders: dict[str, Any] | None = None


class UpdateVisitAnswer(Answer):
    """What POST /api/visits/update answers."""
    session: str | None = None
    when: str | None = None
    actions: list[Any] | None = None
    camera_status: str | None = None
    battery_status: Any = None
    card_status: Any = None
    num_photos: int | None = None
    sd: str | None = None
    date_time_ok: Any = None
    calibration: Any = None
    latitude: Any = None
    longitude: Any = None
    deployment_id: Any = None
    state: str | None = None
    camera_id: str | None = None
    camera_model: Any = None
    camera_serial: str | None = None
    camera_interval: Any = None
    camera_height: Any = None
    camera_depth: Any = None
    camera_tilt: Any = None
    camera_heading: Any = None
    detection_distance: Any = None
    timestamp_issues: Any = None
    bait_use: Any = None
    feature_type: Any = None
    habitat: Any = None
    deployment_groups: Any = None
    comments: str | None = None
    tags: list[Any] | None = None
    id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    location_id: str | None = None
    setup_by: str | None = None
    trappers: str | None = None
    date: str | None = None
    time: str | None = None
    collection_folders: dict[str, Any] | None = None
    camera_ref: str | None = None


class VisitsExported(Answer):
    """The visits as the CSV of a file, its name, and how many."""
    csv: str | None = None
    filename: str | None = None
    count: int | None = None
