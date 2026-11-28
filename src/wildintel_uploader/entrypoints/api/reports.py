"""FastAPI router — the reports (module `modules.reports`), at /api/reports as always. A report that is not there is a 404."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from dishka.integrations.fastapi import DishkaSyncRoute, FromDishka
from fastapi import APIRouter, HTTPException, Response

from wildintel_uploader.modules.reports.domain.ports import BadFormat, ReportMissing, ReportsService
from wildintel_uploader.modules.reports.infrastructure.api_schemas import (  # what its routes answer
    DeleteReportAnswer, GetReportAnswer, ListReportsItem,
)

router = APIRouter(prefix="/api/reports", tags=["reports"], route_class=DishkaSyncRoute)
Reports = FromDishka[ReportsService]
T = TypeVar("T")


def _http(call: Callable[[], T]) -> T:
    try:
        return call()
    except ReportMissing as exc:
        raise HTTPException(404, str(exc)) from exc
    except BadFormat as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("", response_model=list[ListReportsItem], response_model_exclude_unset=True)
def list_reports(reports: Reports) -> list[dict]:
    """What each report says of itself, newest first."""
    return reports.list()


@router.get("/{report_id}", response_model=GetReportAnswer, response_model_exclude_unset=True)
def get_report(report_id: str, reports: Reports) -> dict:
    return _http(lambda: reports.read(report_id))


@router.get("/{report_id}/download", response_model=None)
def download_report(report_id: str, reports: Reports, format: str = "json") -> Response:
    """The report as a file: its own JSON, or a CSV with a row per image and check."""
    body, media_type = _http(lambda: reports.as_file(report_id, format))
    return Response(body, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{report_id}.{format}"'})


@router.get("/{report_id}/image", response_model=None)
def report_image(report_id: str, path: str, reports: Reports, size: str = "thumb") -> Response:
    """An image the report lists, as a JPEG — a thumbnail, or (size=large) one to look at closely."""
    body = _http(lambda: reports.image(report_id, path, size == "large"))
    return Response(body, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/{report_id}", response_model=DeleteReportAnswer, response_model_exclude_unset=True)
def delete_report(report_id: str, reports: Reports) -> dict:
    _http(lambda: reports.delete(report_id))
    return {"status": "ok"}
