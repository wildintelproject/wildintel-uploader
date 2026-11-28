"""A file of visits — plain Python: what its columns may be called and which fields of a visit they give, which fields a visit and what a row
creates need, how a cell says the actions, the revision, the card and the batteries, yes or no, a number or the tags, when a visit was (from when
its entry was created, or the day and the hour typed), the kinds of what is wrong with a row, the locations a visit archives, the username of a
person a file names, and what a file of visits written by the app has in its columns.

Any CSV can be read: the caller says the column of each field (`mapping`, {field: column}), and suggest offers a mapping to start from. The
downloads of the Epicollect5 projects are turned into such a file first (modules.sources)."""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from typing import Any, cast

from wildintel_uploader.modules.visits.domain import wall_clock
from wildintel_uploader.modules.visits.domain.models import VisitsFailed
from wildintel_uploader.modules.visits.domain.shapes import Location, Visit

# What each column of a CSV may be called, to suggest a mapping — compared without case, spaces, dashes, underscores or a number in front.
COLUMN_NAMES: dict[str, tuple[str, ...]] = {
    "location_id": ("site", "location", "locationid", "sitio"),
    "date": ("date", "fecha"),
    "time": ("time", "hora", "hour"),
    "when": ("datetime", "when", "fechahora"),
    "actions": ("actions", "action", "accion"),
    "trappers": ("trappers", "trapper", "who", "tramperos", "responsable"),
    "session": ("session", "revision", "sesion", "collection"),
    "camera_status": ("camerastatus", "status", "state", "estado", "statusofthecame"),
    "battery_status": ("batterystatus", "batteries", "battery", "pilas", "bateria"),
    "card_status": ("cardstatus", "sdstatus", "tarjeta"),
    "card_batteries_ok": ("cardbatteriesok", "cardbatteries", "cardpilasok"),   # how it was before: one column for both
    "num_photos": ("numphotos", "photos", "numimages", "numfotos", "numberofpictures"),
    "sd": ("sd", "sdcard"),
    "date_time_ok": ("datetimeok", "fechahoraok", "dateandhour"),
    "camera_id": ("camera", "cameraid", "camara", "cameralabel", "cameraname"),
    "camera_model": ("cameramodel",),
    "camera_serial": ("cameraserial", "serialnumber", "serial", "numerodeserie"),
    "camera_make": ("cameramake", "make", "marca"),
    "comments": ("notes", "comments", "deploymentcomments", "observaciones", "observation"),
    "setup_by": ("setupby",),
    "latitude": ("latitude", "lat", "latitud", "lat13coordenates", "lat13localizacinactua"),
    "longitude": ("longitude", "lon", "lng", "longitud", "long13coordenates", "long13localizacinactua"),
    "location_latitude": ("locationlatitude", "locationlat"),
    "location_longitude": ("locationlongitude", "locationlon", "locationlng"),
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
    ("location_id", "Location (of the research project)", True),
    ("actions", "Actions (Installation, Revision, Desinstallation, Stolen, Archive — several with +)", True),
    ("date", "Date (YYYY-MM-DD or DD/MM/YYYY)", False),
    ("time", "Time (HH:MM[:SS])", False),
    ("when", "Date and time in one column (YYYY-MM-DD HH:MM:SS)", False),
    ("created_at", "Created at (UTC, as Epicollect writes it)", False),
    ("session", "Revision (R0013, or its number)", False),
    ("trappers", "Who went", False),
    ("camera_status", "Status of the camera", False),
    ("battery_status", "Batteries (OK, NoBatteries)", False),
    ("card_status", "SD card (OK, CardFull)", False),
    ("num_photos", "Images on the card collected", False),
    ("sd", "SD card left", False),
    ("date_time_ok", "Date and time of the camera OK", False),
    ("camera_id", "Camera (its label: what it is called in the field)", False),
    ("camera_model", "Camera model (to create or complete its record)", False),
    ("camera_serial", "Serial number of the camera (to find it, or to create or complete its record)", False),
    ("camera_make", "Make of the camera (to create or complete its record)", False),
    ("comments", "Notes", False),
    ("setup_by", "Set up by", False),
    ("latitude", "Latitude of the visit (where the trapper was when it was noted; the location's when the file has none)", False),
    ("longitude", "Longitude of the visit (where the trapper was when it was noted; the location's when the file has none)", False),
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
    ("location_latitude", "Latitude of the location", False),
    ("location_longitude", "Longitude of the location", False),
    ("timezone", "Timezone of the location (IANA, e.g. Europe/Madrid)", False),
    ("daylight_saving", "Daylight saving time of the location (yes if its cameras follow it, no if they do not)", False),
    ("coordinate_uncertainty", "Coordinate uncertainty of the location (m)", False),
    ("sd_brand", "Brand of the SD card", False),
    ("sd_capacity", "Capacity of the SD card (e.g. 64 GB)", False),
)
REQUIRED = tuple(f for f, _, required in FIELDS if required)
# What the import can create when a visit names a location, a camera or an SD card that does not exist: each one's fields that a row must give — by a column or
# by a default — and the ones that are only asked for when it is created. The fields of the visit that appear here (camera_id, camera_model, sd) become required
# when it is; the coordinates of the location are its own (location_latitude, location_longitude), apart from those of the visit, which a row gives or, when it has none, are those of its location.
CREATABLE: dict[str, dict] = {
    "locations": {"required": ["location_latitude", "location_longitude", "timezone", "daylight_saving"], "extra": ["location_name", "coordinate_uncertainty"]},
    "cameras": {"required": ["camera_id"], "extra": ["camera_model", "camera_make", "camera_serial"]},
    "sd_cards": {"required": ["sd"], "extra": ["sd_brand", "sd_capacity"]},
    # the people who went are what the visits say they are called (who went, who set up): nothing else is asked of them — their username is worked out from the name
    "trappers": {"required": [], "extra": []},
}
# The fields that are not a visit's but an entity's.
ENTITY_ONLY = {f: entity for entity, spec in CREATABLE.items() for f in [*spec["required"], *spec["extra"]] if f in ("location_name", "location_latitude", "location_longitude", "timezone", "daylight_saving", "coordinate_uncertainty", "sd_brand", "sd_capacity", "camera_make")}
ACTIONS = {a.lower(): a for a in ("SiteStart", "Installation", "Revision", "Desinstallation", "Stolen", "Archive")} | {
    # the start of a site, as it is told
    "site start": "SiteStart", "site_start": "SiteStart", "start of site": "SiteStart", "site setup": "SiteStart",
    "location start": "SiteStart", "location_start": "SiteStart", "start of location": "SiteStart", "location setup": "SiteStart",
    # as the datasheets of the field work write them
    "i": "Installation", "r": "Revision", "d": "Desinstallation", "robada": "Stolen", "uninstallation": "Desinstallation", "removal": "Desinstallation",
}
YES = {"yes", "true", "1", "y", "si", "sí"}
NO = {"no", "false", "0", "n"}
CODES = {c.lower(): c for c in ("OK", "CarFull", "NoBatteries", "CarFullNoBatteries")}
# ...and as the datasheet writes them (SinPilas, CarFullSinPilas) and as the form says them in English ("Card full", "No batteries", "Card full and no batteries"),
# compared without spaces, case or the s of the card
CODES_OTHER = {"cardfull": "CarFull", "sinpilas": "NoBatteries", "carfullsinpilas": "CarFullNoBatteries", "cardfullandnobatteries": "CarFullNoBatteries", "carfullandnobatteries": "CarFullNoBatteries"}
EXPORT_FIELDS = tuple(f for f, _, _ in FIELDS if f not in ("when", "created_at") and f not in ENTITY_ONLY)
# The reasons a row is not added that are not errors of its own: it waits for the revision before it, which is not finished or has no visit (#206).
WAITING = {"revision_not_finished", "revision_without_previous"}


class VisitsCsvError(VisitsFailed):
    """The file can't be read as visits at all."""


class RowError(ValueError):
    """What is wrong with a row of the file, with the code of the kind of error it is (see ERROR_LABELS)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def card_code(value) -> str | None:
    """The code of how the card and the batteries were (OK, CarFull, NoBatteries or CarFullNoBatteries), from the code itself or from the other ways it is written;
    None when it is none of them."""
    text = re.sub(r"[\s_-]+", "", str(value).strip().lower())
    return CODES.get(text) or CODES_OTHER.get(text)


# ── what a cell says — None when it is not that; what it is told with is CELL_ERRORS ──

CELL_ERRORS: dict[str, str] = {
    "actions_invalid": "The actions '{value}' are not Installation, Revision, Desinstallation, Stolen or Archive.",
    "session_invalid": "'{value}' is not a revision (R0013, or its number).",
    "card_batteries_invalid": "'{value}' is not OK, Card full, No batteries or Card full and no batteries (CarFull, NoBatteries and CarFullNoBatteries are the codes).",
    "battery_status_invalid": "'{value}' is not OK or No batteries (OK and NoBatteries are the codes).",
    "card_status_invalid": "'{value}' is not OK or Card full (OK and CardFull are the codes).",
    "whole_invalid": "'{value}' is not a whole number.",
    "number_invalid": "'{value}' is not a number.",
    "yes_no_invalid": "'{value}' is not yes or no.",
}


def actions_of(value) -> list[str] | None:
    """The actions a cell says, several joined with + ; / | & or a comma — None when one of them is not an action."""
    names = [ACTIONS.get(a.strip().lower()) for a in re.split(r"[+;/|&,]", str(value)) if a.strip()]
    return None if None in names else [n for n in names if n is not None]


def session_of(value) -> str | None:
    """The revision a cell says — R0013, or its number."""
    m = re.search(r"\d+", str(value))
    return f"R{int(m.group(0)):04d}" if m else None


def whole_of(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None


def number_of(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def yes_no_of(value) -> bool | None:
    word = str(value).lower()
    return (word in YES) if word in YES | NO else None


def tags_of(value) -> list[str]:
    return [t.strip() for t in re.split(r"[|;]", str(value)) if t.strip()]


# What kind of error a problem is, by its code — the rows with the same code are told together. The codes are those of the errors the row raises (RowError, or
# the custom errors of CsvVisit): they do not change when a message is reworded.
ERROR_LABELS: dict[str, str] = {
    "actions_invalid": "Actions not valid",
    "card_batteries_invalid": "Card and batteries not valid",
    "battery_status_invalid": "Batteries not valid",
    "card_status_invalid": "SD card status not valid",
    "yes_no_invalid": "Not yes or no",
    "camera_status_invalid": "Status of the camera not valid",
    "session_invalid": "Revision not valid",
    "revision_not_finished": "Revision started before the one before is finished",
    "revision_without_previous": "Revision before it has no visit",
    "revision_closed": "Revision closed",
    "revision_order": "Revision out of order",
    "visit_repeated": "Location visited twice in a revision",
    "visit_refused": "Breaks the rules of a visit",
    "site_not_a_location": "Not a location of the research project",
    "visit_at_the_same_time": "Visit already there at that time",
    "first_visit_not_installation": "First visit is not an Installation",
    "site_start_repeated": "Location started twice",
    "site_start_not_first": "Location start is not the first visit",
    "visit_before_site_start": "Visit before the location started",
    "required_field": "Something its actions ask is missing",
    "camera_not_at_the_site": "Not the camera at the location",
    "camera_installed_here": "Camera already installed here",
    "camera_installed_elsewhere": "Camera installed at another location",
    "card_archived": "SD card archived",
    "card_is_the_one_collected": "SD card left is the one collected",
    "card_in_another_camera": "SD card in another camera",
    "card_collected_in_revision": "SD card collected in this revision",
    "visit_not_after_the_last": "Visit not after the last one of the location",
    "site_archived": "Location archived",
    "site_has_a_camera": "Location already has a camera",
    "site_without_camera": "Location has no camera",
    "site_planned": "Location planned",
    "archive_with_installation": "Archive with an Installation",
    "archive_camera_still_there": "Camera still there when the location is archived",
    "camera_unknown": "Camera not in the research project",
    "card_unknown": "SD card not in the research project",
    "trapper_unknown": "Trapper not in the settings",
    "date_invalid": "Date or time not valid",
    "number_invalid": "Number not valid",
    "coordinates_missing": "Coordinates of the visit missing",
    "create_missing": "Data to create it is missing",
    "create_invalid": "Data to create it is not valid",
    "visit_invalid": "Value not valid",
}


def error_label(code: str) -> str:
    """The kind of error a code says — see ERROR_LABELS."""
    return ERROR_LABELS.get(code, "Other problem")


# ── the columns ──

def column_key(name: str) -> str:
    """A column name without its number in front (12_Observation), its case, spaces or underscores."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"^\d+_", "", name.strip().lower()))


def suggest(header: list[str]) -> dict[str, str]:
    """For each field of a visit, the column of the header that most likely gives it."""
    names = {alias: field for field, aliases in COLUMN_NAMES.items() for alias in aliases} | {column_key(f): f for f, _, _ in FIELDS}
    mapping: dict[str, str] = {}
    for cell in header:
        field = names.get(column_key(cell))
        if field and field not in mapping:
            mapping[field] = cell
    return mapping


def fields_of(header: list[str], mapping: dict[str, str] | None) -> list[str | None]:
    """The field of a visit each column of the header gives — nothing for a column that is not used."""
    by_column = {column: field for field, column in (mapping or {}).items() if column}
    return [by_column.get(cell) for cell in header]


def field_list() -> list[dict]:
    """The fields of a visit a file can give: what each is, whether the visit needs it, the entity it is only of, and the entities that need it to
    be created."""
    needed_by = {f: [e for e, spec in CREATABLE.items() if f in spec["required"]] for f, _, _ in FIELDS}
    return [{"field": f, "label": label, "required": required, "entity": ENTITY_ONLY.get(f), "required_with": needed_by[f]} for f, label, required in FIELDS]


def rows_of(table: list[list[str]], mapping: dict[str, str] | None, defaults: dict[str, str] | None = None,
            create: dict[str, bool] | None = None) -> tuple[dict[str, str], list[dict[str, str]]]:
    """The file's columns, as the visit's fields they are, and its rows keyed by those fields — `table` being the file's rows, the first its header.

    `defaults` ({field: value}) is what a field is when its column is not in the file or a cell of it is empty; a field with a default counts as given. `create` ({locations, cameras,
    sd_cards}: bool) says which entities are created when they do not exist: the fields they need (see CREATABLE) are required too.

    Raises:
        VisitsCsvError: a required column is missing."""
    fields = fields_of(table[0], mapping)
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


# ── when a visit was ──

def real(date: str, time: str) -> tuple[str, str]:
    """The day and the time, once they are known to be a day and a time that exist (the 13th month, the 25th hour)."""
    try:
        dt.date.fromisoformat(date)
        dt.time.fromisoformat(time)
    except ValueError:
        raise RowError("date_invalid", f"'{date} {time}' is not a date and a time that exist.") from None
    return date, time


def when(row: dict[str, str], location: Location, time_source: str = "created_at") -> tuple[str, str]:
    """The day and the time of a visit: when its entry was created (created_at, UTC, as Epicollect writes it), else its date and time — or, when `time_source`
    is "hour", the date and the hour typed in the form (the wall clock of its location) when the row has them, else the time its entry was created."""
    if "created_at" in row and not (time_source == "hour" and "date" in row and "time" in row):
        try:
            created = dt.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise RowError("date_invalid", f"'{row['created_at']}' is not a created_at (2026-09-04T10:16:31.000Z).") from exc
        if created.tzinfo is not None:
            created = (created - (created.utcoffset() or dt.timedelta(0))).replace(tzinfo=None)
        local = wall_clock.utc_to_local(created.replace(microsecond=0), location)
        return local.date().isoformat(), local.time().isoformat()
    if "when" in row:
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)", row["when"])
        if not m:
            raise RowError("date_invalid", f"'{row['when']}' is not a date and time (YYYY-MM-DD HH:MM:SS).")
        return real(m.group(1), m.group(2) if m.group(2).count(":") == 2 else f"{m.group(2)}:00")
    if "date" not in row or "time" not in row:
        raise RowError("date_invalid", "The date and the time are required.")
    day = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", row["date"]) or re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", row["date"])
    if not day:
        raise RowError("date_invalid", f"'{row['date']}' is not a date (YYYY-MM-DD or DD/MM/YYYY).")
    date = row["date"] if "-" in row["date"] else f"{day.group(3)}-{day.group(2)}-{day.group(1)}"
    return real(date, row["time"] if row["time"].count(":") == 2 else f"{row['time']}:00")


def archived_by(locations: list[Location], visits: list[Visit]) -> list[Location]:
    """The locations as the visits leave them: one that a visit archives (its actions have Archive) is archived on the day of that visit, unless it already was before."""
    archived_on: dict[str, str] = {}
    for v in visits:
        if "Archive" in (v.get("actions") or []):
            site, day = str(v.get("location_id") or "").lower(), str(v.get("date") or "")
            if site and day and (site not in archived_on or day < archived_on[site]):
                archived_on[site] = day
    out = []
    for l in locations:
        on = archived_on.get(str(l.get("location_id") or "").lower())
        already = l.get("status") == "archived" and (not l.get("status_date") or (on and str(l["status_date"]) <= on))
        out.append({**l, "status": "archived", "status_date": on} if on and not already else l)
    return out


def minute_before(time: str) -> str:
    """The minute before a time of the day (HH:MM[:SS]), and the first of the day for the first."""
    h, m = (int(x) for x in time.split(":")[:2])
    total = max(h * 60 + m - 1, 0)
    return f"{total // 60:02d}:{total % 60:02d}:00"


# ── what a row creates ──

def username_of(name: str, taken: set[str]) -> str:
    """The username of a trapper made from the name a visit says: the name without accents, in lower case, with a dot between its words (`Ana Pérez` is `ana.perez`) — another number
    when it is taken (`ana.perez2`). It is what the trapper is called in the app: it can be changed in the settings."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", ".", ascii_name.lower()).strip(".") or "trapper"
    username, n = base, 1
    while username.lower() in taken:
        n += 1
        username = f"{base}{n}"
    return username


def location_fields(site: str, row: dict[str, str]) -> Location:
    """What a row says of the location it creates: its id, its coordinates (the location's, not the visit's) and its timezone.

    Raises:
        RowError: the row has no coordinates or timezone, or does not say whether its cameras follow summer time."""
    try:
        latitude, longitude = float(row["location_latitude"]), float(row["location_longitude"])
    except (KeyError, ValueError) as exc:
        raise RowError("create_missing", f"To create the location {site} the row needs its own coordinates: a latitude and a longitude of the location.") from exc
    if not row.get("timezone"):
        raise RowError("create_missing", f"To create the location {site} the row needs its timezone (e.g. Europe/Madrid).")
    saving = str(row.get("daylight_saving") or "").strip().lower()
    if saving not in YES | NO:
        raise RowError("create_missing", f"To create the location {site} the row needs to say if its cameras follow daylight saving time (yes or no).")
    try:
        uncertainty = int(float(row["coordinate_uncertainty"])) if row.get("coordinate_uncertainty") else None
    except ValueError as exc:
        raise RowError("create_invalid", f"To create the location {site}: {exc}") from exc
    return {"location_id": site, "name": row.get("location_name") or None, "latitude": latitude, "longitude": longitude, "timezone": row["timezone"],
            "ignore_dst": saving in NO, "coordinate_uncertainty": uncertainty, "status": "pending"}


# ── a file of visits written by the app ──

def export_rows(visits: list[Visit]) -> list[list[str]]:
    """The visits as rows the import reads back as they are: a header of EXPORT_FIELDS, then a row for each visit from the oldest — the actions
    joined with +, the tags with |, the yes/no fields as yes or no."""
    def cell(visit: Visit, field: str) -> str:
        value: Any = cast(dict, visit).get(field)   # a field named as the export names it
        if value is None:
            return ""
        if field == "actions":
            return "+".join(value)
        if field == "tags":
            return "|".join(value)
        if isinstance(value, bool):
            return "yes" if value else "no"
        return str(value)

    return [list(EXPORT_FIELDS), *([cell(v, f) for f in EXPORT_FIELDS] for v in sorted(visits, key=lambda v: (str(v.get("date")), str(v.get("time")))))]
