"""The visits of the CSV downloaded from the Epicollect5 project of the field flow: its columns found by the label of their question, ignoring the
number in front, the case and the marks — and a header cut at 20 characters, as Epicollect5 does, by the beginning of it. The day and the time of a
visit are when its entry was created: the form has no date or time to ask for."""
from __future__ import annotations

import csv
import io
from typing import Any

from wildintel_uploader.modules.sources.domain.models import VISIT_COLUMNS, SourceError, form_refs, cell_text, visit_row
from wildintel_uploader.modules.sources.domain.ports import Epicollect5, VisitRows, VisitSource
from wildintel_uploader.modules.sources.domain.settings import Epicollect5Settings


def visits_from_csv(text: str) -> str:
    """The CSV of the form, as the text of a CSV with a row per visit and the columns a visit has. SourceError: no rows, or not the form."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    headers = reader.fieldnames or []
    refs, place = form_refs(list(headers))
    # the day and the time of a visit are when its entry was created (created_at): the form has no date or time to ask for
    missing = [name for name, field in (("locationID", "location_id"), ("Status of the camera", "camera_status")) if field not in refs]
    if "created_at" not in (reader.fieldnames or []):
        missing.append("created_at")
    if missing:
        raise SourceError(f"The file is not the download of the form of a visit: it has no column for {', '.join(missing)}.")
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(VISIT_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for line in reader:
        entry: dict[str, Any] = {ref: line.get(header) for ref, header in ((h, h) for h in refs.values())}
        entry["created_at"] = line.get("created_at")
        if "trappers" in refs and (names := cell_text(line.get(refs["trappers"]))):
            entry[refs["trappers"]] = [n.strip() for n in names.split(",")]
        if place:
            lat, lon = cell_text(line.get(place.get("lat", ""))), cell_text(line.get(place.get("long", "")))
            if lat:
                entry["__place"] = {"latitude": lat, "longitude": lon or ""}
        refs_now = dict(refs)
        if "__place" in entry:
            refs_now["coordinates"] = "__place"
        writer.writerow(visit_row(entry, refs_now))
    return out.getvalue()


def form_columns(text: str) -> dict[str, str]:
    """The columns of a CSV that are the answers of the form — the field of a visit and the header that gives it — with `created_at`, which says
    when, and the two columns of the coordinates (#204). Empty if it is not the form."""
    if form_error(text) is not None:
        return {}
    headers = csv.DictReader(io.StringIO(text.lstrip("\ufeff"))).fieldnames or []
    refs, place = form_refs(list(headers))
    coordinates = {field: place[part] for field, part in (("latitude", "lat"), ("longitude", "long")) if part in place}
    return {**refs, **coordinates, "created_at": "created_at"}


def form_error(text: str) -> str | None:
    """Why a CSV can't be read as the download of the form, or None when it can."""
    try:
        visits_from_csv(text)
    except SourceError as exc:
        return str(exc)
    return None


class EpicollectFormCsv(VisitSource):
    key = "epicollect-csv"
    label = "The CSV downloaded from Epicollect5"

    def visits(self, text: str | None, epicollect: Epicollect5, settings: Epicollect5Settings) -> VisitRows:
        return VisitRows(csv=visits_from_csv(text or ""), time_source="created_at", from_form=True)
