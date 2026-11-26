"""CatalogRepository over a SQL database, with SQLModel (#248): the same port as `json_repository.StoreCatalogRepository`, so that the catalog can be
kept in a database — SQLite in a file by default, or any database SQLAlchemy reaches — without the domain or the use cases knowing.

Each record is a row: a column for each field of the domain, its id and dates, and `extra` — a JSON column — for what a record says that this
version does not know, as the files keep it. The people keep the order they were written in. A research project still has its folder in the
collections folder, where its collections go; what the folder holds besides is what counts as held by it — not the files of the records that, for
now, are still kept there as JSON (its visits, its locations…)."""
from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import JSON, Engine, delete, func
from sqlmodel import Field, Session, SQLModel, create_engine, select

from wildintel_uploader.modules.catalog.domain.models import Audit, ResearchProject, Trapper
from wildintel_uploader.modules.catalog.domain.ports import CatalogRepository
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


_TABLES = [TrapperRow.__table__, ProjectRow.__table__]  # type: ignore[attr-defined]
_AUDIT = ("id", "created_at", "updated_at", "deleted_at")
_TRAPPER = ("username", "name", "affiliation", "email", "status", "trapper_pk")
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
    """The catalog in the database of `engine` — its tables made when they are not there —; the research projects keep their folders in
    `collections_dir`."""

    def __init__(self, engine: Engine, collections_dir: Path) -> None:
        self.engine, self.collections_dir = engine, collections_dir
        SQLModel.metadata.create_all(engine, tables=_TABLES)

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
        (self.collections_dir / project.acronym).mkdir(parents=True, exist_ok=True)   # its folder, where its collections will go

    def save_project(self, project: ResearchProject) -> None:
        with Session(self.engine) as session:
            row = session.get(ProjectRow, project.acronym)
            if row is None:
                raise StorageError(f"The research project '{project.acronym}' isn't in the collections folder.")
            session.add(_set_project(row, project))
            session.commit()

    def held_by_project(self, acronym: str) -> list[str]:
        folder = self.collections_dir / acronym
        return sorted(e.name for e in folder.iterdir() if e.name not in _RECORD_FILE_NAMES) if folder.is_dir() else []
