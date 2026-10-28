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

from wildintel_uploader.core.schemas.requests import VisitRecord
from wildintel_uploader.core.services import visit_rules, visit_time

# What each column of an Epicollect download may be called — compared without case, spaces, dashes, underscores or a number in front.
EPICOLLECT_COLUMNS: dict[str, tuple[str, ...]] = {
    "location_id": ("site", "location", "locationid", "sitio"),
    "date": ("date", "fecha"),
    "time": ("time", "hora"),
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
    "bait_use": ("baituse",),
    "feature_type": ("featuretype",),
    "habitat": ("habitat",),
    "deployment_groups": ("deploymentgroups",),
    "tags": ("tags", "deploymenttags"),
}
# The fields of a visit a CSV can give, in the order they are asked for: what each one is, and whether the visit needs it.
FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("location_id", "Site (a location of the research project)", True),
    ("actions", "Actions (Installation, Revision, Desinstallation, Stolen — several with +)", True),
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
    ("feature_type", "Feature type", False),
    ("habitat", "Habitat", False),
    ("deployment_groups", "Deployment groups", False),
    ("tags", "Tags (separated by |)", False),
)
REQUIRED = tuple(f for f, _, required in FIELDS if required)
EPICOLLECT_NUMBER = re.compile(r"^\s*(\d+)\s*([bB]?)\s*$")
ACTIONS = {a.lower(): a for a in ("Installation", "Revision", "Desinstallation", "Stolen")} | {
    # as the datasheets of the field work write them
    "i": "Installation", "r": "Revision", "d": "Desinstallation", "robada": "Stolen", "uninstallation": "Desinstallation", "removal": "Desinstallation",
}
YES = {"yes", "true", "1", "y", "si", "sí"}
NO = {"no", "false", "0", "n"}
CODES = {c.lower(): c for c in ("OK", "CarFull", "SinPilas", "CarFullSinPilas")}


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
    """The field of a visit each column of the header gives — nothing for a column that is not used."""
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


def _rows(text: str, fmt: str, mapping: dict[str, str] | None) -> tuple[dict[str, str], list[dict[str, str]]]:
    """The file's columns, as the visit's fields they are, and its rows keyed by those fields."""
    table = _table(text)
    fields = _fields(table[0], fmt, mapping)
    present = {f for f in fields if f}
    missing = [f for f in REQUIRED if f not in present]
    if not present & {"created_at", "when"} and not {"date", "time"} <= present:
        missing.append("the date and the time (or created_at)")
    if missing:
        raise VisitsCsvError(f"The file has no column for: {', '.join(missing)}. Columns found: {', '.join(c.strip() for c in table[0])}.")
    rows = [{f: cell.strip() for f, cell in zip(fields, row) if f and cell.strip()} for row in table[1:]]
    return {f: c for f, c in zip(fields, table[0]) if f}, rows


def _local(created: dt.datetime, location: dict) -> dt.datetime:
    """The time of an entry — UTC — in the timezone of the location, with no summer time when the location ignores it; UTC when it has none."""
    return visit_time.utc_to_local(created, location)


def _when(row: dict[str, str], location: dict) -> tuple[str, str]:
    """The day and the time of a visit: when its entry was created (created_at, UTC, as Epicollect writes it), else its date and time."""
    if "created_at" in row:
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


def parse_visits(text: str, locations: list[dict], kept: list[dict], site_prefix: str = "", fmt: str = "mapped", mapping: dict[str, str] | None = None) -> dict:
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

    Returns {"visits": [...], "problems": [{"row", "message"}], "skipped": int, "ignored": int, "new_sites": [...], "warnings": [str]} — the rows
    numbered as in the file, the header being 1.

    Raises:
        VisitsCsvError: the file is empty or lacks a required column.
    """
    columns, rows = _rows(text, fmt, mapping)
    epicollect = fmt == "epicollect" and "created_at" in columns
    known = {str(l.get("location_id", "")).lower(): l for l in locations}
    already = {(str(v.get("location_id", "")).lower(), v.get("date"), v.get("time")) for v in kept}
    problems: list[dict] = []
    parsed: list[tuple[int, dict]] = []
    skipped = 0
    ignored = 0
    held: dict[str, list[dict]] = {}  # the visits to sites that are not locations of the research project, by site

    def problem(n: int, message: str) -> None:
        problems.append({"row": n, "message": message})

    for n, row in enumerate(rows, start=2):
        if epicollect and ("session" not in row or "location_id" not in row):
            ignored += 1
            continue
        site = _site(row.get("location_id", ""), site_prefix) if fmt == "epicollect" else row.get("location_id", "")
        location = known.get(site.lower())
        unknown = location is None
        if unknown:
            location = {}  # held with its site apart: the time is read as UTC, as nothing says better
        try:
            date, time = _when(row, location)
            actions = [ACTIONS.get(a.strip().lower()) for a in re.split(r"[+;/|&,]", row.get("actions", "")) if a.strip()]
            if not actions or None in actions:
                raise ValueError(f"The actions '{row.get('actions', '')}' are not Installation, Revision, Desinstallation or Stolen.")
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
            for f in ("timestamp_issues", "bait_use"):
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
            continue
        if (record["location_id"].lower(), record["date"], record["time"]) in already:
            skipped += 1
            continue
        already.add((record["location_id"].lower(), record["date"], record["time"]))
        parsed.append((n, record | {"_given": "session" in row}))

    count: dict[str, int] = {}
    for loc in {r["location_id"].lower() for _, r in parsed}:
        count[loc] = sum(1 for v in kept if str(v.get("location_id", "")).lower() == loc)
    visits = []
    for _, record in sorted(parsed, key=lambda p: (p[1]["date"], p[1]["time"])):
        given = record.pop("_given")
        loc = record["location_id"].lower()
        if not given:
            record["session"] = f"R{count[loc] + 1:04d}"
        count[loc] += 1
        visits.append(record)
    new_sites = [visit_rules.new_site(site, records, locations) for site, records in sorted(held.items())]
    return {"visits": visits, "problems": problems, "skipped": skipped, "ignored": ignored, "new_sites": new_sites, "warnings": visit_rules.history_warnings(visits, kept)}


def _first(exc: ValidationError) -> str:
    error = exc.errors()[0]
    where = ".".join(str(p) for p in error["loc"])
    return f"{where}: {error['msg']}" if where else error["msg"]
