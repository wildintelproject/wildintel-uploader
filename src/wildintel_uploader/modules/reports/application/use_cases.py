"""The use cases of the reports."""
from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

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

    def save_validation(self, found: dict, folder: Path, checks: Iterable[str] | None) -> str:
        return self._kept.save("validation", found, folder, checks)

    def save_postvalidation(self, result: dict, deployment_id: str, folder: Path, parameters: dict | None) -> str:
        return self._kept.save("postvalidation", result, deployment_id, folder, parameters)

    def save_preprocessing(self, records: list[dict], skipped: list[dict], deployment_id: str, source: Path, dest: Path, options: dict) -> str:
        return self._kept.save("preprocessing", records, skipped, deployment_id, source, dest, options)

    def save_visits_import(self, project: str, result: dict, saved: int) -> str:
        return self._kept.save("visits", project, result, saved)

    def save_upload(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> str:
        return self._kept.save("upload", collection, project, items, started_at=started_at, finished_at=finished_at)

    def save_repair(self, deployment_id: str, dest: Path, files: list[tuple[str, bool, str]], seal: dict | None,
                    preprocessing: dict[str, dict[str, str]]) -> str:
        return self._kept.save("repair", deployment_id, dest, files, seal, preprocessing)
