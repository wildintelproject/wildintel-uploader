"""The ports of the postvalidation over the code of before: the record of a camera (the catalog, through its contract), how a camera is told
(VALIDATION, as config reads it), the reports (through their contract)."""
from __future__ import annotations

import logging
from pathlib import Path

from wildintel_uploader.modules.postvalidation.domain.ports import CameraLevels, CameraRecords, PostvalidationReports, PreviousRevisions
from wildintel_uploader.modules.postvalidation.domain.statistics import DeploymentTimes, Revision
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.settings.domain.ports import StoredSettings

logger = logging.getLogger(__name__)


class CatalogCameras(CameraRecords):
    """The record of a camera as the catalog keeps it — through its contract, given when it is needed."""

    def __init__(self, catalog) -> None:
        self._catalog = catalog

    def camera(self, research_project_id: str | None, camera_id: str | None) -> dict | None:
        camera = self._catalog().camera(research_project_id, camera_id) if research_project_id and camera_id else None
        if camera is None:
            return None
        return {"label": camera.label, "camera_id": camera.camera_id, "camera_make": camera.camera_make, "camera_model": camera.camera_model}


class LevelsInUse(CameraLevels):
    def __init__(self, settings: StoredSettings) -> None:
        self._settings = settings   # the settings as settings.toml keeps them

    def levels(self) -> list[list[str]]:
        return self._settings.load_settings().VALIDATION.camera_levels


class SavedPostvalidationReports(PostvalidationReports):
    """Through the contract of the reports."""

    def __init__(self, reports: ReportsService) -> None:
        self._reports = reports

    def postvalidation(self, result: dict, deployment_id: str, folder: Path, parameters: dict) -> str | None:
        """None when it can't be written: that is no reason to fail what it reports."""
        from wildintel_uploader.shared.logs import debugging
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
