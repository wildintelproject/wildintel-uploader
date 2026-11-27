"""How the forms of Epicollect5 are understood, without reaching it: the inputs of a project, what an entry says of a deployment, a visit as a row of
the columns a visit has, and the columns of the CSV Epicollect5 gives. Plain Python."""
from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

# The kinds of place a deployment is at, as Camtrap DP names them (featureType).
FEATURE_TYPES = frozenset({"roadPaved", "roadDirt", "trailHiking", "trailGame", "roadUnderpass", "roadOverpass", "roadBridge", "culvert", "burrow",
                           "nestSite", "carcass", "waterSource", "fruitingTree"})


class SourceError(Exception):
    """Something the user can act on: no project set, the project is private and the client is wrong, the server is unreachable, a file that is
    not the form of a visit."""


class Unreachable(SourceError):
    """Epicollect5 could not be reached — the network, or an answer that is not JSON —: `detail` says what happened."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Could not reach Epicollect5: {detail}")
        self.detail = detail


# Inputs that hold nothing to map: a text to read, and the containers (their own inputs are listed instead).
_NOT_DATA = {"readme", "group", "branch"}


def _walk(inputs: list[dict], form: str, group: str | None = None, branch: str | None = None) -> list[dict]:
    """The inputs of a form, flattened: those inside a group or a branch say which."""
    found: list[dict] = []
    for item in inputs:
        kind = item.get("type") or ""
        label = (item.get("question") or item.get("label") or item.get("ref") or "").strip()
        if kind == "group":
            found += _walk(item.get("group") or [], form, group=label or group, branch=branch)
        elif kind == "branch":
            found += _walk(item.get("branch") or [], form, group=group, branch=label or branch)
        elif kind not in _NOT_DATA and item.get("ref"):
            options = [a.get("answer") for a in item.get("possible_answers") or [] if a.get("answer")]
            found.append({"ref": item["ref"], "label": label, "type": kind, "form": form, "group": group, "branch": branch, "options": options})
    return found


def parse_project(definition: dict) -> dict:
    """The project's name and slug and every input of every form, from the export of the project (GET /api/export/project/<slug>)."""
    project = ((definition.get("data") or {}).get("project")) or {}
    if not project:
        errors = definition.get("errors") or []
        detail = errors[0].get("title") if errors and isinstance(errors[0], dict) else None
        raise SourceError(detail or "Epicollect5 did not answer with a project definition.")
    inputs: list[dict] = []
    for form in project.get("forms") or []:
        inputs += _walk(form.get("inputs") or [], form.get("name") or form.get("ref") or "")
    return {"project": {"name": project.get("name") or "", "slug": project.get("slug") or ""}, "inputs": inputs}


# The client's token, kept while it is valid: every read would ask for a new one, and Epicollect5 limits how many it gives.


# ── The entries: one row of the form is one deployment ──

_YES = {"yes", "true", "1", "y", "si", "sí"}
# Fields that hold text as it is, a number, a yes/no, or a list.
# Fields that hold text as it is, a number, a yes/no, or a list.
_TEXT = ("location_name", "camera_model", "camera_id", "habitat", "setup_by", "deployment_groups", "comments")


_NUMBER = ("camera_interval", "detection_distance", "camera_height", "camera_depth", "camera_tilt", "camera_heading")


_BOOL = ("bait_use", "timestamp_issues")


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list)):
        return None
    return str(value).strip() or None


def _number(value: Any) -> float | int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return None
    return int(number) if number.is_integer() else number


def _day(value: Any) -> date | None:
    """A date as Epicollect5 gives it: ISO (with or without a time), or as the form's own format — day first, as in Europe."""
    text = _text(value)
    if text is None:
        return None
    text = text.replace("Z", "")
    for pattern in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _clock(value: Any) -> time | None:
    text = _text(value)
    if text is None:
        return None
    match = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?", text)
    if not match:
        return None
    hour, minute, second, meridiem = int(match.group(1)), int(match.group(2)), int(match.group(3) or 0), (match.group(4) or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    try:
        return time(hour, minute, second)
    except ValueError:
        return None


def _yes_no(value: Any) -> bool | None:
    """A radio or a dropdown says yes or no; a checkbox is a list, ticked or not. Nothing answered is not recorded."""
    if isinstance(value, list):
        return any(str(v).strip().lower() in _YES for v in value)
    text = _text(value)
    return None if text is None else text.lower() in _YES


def _place(value: Any) -> dict | None:
    return value if isinstance(value, dict) and value.get("latitude") not in (None, "") else None


def entry_fields(entry: dict, mapping: dict[str, str]) -> dict:
    """What an entry says of a deployment, by field, through the mapping. The day and the time are kept apart (start_date /
    start_time, end_date / end_time): the wizard has the images' own times to complete a day with. What the entry leaves
    blank, or says in a way that can't be read, is not in the result."""
    raw = {key: entry.get(ref) for key, ref in mapping.items() if ref}
    found: dict[str, Any] = {}

    for key in _TEXT:
        if (value := _text(raw.get(key))) is not None:
            found[key] = value
    if (value := _text(raw.get("location_id"))) is not None:
        found["location_id"] = value
    for key in _NUMBER:
        if (value := _number(raw.get(key))) is not None:
            found[key] = value
    for key in _BOOL:
        if (flag := _yes_no(raw.get(key))) is not None:
            found[key] = flag
    if (value := _text(raw.get("feature_type"))) in FEATURE_TYPES:
        found["feature_type"] = value

    tags = raw.get("tags")
    items = tags if isinstance(tags, list) else (str(tags).split(",") if _text(tags) else [])
    if tags_found := [str(t).strip() for t in items if str(t).strip()]:
        found["tags"] = tags_found

    # A GPS input gives all three; a decimal input gives its own.
    for key, part in (("latitude", "latitude"), ("longitude", "longitude"), ("coordinate_uncertainty", "accuracy")):
        place = _place(entry.get(mapping.get(key) or ""))
        value = _number(place.get(part)) if place else _number(raw.get(key))
        if value is not None:
            found[key] = value

    if (value := _number(raw.get("revision"))) is not None:
        found["revision"] = int(value)
    for key in ("start_date", "end_date"):
        if (day := _day(raw.get(key))) is not None:
            found[key] = day.isoformat()
    for key in ("start_time", "end_time"):
        if (clock := _clock(raw.get(key))) is not None:
            found[key] = clock.strftime("%H:%M:%S")
    return found


# Inputs whose answer is a file, not something to read.


# Inputs whose answer is a file, not something to read.
_MEDIA = {"photo", "audio", "video"}


def _answer_text(value: Any) -> str | None:
    """An answer as a line of text: a place as "lat, lon", a list joined, anything else as it is. Nothing answered is None."""
    if isinstance(value, dict):
        lat, lon = value.get("latitude"), value.get("longitude")
        return f"{lat}, {lon}" if lat not in (None, "") and lon not in (None, "") else None
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip()) or None
    return _text(value)


def unmapped_notes(entry: dict, inputs: list[dict], mapping: dict[str, str]) -> str | None:
    """What the entry answers in the inputs of the form that no field of a deployment is mapped to, a line each as
    "question: answer". None when there is nothing."""
    mapped = set(mapping.values())
    lines = []
    for item in inputs:
        if item["ref"] in mapped or item["type"] in _MEDIA:
            continue
        if (answer := _answer_text(entry.get(item["ref"]))) is not None:
            lines.append(f"{item['label'] or item['ref']}: {answer}")
    return "\n".join(lines) or None


# ── The entries of the form of the field flow of a visit: one entry is one visit ──

# What each question of the form of a visit is (found by its label, ignoring case and spaces), and the field of a visit it gives.
VISIT_QUESTIONS: dict[str, str] = {
    "setupby": "trappers", "collection": "session", "revision": "session", "date": "date", "locationid": "location_id", "statusofthecamera": "camera_status",
    "cardandbatteries": "card_batteries_ok", "batterystatus": "battery_status", "batteriesstatus": "battery_status", "cardstatus": "card_status", "nºpicturescollected": "num_photos", "dateandtimeok": "date_time_ok", "action": "action",
    "actionaftertheft": "action_after_theft", "cameraname": "camera_label", "cameramodel": "camera_model", "serialnumber": "camera_serial",
    "cameraheight": "camera_height", "cameradelay": "camera_interval", "cameratilt": "camera_tilt", "cameraheading": "camera_heading",
    "detectiondistance": "detection_distance", "baituse": "bait_use", "featuretype": "feature_type", "habitat": "habitat", "sdtoinsert": "sd",
    "actionafterthereview": "action", "actionafterinspection": "action", "calibration": "calibration", "observations": "comments", "coordinates": "coordinates", "time": "time",
}
# what the form answers of the card and the batteries — one question — and what each of them is


# what the form answers of the card and the batteries — one question — and what each of them is
_CARD_CODES = {"ok": ("OK", "OK"), "card full": ("OK", "CardFull"), "no batteries": ("NoBatteries", "OK"), "card full and no batteries": ("NoBatteries", "CardFull")}


VISIT_COLUMNS = (
    "location_id", "session", "date", "time", "created_at", "actions", "trappers", "setup_by", "camera_status", "battery_status", "card_status", "num_photos", "date_time_ok", "camera_id", "camera_serial", "camera_model",
    "camera_height", "camera_interval", "camera_tilt", "camera_heading", "detection_distance", "bait_use", "feature_type", "habitat", "sd", "calibration", "comments", "latitude", "longitude",
)


def _label(text: str) -> str:
    return re.sub(r"\s+", "", text or "").lower()


# What the form answers of the status of the camera when there is none at the site: the old form said it as a new site or an inactive one


# What the form answers of the status of the camera when there is none at the site: the old form said it as a new site or an inactive one
_NO_CAMERA = ("no camera at the site", "new site", "inactive site")


def visit_actions(status: str | None, action: str | None, action_after_theft: str | None) -> str:
    """What a visit did, from what the form answers — one simple rule: an Installation if the status says there is no camera at the site (a new site, or an inactive one: its camera was removed before — the form now says it in one option) and one is put up; the action after a theft if the camera was
    stolen; the action otherwise. As the visit keeps them: a camera inspected is a Revision, replaced is a Revision, a Desinstallation and an Installation (after a theft, a Stolen and an
    Installation), a camera removed is a Revision and a Desinstallation, and a site removed is those two and an Archive — the location is given up — (after a theft, a
    Stolen and an Archive; after a theft a camera removed — not replaced, the site stays open — is a Stolen alone)."""
    status = (status or "").strip().lower()
    if status in _NO_CAMERA:
        return "Installation"  # no camera at the site — new, or its camera was removed before — has one put up: the form asks the same questions in both
    if status == "stolen":
        return {"camera replacement": "Stolen + Installation", "site removal": "Stolen + Archive", "camera removal": "Stolen", "none": "Stolen"}.get((action_after_theft or "").strip().lower(), "")
    return {
        "camera inspection": "Revision", "keep the camera": "Revision", "camera replacement": "Revision + Desinstallation + Installation", "camera removal": "Revision + Desinstallation",
        "site removal": "Revision + Desinstallation + Archive",
    }.get((action or "").strip().lower(), "")


def visit_row(entry: dict, refs: dict[str, str]) -> dict[str, str]:
    """A visit, as a row with the columns a visit has, from an entry of the form of the field flow. `refs` says the ref of the input each field comes from. What the
    entry leaves blank is not in the row. The camera's height is noted in centimetres and a visit keeps it in metres."""
    raw = {field: entry.get(ref) for field, ref in refs.items()}
    row: dict[str, str] = {}
    if (text := _text(raw.get("location_id"))) is not None:
        row["location_id"] = text
    if (text := _text(raw.get("session"))) is not None:
        row["session"] = text
    if (day := _day(raw.get("date"))) is not None:
        row["date"] = day.isoformat()
    if (clock := _clock(raw.get("time"))) is not None:
        row["time"] = clock.strftime("%H:%M:%S")
    if _text(entry.get("created_at")):
        row["created_at"] = str(entry["created_at"])
    if actions := visit_actions(_text(raw.get("camera_status")), _text(raw.get("action")), _text(raw.get("action_after_theft"))):
        row["actions"] = actions
    trappers = raw.get("trappers")
    names = trappers if isinstance(trappers, list) else ([trappers] if _text(trappers) else [])
    if names := [str(n).strip() for n in names if str(n).strip()]:
        row["trappers"] = ", ".join(names)
        row["setup_by"] = names[0]
    if (text := _text(raw.get("camera_status"))) is not None and text.strip().lower() != "no camera at the site":   # no camera is not a status of a camera: nothing is kept
        row["camera_status"] = text
    if (text := _text(raw.get("card_batteries_ok"))) is not None and text.lower() in _CARD_CODES:
        row["battery_status"], row["card_status"] = _CARD_CODES[text.lower()]
    # the form that asks the batteries and the card apart: each answer is its own column (the codes are read as they are written)
    for field in ("battery_status", "card_status"):
        if (text := _text(raw.get(field))) is not None:
            row[field] = text
    if (number := _number(raw.get("num_photos"))) is not None:
        row["num_photos"] = str(int(number))
    if (text := _text(raw.get("date_time_ok"))) is not None:
        row["date_time_ok"] = "Yes" if text.lower().startswith("ok") else "No"
    # the camera is what it is called in the field — its name (#231); its serial number only finds it, or creates or completes its record
    if (text := _text(raw.get("camera_label")) or _text(raw.get("camera_id"))) is not None:
        row["camera_id"] = text
    for field in ("camera_serial", "camera_model", "feature_type", "habitat", "comments"):
        if (text := _text(raw.get(field))) is not None:
            row[field] = text
    # the card is what the SD cards of the project are called — its number: the form is a free text, where it is written "SD 7", "sd-7" or "7"
    if (text := _text(raw.get("sd"))) is not None:
        row["sd"] = re.sub(r"^sd\s*[-_#.:]?\s*", "", text, flags=re.IGNORECASE) or text
    if (number := _number(raw.get("camera_height"))) is not None:
        row["camera_height"] = str(round(number / 100, 4))
    for field in ("camera_interval", "camera_tilt", "camera_heading", "detection_distance"):
        if (number := _number(raw.get(field))) is not None:
            row[field] = str(number)
    for field in ("bait_use", "calibration"):
        if (flag := _yes_no(raw.get(field))) is not None:
            row[field] = "yes" if flag else "no"
    if (place := _place(raw.get("coordinates"))) is not None:
        row["latitude"], row["longitude"] = str(place["latitude"]), str(place.get("longitude", ""))
    return row


# Epicollect5 cuts the headers of the CSV it gives at this many characters.
_HEADER_LIMIT = 20


def _header_key(header: str) -> tuple[str, str | None]:
    """A column of the CSV Epicollect5 gives, as the question it answers: its label with no number in front and no marks, and which part of a place it is, if it is one
    (`lat_26_Coordinates`, `long_26_Coordinates`)."""
    part = None
    match = re.match(r"(?i)^(lat|long|accuracy)_(.*)$", header.strip())
    if match:
        part, header = match.group(1).lower(), match.group(2)
    header = re.sub(r"^\d+_", "", header.strip())
    return re.sub(r"[\W_]+", "", header).lower(), part


def _form_refs(headers: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """The columns of the CSV of the form that answer each question of a visit (the field of the visit, the header of the column) and the ones that say where it was (`lat`, `long`)."""
    questions = {re.sub(r"[\W_]+", "", k).lower(): v for k, v in VISIT_QUESTIONS.items()} | {"npicturescollected": "num_photos"}
    refs: dict[str, str] = {}
    place: dict[str, str] = {}
    cut_headers: list[tuple[str, str]] = []
    for header in headers:
        key, part = _header_key(header)
        if key == "coordinates" and part in ("lat", "long"):
            place[part] = header
        elif part is None and key in questions:
            refs[questions[key]] = header
        elif part is None and len(header.strip()) >= _HEADER_LIMIT:
            # Epicollect5 cuts a header — its number, an underscore and the question — at 20 characters ("7_Status_of_the_came"): the question is then the beginning of a label
            cut_headers.append((key, header))
    # a cut header may begin more than one label ("10_Action_after_the_" is "Action after the review" and "Action after theft"): the question that another column already is is not it
    for _ in range(len(cut_headers)):
        for key, header in list(cut_headers):
            cut = {field for label, field in questions.items() if label.startswith(key) and len(key) >= 3} - set(refs)
            if len(cut) == 1:
                refs[cut.pop()] = header
                cut_headers.remove((key, header))
    return refs, place
