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

from pydantic import ValidationError

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


# What kind of error a problem is, from what it says — the rows with the same kind are told together. The first pattern that matches wins.
ERROR_KINDS: tuple[tuple[str, str], ...] = (
    (r"^The actions", "Actions not valid"),
    (r"is not OK, CarFull", "Card and batteries not valid"),
    (r"is not yes or no", "Not yes or no"),
    (r"is not a session", "Session not valid"),
    (r"cannot start:", "Revision started before the one before is finished"),
    (r"is closed:", "Revision closed"),
    (r"time data|does not match format|not a date|Invalid isoformat|unconverted data", "Date or time not valid"),
    (r"could not convert|invalid literal|not a whole number|not a number", "Number not valid"),
    (r"^To create the", "Data to create it is missing"),
    (r"^The visit time|^Field required|^Value error|^Input should", "Value not valid"),
)


def error_kind(message: str) -> str:
    """The kind of error a message says — see ERROR_KINDS."""
    return next((label for pattern, label in ERROR_KINDS if re.search(pattern, message)), "Other problem")


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


def _when(row: dict[str, str], location: dict, time_source: str = "created_at") -> tuple[str, str]:
    """The day and the time of a visit: when its entry was created (created_at, UTC, as Epicollect writes it), else its date and time — or, when `time_source`
    is "hour", the date and the hour typed in the form (the wall clock of its location) when the row has them, else the time its entry was created."""
    if "created_at" in row and not (time_source == "hour" and "date" in row and "time" in row):
        try:
            created = dt.datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"'{row['created_at']}' is not a created_at (2026-09-04T10:16:31.000Z).") from exc
        if created.tzinfo is not None:
            created = (created - created.utcoffset()).replace(tzinfo=None)
        local = _local(created.replace(microsecond=0), location)
        return local.date().isoformat(), local.time().isoformat()
    if "when" in row:
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)", row["when"])
        if not m:
            raise ValueError(f"'{row['when']}' is not a date and time (YYYY-MM-DD HH:MM:SS).")
        return m.group(1), m.group(2) if m.group(2).count(":") == 2 else f"{m.group(2)}:00"
    if "date" not in row or "time" not in row:
        raise ValueError("The date and the time are required.")
    day = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", row["date"]) or re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", row["date"])
    if not day:
        raise ValueError(f"'{row['date']}' is not a date (YYYY-MM-DD or DD/MM/YYYY).")
    date = row["date"] if "-" in row["date"] else f"{day.group(3)}-{day.group(2)}-{day.group(1)}"
    return date, row["time"] if row["time"].count(":") == 2 else f"{row['time']}:00"


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
    date_warnings: list[str] = []
    # A revision is one visit to each site: the session and the site of a visit already kept are taken, whatever its camera or its actions
    same_visit = {(str(v.get("session") or "").upper(), str(v.get("location_id", "")).lower()) for v in kept if v.get("session")}

    # What became of each row of the file: {row: {"row", "site", "result", "message"}} — result is ok, problem, already_kept, new_site or ignored.
    report: dict[int, dict] = {}

    def problem(n: int, message: str) -> None:
        problems.append({"row": n, "message": message})
        report[n] = {**report.get(n, {"row": n, "site": ""}), "result": "problem", "label": error_kind(message), "message": message}

    for n, row in enumerate(rows, start=2):
        found = re.search(r"\d+", row.get("session", ""))
        report[n] = {"row": n, "site": row.get("location_id", ""), "session": f"R{int(found.group(0)):04d}" if found else "", "result": "ok", "label": "", "message": ""}
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
        except ValueError as exc:
            problem(n, str(exc))
            continue
        if unknown:
            location = {}  # held with its site apart: the time is read as UTC, as nothing says better
        try:
            date, time = _when(row, location, time_source)
            if fmt == "epicollect" and "created_at" in row and "date" in row and time_source != "hour":
                try:
                    created_day = _when({"created_at": row["created_at"]}, location)[0]
                    typed_day = _when({"date": row["date"], "time": "00:00"}, location)[0]
                    if created_day != typed_day:
                        date_warnings.append(f"Row {n} ({site}): the date typed, {typed_day}, differs from the day of the entry, {created_day}; the time of the entry was used.")
                except ValueError:
                    pass
            actions = [ACTIONS.get(a.strip().lower()) for a in re.split(r"[+;/|&,]", row.get("actions", "")) if a.strip()]
            # a visit that could not be made has no action: it is exported so, and read back so
            if None in actions or (not actions and not visit_rules.is_not_revised({"status": row.get("status")})):
                raise ValueError(f"The actions '{row.get('actions', '')}' are not Installation, Revision, Desinstallation, Stolen or Archive.")
            if create.get("cameras") and row.get("camera_id"):
                camera = _new_camera(re.sub(r"\.0+$", "", row["camera_id"]), row)
                if camera["camera_id"].lower() not in cameras_known:
                    made["cameras"].append(camera)
            if create.get("sd_cards") and row.get("sd") and row["sd"].lower() not in cards_known:
                made["sd_cards"].append(_new_card(row["sd"], row))
            data: dict = {
                f: row[f] for f in ("trappers", "status", "sd", "date_time_ok", "camera_id", "camera_model", "comments", "setup_by", "session") if f in row
            }
            if "card_batteries_ok" in row:
                code = CODES.get(row["card_batteries_ok"].lower())
                if code is None:
                    raise ValueError(f"'{row['card_batteries_ok']}' is not OK, CarFull, SinPilas or CarFullSinPilas.")
                data["card_batteries_ok"] = code
            if "num_photos" in row:
                data["num_photos"] = int(row["num_photos"])
            for f in ("camera_interval", "camera_tilt", "camera_heading"):
                if f in row:
                    data[f] = int(float(row[f]))
            for f in ("camera_height", "camera_depth", "detection_distance"):
                if f in row:
                    data[f] = float(row[f])
            for f in ("timestamp_issues", "bait_use", "calibration"):
                if f in row:
                    word = row[f].lower()
                    if word not in YES | NO:
                        raise ValueError(f"'{row[f]}' is not yes or no.")
                    data[f] = word in YES
            for f in ("feature_type", "habitat", "deployment_groups"):
                if f in row:
                    data[f] = row[f]
            if "tags" in row:
                data["tags"] = [t.strip() for t in re.split(r"[|;]", row["tags"]) if t.strip()]
            # the GPS of the note is compared with the location's, to check that the site is the right one
            if row.get("latitude") and row.get("longitude") and location.get("latitude") is not None and location.get("longitude") is not None:
                gap = visit_rules.distance_m(float(row["latitude"]), float(row["longitude"]), float(location["latitude"]), float(location["longitude"]))
                if gap > visit_rules.GPS_TOLERANCE_M:
                    date_warnings.append(f"Row {n} ({site}): the GPS of the note is {round(gap)} m from the location; check that the site is the right one.")
            for f in ("latitude", "longitude"):
                value = row.get(f) or location.get(f)
                if value not in (None, ""):
                    data[f] = float(value)
            if "camera_id" in data:
                data["camera_id"] = re.sub(r"\.0+$", "", data["camera_id"])
            if "session" in data:
                m = re.search(r"\d+", data["session"])
                if not m:
                    raise ValueError(f"'{data['session']}' is not a session (R0013, or its number).")
                data["session"] = f"R{int(m.group(0)):04d}"
            visit = {"location_id": location.get("location_id", site), "date": date, "time": time, "actions": actions, **data}
            visit.setdefault("session", "R0000")  # worked out below, when the order of the visits is known
            record = VisitRecord.model_validate(visit).model_dump(mode="json")
            record["when"] = visit_time.to_when(record["date"], record["time"], location)
        except (ValueError, ValidationError) as exc:
            problem(n, _first(exc) if isinstance(exc, ValidationError) else str(exc))
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
            problem(n, f"{record['session']} is closed: every location has its visit in it, so nothing new can be imported in it.")
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
    warnings = [*date_warnings, *visit_rules.session_jump(visits, kept), *visit_rules.history_warnings(visits, kept, options.get("cards"))]
    notes = visit_rules.history_notes(visits, kept)
    # a revision is not started before the one before it is finished: its visits are refused, with the rows they come from
    refused = visit_rules.revision_gate(visits, kept, [*locations, *new_locations.values()])
    for visit, why in refused:
        problem(row_of[id(visit)], why)
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
    for n in sorted(kept_rows):
        names = [f"the location {l['location_id']}" for l in made_by_row.get(n, {}).get("locations", [])]
        names += [f"the camera {c['camera_id']}" for c in made_by_row.get(n, {}).get("cameras", [])]
        names += [f"the SD card {c['label']}" for c in made_by_row.get(n, {}).get("sd_cards", [])]
        if names and n in report and report[n]["result"] == "ok":
            report[n]["message"] = f"The visit is added, and creates {', '.join(names)}."
    return {"visits": visits, "problems": problems, "rows": [report[n] for n in sorted(report)], "skipped": skipped, "ignored": ignored, "new_sites": new_sites,
            "create": create_out, "warnings": list(dict.fromkeys(warnings)), "notes": notes}


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
        ValueError: the row has no coordinates or timezone, or they are not valid."""
    try:
        latitude, longitude = float(row["latitude"]), float(row["longitude"])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"To create the location {site} the row needs its coordinates: a latitude and a longitude.") from exc
    if not row.get("timezone"):
        raise ValueError(f"To create the location {site} the row needs its timezone (e.g. Europe/Madrid).")
    try:
        uncertainty = int(float(row["coordinate_uncertainty"])) if row.get("coordinate_uncertainty") else None
        return LocationRecord(location_id=site, name=row.get("location_name") or None, latitude=latitude, longitude=longitude, timezone=row["timezone"],
                              coordinate_uncertainty=uncertainty).model_dump(mode="json")
    except (ValidationError, ValueError) as exc:
        raise ValueError(f"To create the location {site}: {_first(exc) if isinstance(exc, ValidationError) else exc}") from exc


def _new_camera(camera_id: str, row: dict[str, str]) -> dict:
    """The camera a row creates: called by its id, with the model of the row.

    Raises:
        ValueError: the row has no model."""
    if not row.get("camera_model"):
        raise ValueError(f"To create the camera {camera_id} the row needs its model.")
    return config.Camera(label=camera_id, camera_id=camera_id, camera_model=row["camera_model"]).model_dump(mode="json")


def _new_card(label: str, row: dict[str, str]) -> dict:
    """The SD card a row creates: its id is its label, with the brand — and the capacity — of the row.

    Raises:
        ValueError: the row has no brand."""
    if not row.get("sd_brand"):
        raise ValueError(f"To create the SD card {label} the row needs its brand.")
    return config.SdCard(label=label, brand=row["sd_brand"], capacity=row.get("sd_capacity") or None).model_dump(mode="json")


def _first(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(p) for p in error["loc"])
    return f"{where}: {error['msg']}" if where else error["msg"]


def write_report(root, research_project_id: str, result: dict, saved: int) -> str | None:
    """The report of an import of visits, beside the visits of the research project (`visits_import_<day>_<time>.txt`): how many were kept, and what was
    wrong, odd or worth knowing. Returns its path — None when it could not be written."""
    from pathlib import Path  # noqa: PLC0415
    lines = [f"Visits kept to {research_project_id}: {saved} ({result.get('history', 0)} from the history)", f"Already kept: {result.get('skipped', 0)}"]
    for p in result.get("problems", []):
        lines.append(f"PROBLEM {'history ' if p.get('history') else ''}row {p['row']}: {p['message']}")
    for s in result.get("new_sites", []):
        lines.append(f"NEW SITE {s['site']}: {s['visits']} visit(s) held; nearest location {s['nearest']['location_id'] + ' at ' + str(s['nearest']['distance_m']) + ' m' if s['nearest'] else 'unknown'}"
                     f"{'; one character apart from ' + ', '.join(s['similar']) if s['similar'] else ''}")
    lines += [f"WARNING: {w}" for w in result.get("warnings", [])]
    lines += result.get("notes", [])
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = Path(root) / research_project_id / f"visits_import_{stamp}.txt"
    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        return None
    return str(path)
