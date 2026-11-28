"""#248: the repositories of the catalog are one port with two adapters — the JSON files of the collections folder and a SQL database (SQLModel) —:
the same tests, on both, say they keep the same; and the whole catalog works the same on the database."""
from dataclasses import replace
from pathlib import Path

import pytest

from wildintel_uploader.modules.catalog.application.use_cases import CatalogUseCases
from wildintel_uploader.modules.catalog.domain.models import Audit, ProjectExists, ResearchProject, Trapper
from wildintel_uploader.modules.catalog.infrastructure.json_repository import StoreCatalogRepository
from wildintel_uploader.modules.catalog.infrastructure.sql_repository import SqlCatalogRepository, sqlite_engine
from wildintel_uploader.modules.catalog.infrastructure.project_folders import ResearchProjectFolders
from wildintel_uploader.shared import storage
from wildintel_uploader.shared.storage import StorageError


@pytest.fixture(params=["json", "sql"])
def repository(request, tmp_path: Path):
    collections = tmp_path / "collections"
    collections.mkdir()
    if request.param == "json":
        return StoreCatalogRepository(storage.open_store(collections))
    return SqlCatalogRepository(sqlite_engine(tmp_path / "db" / "catalog.sqlite3"))


def test_the_people_are_kept_as_they_were_written_in_their_order_with_their_dates_and_what_this_version_does_not_know(repository):
    people = [Trapper(username="luis", name="Luis", audit=Audit(id="l", created_at="T1", updated_at="T2")),
              Trapper(username="ana", name="Ana", affiliation="EBD", email="ana@example.org", status="inactive", trapper_pk=7,
                      audit=Audit(id="a", created_at="T1", updated_at="T1", deleted_at="T3"), extra={"badge": 12})]
    repository.write_trappers(people)
    assert repository.read_trappers() == people
    repository.write_trappers(people[:1])                                       # all of them at once: what was there is replaced
    assert repository.read_trappers() == people[:1]


def test_the_research_projects_are_kept_and_found_by_their_acronym(repository):
    dona = ResearchProject(acronym="DONA", name="Doñana", status="planned", keywords="lynx", trapper_pk=3, audit=Audit(id="p", created_at="T1"),
                           extra={"marker": "x"})
    repository.add_project(dona)
    repository.add_project(ResearchProject(acronym="ALBA", name="Albacete"))

    assert repository.read_project("DONA") == dona and repository.read_project("NOPE") is None
    assert [p.acronym for p in repository.read_projects()] == ["ALBA", "DONA"]
    with pytest.raises(StorageError):
        repository.add_project(dona)
    changed = ResearchProject(acronym="DONA", name="Doñana NP", audit=Audit(id="p", created_at="T1", updated_at="T2"))
    repository.save_project(changed)
    assert repository.read_project("DONA") == changed
    with pytest.raises(StorageError):
        repository.save_project(ResearchProject(acronym="NOPE", name="Nope"))


def test_what_a_research_project_holds_is_what_its_folder_has_besides_its_records(repository, tmp_path: Path):
    folders = ResearchProjectFolders(lambda: tmp_path / "collections")
    repository.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    folders.make("DONA")
    folder = tmp_path / "collections" / "DONA"
    (folder / "visits.json").write_text("[]", encoding="utf-8")                # a record, not held
    assert folders.held("DONA", repository.files_of("DONA")) == []
    (folder / "R0001").mkdir()
    assert folders.held("DONA", repository.files_of("DONA")) == ["R0001"]
    assert folders.held("NOPE", repository.files_of("NOPE")) == []


def test_the_locations_are_kept_for_each_research_project_in_their_order(repository):
    from wildintel_uploader.modules.catalog.domain.models import Location

    madrid = Location(location_id="DONA_02", timezone="Europe/Madrid", ignore_dst=True, latitude=37.1, longitude=-6.4, name="Two", status="active",
                      in_service="2026-01-01", audit=Audit(id="l2", created_at="T1"), extra={"habitat": "scrub"})
    bare = Location(location_id="DONA_01", audit=Audit(id="l1", deleted_at="T2"))     # one kept by a version that did not ask for where it is
    repository.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    repository.add_project(ResearchProject(acronym="ALBA", name="Albacete"))
    repository.write_locations("DONA", [madrid, bare])
    repository.write_locations("ALBA", [replace(bare, location_id="ALBA_01")])

    assert repository.read_locations("DONA") == [madrid, bare] and [loc.location_id for loc in repository.read_locations("ALBA")] == ["ALBA_01"]
    repository.write_locations("DONA", [madrid])
    assert repository.read_locations("DONA") == [madrid] and repository.read_locations("NOPE") == []


def test_a_checkpoint_puts_back_what_a_research_project_and_the_people_were(repository):
    """#248: what a save of many writes undoes when one fails — on files and on a database alike."""
    from wildintel_uploader.modules.catalog.domain.models import Location

    repository.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    ana = Trapper(username="ana", name="Ana", audit=Audit(id="a", created_at="T1"))
    one = Location(location_id="DONA_01", audit=Audit(id="l1", created_at="T1"))
    repository.write_trappers([ana])
    repository.write_locations("DONA", [one])
    put_back = repository.checkpoint("DONA")

    repository.write_trappers([ana, Trapper(username="luis", name="Luis", audit=Audit(id="l", created_at="T2"))])
    repository.write_locations("DONA", [one, Location(location_id="DONA_02", audit=Audit(id="l2", created_at="T2"))])
    repository.write_roles("DONA", [])
    put_back()

    assert repository.read_trappers() == [ana] and repository.read_locations("DONA") == [one] and repository.read_roles("DONA") == []


def test_the_whole_catalog_works_the_same_on_a_database(tmp_path: Path):
    class NoLegacy:
        def take(self):
            return []

    class NoVisits:
        def has_visits(self, acronym):
            return False

    class Clock:
        def now(self):
            return "2026-11-27T10:00:00Z"

        def today(self):
            return "2026-11-27"

    class NoHistory:
        def record_location(self, project, before, after):
            pass

    catalog = CatalogUseCases(SqlCatalogRepository(sqlite_engine(tmp_path / "catalog.sqlite3")), folders=ResearchProjectFolders(lambda: tmp_path),
                              legacy_trappers=NoLegacy(),
                              visits=NoVisits(), status_history=NoHistory(), clock=Clock())
    catalog.add_trappers([Trapper(username="ana", name="Ana")])
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    assert (tmp_path / "DONA").is_dir()   # its folder, where its collections will go — beside the database, not in it
    with pytest.raises(ProjectExists):
        catalog.add_project(ResearchProject(acronym="DONA", name="Again"))
    catalog.update_project("dona", {"status": "finished"})

    again = SqlCatalogRepository(sqlite_engine(tmp_path / "catalog.sqlite3"))      # what was kept is there for the next one
    assert [t.username for t in again.read_trappers()] == ["ana"] and again.read_project("DONA").status == "finished"
