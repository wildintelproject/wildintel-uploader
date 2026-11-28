"""#248: the tables of the catalog in a database keep their version, and a database of a version before is brought to the last one."""
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, inspect, text
from sqlmodel import SQLModel

from wildintel_uploader.modules.catalog.infrastructure import sql_migrations
from wildintel_uploader.modules.catalog.infrastructure.sql_migrations import Migration, migrate, version_of
from wildintel_uploader.modules.catalog.infrastructure.sql_repository import _TABLES, SqlCatalogRepository
from wildintel_uploader.shared.errors import StorageError

NAMES = [t.name for t in _TABLES]


def _engine(tmp_path: Path) -> Engine:
    return create_engine(f"sqlite:///{tmp_path / 'catalog.sqlite3'}")


def _create(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine, tables=_TABLES)


def _columns(engine: Engine, table: str) -> set[str]:
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_a_new_database_is_made_at_the_last_version(tmp_path: Path):
    engine = _engine(tmp_path)
    SqlCatalogRepository(engine)
    assert version_of(engine, NAMES) == sql_migrations.latest() and set(NAMES) <= set(inspect(engine).get_table_names())


def test_a_database_made_before_the_versions_were_kept_is_version_1_and_keeps_what_it_has(tmp_path: Path):
    engine = _engine(tmp_path)
    _create(engine)   # as the app made it before: the tables, no version
    with engine.begin() as c:
        c.execute(text("INSERT INTO trappers (id, username, name, status, row, created_at, updated_at, extra) "
                       "VALUES ('t1', 'ana', 'Ana', 'active', 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '{}')"))
    repository = SqlCatalogRepository(engine)
    assert version_of(engine, NAMES) == 1
    assert [t.username for t in repository.read_trappers()] == ["ana"]


def test_the_migrations_a_database_lacks_are_made_in_order_each_once(tmp_path: Path):
    engine = _engine(tmp_path)
    _create(engine)
    made: list[int] = []

    def add_a_column(connection):
        made.append(2)
        connection.execute(text("ALTER TABLE cameras ADD COLUMN firmware VARCHAR"))
    migrations = (Migration(2, "cameras say their firmware", add_a_column), Migration(3, "nothing", lambda c: made.append(3)))

    assert migrate(engine, _create, NAMES, migrations) == 3
    assert migrate(engine, _create, NAMES, migrations) == 3   # opened again: nothing is made twice
    assert made == [2, 3] and "firmware" in _columns(engine, "cameras") and version_of(engine, NAMES) == 3


def test_a_migration_that_fails_leaves_the_database_at_the_version_before(tmp_path: Path):
    engine = _engine(tmp_path)
    _create(engine)

    def fails(connection):
        connection.execute(text("ALTER TABLE cameras ADD COLUMN firmware VARCHAR"))
        raise RuntimeError("half way")
    with pytest.raises(RuntimeError):
        migrate(engine, _create, NAMES, (Migration(2, "fails", fails),))
    assert version_of(engine, NAMES) == 1 and "firmware" not in _columns(engine, "cameras")


def test_a_database_of_a_later_version_of_the_app_is_refused_and_not_changed(tmp_path: Path):
    engine = _engine(tmp_path)
    migrate(engine, _create, NAMES, (Migration(2, "later", lambda c: None),))
    with pytest.raises(StorageError, match="later version of the app"):
        SqlCatalogRepository(engine)
    assert version_of(engine, NAMES) == 2


def test_the_migrations_are_numbered_in_order():
    with pytest.raises(ValueError):
        migrate(create_engine("sqlite://"), _create, NAMES, (Migration(3, "skips 2", lambda c: None),))


def test_a_database_of_version_1_migrated_to_the_last_has_the_tables_the_models_say(tmp_path: Path):
    """What keeps a new migration honest: from the first tables, the migrations make what the models are now."""
    old, new = _engine(tmp_path), create_engine(f"sqlite:///{tmp_path / 'new.sqlite3'}")
    _create(old)
    migrate(old, _create, NAMES)
    _create(new)
    assert {t: _columns(old, t) for t in NAMES} == {t: _columns(new, t) for t in NAMES}
