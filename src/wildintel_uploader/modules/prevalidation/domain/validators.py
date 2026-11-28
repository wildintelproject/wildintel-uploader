"""A validator of the images, as a class (#246): its key — the name the settings, the reports and the pages use —, its label and what it says,
and what it finds in the folder, by the keys the results have always had (corrupted, sequence_issues, cameras, exif_missing…)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions


class ImageValidator(ABC):
    key: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]

    @abstractmethod
    def run(self, folder: MediaFolder, options: ImageOptions) -> dict:
        """What it found, by the keys of the result."""
