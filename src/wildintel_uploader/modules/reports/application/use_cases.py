"""The use cases of the reports: each kind built from what was done — the images of its folder listed, the failed ones dated —, kept, read,
listed, given as a file, its images shown small, deleted."""
from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wildintel_uploader.modules.reports.domain import report as rules
from wildintel_uploader.modules.reports.domain.ports import BadFormat, FolderImages, ImageDates, KeptReports, ReportMissing, ReportsService

THUMBNAIL = 320
LARGE = 1280


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ReportsUseCases(ReportsService):
    def __init__(self, kept: KeptReports, images: FolderImages, dates: ImageDates, now: Callable[[], datetime] = _now) -> None:
        self._kept, self._images, self._dates, self._now = kept, images, dates, now

    # ── building ──

    def _built(self, builder: rules.ReportBuilder) -> dict:
        root = Path(builder.source_dir) if builder.source_dir else None
        failed = builder.failed_images()
        read = self._dates.dates([root / n for n in failed]) if root and failed else {}
        return builder.build(self._now().isoformat(timespec="seconds"), {n: read.get(root / n) for n in failed} if root else None)

    def validation_report(self, found: dict, source: Path, checks: Iterable[str] | None = None) -> dict:
        return self._built(rules.validation_report(found, source, self._images.images(source), checks))

    def postvalidation_report(self, result: dict, deployment_id: str, source: Path, parameters: dict | None = None) -> dict:
        return self._built(rules.postvalidation_report(result, deployment_id, source, self._images.images(source), parameters))

    def repair_report(self, deployment_id: str, dest: Path, files: list[tuple[str, bool, str]], seal: dict | None,
                      preprocessing: dict[str, dict[str, str]]) -> dict:
        return self._built(rules.repair_report(deployment_id, dest, self._images.images(dest), files, seal, preprocessing))

    def preprocessing_report(self, records: list[dict], skipped: list[dict], deployment_id: str, source: Path, dest: Path, options: dict) -> dict:
        return self._built(rules.preprocessing_report(records, skipped, deployment_id, source, dest, options))

    def upload_report(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> dict:
        return self._built(rules.upload_report(collection, project, items, started_at=started_at, finished_at=finished_at))

    def visits_import_report(self, project: str, result: dict, saved: int) -> dict:
        return self._built(rules.visits_import_report(project, result, saved))

    # ── keeping and giving ──

    def save(self, report: dict) -> str:
        """Keeps a report and says its id — also set in the report."""
        report["id"] = self._kept.keep(report, report["kind"], rules.report_name(report))
        return report["id"]

    def read(self, report_id: str) -> dict:
        if not rules.is_report_id(report_id):
            raise ReportMissing(f"'{report_id}' isn't a report.")
        return self._kept.read(report_id)

    def list(self) -> list[dict]:
        return [rules.summary(r) for r in self._kept.all()]

    def as_file(self, report_id: str, fmt: str) -> tuple[str, str]:
        report = self.read(report_id)
        if fmt == "csv":
            return rules.to_csv(report), "text/csv; charset=utf-8"
        if fmt == "json":
            return json.dumps(report, indent=2, ensure_ascii=False), "application/json"
        raise BadFormat("The format is json or csv.")

    def image(self, report_id: str, path: str, large: bool = False) -> bytes:
        """An image a report names, small — only the images the report lists are shown, so this is no way to read other files."""
        report = self.read(report_id)
        if not rules.lists(report, path):
            raise ReportMissing(f"The report doesn't have the image '{path}'.")
        return self._images.small(Path(report["source_dir"]), path, LARGE if large else THUMBNAIL)

    def delete(self, report_id: str) -> None:
        self.read(report_id)
        self._kept.delete(report_id)

    def delete_older_than(self, days: int) -> int:
        cutoff = self._now() - timedelta(days=days)
        gone = 0
        for item in self.list():
            try:
                if datetime.fromisoformat(item["created_at"]) < cutoff:
                    self.delete(item["id"])
                    gone += 1
            except (TypeError, ValueError, ReportMissing):
                continue
        return gone

    # ── what the other modules keep ──

    def save_validation(self, found: dict, folder: Path, checks: Iterable[str] | None) -> str:
        return self.save(self.validation_report(found, folder, checks))

    def save_postvalidation(self, result: dict, deployment_id: str, folder: Path, parameters: dict | None) -> str:
        return self.save(self.postvalidation_report(result, deployment_id, folder, parameters))

    def save_preprocessing(self, records: list[dict], skipped: list[dict], deployment_id: str, source: Path, dest: Path, options: dict) -> str:
        return self.save(self.preprocessing_report(records, skipped, deployment_id, source, dest, options))

    def save_visits_import(self, project: str, result: dict, saved: int) -> str:
        return self.save(self.visits_import_report(project, result, saved))

    def save_upload(self, collection: str, project: str, items: list[dict], started_at: str, finished_at: str) -> str:
        return self.save(self.upload_report(collection, project, items, started_at, finished_at))

    def save_repair(self, deployment_id: str, dest: Path, files: list[tuple[str, bool, str]], seal: dict | None,
                    preprocessing: dict[str, dict[str, str]]) -> str:
        return self.save(self.repair_report(deployment_id, dest, files, seal, preprocessing))
