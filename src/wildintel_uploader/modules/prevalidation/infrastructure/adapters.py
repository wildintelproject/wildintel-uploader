"""The ports out of the prevalidation: the images imported before (the deployments, through their contract), VALIDATION as the settings keep
it, and the reports (through their contract)."""
from __future__ import annotations

import logging
from pathlib import Path

from wildintel_uploader.modules.prevalidation.domain.models import PrevalidationError
from wildintel_uploader.modules.prevalidation.domain.ports import ImportedImages, PrevalidationReports, PrevalidationSettings
from wildintel_uploader.modules.prevalidation.domain.settings import ValidationSettings
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.settings.domain.ports import StoredSettings

logger = logging.getLogger(__name__)


class PreprocessedImages(ImportedImages):
    """As the deployments say them — through their contract, given when it is needed."""

    def __init__(self, deployments) -> None:
        self._deployments = deployments

    def source_hashes(self, research_project_id: str, exclude_deployment: str | None = None) -> dict[str, list[dict]]:
        from wildintel_uploader.modules.deployments.domain.models import DeploymentsError
        try:
            return self._deployments().imported_images(research_project_id, exclude_deployment)
        except DeploymentsError as exc:
            raise PrevalidationError(exc.message) from exc


class ValidationInUse(PrevalidationSettings):
    def __init__(self, settings: StoredSettings) -> None:
        self._settings = settings   # the settings as settings.toml keeps them

    def current(self) -> ValidationSettings:
        kept = self._settings.load_settings().VALIDATION
        return ValidationSettings(**{**kept.model_dump(), "camera_levels": tuple(tuple(level) for level in kept.camera_levels),
                                     "exif_fields": tuple(kept.exif_fields)})


class SavedValidationReports(PrevalidationReports):
    """Through the contract of the reports."""

    def __init__(self, reports: ReportsService) -> None:
        self._reports = reports

    def validation(self, result: dict, folder: Path, checks: frozenset[str] | None) -> str | None:
        """None when it can't be written: that is no reason to fail what it reports."""
        from wildintel_uploader.shared.logs import debugging
        try:
            return self._reports.save_validation(result, folder, checks)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not write the report: %s", exc, exc_info=debugging())
            return None
