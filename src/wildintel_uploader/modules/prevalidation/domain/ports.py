"""The contract of the prevalidation, and what its use cases are given: what is known of the files (the contract of modules.fileinfo) and how to go
through the images in parallel."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.folder import Progress
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
