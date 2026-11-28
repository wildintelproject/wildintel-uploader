"""A file of visits as a CSV: its rows (the delimiter the header has most of), its text written for a spreadsheet, and its cells and records
checked with the models of the visits — each cell read as its field takes it (domain.visit_file says how), what is wrong told with the code of
its kind."""
from __future__ import annotations

import csv
import io
from typing import cast

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError

from wildintel_uploader.modules.visits.domain import rules as visit_rules
from wildintel_uploader.modules.visits.domain import visit_file as rules
from wildintel_uploader.modules.visits.domain.ports import Visit, VisitFile
from wildintel_uploader.modules.visits.domain.shapes import Location
from wildintel_uploader.modules.visits.domain.visit_file import ERROR_LABELS, RowError, VisitsCsvError
from wildintel_uploader.modules.visits.infrastructure.records import NewLocationRecord as LocationRecord, VisitRecord


def _custom(code: str, message: str, value) -> PydanticCustomError:
    return PydanticCustomError(code, message, {"value": value})


def _read(value, reader, code: str, template: str | None = None):
    read = reader(value)
    if read is None:
        raise _custom(code, template or rules.CELL_ERRORS[code], value)
    return read


class CsvVisit(BaseModel):
    """The cells of a row of the file, read as what they say of a visit — all text, as the file has it. A cell that is not what its field takes raises an error with
    its code (see ERROR_LABELS); what the row does not say is left unset, so that only what it says is kept (`model_dump(exclude_unset=True)`)."""

    model_config = ConfigDict(extra="ignore")

    actions: list[str] = []
    session: str | None = None
    camera_status: str | None = None
    trappers: str | None = None
    sd: str | None = None
    date_time_ok: str | None = None
    camera_id: str | None = None
    camera_model: str | None = None
    camera_serial: str | None = None   # #231: the serial number finds the camera, or creates or completes its record
    camera_make: str | None = None
    comments: str | None = None
    setup_by: str | None = None
    battery_status: str | None = None
    card_status: str | None = None
    card_batteries_ok: str | None = None   # how it was before: one column for both
    num_photos: int | None = None
    camera_interval: int | None = None
    camera_tilt: int | None = None
    camera_heading: int | None = None
    camera_height: float | None = None
    camera_depth: float | None = None
    detection_distance: float | None = None
    timestamp_issues: bool | None = None
    bait_use: bool | None = None
    calibration: bool | None = None
    feature_type: str | None = None
    habitat: str | None = None
    deployment_groups: str | None = None
    tags: list[str] | None = None
    latitude: float | None = None
    longitude: float | None = None

    @field_validator("actions", mode="before")
    @classmethod
    def _actions(cls, value):
        return _read(value, rules.actions_of, "actions_invalid")

    @field_validator("session", mode="before")
    @classmethod
    def _session(cls, value):
        return _read(value, rules.session_of, "session_invalid")

    @field_validator("card_batteries_ok", mode="before")
    @classmethod
    def _card_batteries(cls, value):
        return _read(value, rules.card_code, "card_batteries_invalid")

    @field_validator("battery_status", mode="before")
    @classmethod
    def _battery(cls, value):
        return _read(value, visit_rules.battery_status_code, "battery_status_invalid")

    @field_validator("card_status", mode="before")
    @classmethod
    def _card(cls, value):
        return _read(value, visit_rules.card_status_code, "card_status_invalid")

    @field_validator("camera_status", mode="before")
    @classmethod
    def _camera_status(cls, value):
        statuses = visit_rules.CAMERA_STATUSES
        return _read(value, visit_rules.camera_status_code, "camera_status_invalid", "'{value}' is not " + ", ".join(statuses[:-1]) + " or " + statuses[-1] + ".")

    @field_validator("num_photos", "camera_interval", "camera_tilt", "camera_heading", mode="before")
    @classmethod
    def _whole(cls, value):
        return _read(value, rules.whole_of, "number_invalid", rules.CELL_ERRORS["whole_invalid"])

    @field_validator("camera_height", "camera_depth", "detection_distance", "latitude", "longitude", mode="before")
    @classmethod
    def _number(cls, value):
        return _read(value, rules.number_of, "number_invalid")

    @field_validator("timestamp_issues", "bait_use", "calibration", mode="before")
    @classmethod
    def _yes_no(cls, value):
        return _read(value, rules.yes_no_of, "yes_no_invalid")

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, value):
        return rules.tags_of(value)

    @model_validator(mode="after")
    def _something_was_done(self):
        # a visit that could not be made has no action: it is exported so, and read back so
        if not self.actions and not visit_rules.is_not_revised({"camera_status": self.camera_status}):
            raise _custom("actions_invalid", rules.CELL_ERRORS["actions_invalid"], "")
        return self


def _problem_of(exc: ValidationError) -> RowError:
    """The first error of a validation: a custom error of CsvVisit as it is, the others — a value the model of the visit refuses — as "visit_invalid",
    with the field they are of."""
    error = exc.errors()[0]
    where = ".".join(str(p) for p in error["loc"])
    code = error["type"] if error["type"] in ERROR_LABELS else "visit_invalid"
    # the actions, the session and the card already say what they are of; the rest are told with their field
    return RowError(code, error["msg"] if not where or code in ("actions_invalid", "session_invalid", "card_batteries_invalid") else f"{where}: {error['msg']}")


def _first(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(p) for p in error["loc"])
    return f"{where}: {error['msg']}" if where else error["msg"]


class CsvVisitFile(VisitFile):
    def table(self, text: str) -> list[list[str]]:
        text = text.lstrip("﻿")
        head = text.splitlines()[0] if text.strip() else ""
        delimiter = max(",;\t", key=head.count)
        table = [row for row in csv.reader(io.StringIO(text), delimiter=delimiter) if any(cell.strip() for cell in row)]
        if not table:
            raise VisitsCsvError("The file is empty.")
        return table

    def write(self, rows: list[list[str]]) -> str:
        out = io.StringIO()
        csv.writer(out, lineterminator="\r\n").writerows(rows)
        return "﻿" + out.getvalue()   # a byte order mark, so that a spreadsheet reads the accents

    def cells(self, row: dict[str, str]) -> dict:
        try:
            return CsvVisit.model_validate(row).model_dump(exclude_unset=True)
        except ValidationError as exc:
            raise _problem_of(exc) from exc

    def record(self, visit: Visit) -> Visit:
        try:
            return cast(Visit, VisitRecord.model_validate(visit).model_dump(mode="json"))   # checked: a visit
        except ValidationError as exc:
            raise _problem_of(exc) from exc

    def location(self, fields: Location) -> Location:
        try:
            return cast(Location, LocationRecord.model_validate(dict(fields)).model_dump(mode="json"))   # checked: a location
        except ValidationError as exc:
            raise RowError("create_invalid", f"To create the location {fields.get('location_id')}: {_first(exc)}") from exc

    def normalized(self, visit: Visit) -> Visit:
        return cast(Visit, VisitRecord.model_validate(visit).model_dump(mode="json"))
