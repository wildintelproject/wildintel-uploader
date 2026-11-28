"""The versions of the tables of the catalog in a database (#248): what create_all does not do — change a database made by a version before. The
database keeps the version of its tables in `schema_version`; when it is opened, each migration it lacks is made, in order, each in a transaction of
its own, and the version is written with it. Plain SQLAlchemy, whatever database it reaches.

    - a new database: its tables are made as they are now, at the last version;
    - a database made before the versions were kept (its tables there, `schema_version` not): version 1, the tables as they were first made;
    - a database of a later version of the app than this one: refused, never changed — this version does not know its tables.

A change to the tables is a new migration at the end of MIGRATIONS — its version the next number, what it does to a database of the one before —,
never a change to one already there: a database may have made it already. A test checks that a database of version 1 migrated to the last has the
tables the models say."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from sqlalchemy import Column, Connection, Engine, Integer, MetaData, Table, inspect, select

from wildintel_uploader.shared.errors import StorageError


@dataclass(frozen=True)
class Migration:
    """What takes the tables from the version before to `version`: `change` runs inside the transaction that writes the version."""
    version: int
    says: str
    change: Callable[[Connection], None]


# The versions after the first, in order. Version 1 is the tables as they were first made (#248): trappers, research_projects, locations, cameras,
# sd_cards and roles.
MIGRATIONS: tuple[Migration, ...] = ()

_versions = MetaData()
_schema_version = Table("schema_version", _versions, Column("version", Integer, nullable=False))


def latest(migrations: Sequence[Migration] = MIGRATIONS) -> int:
    return migrations[-1].version if migrations else 1


def version_of(engine: Engine, tables: Sequence[str]) -> int | None:
    """The version of the tables of a database — 1 if they were made before the versions were kept —, None if it has none of them yet."""
    names = set(inspect(engine).get_table_names())
    if "schema_version" in names:
        with engine.connect() as connection:
            kept = connection.execute(select(_schema_version.c.version)).scalar()
        if kept is not None:
            return int(kept)
    return 1 if names & set(tables) else None


def migrate(engine: Engine, create: Callable[[Engine], None], tables: Sequence[str], migrations: Sequence[Migration] = MIGRATIONS) -> int:
    """Brings the tables of a database to the last version — made with `create` if there are none — and says the version they are at."""
    numbers = [m.version for m in migrations]
    if numbers != list(range(2, 2 + len(numbers))):
        raise ValueError(f"The migrations of the catalog are not 2, 3, 4… in order: {numbers}")
    last = latest(migrations)
    found = version_of(engine, tables)
    if found is not None and found > last:
        raise StorageError(f"The catalog's database is of a later version of the app (its tables are at version {found}, this version knows up to "
                           f"{last}): open it with that version, or update this one.")
    _versions.create_all(engine)
    if found is None:
        create(engine)
        _write(engine, last)
        return last
    if version_of(engine, ()) is None:
        _write(engine, found)   # made before the versions were kept (version 1): say so, then migrate
    for migration in migrations:
        if migration.version > found:
            def step(connection: Connection, migration: Migration = migration) -> None:
                migration.change(connection)
                connection.execute(_schema_version.delete())
                connection.execute(_schema_version.insert().values(version=migration.version))
            _in_one_transaction(engine, step)
    return last


def _in_one_transaction(engine: Engine, work: Callable[[Connection], None]) -> None:
    """All of `work` or none of it — its changes to the tables too. SQLite's driver commits before a change to a table (ALTER TABLE…) unless it is
    told not to begin transactions by itself: then the one begun here holds the change, and a migration that fails half way leaves nothing."""
    if engine.dialect.name != "sqlite":
        with engine.begin() as connection:
            work(connection)
        return
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql("BEGIN")
        try:
            work(connection)
        except BaseException:
            connection.exec_driver_sql("ROLLBACK")
            raise
        connection.exec_driver_sql("COMMIT")


def _write(engine: Engine, version: int) -> None:
    with engine.begin() as connection:
        connection.execute(_schema_version.delete())
        connection.execute(_schema_version.insert().values(version=version))
