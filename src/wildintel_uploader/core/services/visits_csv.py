"""Reads the visits to the camera traps of a research project from a CSV file (see local_folder_service.write_visits), in one of two ways:

- "epicollect": the Epicollect download of a field trip, as the field records of the project read it (the FileTimestamps tool, services/fieldlog
  in the field-records work): the columns of the form are found by their names — 1_Responsable, 2_Collection, 4_Location, 5_Camera, 6_Action,
  7_Status_of_the_came, 8_Card_Batteries, 9_Number_of_pictures, 10_SD, 11_Date_and_hour, 12_Observation, lat_13_Coordenates,
  long_13_Coordenates — whatever their case, spaces or number in front; so are those of the Doñana form (Spanish headers, the actions R, I, D
  and ROBADA, the sites as numbers). The time of a visit is when its entry was created (created_at, UTC), put in the timezone of the location.
- "mapped": any other CSV, with the column that gives each field of a visit (see FIELDS) said by the caller (`mapping`, {field: column name});
  suggest_mapping offers a mapping to start from."""
from __future__ import annotations

import csv
import datetime as dt
import io
import re

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError

from wildintel_uploader.core import config
from wildintel_uploader.core.schemas.requests import LocationRecord, VisitRecord
from wildintel_uploader.core.services import visit_rules, visit_time

# What each column of an Epicollect download may be called — compared without case, spaces, dashes, underscores or a number in front.
EPICOLLECT_COLUMNS: dict[str, tuple[str, ...]] = {
    "location_id": ("site", "location", "locationid", "sitio"),
    "date": ("date", "fecha"),
    "time": ("time", "hora", "hour"),
    "when": ("datetime", "when", "fechahora"),
    "actions": ("actions", "action", "accion"),
    "trappers": ("trappers", "trapper", "who", "tramperos", "responsable"),
    "session": ("session", "revision", "sesion", "collection"),
    "status": ("status", "state", "estado", "statusofthecame"),
    "card_batteries_ok": ("cardbatteriesok", "cardbatteries", "cardpilasok"),
    "num_photos": ("numphotos", "photos", "numimages", "numfotos", "numberofpictures"),
    "sd": ("sd", "sdcard"),
    "date_time_ok": ("datetimeok", "fechahoraok", "dateandhour"),
    "camera_id": ("camera", "cameraid", "camara"),
    "camera_model": ("cameramodel",),
    "comments": ("notes", "comments", "deploymentcomments", "observaciones", "observation"),
    "setup_by": ("setupby",),
    "latitude": ("latitude", "lat", "latitud", "lat13coordenates", "lat13localizacinactua"),
    "longitude": ("longitude", "lon", "lng", "longitud", "long13coordenates", "long13localizacinactua"),
    "created_at": ("createdat",),
    # what a deployment has beside, named as Camtrap DP names it (or as the visit does)
    "camera_interval": ("cameradelay", "camerainterval"),
    "camera_height": ("cameraheight",),
    "camera_depth": ("cameradepth",),
    "camera_tilt": ("cameratilt",),
    "camera_heading": ("cameraheading",),
    "detection_distance": ("detectiondistance",),
    "timestamp_issues": ("timestampissues",),
    "calibration": ("calibration", "cameracalibrated"),
    "bait_use": ("baituse",),
    "feature_type": ("featuretype",),
    "habitat": ("habitat",),
    "deployment_groups": ("deploymentgroups",),
    "tags": ("tags", "deploymenttags"),
}
# The fields of a visit a CSV can give, in the order they are asked for: what each one is, and whether the visit needs it.
FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("location_id", "Site (a location of the research project)", True),
    ("actions", "Actions (Installation, Revision, Desinstallation, Stolen, Archive — several with +)", True),
    ("date", "Date (YYYY-MM-DD or DD/MM/YYYY)", False),
    ("time", "Time (HH:MM[:SS])", False),
    ("when", "Date and time in one column (YYYY-MM-DD HH:MM:SS)", False),
    ("created_at", "Created at (UTC, as Epicollect writes it)", False),
    ("session", "Session (R0013, or its number)", False),
    ("trappers", "Who went", False),
    ("status", "Status of the camera", False),
    ("card_batteries_ok", "Card and batteries (OK, CarFull, SinPilas, CarFullSinPilas)", False),
    ("num_photos", "Photos on the card collected", False),
    ("sd", "SD card left", False),
    ("date_time_ok", "Date and time of the camera OK", False),
    ("camera_id", "Camera id", False),
    ("camera_model", "Camera model", False),
    ("comments", "Notes", False),
    ("setup_by", "Set up by", False),
    ("latitude", "Latitude", False),
    ("longitude", "Longitude", False),
    ("camera_interval", "Camera delay (s)", False),
    ("camera_height", "Camera height (m)", False),
    ("camera_depth", "Camera depth (m)", False),
    ("camera_tilt", "Camera tilt (°)", False),
    ("camera_heading", "Camera heading (°)", False),
    ("detection_distance", "Detection distance (m)", False),
    ("timestamp_issues", "Timestamp issues (yes/no)", False),
    ("bait_use", "Bait use (yes/no)", False),
    ("calibration", "Camera calibrated (yes/no)", False),
    ("feature_type", "Feature type", False),
    ("habitat", "Habitat", False),
    ("deployment_groups", "Deployment groups", False),
    ("tags", "Tags (separated by |)", False),
    # what a row says of the entities it may create (see CREATABLE): they are not fields of the visit
    ("location_name", "Name of the location", False),
    ("timezone", "Timezone of the location (IANA, e.g. Europe/Madrid)", False),
    ("coordinate_uncertainty", "Coordinate uncertainty of the location (m)", False),
    ("sd_brand", "Brand of the SD card", False),
    ("sd_capacity", "Capacity of the SD card (e.g. 64 GB)", False),
)
REQUIRED = tuple(f for f, _, required in FIELDS if required)
# What the import can create when a visit names a location, a camera or an SD card that does not exist: each one's fields that a row must give — by a column or
# by a default — and the ones that are only asked for when it is created. The fields of the visit that appear here (latitude, longitude, camera_id, camera_model, sd)
# become required when it is.
CREATABLE: dict[str, dict] = {
    "locations": {"required": ["latitude", "longitude", "timezone"], "extra": ["location_name", "coordinate_uncertainty"]},
    "cameras": {"required": ["camera_id", "camera_model"], "extra": []},
    "sd_cards": {"required": ["sd", "sd_brand"], "extra": ["sd_capacity"]},
}
# The fields that are not a visit's but an entity's.
ENTITY_ONLY = {f: entity for entity, spec in CREATABLE.items() for f in [*spec["required"], *spec["extra"]] if f in ("location_name", "timezone", "coordinate_uncertainty", "sd_brand", "sd_capacity")}
EPICOLLECT_NUMBER = re.compile(r"^\s*(\d+)\s*([bB]?)\s*$")
ACTIONS = {a.lower(): a for a in ("Installation", "Revision", "Desinstallation", "Stolen", "Archive")} | {
    # as the datasheets of the field work write them
    "i": "Installation", "r": "Revision", "d": "Desinstallation", "robada": "Stolen", "uninstallation": "Desinstallation", "removal": "Desinstallation",
}
YES = {"yes", "true", "1", "y", "si", "sí"}
NO = {"no", "false", "0", "n"}
CODES = {c.lower(): c for c in ("OK", "CarFull", "SinPilas", "CarFullSinPilas")}
# ...and as the form says them in English: "Card full", "No batteries", "Card full and no batteries" (written without spaces, case or the s of the card)
CODES_ENGLISH = {"cardfull": "CarFull", "nobatteries": "SinPilas", "cardfullandnobatteries": "CarFullSinPilas", "carfullandnobatteries": "CarFullSinPilas"}


def card_code(value) -> str | None:
    """The code of how the card and the batteries were, from the code itself or from its English wording; None when it is neither."""
    text = str(value).strip().lower()
    return CODES.get(text) or CODES_ENGLISH.get(re.sub(r"[\s_-]+", "", text))


def id_of(value) -> str:
    """The id of a camera or an SD card from a cell that may say more than it: "68 now. Before 26" is 68, "Now 17, before 09" is 17, "42b" stays as it is. What a cell
    says after the id is left out; an id of letters and digits with no spaces is taken as it is."""
    text = str(value).strip()
    if re.fullmatch(r"[\w.-]+", text):
        return text
    now = re.search(r"\bnow\b\W*(\d+[A-Za-z]?)\b", text, re.IGNORECASE)
    first = re.search(r"\b\d+[A-Za-z]?\b", text)
    found = now or first
    return found.group(1 if now else 0) if found else text


# What kind of error a problem is, by its code — the rows with the same code are told together. The codes are those of the errors the row raises (RowError, or
# the custom errors of CsvVisit): they do not change when a message is reworded.
ERROR_LABELS: dict[str, str] = {
    "actions_invalid": "Actions not valid",
    "card_batteries_invalid": "Card and batteries not valid",
    "yes_no_invalid": "Not yes or no",
    "session_invalid": "Session not valid",
    "revision_not_finished": "Revision started before the one before is finished",
    "revision_closed": "Revision closed",
    "date_invalid": "Date or time not valid",
    "number_invalid": "Number not valid",
    "create_missing": "Data to create it is missing",
    "create_invalid": "Data to create it is not valid",
    "visit_invalid": "Value not valid",
}


def error_label(code: str) -> str:
    """The kind of error a code says — see ERROR_LABELS."""
    return ERROR_LABELS.get(code, "Other problem")


class RowError(ValueError):
    """What is wrong with a row of the file, with the code of the kind of error it is (see ERROR_LABELS)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _custom(code: str, message: str, value) -> PydanticCustomError:
    return PydanticCustomError(code, message, {"value": value})


class CsvVisit(BaseModel):
    """The cells of a row of the file, read as what they say of a visit — all text, as the file has it. A cell that is not what its field takes raises an error with
    its code (see ERROR_LABELS); what the row does not say is left unset, so that only what it says is kept (`model_dump(exclude_unset=True)`)."""

    model_config = ConfigDict(extra="ignore")

    actions: list[str] = []
    session: str | None = None
    status: str | None = None
    trappers: str | None = None
    sd: str | None = None
    date_time_ok: str | None = None
    camera_id: str | None = None
    camera_model: str | None = None
    comments: str | None = None
    setup_by: str | None = None
    card_batteries_ok: str | None = None
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
        names = [ACTIONS.get(a.strip().lower()) for a in re.split(r"[+;/|&,]", str(value)) if a.strip()]
        if None in names:
            raise _custom("actions_invalid", "The actions '{value}' are not Installation, Revision, Desinstallation, Stolen or Archive.", value)
        return names

    @field_validator("session", mode="before")
    @classmethod
    def _session(cls, value):
        m = re.search(r"\d+", str(value))
        if not m:
            raise _custom("session_invalid", "'{value}' is not a session (R0013, or its number).", value)
        return f"R{int(m.group(0)):04d}"

    @field_validator("camera_id", mode="before")
    @classmethod
    def _camera(cls, value):
        return re.sub(r"\.0+$", "", id_of(value))

    @field_validator("sd", mode="before")
    @classmethod
    def _sd(cls, value):
        return id_of(value)

    @field_validator("card_batteries_ok", mode="before")
    @classmethod
    def _card_batteries(cls, value):
        code = card_code(value)
        if code is None:
            raise _custom("card_batteries_invalid", "'{value}' is not OK, Card full, No batteries or Card full and no batteries (or CarFull, SinPilas, CarFullSinPilas).", value)
        return code

    @field_validator("num_photos", "camera_interval", "camera_tilt", "camera_heading", mode="before")
    @classmethod
    def _whole(cls, value):
        try:
            return int(float(value))
        except (TypeError, ValueError, OverflowError):
            raise _custom("number_invalid", "'{value}' is not a whole number.", value) from None

    @field_validator("camera_height", "camera_depth", "detection_distance", "latitude", "longitude", mode="before")
    @classmethod
    def _number(cls, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise _custom("number_invalid", "'{value}' is not a number.", value) from None

    @field_validator("timestamp_issues", "bait_use", "calibration", mode="before")
    @classmethod
    def _yes_no(cls, value):
        word = str(value).lower()
        if word not in YES | NO:
            raise _custom("yes_no_invalid", "'{value}' is not yes or no.", value)
        return word in YES

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, value):
        return [t.strip() for t in re.split(r"[|;]", str(value)) if t.strip()]

    @model_validator(mode="after")
    def _something_was_done(self):
        # a visit that could not be made has no action: it is exported so, and read back so
        if not self.actions and not visit_rules.is_not_revised({"status": self.status}):
            raise _custom("actions_invalid", "The actions '{value}' are not Installation, Revision, Desinstallation, Stolen or Archive.", "")
        return self


def _problem_of(exc: ValidationError) -> tuple[str, str]:
    """The code and the message of the first error of a validation: those of a custom error of CsvVisit as they are, the others — a value the model of the visit
    refuses — as "visit_invalid", with the field they are of."""
    error = exc.errors()[0]
    where = ".".join(str(p) for p in error["loc"])
    code = error["type"] if error["type"] in ERROR_LABELS else "visit_invalid"
    # the actions, the session and the card already say what they are of; the rest are told with their field
    return code, error["msg"] if not where or code in ("actions_invalid", "session_invalid", "card_batteries_invalid") else f"{where}: {error['msg']}"


class VisitsCsvError(Exception):
    """The file can't be read as visits at all."""


def _key(name: str) -> str:
    """A column name without its number in front (12_Observation), its case, spaces or underscores."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^\d+_", "", name.strip().lower()))


def _table(text: str) -> list[list[str]]:
    """The rows of the file, the first being its header — the delimiter is the one the header has most of."""
    text = text.lstrip("﻿")
    head = text.splitlines()[0] if text.strip() else ""
    delimiter = max(",;\t", key=head.count)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    table = [row for row in reader if any(cell.strip() for cell in row)]
    if not table:
        raise VisitsCsvError("The file is empty.")
    return table


def _fields(header: list[str], fmt: str, mapping: dict[str, str] | None) -> list[str | None]:
    """The field of a visit each column of the header gives — nothing for a column that is not used. In an Epicollect download the columns are found by the
    names they usually have."""
    if fmt == "mapped":
        by_column = {column: field for field, column in (mapping or {}).items() if column}
        return [by_column.get(cell) for cell in header]
    by_name = {alias: field for field, aliases in EPICOLLECT_COLUMNS.items() for alias in aliases}
    return [by_name.get(_key(cell)) for cell in header]


def suggest_mapping(text: str) -> dict:
    """The columns of a CSV, a few of its rows, and for each field of a visit the column that most likely gives it — to start a mapping from."""
    table = _table(text)
    header = table[0]
    names = {alias: field for field, aliases in EPICOLLECT_COLUMNS.items() for alias in aliases} | {_key(f): f for f, _, _ in FIELDS}
    mapping: dict[str, str] = {}
    for cell in header:
        field = names.get(_key(cell))
        if field and field not in mapping:
            mapping[field] = cell
    return {"columns": header, "sample": table[1:4], "mapping": mapping}


def _rows(text: str, fmt: str, mapping: dict[str, str] | None, defaults: dict[str, str] | None = None,
          create: dict[str, bool] | None = None) -> tuple[dict[str, str], list[dict[str, str]]]:
    """The file's columns, as the visit's fields they are, and its rows keyed by those fields.

    `defaults` ({field: value}) is what a field is when its column is not in the file or a cell of it is empty; a field with a default counts as given. `create` ({locations, cameras,
    sd_cards}: bool) says which entities are created when they do not exist: the fields they need (see CREATABLE) are required too."""
    table = _table(text)
    fields = _fields(table[0], fmt, mapping)
    defaults = {f: v.strip() for f, v in (defaults or {}).items() if f and str(v).strip()}
    present = {f for f in fields if f} | set(defaults)
    missing = [f for f in REQUIRED if f not in present]
    missing += [f for entity, on in (create or {}).items() if on and entity in CREATABLE for f in CREATABLE[entity]["required"] if f not in present and f not in missing]
    if not present & {"created_at", "when"} and not {"date", "time"} <= present:
        missing.append("the date and the time (or created_at)")
    if missing:
        raise VisitsCsvError(f"The file has no column for: {', '.join(missing)}. Columns found: {', '.join(c.strip() for c in table[0])}.")
    rows = [{**defaults, **{f: cell.strip() for f, cell in zip(fields, row) if f and cell.strip()}} for row in table[1:]]
    return {f: c for f, c in zip(fields, table[0]) if f}, rows


def _local(created: dt.datetime, location: dict) -> dt.datetime:
    """The time of an entry — UTC — in the timezone of the location, with no summer time when the location ignores it; UTC when it has none."""
    return visit_time.utc_to_local(created, location)


def _real(date: str, time: str) -> tuple[str, str]:
    """The day and the time, once they are known to be a day and a time that exist (the 13th month, the 25th hour)."""
    try:
        dt.date.fromisoformat(date)
        dt.time.fromisoformat(time)
    except ValueError:
        raise RowError("date_invalid", f"'{date} {time}' is not a date and a time that exist.") from None
    return date, time


def _when(row: dict[str, str], location: dict, time_source: str = "created_at") -> tuple[str, str]:
    """The day and the time of a visit: when its entry was created (created_at, UTC, as Epicollect writes it), else its date and time — or, when `time_source`
    is "hour", the date and the hour typed in the form (the wall clock of its location) when the row has them, else the time its entry was created."""
    if "created_at" in row and not (time_source == "hour" and "date" in row and "time" in row):
        try:
            created = dt.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise RowError("date_invalid", f"'{row['created_at']}' is not a created_at (2026-09-04T10:16:31.000Z).") from exc
        if created.tzinfo is not None:
            created = (created - created.utcoffset()).replace(tzinfo=None)
        local = _local(created.replace(microsecond=0), location)
        return local.date().isoformat(), local.time().isoformat()
    if "when" in row:
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)", row["when"])
        if not m:
            raise RowError("date_invalid", f"'{row['when']}' is not a date and time (YYYY-MM-DD HH:MM:SS).")
        return _real(m.group(1), m.group(2) if m.group(2).count(":") == 2 else f"{m.group(2)}:00")
    if "date" not in row or "time" not in row:
        raise RowError("date_invalid", "The date and the time are required.")
    day = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", row["date"]) or re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", row["date"])
    if not day:
        raise RowError("date_invalid", f"'{row['date']}' is not a date (YYYY-MM-DD or DD/MM/YYYY).")
    date = row["date"] if "-" in row["date"] else f"{day.group(3)}-{day.group(2)}-{day.group(1)}"
    return _real(date, row["time"] if row["time"].count(":") == 2 else f"{row['time']}:00")


def _site(text: str, prefix: str) -> str:
    """A site as the forms write it: its id, or only its number (12, or 12B for the second camera of a site) — then with the prefix of the project."""
    m = EPICOLLECT_NUMBER.match(text)
    return f"{prefix}{int(m.group(1)):04d}{'_B' if m.group(2) else ''}" if m else text


def parse_visits(text: str, locations: list[dict], kept: list[dict], site_prefix: str = "", fmt: str = "mapped", mapping: dict[str, str] | None = None,
                 options: dict | None = None) -> dict:
    """The visits in the CSV `text` that can be kept, and what is wrong with the rest.

    `fmt` is how the file is read: "epicollect" or "mapped" (with `mapping`, {field: column}) — see the top of the module.
    A site must be a location of the research project (found ignoring case; in an Epicollect download a number alone is that of `site_prefix`); its coordinates
    are the visit's unless the row has its own. A row without a session gets the next of its location, counted from the visits already
    kept. A visit already kept — the same location, day and time — is left as it is, and counted as skipped. In an Epicollect download
    (it has created_at) the entries without a collection number or a site are those of old versions of the form: ignored, and counted.

    A site that is not a location is not a problem to throw the rows away for: it may be a site that is really new, or one misnamed in the field. Its
    visits are held and the site comes back in "new_sites" with what tells the two apart (the coordinates of its first visit, the nearest location and
    how far, the ids one character apart — see visit_rules.new_site), to add it as a location or to correct the file. What is odd in the visits that are
    kept — what their actions ask and they lack, a camera or a card where it cannot be, two Revisions in a session… — comes back in "warnings": the
    visits are kept as the field wrote them and questioned, as the field records are.

    `options` are the settings of the field records: "time_source" ("created_at", or "hour" to read the date and the hour typed) and "cards" (the SD cards of the settings, to tell which are archived). A row whose session and site are those of a visit already
    kept is that visit: left as it is, and counted as skipped.

    Returns {"visits": [...], "problems": [{"row", "message"}], "skipped": int, "ignored": int, "new_sites": [...], "warnings": [str], "notes": [str]} — the rows
    numbered as in the file, the header being 1. "notes" are what is worth knowing but not wrong: the sites of the trip before not visited on this one (their cameras
    are still out), visits where nothing was collected, visits with no photo count.

    Raises:
        VisitsCsvError: the file is empty or lacks a required column.
    """
    options = options or {}
    time_source = options.get("time_source") or "created_at"
    create = {entity: bool(on) for entity, on in (options.get("create") or {}).items() if entity in CREATABLE}
    columns, rows = _rows(text, fmt, mapping, options.get("defaults"), create)
    epicollect = fmt == "epicollect" and "created_at" in columns
    known = {str(l.get("location_id", "")).lower(): l for l in locations}
    # What a row creates when its location, camera or SD card does not exist and it is asked to: {row: {"locations": [...], "cameras": [...], "sd_cards": [...]}}, and the
    # locations made from the first row that gave each site (the other rows of it are read in its timezone).
    cameras_known = {str(c.get(k) or "").lower() for c in options.get("cameras") or [] for k in ("camera_id", "label")} - {""}
    cards_known = {str(c.get("label") or "").lower() for c in options.get("cards") or []} - {""}
    made_by_row: dict[int, dict[str, list[dict]]] = {}
    new_locations: dict[str, dict] = {}
    already = {(str(v.get("location_id", "")).lower(), v.get("date"), v.get("time")) for v in kept}
    problems: list[dict] = []
    parsed: list[tuple[int, dict]] = []
    skipped = 0
    ignored = 0
    held: dict[str, list[dict]] = {}  # the visits to sites that are not locations of the research project, by site
    row_warnings: list[tuple[int, str]] = []  # what is odd in a row by itself: its row, and what
    # A revision is one visit to each site: the session and the site of a visit already kept are taken, whatever its camera or its actions
    same_visit = {(str(v.get("session") or "").upper(), str(v.get("location_id", "")).lower()) for v in kept if v.get("session")}

    # What became of each row of the file: {row: {"row", "site", "result", "message"}} — result is ok, problem, already_kept, new_site or ignored.
    report: dict[int, dict] = {}

    def problem(n: int, message: str, code: str = "other") -> None:
        problems.append({"row": n, "message": message})
        report[n] = {**report.get(n, {"row": n, "site": ""}), "result": "problem", "label": error_label(code), "message": message}

    for n, row in enumerate(rows, start=2):
        found = re.search(r"\d+", row.get("session", ""))
        report[n] = {"row": n, "site": row.get("location_id", ""), "session": f"R{int(found.group(0)):04d}" if found else "", "actions": row.get("actions", ""), "result": "ok", "label": "", "message": "", "data": dict(row)}
        if epicollect and ("session" not in row or "location_id" not in row):
            ignored += 1
            report[n] |= {"result": "ignored", "label": "Entry of an old form", "message": "It has no session or no site: it is an entry of an old version of the form."}
            continue
        site = _site(row.get("location_id", ""), site_prefix) if fmt == "epicollect" else row.get("location_id", "")
        location = known.get(site.lower()) or new_locations.get(site.lower())
        unknown = location is None
        made: dict[str, list[dict]] = {"locations": [], "cameras": [], "sd_cards": []}
        try:
            if unknown and create.get("locations"):
                location = _new_location(site, row)
                made["locations"].append(location)
                unknown = False
        except RowError as exc:
            problem(n, str(exc), exc.code)
            continue
        if unknown:
            location = {}  # held with its site apart: the time is read as UTC, as nothing says better
        try:
            date, time = _when(row, location, time_source)
            report[n] |= {"date": date, "time": time[:5]}
            if fmt == "epicollect" and "created_at" in row and "date" in row and time_source != "hour":
                try:
                    created_day = _when({"created_at": row["created_at"]}, location)[0]
                    typed_day = _when({"date": row["date"], "time": "00:00"}, location)[0]
                    if created_day != typed_day:
                        row_warnings.append((n, f"Row {n} ({site}): the date typed, {typed_day}, differs from the day of the entry, {created_day}; the time of the entry was used."))
                except RowError:
                    pass
            # what the cells say of the visit — each one read as its field takes it, or refused with the code of what is wrong
            cells = CsvVisit.model_validate(row)
            actions = cells.actions
            report[n]["actions"] = " + ".join(actions)  # as the dashboard of visits says them
            if create.get("cameras") and row.get("camera_id"):
                camera = _new_camera(cells.camera_id, row)
                if camera["camera_id"].lower() not in cameras_known:
                    made["cameras"].append(camera)
            if create.get("sd_cards") and row.get("sd") and row["sd"].lower() not in cards_known:
                made["sd_cards"].append(_new_card(row["sd"], row))
            data = cells.model_dump(exclude_unset=True, exclude={"actions"})
            # the GPS of the note is compared with the location's, to check that the site is the right one
            if data.get("latitude") is not None and data.get("longitude") is not None and location.get("latitude") is not None and location.get("longitude") is not None:
                gap = visit_rules.distance_m(data["latitude"], data["longitude"], float(location["latitude"]), float(location["longitude"]))
                if gap > visit_rules.GPS_TOLERANCE_M:
                    row_warnings.append((n, f"Row {n} ({site}): the GPS of the note is {round(gap)} m from the location; check that the site is the right one."))
            for f in ("latitude", "longitude"):
                if f not in data and location.get(f) not in (None, ""):
                    data[f] = float(location[f])
            visit = {"location_id": location.get("location_id", site), "date": date, "time": time, "actions": actions, **data}
            visit.setdefault("session", "R0000")  # worked out below, when the order of the visits is known
            record = VisitRecord.model_validate(visit).model_dump(mode="json")
            record["when"] = visit_time.to_when(record["date"], record["time"], location)
        except RowError as exc:
            problem(n, str(exc), exc.code)
            continue
        except ValidationError as exc:
            code, message = _problem_of(exc)
            problem(n, message, code)
            continue
        except ValueError as exc:
            problem(n, str(exc))
            continue
        if unknown:
            held.setdefault(site, []).append(record)
            report[n] |= {"result": "new_site", "label": "Site is not a location", "message": f"{site} is not a location of the research project: the visit is held until the site is added or the file corrected."}
            continue
        again = (str(record["session"]).upper(), record["location_id"].lower())
        if (record["location_id"].lower(), record["date"], record["time"]) in already or ("session" in row and again in same_visit):
            skipped += 1
            closed = visit_rules.is_closed_revision(record["session"], kept, locations)
            same_time = (record["location_id"].lower(), record["date"], record["time"]) in already
            report[n] |= {"result": "already_kept", "label": "Already kept", "message": (f"A visit to {record['location_id']} on {record['date']} at {record['time']} is already kept: it is not imported again." if same_time
                                                              else f"The {record['session']} visit of {record['location_id']} is already kept: it is not imported again."
                                                                 + (f" {record['session']} is closed — every location has its visit — so nothing new can be imported in it." if closed else ""))}
            continue
        if visit_rules.is_closed_revision(record["session"], kept, locations):
            problem(n, f"{record['session']} is closed: every location has its visit in it, so nothing new can be imported in it.", "revision_closed")
            continue
        already.add((record["location_id"].lower(), record["date"], record["time"]))
        parsed.append((n, record | {"_given": "session" in row}))
        if made["locations"]:
            new_locations[site.lower()] = made["locations"][0]
        made_by_row[n] = made

    row_of = {id(r): n for n, r in parsed}
    count: dict[str, int] = {}
    for loc in {r["location_id"].lower() for _, r in parsed}:
        count[loc] = sum(1 for v in kept if str(v.get("location_id", "")).lower() == loc)
    visits = []
    for _, record in sorted(parsed, key=lambda p: (p[1]["date"], p[1]["time"])):
        given = record.pop("_given")
        loc = record["location_id"].lower()
        # a visit that does not put a camera up is of the one at the site: an inspection or a removal does not say which — it is the one of the deployment that is open
        if not record.get("camera_id") and "Installation" not in record["actions"]:
            there = visit_rules.camera_at_site([*kept, *visits], record["location_id"], record.get("when") or f"{record['date']}T{record['time']}")
            if there:
                record["camera_id"] = there["camera"]
        if not given:
            record["session"] = f"R{count[loc] + 1:04d}"
        count[loc] += 1
        visits.append(record)
    new_sites = [visit_rules.new_site(site, records, locations) for site, records in sorted(held.items())]
    # what is odd, said once and told in the rows it is about: the visits that make it odd are rows of the file
    said: list[tuple[str, list[int]]] = [(message, [n]) for n, message in row_warnings]
    for message, about in [*visit_rules.session_jump_items(visits, kept), *visit_rules.history_warning_items(visits, kept, options.get("cards"))]:
        said.append((message, sorted({row_of[id(v)] for v in about if id(v) in row_of})))
    warnings = list(dict.fromkeys(message for message, _ in said))
    notes = visit_rules.history_notes(visits, kept)
    # a revision is not started before the one before it is finished: its visits are refused, with the rows they come from
    refused = visit_rules.revision_gate(visits, kept, [*locations, *new_locations.values()])
    for visit, why in refused:
        problem(row_of[id(visit)], why, "revision_not_finished")
    visits = [v for v in visits if id(v) not in {id(r) for r, _ in refused}]
    # what is created is what the visits that are kept need: a location, a camera or an SD card that only a refused visit named is not
    kept_rows = {row_of[id(v)] for v in visits}
    sites = {v["location_id"].lower() for v in visits}
    create_out: dict[str, list[dict]] = {"locations": [l for site, l in new_locations.items() if site in sites], "cameras": [], "sd_cards": []}
    for n in sorted(kept_rows):
        for kind in ("cameras", "sd_cards"):
            for entity in made_by_row.get(n, {}).get(kind, []):
                key = str(entity.get("camera_id") or entity.get("label")).lower()
                if key not in {str(e.get("camera_id") or e.get("label")).lower() for e in create_out[kind]}:
                    create_out[kind].append(entity)
    # a warning goes to the rows that are added; one about no row, or only about rows that are not added, is said apart
    loose: list[str] = []
    for message, rows_about in said:
        added = [n for n in rows_about if n in kept_rows]
        if not added:
            loose.append(message)
        for n in added:
            if message not in report[n].setdefault("warnings", []):
                report[n]["warnings"].append(message)
    for n in sorted(kept_rows):
        names = [f"the location {l['location_id']}" for l in made_by_row.get(n, {}).get("locations", [])]
        names += [f"the camera {c['camera_id']}" for c in made_by_row.get(n, {}).get("cameras", [])]
        names += [f"the SD card {c['label']}" for c in made_by_row.get(n, {}).get("sd_cards", [])]
        if names and n in report and report[n]["result"] == "ok":
            report[n]["message"] = f"The visit is added, and creates {', '.join(names)}."
    return {"visits": visits, "problems": problems, "rows": [report[n] for n in sorted(report)], "skipped": skipped, "ignored": ignored, "new_sites": new_sites,
            "create": create_out, "warnings": warnings, "loose_warnings": list(dict.fromkeys(loose)), "notes": notes}


# The columns of an export: the fields of a visit a CSV can give, by their names — which the import finds by themselves — less the two that are worked out
# from the others (the instant of the visit and the time of the entry) and what the visit gets once it is kept (its state and its deployment).
EXPORT_FIELDS = tuple(f for f, _, _ in FIELDS if f not in ("when", "created_at") and f not in ENTITY_ONLY)


def export_visits(visits: list[dict]) -> str:
    """The visits as CSV text that the import reads back as they are: a column for each field of EXPORT_FIELDS, the actions joined with +, the tags with |,
    the yes/no fields as yes or no, and the visits from the oldest. It starts with a byte order mark, so that a spreadsheet reads the accents."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(EXPORT_FIELDS)

    def cell(visit: dict, field: str) -> str:
        value = visit.get(field)
        if value is None:
            return ""
        if field == "actions":
            return "+".join(value)
        if field == "tags":
            return "|".join(value)
        if isinstance(value, bool):
            return "yes" if value else "no"
        return str(value)

    for visit in sorted(visits, key=lambda v: (str(v.get("date")), str(v.get("time")))):
        writer.writerow([cell(visit, f) for f in EXPORT_FIELDS])
    return "\ufeff" + out.getvalue()


def _new_location(site: str, row: dict[str, str]) -> dict:
    """The location a row creates: its id, its coordinates and its timezone are the row's.

    Raises:
        RowError: the row has no coordinates or timezone, or they are not valid."""
    try:
        latitude, longitude = float(row["latitude"]), float(row["longitude"])
    except (KeyError, ValueError) as exc:
        raise RowError("create_missing", f"To create the location {site} the row needs its coordinates: a latitude and a longitude.") from exc
    if not row.get("timezone"):
        raise RowError("create_missing", f"To create the location {site} the row needs its timezone (e.g. Europe/Madrid).")
    try:
        uncertainty = int(float(row["coordinate_uncertainty"])) if row.get("coordinate_uncertainty") else None
        return LocationRecord(location_id=site, name=row.get("location_name") or None, latitude=latitude, longitude=longitude, timezone=row["timezone"],
                              coordinate_uncertainty=uncertainty).model_dump(mode="json")
    except (ValidationError, ValueError) as exc:
        raise RowError("create_invalid", f"To create the location {site}: {_first(exc) if isinstance(exc, ValidationError) else exc}") from exc


def _new_camera(camera_id: str, row: dict[str, str]) -> dict:
    """The camera a row creates: called by its id, with the model of the row.

    Raises:
        RowError: the row has no model."""
    if not row.get("camera_model"):
        raise RowError("create_missing", f"To create the camera {camera_id} the row needs its model.")
    return config.Camera(label=camera_id, camera_id=camera_id, camera_model=row["camera_model"]).model_dump(mode="json")


def _new_card(label: str, row: dict[str, str]) -> dict:
    """The SD card a row creates: its id is its label, with the brand — and the capacity — of the row.

    Raises:
        RowError: the row has no brand."""
    if not row.get("sd_brand"):
        raise RowError("create_missing", f"To create the SD card {label} the row needs its brand.")
    return config.SdCard(label=label, brand=row["sd_brand"], capacity=row.get("sd_capacity") or None).model_dump(mode="json")


def _first(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(p) for p in error["loc"])
    return f"{where}: {error['msg']}" if where else error["msg"]
