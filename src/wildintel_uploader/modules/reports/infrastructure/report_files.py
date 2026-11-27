"""The reports as files in the reports folder, over the code of before (report_service); what it refuses is ReportMissing."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from wildintel_uploader.modules.reports.domain.ports import KeptReports, ReportMissing

T = TypeVar("T")


def _old():
    from wildintel_uploader.modules.reports.infrastructure import report_service
    return report_service


def _ours(call: Callable[[], T]) -> T:
    try:
        return call()
    except _old().ReportError as exc:
        raise ReportMissing(str(exc)) from exc


class ReportFiles(KeptReports):
    def list(self) -> list[dict]:
        return _old().list_reports()

    def read(self, report_id: str) -> dict:
        return _ours(lambda: _old().read(report_id))

    def csv(self, report: dict) -> str:
        return _old().to_csv(report)

    def image(self, report_id: str, path: str, large: bool) -> bytes:
        rs = _old()
        return _ours(lambda: rs.image_jpeg(report_id, path, rs.LARGE if large else rs.THUMBNAIL))

    def delete(self, report_id: str) -> None:
        _ours(lambda: _old().delete(report_id))

    def save(self, kind: str, *args, **kwargs) -> str:
        rs = _old()
        build = {"validation": rs.validation_report, "postvalidation": rs.postvalidation_report, "preprocessing": rs.preprocessing_report,
                 "visits": rs.visits_import_report, "upload": rs.upload_report, "repair": rs.repair_report}[kind]
        return rs.save(build(*args, **kwargs))
