"""The use cases of the prevalidation: the validators asked for, in their order, over one MediaFolder — so that what one reads is there for the
next —, each told when it starts and ends."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder, ParallelMap, Progress
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions, PrevalidationError
from wildintel_uploader.modules.prevalidation.domain.ports import ImportedImages, OnCheck, PrevalidationReports, PrevalidationService, PrevalidationSettings
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator


class PrevalidationUseCases(PrevalidationService):
    """Over the validators it is given (domain/checks, put together in wiring), in their order."""

    def __init__(self, info: FileInfoService, pmap: ParallelMap, validators: tuple[type[ImageValidator], ...], *, imported: ImportedImages | None = None,
                 settings: PrevalidationSettings | None = None, reports: PrevalidationReports | None = None) -> None:
        self._info, self._pmap, self._validators = info, pmap, validators
        self._imported, self._settings, self._reports = imported, settings, reports

    def validators(self, keys: frozenset[str] | None = None) -> list[ImageValidator]:
        return [v() for v in self._validators if keys is None or v.key in keys]

    def validate(self, folder: Path, validators: Sequence[ImageValidator] | None = None, *, detail: bool = False,
                 imported: dict[str, list[dict]] | None = None, progress: Progress | None = None, exif_fields: list[str] | None = None,
                 camera_levels: list[list[str]] | None = None, on_check: OnCheck | None = None) -> dict:
        if not self._info.is_folder(folder):
            raise PrevalidationError(f"Not a folder: {folder}")
        media = MediaFolder(folder, self._info, self._pmap, progress)
        options = ImageOptions(detail=detail, exif_fields=exif_fields, camera_levels=camera_levels, imported=imported)
        result: dict = {"checked_count": len(media.images)}
        for validator in (validators if validators is not None else self.validators()):
            if on_check:
                on_check(validator.key, "running")
            found = validator.run(media, options)
            if media.reader is not None and "exiftool" not in result:   # once the cameras were read: whether ExifTool read them
                result["exiftool"] = media.reader == "exiftool"
            result.update(found)
            if on_check:
                on_check(validator.key, "done")
        return result

    def check_folder(self, folder: Path, checks: frozenset[str] | None = None, *, research_project_id: str | None = None,
                     deployment_id: str | None = None, progress: Progress | None = None, on_check: OnCheck | None = None) -> dict:
        imported = None
        if research_project_id and self._imported is not None and (checks is None or "duplicates" in checks):
            imported = self._imported.source_hashes(research_project_id, deployment_id)
        settings = self._settings.current() if self._settings is not None else None
        result = self.validate(folder, self.validators(checks), detail=True, imported=imported, progress=progress,
                               exif_fields=list(settings.exif_fields) if settings else None,
                               camera_levels=[list(level) for level in settings.camera_levels] if settings else None, on_check=on_check)
        return {**result, "report_id": self._reports.validation(result, folder, checks) if self._reports is not None else None}
