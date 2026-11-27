"""The ports of the postvalidation over the code of before: the record of a camera (the catalog's functions of before), how a camera is told
(VALIDATION, as config reads it), the reports (report_service)."""
from __future__ import annotations

import logging
from pathlib import Path

from wildintel_uploader.modules.postvalidation.domain.ports import CameraLevels, CameraRecords, PostvalidationReports, PreviousRevisions
from wildintel_uploader.modules.postvalidation.domain.statistics import DeploymentTimes, Revision
from wildintel_uploader.modules.reports.domain.ports import ReportsService

logger = logging.getLogger(__name__)


class CatalogCameras(CameraRecords):
    def camera(self, research_project_id: str | None, camera_id: str | None) -> dict | None:
        from wildintel_uploader.core import config
        from wildintel_uploader.core.services import local_folder_service
        return local_folder_service.camera_record(config.collections_dir(), research_project_id, camera_id)


class LevelsInUse(CameraLevels):
    def levels(self) -> list[list[str]]:
        from wildintel_uploader.core import config
        return config.load_settings().VALIDATION.camera_levels


class SavedPostvalidationReports(PostvalidationReports):
    """Through the contract of the reports."""

    def __init__(self, reports: ReportsService) -> None:
        self._reports = reports

    def postvalidation(self, result: dict, deployment_id: str, folder: Path, parameters: dict) -> str | None:
        """None when it can't be written: that is no reason to fail what it reports."""
        from wildintel_uploader.core.logging_setup import debugging
        try:
            return self._reports.save_postvalidation(result, deployment_id, folder, parameters)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not write the report: %s", exc, exc_info=debugging())
            return None


class RevisionsOfTheDeployments(PreviousRevisions):
    """As the deployments say them — through their contract, given when it is needed."""

    def __init__(self, deployments) -> None:
        self._deployments = deployments

    def of(self, research_project_id: str, deployment_id: str) -> list:
        return [Revision(r["revision"], r["deployment_id"], DeploymentTimes(r["image_count"], r["times"]))
                for r in self._deployments().previous_revisions(research_project_id, deployment_id)]
