"""The use cases of the postvalidation: the validators asked for, in their order, over one MediaFolder, each told when it starts and ends."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder, ParallelMap
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.postvalidation.domain.models import DeploymentContext, PostvalidationError
from wildintel_uploader.modules.postvalidation.domain.ports import OnCheck, PostvalidationService
from wildintel_uploader.modules.postvalidation.domain.validators import DeploymentValidator


class PostvalidationUseCases(PostvalidationService):
    """Over the validators it is given (infrastructure/validators, put together in wiring), in their order."""

    def __init__(self, info: FileInfoService, pmap: ParallelMap, validators: tuple[type[DeploymentValidator], ...]) -> None:
        self._info, self._pmap, self._validators = info, pmap, validators

    def validators(self, keys: frozenset[str] | None = None) -> list[DeploymentValidator]:
        return [v() for v in self._validators if keys is None or v.key in keys]

    def validate(self, folder: Path, context: DeploymentContext, validators: Sequence[DeploymentValidator] | None = None, *,
                 on_check: OnCheck | None = None) -> dict:
        if not folder.is_dir():
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
