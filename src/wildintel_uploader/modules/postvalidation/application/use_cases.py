"""The use cases of the postvalidation: the validators asked for, in their order, over one MediaFolder, each told when it starts and ends."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder, ParallelMap
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext, PostvalidationError
from wildintel_uploader.modules.postvalidation.domain.ports import (
    CameraLevels, CameraRecords, OnCheck, PostvalidationReports, PostvalidationService, PreviousRevisions,
)
from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator


class PostvalidationUseCases(PostvalidationService):
    """Over the validators it is given (infrastructure/validators, put together in wiring), in their order."""

    def __init__(self, info: FileInfoService, pmap: ParallelMap, validators: tuple[type[DeploymentValidator], ...], *, cameras: CameraRecords | None = None,
                 levels: CameraLevels | None = None, reports: PostvalidationReports | None = None, revisions: PreviousRevisions | None = None) -> None:
        self._info, self._pmap, self._validators = info, pmap, validators
        self._cameras, self._levels, self._reports, self._revisions = cameras, levels, reports, revisions

    def validators(self, keys: frozenset[str] | None = None) -> list[DeploymentValidator]:
        return [v() for v in self._validators if keys is None or v.key in keys]

    def validate(self, folder: Path, context: DeploymentContext, validators: Sequence[DeploymentValidator] | None = None, *,
                 on_check: OnCheck | None = None) -> dict:
        if not self._info.is_folder(folder):
            raise PostvalidationError(f"Not a folder: {folder}")
        if context.tolerance_hours < 0:
            raise PostvalidationError("The tolerance can't be negative.")
        media = MediaFolder(folder, self._info, self._pmap)
        result: dict = {"checked_count": len(media.images)}
        for validator in (validators if validators is not None else self.validators()):
            if on_check:
                on_check(validator.key, "running")
            result.update(validator.run(media, context))
            if on_check:
                on_check(validator.key, "done")
        return result

    def check_deployment(self, folder: Path, context: DeploymentContext, checks: frozenset[str] | None = None, *, on_check: OnCheck | None = None) -> dict:
        camera = self._cameras.camera(context.research_project_id, context.deployment.camera_id) if self._cameras else context.camera
        context = replace(context, camera=camera, camera_levels=self._levels.levels() if self._levels is not None else context.camera_levels)
        validators = self.validators(checks)
        # the previous revisions of the location, read once for the statistical checks — and only when one of them is asked for
        if self._revisions is not None and context.research_project_id and any(v.statistical for v in validators):
            context = replace(context, previous=tuple(self._revisions.of(context.research_project_id, context.deployment.deployment_id)))
        result = self.validate(folder, context, validators, on_check=on_check)
        parameters = {"checks": sorted(checks) if checks is not None else None, "tolerance_hours": context.tolerance_hours, **(context.statistics or {})}
        report = self._reports.postvalidation(result, context.deployment.deployment_id, folder, parameters) if self._reports is not None else None
        return {**result, "report_id": report}
