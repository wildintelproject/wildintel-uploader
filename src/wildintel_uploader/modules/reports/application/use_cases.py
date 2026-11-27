"""The use cases of the reports."""
from __future__ import annotations

import json

from wildintel_uploader.modules.reports.domain.ports import BadFormat, KeptReports, ReportsService


class ReportsUseCases(ReportsService):
    def __init__(self, kept: KeptReports) -> None:
        self._kept = kept

    def list(self) -> list[dict]:
        return self._kept.list()

    def read(self, report_id: str) -> dict:
        return self._kept.read(report_id)

    def as_file(self, report_id: str, fmt: str) -> tuple[str, str]:
        report = self._kept.read(report_id)
        if fmt == "csv":
            return self._kept.csv(report), "text/csv; charset=utf-8"
        if fmt == "json":
            return json.dumps(report, indent=2, ensure_ascii=False), "application/json"
        raise BadFormat("The format is json or csv.")

    def image(self, report_id: str, path: str, large: bool = False) -> bytes:
        return self._kept.image(report_id, path, large)

    def delete(self, report_id: str) -> None:
        self._kept.delete(report_id)
