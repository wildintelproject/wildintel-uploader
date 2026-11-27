"""CatalogRepository over a SQL database, with SQLModel (#248): the same port as `json_repository.StoreCatalogRepository`, so that the catalog can be
kept in a database — SQLite in a file by default, or any database SQLAlchemy reaches — without the domain or the use cases knowing.

Each record is a row: a column for each field of the domain, its id and dates, and `extra` — a JSON column — for what a record says that this
version does not know, as the files keep it. The people and the locations keep the order they were written in; a location says its research project. A research project still has its folder in the
collections folder, where its collections go; what the folder holds besides is what counts as held by it — not the files of the records that, for
now, are still kept there as JSON (its visits, its locations…)."""
from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import JSON, Engine, delete, func
from sqlmodel import Field, Session, SQLModel, create_engine, select

from wildintel_uploader.modules.catalog.domain.models import Audit, Camera, Location, ResearchProject, Role, SdCard, Trapper
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository
from wildintel_uploader.modules.catalog.infrastructure.sql_migrations import migrate
from wildintel_uploader.shared.storage import StorageError
from wildintel_uploader.shared.storage.json_files import PROJECT_FILE, RECORD_FILES

# The files of the JSON records that may be in the folder of a research project: they are records, not what it holds.
_RECORD_FILE_NAMES = frozenset({PROJECT_FILE, *RECORD_FILES.values()})


# ── the tables ──

class _Audited(SQLModel):
    """The id and the dates every record keeps of itself, and what it says that this version does not know."""
    id: Optional[str] = Field(default=None, index=True)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deleted_at: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict, sa_type=JSON)   # a column of its own in each table


class TrapperRow(_Audited, table=True):
    __tablename__ = "trappers"
    row: Optional[int] = Field(default=None, primary_key=True)   # the order they were written in
    username: str = Field(index=True)
    name: str
    affiliation: Optional[str] = None
    email: Optional[str] = None
    status: str = "active"
    trapper_pk: Optional[int] = None


class ProjectRow(_Audited, table=True):
    __tablename__ = "research_projects"
    acronym: str = Field(primary_key=True)
    name: str
    sampling_design: int = 1
    sensor_method: int = 1
    animal_types: int = 1
    bait_use: int = 1
    event_interval: int = 0
    status: str = "active"
    keywords: str = ""
    abstract: str = ""
    methods: str = ""
    description: str = ""
    trapper_pk: Optional[int] = None


class LocationRow(_Audited, table=True):
    __tablename__ = "locations"
    row: Optional[int] = Field(default=None, primary_key=True)   # the order they were written in
    project: str = Field(index=True)                              # the acronym of its research project
    location_id: str = Field(index=True)
    name: Optional[str] = None
    timezone: Optional[str] = None
    ignore_dst: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    coordinate_uncertainty: Optional[int] = None
    in_service: Optional[str] = None
    trapper_pk: Optional[int] = None
    status: str = "pending"
    status_date: Optional[str] = None
    status_note: Optional[str] = None


class _Equipment(_Audited):
    row: Optional[int] = Field(default=None, primary_key=True)
    project: str = Field(index=True)
    label: str
    in_service: Optional[str] = None
    status: str = "ready"
    archive_reason: Optional[str] = None
    status_date: Optional[str] = None
    status_note: Optional[str] = None


class CameraRow(_Equipment, table=True):
    __tablename__ = "cameras"
    camera_id: Optional[str] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    connectivity: Optional[str] = None
    power_source: Optional[str] = None
    battery_removable: Optional[str] = None


class SdCardRow(_Equipment, table=True):
    __tablename__ = "sd_cards"
    brand: Optional[str] = None
    capacity: Optional[str] = None


class RoleRow(_Audited, table=True):
    __tablename__ = "roles"
    row: Optional[int] = Field(default=None, primary_key=True)
    project: str = Field(index=True)
    trapper: Optional[str] = None
    trapper_ref: Optional[str] = None
    role: str = "contributor"


_TABLES = [t.__table__ for t in (TrapperRow, ProjectRow, LocationRow, CameraRow, SdCardRow, RoleRow)]  # type: ignore[attr-defined]
_EQUIPMENT = {"cameras": (CameraRow, Camera, ("label", "camera_id", "camera_make", "camera_model", "connectivity", "power_source", "battery_removable",
                                               "in_service", "status", "archive_reason", "status_date", "status_note")),
              "sd_cards": (SdCardRow, SdCard, ("label", "brand", "capacity", "in_service", "status", "archive_reason", "status_date", "status_note"))}
_AUDIT = ("id", "created_at", "updated_at", "deleted_at")
_TRAPPER = ("username", "name", "affiliation", "email", "status", "trapper_pk")
_LOCATION = ("location_id", "name", "timezone", "ignore_dst", "latitude", "longitude", "coordinate_uncertainty", "in_service", "trapper_pk", "status",
             "status_date", "status_note")
_PROJECT = ("acronym", "name", "sampling_design", "sensor_method", "animal_types", "bait_use", "event_interval", "status", "keywords", "abstract",
            "methods", "description", "trapper_pk")


# ── rows and the domain, one into the other ──

def _audit(row: _Audited) -> Audit:
    return Audit(**{k: getattr(row, k) for k in _AUDIT})


def _trapper(row: TrapperRow) -> Trapper:
    return Trapper(**{k: getattr(row, k) for k in _TRAPPER}, audit=_audit(row), extra=dict(row.extra or {}))


def _trapper_row(trapper: Trapper) -> TrapperRow:
    return TrapperRow(**{k: getattr(trapper, k) for k in _TRAPPER}, **{k: getattr(trapper.audit, k) for k in _AUDIT}, extra=dict(trapper.extra))


def _project(row: ProjectRow) -> ResearchProject:
    return ResearchProject(**{k: getattr(row, k) for k in _PROJECT}, audit=_audit(row), extra=dict(row.extra or {}))


def _location(row: LocationRow) -> Location:
    return Location(**{k: getattr(row, k) for k in _LOCATION}, audit=_audit(row), extra=dict(row.extra or {}))


def _location_row(project: str, location: Location) -> LocationRow:
    return LocationRow(project=project, **{k: getattr(location, k) for k in _LOCATION}, **{k: getattr(location.audit, k) for k in _AUDIT},
                       extra=dict(location.extra))


def _set_project(row: ProjectRow, project: ResearchProject) -> ProjectRow:
    for k in _PROJECT:
        setattr(row, k, getattr(project, k))
    for k in _AUDIT:
        setattr(row, k, getattr(project.audit, k))
    row.extra = dict(project.extra)
    return row


# ── the repository ──

@lru_cache(maxsize=8)
def _engine(url: str) -> Engine:
    return create_engine(url)


def sqlite_engine(path: Path) -> Engine:
    """An engine for a SQLite database in a file — its folder made the first time —, one for each file for as long as the app lives."""
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return _engine(f"sqlite:///{path}")


class SqlCatalogRepository(CatalogRepository):
    """The catalog in the database of `engine` — its tables made when they are not there, and migrated when they are of a version before. It keeps records only: the folders of the research
    projects are not its own (ports.ProjectFolders)."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        # made when they are not there, brought to the last version when they are of one before (sql_migrations)
        migrate(engine, lambda e: SQLModel.metadata.create_all(e, tables=_TABLES), [t.name for t in _TABLES])

    # the people

    def read_trappers(self) -> list[Trapper]:
        with Session(self.engine) as session:
            return [_trapper(r) for r in session.exec(select(TrapperRow).order_by(TrapperRow.row))]

    def write_trappers(self, trappers: Iterable[Trapper]) -> None:
        """All of them at once, in one transaction: what was there is replaced."""
        with Session(self.engine) as session:
            session.exec(delete(TrapperRow))  # type: ignore[call-overload]
            session.add_all([_trapper_row(t) for t in trappers])
            session.commit()

    # the research projects

    def read_projects(self) -> list[ResearchProject]:
        with Session(self.engine) as session:
            return [_project(r) for r in session.exec(select(ProjectRow).order_by(func.lower(ProjectRow.acronym)))]

    def read_project(self, acronym: str) -> ResearchProject | None:
        with Session(self.engine) as session:
            row = session.get(ProjectRow, acronym)
            return _project(row) if row is not None else None

    def add_project(self, project: ResearchProject) -> None:
        with Session(self.engine) as session:
            if session.get(ProjectRow, project.acronym) is not None:
                raise StorageError(f"The research project '{project.acronym}' already exists.")
            session.add(_set_project(ProjectRow(acronym=project.acronym, name=project.name), project))
            session.commit()

    def save_project(self, project: ResearchProject) -> None:
        with Session(self.engine) as session:
            row = session.get(ProjectRow, project.acronym)
            if row is None:
                raise StorageError(f"The research project '{project.acronym}' isn't in the collections folder.")
            session.add(_set_project(row, project))
            session.commit()

    def files_of(self, acronym: str) -> set[str]:
        return set(_RECORD_FILE_NAMES)   # none of its own: those a move from the files may have left

    # the locations

    def read_locations(self, project: str) -> list[Location]:
        with Session(self.engine) as session:
            return [_location(r) for r in session.exec(select(LocationRow).where(LocationRow.project == project).order_by(LocationRow.row))]

    def write_locations(self, project: str, locations: list[Location]) -> None:
        """All the locations of the research project at once, in one transaction: what it had is replaced."""
        with Session(self.engine) as session:
            session.exec(delete(LocationRow).where(LocationRow.project == project))  # type: ignore[call-overload]
            session.add_all([_location_row(project, loc) for loc in locations])
            session.commit()

    # the equipment and the roles

    def read_equipment(self, project: str, kind: str) -> list:
        row_class, domain_class, fields = _EQUIPMENT[kind]
        with Session(self.engine) as session:
            rows = session.exec(select(row_class).where(row_class.project == project).order_by(row_class.row))
            return [domain_class(**{k: getattr(r, k) for k in fields}, audit=_audit(r), extra=dict(r.extra or {})) for r in rows]

    def write_equipment(self, project: str, kind: str, items: list) -> None:
        row_class, _, fields = _EQUIPMENT[kind]
        with Session(self.engine) as session:
            session.exec(delete(row_class).where(row_class.project == project))  # type: ignore[call-overload]
            session.add_all([row_class(project=project, **{k: getattr(i, k) for k in fields}, **{k: getattr(i.audit, k) for k in _AUDIT},
                                       extra=dict(i.extra)) for i in items])
            session.commit()

    def read_roles(self, project: str) -> list[Role]:
        with Session(self.engine) as session:
            rows = session.exec(select(RoleRow).where(RoleRow.project == project).order_by(RoleRow.row))
            return [Role(trapper=r.trapper, role=r.role, trapper_ref=r.trapper_ref, audit=_audit(r), extra=dict(r.extra or {})) for r in rows]

    def write_roles(self, project: str, roles: list[Role]) -> None:
        with Session(self.engine) as session:
            session.exec(delete(RoleRow).where(RoleRow.project == project))  # type: ignore[call-overload]
            session.add_all([RoleRow(project=project, trapper=None if r.trapper_ref else r.trapper, trapper_ref=r.trapper_ref, role=r.role,
                                     **{k: getattr(r.audit, k) for k in _AUDIT}, extra=dict(r.extra)) for r in roles])
            session.commit()
