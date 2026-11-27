"""The contract of the fixes of the dates (TimeFixService), what it refuses, and what its use cases are given: the period a visit gives, and the
images of a folder — read, shifted, taken out — with the fixes written down."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

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


class VisitPeriods(ABC):
    @abstractmethod
    def period(self, visit: VisitOfTheImages) -> Period: ...


class TimedImages(ABC):
    @abstractmethod
    def timeline(self, folder: str, period: Period | None) -> dict: ...

    @abstractmethod
    def shift(self, folder: str, period: Period | None, first: str, last: str | None, offset_seconds: int, reason: str) -> dict: ...

    @abstractmethod
    def remove(self, folder: str, period: Period | None, names: list[str], reason: str) -> dict: ...
