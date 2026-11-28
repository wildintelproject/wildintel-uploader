"""A step of the preprocessing, as a class (#246): its key and label, whether the options ask for it, and what it does — to one image, on what the
steps before it left in its record (ImageStep), or to all of them once they are prepared (FolderStep: the XMP, written in batches, and the hashes of
the files as they end up)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar

from wildintel_uploader.modules.fileinfo.domain.models import CameraInfo
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.preprocessing.domain.models import ImageWork, PreprocessOptions
from wildintel_uploader.shared.deployment_record import DeploymentRecord


@dataclass(frozen=True)
class Job:
    """What every step of a deployment is given: its options, the deployment, what is known of the files, what was read of all its images at
    once — their dates and their cameras (one run of ExifTool, #227) —, and where ExifTool is (None: it isn't)."""
    options: PreprocessOptions
    deployment: DeploymentRecord          # the whole record: it is written beside the images and sealed with them
    info: FileInfoService
    dates: dict = field(default_factory=dict)
    cameras: dict = field(default_factory=dict)
    exiftool: str | None = None

    def date_of(self, work: ImageWork) -> datetime | None:
        return self.dates[work.source] if work.source in self.dates else self.info.dates([work.source]).get(work.source)

    def camera_of(self, work: ImageWork) -> CameraInfo:
        return self.cameras.get(work.source) or CameraInfo()


class ImageStep(ABC):
    key: ClassVar[str]
    label: ClassVar[str]

    def wanted(self, options: PreprocessOptions) -> bool:
        """Whether the options ask for it: most steps always run, each doing what the options say."""
        return True

    @abstractmethod
    def run(self, work: ImageWork, job: Job) -> None:
        """Does its part to the image, and writes what it found out or did in its record."""


class FolderStep(ABC):
    key: ClassVar[str]
    label: ClassVar[str]

    def wanted(self, options: PreprocessOptions) -> bool:
        return True

    def check(self, job: Job) -> None:
        """What it needs, said before anything is written — PreprocessingError when it can't be done."""

    @abstractmethod
    def run(self, works: list[ImageWork], job: Job) -> Iterator[dict]:
        """Does its part to the images prepared, telling how far it is with events."""
