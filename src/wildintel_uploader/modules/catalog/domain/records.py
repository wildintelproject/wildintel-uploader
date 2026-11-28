"""The records of the catalog as a backup copies and restores them (#248) — CatalogRecordStore: the research projects, their locations, cameras
and SD cards as they are kept, read and written as they are, ids and dates too (a restored record is the one that was kept, not a new one); and
the people and their roles as a backup holds them, through the rules of the catalog. For a backup only: every other module asks the catalog's
contract (CatalogService) and sees its models. What it refuses is a StorageError (shared.storage)."""
from __future__ import annotations

from collections.abc import Callable

from typing import Protocol


class CatalogRecordStore(Protocol):
    """The records of the catalog as they are kept — round its rules, for a backup only."""

    def project_record(self, project: str) -> dict | None:
        """The record of a research project as it is kept — removed or not —, or None."""

    def put_project_record(self, record: dict) -> None:
        """Keeps the record as it is given — its id and dates too —, in place of the one kept, or as a new one (with its folder)."""

    def checkpoint(self, project: str) -> Callable[[], None]:
        """What is kept of a research project — its record, locations, cameras, SD cards and roles — and the people, and how to put it back exactly
        as it was: a restoration that fails half way undoes what it wrote."""

    def location_records(self, project: str) -> list[dict]: ...
    def put_location_records(self, project: str, records: list[dict]) -> None: ...
    def equipment_records(self, project: str, kind: str) -> list[dict]: ...
    def put_equipment_records(self, project: str, kind: str, records: list[dict]) -> None: ...

    # the people and the roles, as a backup holds them: by the rules of the catalog — a person known by its username, a role by its person's name
    def trappers(self) -> list[dict]: ...
    def keep_trappers(self, trappers: list[dict]) -> None: ...
    def roles(self, project: str, include_deleted: bool = False) -> list[dict]: ...
    def keep_roles(self, project: str, roles: list[dict]) -> None: ...
