"""The contract of the fixes of the dates (TimeFixService), what it refuses, and what its use cases are given: the visits of a location, the
images of a folder and their dates, a way to shift their dates, the fixes written down beside them, and the tolerance of the settings."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

Period = tuple[datetime, datetime]


class TimeFixError(Exception):
    """A folder that isn't one, a run that isn't there, an offset that can't be, a visit that gives no period…"""


@dataclass(frozen=True)
class VisitOfTheImages:
    """The visit that left the camera — by its research project, location, day and time —, whose deployment's period the images are checked against."""
    research_project_id: str
    location_id: str
    date: str
    time: str


class TimeFixService(ABC):

    @abstractmethod
    def timeline(self, folder: str, visit: VisitOfTheImages | None = None) -> dict:
        """The images of the folder in the camera's order, with their times, segments and the fixes made so far."""

    @abstractmethod
    def shift(self, folder: str, visit: VisitOfTheImages | None, first: str, last: str | None, offset_seconds: int, reason: str = "") -> dict:
        """Moves the date and time of a run of images by an offset; the timeline after it."""

    @abstractmethod
    def remove(self, folder: str, visit: VisitOfTheImages | None, names: list[str], reason: str = "") -> dict:
        """Takes images whose time can't be made right out of the folder; the timeline after it."""


class VisitsOfTheLocation(ABC):
    @abstractmethod
    def visits(self, research_project_id: str, location_id: str) -> list[dict]:
        """The visits kept to a location. Raises TimeFixError when they can't be read."""


class ImageFolder(ABC):
    @abstractmethod
    def open(self, folder: str) -> Path:
        """The folder. Raises TimeFixError when it is not one."""

    @abstractmethod
    def images(self, folder: Path) -> list[Path]:
        """Its images, in the order the camera numbered them."""

    @abstractmethod
    def delete(self, images: list[Path]) -> None:
        ...


class ImageDates(Protocol):
    def dates(self, paths: list[Path]) -> dict[Path, datetime | None]:
        """When each image says it was taken (what the images say: modules.fileinfo)."""
        ...


class DateShifter(ABC):
    @abstractmethod
    def shift(self, folder: Path, images: list[Path], offset_seconds: int) -> None:
        """Moves every date of the images by the offset. Raises TimeFixError when it can't."""


class Corrections(ABC):
    @abstractmethod
    def read(self, folder: Path) -> list[dict]:
        ...

    @abstractmethod
    def write(self, folder: Path, entry: dict) -> None:
        """Writes a fix down beside the images — what, to which, by how much, why —, with when and by whom."""


class Tolerance(ABC):
    @abstractmethod
    def hours(self) -> float:
        """How far from the deployment's period an image may be and still be in it (POSTVALIDATION.tolerance_hours)."""
