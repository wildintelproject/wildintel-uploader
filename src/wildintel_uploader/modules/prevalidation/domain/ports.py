"""The contract of the prevalidation, and what its use cases are given: what is known of the files (the contract of modules.fileinfo) and how to go
through the images in parallel."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.folder import Progress
from wildintel_uploader.modules.prevalidation.domain.settings import ValidationSettings
from wildintel_uploader.modules.prevalidation.domain.validators import ImageValidator

# on_check(check, state): a check starts ("running") or ends ("done").
OnCheck = Callable[[str, str], None]


class PrevalidationService(ABC):

    @abstractmethod
    def validators(self, keys: frozenset[str] | None = None) -> list[ImageValidator]:
        """The validators of the images, in the order they run — those of these keys (the names the settings and the pages use), or all."""

    @abstractmethod
    def validate(self, folder: Path, validators: Sequence[ImageValidator] | None = None, *, detail: bool = False,
                 imported: dict[str, list[dict]] | None = None, progress: Progress | None = None, exif_fields: list[str] | None = None,
                 camera_levels: list[list[str]] | None = None, on_check: OnCheck | None = None) -> dict:
        """Runs these validators over the images of the folder, in the order given (None: all, in theirs): {"checked_count", "exiftool" once the
        cameras were read, and what each found}. `progress(step, done, total)` is told how far the long steps are ("cameras", "dates", "corrupted"), and `on_check` when each check
        starts and ends. PrevalidationError: the folder isn't one."""

    @abstractmethod
    def check_folder(self, folder: Path, checks: frozenset[str] | None = None, *, research_project_id: str | None = None,
                     deployment_id: str | None = None, progress: Progress | None = None, on_check: OnCheck | None = None) -> dict:
        """The checks of the images of a folder as an import asks for them — those of these keys (None: all) with what the settings say of them,
        the duplicates also among the images imported before into the research project (but those of `deployment_id`, imported again) —, every
        file of a field that lacks it, and the id of their report ("report_id", None when it could not be written)."""


# ── out ──

class ImportedImages(ABC):
    @abstractmethod
    def source_hashes(self, research_project_id: str, exclude_deployment: str | None = None) -> dict[str, list[dict]]:
        """The images already imported into a research project, by the SHA-1 of the original: {"deployment_id", "collection", "original"}.
        PrevalidationError when the research project can't be read."""


class PrevalidationSettings(ABC):
    @abstractmethod
    def current(self) -> ValidationSettings:
        """The section VALIDATION in use."""


class PrevalidationReports(ABC):
    @abstractmethod
    def validation(self, result: dict, folder: Path, checks: frozenset[str] | None) -> str | None:
        """Keeps the report of a prevalidation; its id, or None when it could not be written."""
