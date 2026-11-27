"""The web API of the visits as JSON — Pydantic models of what the requests send, for the routers of entrypoints/api/visits.py, with their fields
and their checks as they were, so that the API did not change."""
from __future__ import annotations

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
    # needs become required (see visits_csv.CREATABLE).
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
