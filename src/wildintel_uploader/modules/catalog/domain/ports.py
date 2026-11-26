"""The contracts of the catalog (#248), on both sides of it:

- **In** — `CatalogService`: what the module offers, which the entry points (and the other modules) call. Implemented by
  `application.use_cases.CatalogUseCases`.
- **Out** — what it needs from outside: `CatalogRepository`, where its records are kept (the JSON files of the collections folder,
  `infrastructure.json_repository`); `LegacyTrappers`, the people versions before kept in the settings (`infrastructure.legacy`, through the contract
  of the module of the settings); `Clock`, the instant."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from wildintel_uploader.modules.catalog.domain.models import Trapper


@dataclass(frozen=True)
class AddedTrappers:
    """What adding people did: the usernames added, and those left out because they were taken."""
    added: list[str]
    skipped: list[str]


# ── in: what the module offers ──

class CatalogService(Protocol):
    """The catalog. Besides the errors each method names, a record or a list that cannot be is the domain's CatalogError."""

    def trappers(self, include_deleted: bool = False) -> list[Trapper]:
        """The people. A removed one is not listed unless asked for: the visits it made still say who it was."""

    def save_trappers(self, trappers: list[Trapper]) -> list[Trapper]:
        """Keeps these people as all of them (see domain.rules.saved_trappers), and gives them as they were kept."""

    def add_trappers(self, trappers: list[Trapper]) -> AddedTrappers:
        """Adds the people that are not kept yet — active —; one with the username of another, whatever its case, is left out."""


# ── out: what the module needs ──

class CatalogRepository(Protocol):
    """Where the records of the catalog are kept."""

    def read_trappers(self) -> list[Trapper]:
        """All the people kept, the removed ones too; one kept before the ids existed gets the same id whenever it is read."""

    def write_trappers(self, trappers: list[Trapper]) -> None:
        """Keeps these as all the people."""


class LegacyTrappers(Protocol):
    """The people versions before kept in the settings."""

    def take(self) -> list[Trapper]:
        """Gives them, and they are no longer there: the catalog keeps them from now on."""


class Clock(Protocol):
    def now(self) -> str:
        """The instant, as the dates of a record are written: ISO 8601, UTC, with a Z."""
