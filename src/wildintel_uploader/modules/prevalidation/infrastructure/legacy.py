"""The ports of the prevalidation over the code of before: the images imported before (their preprocessing.json, local_folder_service), the
settings in use, the reports (report_service)."""
from __future__ import annotations

import logging
from pathlib import Path

from wildintel_uploader.modules.prevalidation.domain.models import PrevalidationError
from wildintel_uploader.modules.prevalidation.domain.ports import ImportedImages, PrevalidationReports, PrevalidationSettings
from wildintel_uploader.modules.prevalidation.domain.settings import ValidationSettings

logger = logging.getLogger(__name__)


class PreprocessedImages(ImportedImages):
    def source_hashes(self, research_project_id: str, exclude_deployment: str | None = None) -> dict[str, list[dict]]:
        from wildintel_uploader.core import config
        from wildintel_uploader.core.services import local_folder_service
        try:
            return local_folder_service.imported_source_hashes(config.collections_dir(), research_project_id, exclude_deployment)
        except local_folder_service.LocalFolderError as exc:
            raise PrevalidationError(str(exc)) from exc


class ValidationInUse(PrevalidationSettings):
    """VALIDATION as the code of before reads the settings (config.load_settings)."""

    def current(self) -> ValidationSettings:
        from wildintel_uploader.core import config
        kept = config.load_settings().VALIDATION
        return ValidationSettings(**{**kept.model_dump(), "camera_levels": tuple(tuple(level) for level in kept.camera_levels),
                                     "exif_fields": tuple(kept.exif_fields)})


class SavedValidationReports(PrevalidationReports):
    def validation(self, result: dict, folder: Path, checks: frozenset[str] | None) -> str | None:
        """None when it can't be written: that is no reason to fail what it reports."""
        from wildintel_uploader.core.logging_setup import debugging
        from wildintel_uploader.core.services import report_service
        try:
            return report_service.save(report_service.validation_report(result, folder, checks))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not write the report: %s", exc, exc_info=debugging())
            return None
