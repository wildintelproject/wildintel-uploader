"""The history of visits of a research project — the fieldwork datasheet, an .xlsx — read as the rows of a CSV, so that it is read as visits the way an Epicollect
download is: its columns (Trappers, Session, Date, Time or DateTime, Site, Camera, Action, Status, CardBatteriesOK, NumPhotos, SD, DateTimeOK, Notes,
Longitude, Latitude, and the Camtrap DP fields the field survey may have added) are found by their names, in English or in Spanish (Tramperos, Sesion, Fecha, Hora…)."""
from __future__ import annotations

import csv
import datetime as dt
import io
import zipfile

from wildintel_uploader.core.services import visits_csv


class VisitsXlsxError(Exception):
    """The file can't be read as a history of visits."""


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, dt.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, dt.time):
        return value.strftime("%H:%M:%S")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def to_csv(data: bytes) -> str:
    """The first worksheet of the workbook that has a Site (or Sitio) column and an Action (or Accion) one, as the text of a CSV — its first row the header.

    Raises:
        VisitsXlsxError: it isn't an .xlsx workbook, or no sheet of it looks like a history of visits.
    """
    try:
        import openpyxl  # noqa: PLC0415 — only needed here
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise VisitsXlsxError("The history is not an .xlsx workbook: save the spreadsheet as .xlsx (Excel Workbook).") from exc
    for sheet in workbook.worksheets:
        rows = [[_cell(v) for v in row] for row in sheet.iter_rows(values_only=True)]
        rows = [r for r in rows if any(r)]
        if not rows:
            continue
        names = {visits_csv._key(c) for c in rows[0]}
        if names & set(visits_csv.EPICOLLECT_COLUMNS["location_id"]) and names & set(visits_csv.EPICOLLECT_COLUMNS["actions"]):
            out = io.StringIO()
            csv.writer(out).writerows(rows)
            return out.getvalue()
    raise VisitsXlsxError("No sheet of the workbook looks like a history of visits: it needs a Site (Sitio) column and an Action (Accion) one in its first row.")
