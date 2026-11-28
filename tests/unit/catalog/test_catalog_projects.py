"""#248: the research projects of the catalog (modules.catalog) — their rules, the use cases over a repository in memory, what a record says that
this version does not know, and the entry points, at /api/catalog and at the addresses of before."""
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from wildintel_uploader.modules.catalog.application.use_cases import CatalogUseCases
from wildintel_uploader.modules.catalog.domain.models import (
    CatalogError, ProjectArchived, ProjectExists, ProjectHasVisits, ProjectNotActive, ProjectNotEmpty, ResearchProject, UnknownProject,
)
from wildintel_uploader.modules.catalog.infrastructure.mapping import project_from_record, project_to_record


# ── the domain ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("values, field", [
    ({"acronym": "DO"}, "acronym"), ({"acronym": "TOO_LONG_ONE"}, "acronym"), ({"acronym": "-DONA"}, "acronym"),
    ({"name": ""}, "name"), ({"sampling_design": 7}, "sampling_design"), ({"bait_use": True}, "bait_use"),
    ({"event_interval": -1}, "event_interval"), ({"status": "paused"}, "status"), ({"abstract": "x" * 2001}, "abstract"),
])
def test_a_research_project_that_cannot_be_is_refused_naming_what(values, field):
    with pytest.raises(CatalogError) as refused:
        ResearchProject(**{"acronym": "DONA", "name": "Doñana", **values})
    assert refused.value.field == field


def test_what_a_record_says_that_this_version_does_not_know_is_kept():
    record = {"name": "Doñana", "acronym": "DONA", "marker": "from a sync", "status": "active", "id": "p1", "created_at": "T1"}
    assert project_from_record(record).extra == {"marker": "from a sync"}
    assert {k: v for k, v in project_to_record(project_from_record(record)).items() if k in record} == record


# ── the use cases, over a repository in memory ───────────────────────────────

class Folders:
    """The folders of the research projects, in memory: what each holds besides its records, and which were made."""

    def __init__(self) -> None:
        self.holding: dict[str, list[str]] = {}
        self.made: list[str] = []

    def make(self, acronym):
        self.made.append(acronym)

    def held(self, acronym, besides):
        return [name for name in self.holding.get(acronym, []) if name not in besides]


class Repository:
    def __init__(self) -> None:
        self.projects: dict[str, ResearchProject] = {}
        self.locations: dict[str, list] = {}

    def read_trappers(self):
        return []

    def write_trappers(self, trappers) -> None:
        pass

    def read_projects(self):
        return list(self.projects.values())

    def read_project(self, acronym):
        return self.projects.get(acronym)

    def add_project(self, project) -> None:
        self.projects[project.acronym] = project

    def save_project(self, project) -> None:
        self.projects[project.acronym] = project

    def files_of(self, acronym):
        return set()

    def read_locations(self, project):
        return list(self.locations.get(project, []))

    def write_locations(self, project, locations) -> None:
        self.locations[project] = list(locations)


class Visits:
    def __init__(self, of=()) -> None:
        self.of, self.at, self.refusal = set(of), {}, None

    def has_visits(self, acronym):
        return acronym in self.of

    def visits_at(self, project, location_id):
        return self.at.get(location_id, 0)

    def site_status_refusal(self, project, locations, location, wanted):
        return self.refusal


class Clock:
    def __init__(self) -> None:
        self.at = "T1"

    def now(self):
        return self.at

    def today(self):
        return "2026-11-27"


class NoLegacy:
    def take(self):
        return []


class History:
    def __init__(self) -> None:
        self.lines: list[tuple] = []

    def record_location(self, project, before, after) -> None:
        if before is None or before.status != after.status:
            self.lines.append((project, after.location_id, before.status if before else None, after.status))


@pytest.fixture
def world():
    repository, visits, clock = Repository(), Visits(), Clock()
    repository.folders = Folders()   # beside the records, as the collections folder has them
    ids = iter(f"id-{n}" for n in range(100))
    catalog = CatalogUseCases(repository, folders=repository.folders, legacy_trappers=NoLegacy(), visits=visits, status_history=History(), clock=clock,
                              new_id=lambda: next(ids))
    return catalog, repository, visits, clock


def test_a_research_project_is_added_once_and_one_removed_comes_back_as_it_was_created(world):
    catalog, repository, _, clock = world
    added = catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    assert (added.audit.id, added.audit.created_at) == ("id-0", "T1")
    with pytest.raises(ProjectExists) as taken:
        catalog.add_project(ResearchProject(acronym="DONA", name="Again"))
    assert taken.value.message == "The research project 'DONA' already exists."

    clock.at = "T2"
    catalog.delete_project("dona")                                   # whatever its case
    assert catalog.projects() == [] and repository.projects["DONA"].audit.deleted_at == "T2"
    clock.at = "T3"
    back = catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    assert (back.audit.id, back.audit.created_at, back.audit.updated_at, back.deleted) == ("id-0", "T1", "T3", False)


def test_a_research_project_changes_what_is_asked_and_never_its_acronym(world):
    catalog, _, visits, clock = world
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana", status="planned"))
    clock.at = "T2"
    changed = catalog.update_project("DONA", {"name": "Doñana NP", "acronym": "NOPE", "status": "active"})
    assert (changed.acronym, changed.name, changed.status, changed.audit.updated_at) == ("DONA", "Doñana NP", "active", "T2")

    visits.of.add("DONA")
    with pytest.raises(ProjectHasVisits):
        catalog.update_project("DONA", {"status": "planned"})
    catalog.update_project("DONA", {"status": "archived"})
    with pytest.raises(ProjectArchived) as archived:
        catalog.update_project("DONA", {"name": "Other"})
    assert archived.value.message == "The research project 'DONA' is archived: it can't be modified."
    with pytest.raises(ProjectArchived):
        catalog.delete_project("DONA")
    with pytest.raises(UnknownProject):
        catalog.update_project("NOPE", {"name": "x"})


def test_a_research_project_that_holds_collections_is_not_removed(world):
    catalog, repository, _, _ = world
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    repository.folders.holding["DONA"] = ["R0001", "R0002"]
    with pytest.raises(ProjectNotEmpty) as held:
        catalog.delete_project("DONA")
    assert "still holds R0001, R0002" in held.value.message


def test_new_visits_need_an_active_research_project(world):
    catalog, _, _, _ = world
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana", status="finished"))
    assert catalog.require_project("DONA").acronym == "DONA"
    with pytest.raises(ProjectNotActive) as finished:
        catalog.require_project("DONA", active=True)
    assert "is finished: new visits are only kept to an active one" in finished.value.message
    with pytest.raises(UnknownProject):
        catalog.require_project("NOPE")


# ── the entry points ─────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path: Path):
    from wildintel_uploader.web.main import app
    with patch("wildintel_uploader.entrypoints.config.collections_dir", return_value=tmp_path):
        yield TestClient(app)


def test_the_web_api_of_the_research_projects(client, tmp_path: Path):
    assert client.post("/api/catalog/projects", json={"name": "Doñana", "acronym": "DONA"}).status_code == 201
    assert (tmp_path / "DONA").is_dir()                                                     # its folder
    assert client.post("/api/catalog/projects", json={"name": "Again", "acronym": "DONA"}).status_code == 409
    assert client.get("/api/catalog/projects/dona").json()["name"] == "Doñana"
    assert client.patch("/api/catalog/projects/DONA", json={"status": "finished"}).json()["status"] == "finished"
    assert client.patch("/api/catalog/projects/DONA", json={"sampling_design": 9}).status_code == 422
    assert client.patch("/api/catalog/projects/NOPE", json={"name": "x"}).status_code == 404
    (tmp_path / "DONA" / "R0001").mkdir()
    assert client.delete("/api/catalog/projects/DONA").status_code == 409
    (tmp_path / "DONA" / "R0001").rmdir()
    assert client.delete("/api/catalog/projects/DONA").json() == {"deleted": "DONA"}
    assert client.get("/api/catalog/projects").json() == [] and len(client.get("/api/catalog/projects", params={"include_deleted": True}).json()) == 1


def test_the_addresses_of_before_answer_as_they_did(client):
    saved = client.post("/api/deployment-import/research-projects/save", json={"name": "Doñana", "acronym": "DONA"})
    assert saved.status_code == 200 and saved.json()["acronym"] == "DONA" and saved.json()["id"]
    again = client.post("/api/deployment-import/research-projects/save", json={"name": "Doñana", "acronym": "DONA"})
    assert again.status_code == 409 and "already exists" in again.json()["detail"]
    assert [p["acronym"] for p in client.post("/api/deployment-import/research-projects/list").json()["results"]] == ["DONA"]
    assert client.post("/api/deployment-import/research-projects/update", json={"acronym": "NOPE", "name": "x"}).status_code == 404
    assert client.post("/api/deployment-import/research-projects/update", json={"acronym": "DONA", "keywords": "lynx"}).json()["keywords"] == "lynx"
    assert client.post("/api/deployment-import/research-projects/delete", json={"research_project_id": "DONA"}).json() == {"deleted": "DONA"}
    assert client.post("/api/deployment-import/research-projects/delete", json={"research_project_id": "DONA"}).status_code == 404


def test_the_command_line_of_the_research_projects(tmp_path: Path):
    from wildintel_uploader.entrypoints.cli.app import app as cli
    from wildintel_uploader.entrypoints.cli import injection

    injection._container = None
    with patch("wildintel_uploader.entrypoints.config.collections_dir", return_value=tmp_path):
        run = CliRunner()
        assert run.invoke(cli, ["catalog", "projects", "add", "DONA", "Doñana", "--status", "planned"]).exit_code == 0
        taken = run.invoke(cli, ["catalog", "projects", "add", "DONA", "Again"])
        assert taken.exit_code == 1 and "already exists" in taken.output
        assert run.invoke(cli, ["catalog", "projects", "add", "DO", "Short"]).exit_code == 1
        assert run.invoke(cli, ["catalog", "projects", "set-status", "DONA", "active"]).exit_code == 0
        assert "Doñana" in run.invoke(cli, ["catalog", "projects", "show", "dona"], terminal_width=200).output
        listed = run.invoke(cli, ["catalog", "projects", "list"], terminal_width=200).output
        assert "DONA" in listed and "active" in listed and "1 research project" in listed
        assert run.invoke(cli, ["catalog", "projects", "delete", "DONA", "--yes"]).exit_code == 0
        assert "0 research projects" in run.invoke(cli, ["catalog", "projects", "list"]).output


def test_utc_is_the_same_for_the_catalog_and_for_the_visits():
    from wildintel_uploader.modules.visits.domain import wall_clock as visit_time
    from wildintel_uploader.modules.catalog.domain import models
    assert models._UTC_ZONES == visit_time._UTC_ZONES and models.DEFAULT_TIMEZONE == visit_time.DEFAULT_TIMEZONE
