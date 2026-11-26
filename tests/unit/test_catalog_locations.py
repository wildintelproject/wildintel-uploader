"""#248: the locations of the catalog (modules.catalog) — their rules, the use cases over a repository in memory, and the entry points, at
/api/catalog and at the addresses of before."""
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from wildintel_uploader.modules.catalog.domain.models import (
    CatalogError, Location, LocationArchived, LocationExists, LocationFromTrapper, LocationHasVisits, LocationTimeFixed, NewLocationStatus,
    ProjectArchived, ResearchProject, SiteStatusRefused, UnknownLocation, UnknownProject,
)


def _madrid(location_id="DONA_01", **values) -> Location:
    return Location(**{"location_id": location_id, "timezone": "Europe/Madrid", "ignore_dst": True, "latitude": 37.0, "longitude": -6.4, **values})


@pytest.mark.parametrize("values, field", [
    ({"location_id": ""}, "location_id"), ({"timezone": "Mars/Olympus"}, "timezone"), ({"latitude": 91}, "latitude"),
    ({"longitude": -181}, "longitude"), ({"coordinate_uncertainty": 0}, "coordinate_uncertainty"), ({"in_service": "1/1/2026"}, "in_service"),
    ({"status": "retired"}, "status"),
])
def test_a_location_that_cannot_be_is_refused_naming_what(values, field):
    with pytest.raises(CatalogError) as refused:
        _madrid(**values)
    assert refused.value.field == field


def test_a_location_kept_by_a_version_that_did_not_ask_where_it_is_is_read_all_the_same():
    from wildintel_uploader.modules.catalog.infrastructure.mapping import location_from_record
    old = location_from_record({"location_id": "DONA_09", "status": "retired"}, "DONA")
    assert (old.timezone, old.latitude, old.status) == (None, None, "archived") and old.audit.id   # retired is archived; it gets the same id always
    assert location_from_record({"location_id": "DONA_09"}, "DONA").audit.id == old.audit.id


def test_a_location_is_added_once_put_into_production_today_and_one_removed_comes_back(world):
    catalog, repository, _, clock = world
    with pytest.raises(UnknownProject):
        catalog.add_location("DONA", _madrid())
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    added = catalog.add_location("DONA", _madrid())
    assert (added.in_service, added.status, added.audit.created_at) == ("2026-11-27", "pending", "T1")
    with pytest.raises(LocationExists) as taken:
        catalog.add_location("DONA", _madrid("dona_01"))                                           # whatever its case
    assert taken.value.message == "The location 'dona_01' already exists in DONA."
    with pytest.raises(NewLocationStatus):
        catalog.add_location("DONA", _madrid("DONA_02", status="active"), by_hand=True)            # a visit makes it active

    clock.at = "T2"
    catalog.delete_location("DONA", "DONA_01")
    assert catalog.locations("DONA") == [] and catalog.locations("DONA", include_deleted=True)[0].audit.deleted_at == "T2"
    back = catalog.add_location("DONA", _madrid(name="Back"))
    assert (back.audit.id, back.audit.created_at, back.name, len(repository.locations["DONA"])) == (added.audit.id, "T1", "Back", 1)


def test_a_location_changes_what_is_asked_but_never_its_time_nor_what_the_visits_say(world):
    catalog, _, visits, _ = world
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    catalog.add_location("DONA", _madrid())

    assert catalog.update_location("DONA", "dona_01", {"name": "One", "timezone": "Europe/Madrid", "ignore_dst": True}).name == "One"
    with pytest.raises(LocationTimeFixed) as fixed:
        catalog.update_location("DONA", "DONA_01", {"timezone": "Atlantic/Canary"})
    assert fixed.value.message == "The timezone of a location can't be changed once it is created: DONA_01 is Europe/Madrid."
    with pytest.raises(LocationTimeFixed):
        catalog.update_location("DONA", "DONA_01", {"ignore_dst": False})

    visits.refusal = "DONA_01 is active when it has a camera: …"
    with pytest.raises(SiteStatusRefused) as refused:
        catalog.update_location("DONA", "DONA_01", {"status": "active"})
    assert refused.value.message == visits.refusal
    assert catalog.update_location("DONA", "DONA_01", {"status": "active"}, by_visit=True).status == "active"   # a visit moves it as it moves
    visits.refusal = None
    catalog.update_location("DONA", "DONA_01", {"status": "archived"})
    with pytest.raises(LocationArchived):
        catalog.update_location("DONA", "DONA_01", {"status": "active"}, by_visit=True)
    with pytest.raises(UnknownLocation):
        catalog.update_location("DONA", "NOPE", {"name": "x"})


def test_each_change_of_status_is_written_down(world):
    catalog, _, _, _ = world
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    catalog.add_location("DONA", _madrid())
    catalog.update_location("DONA", "DONA_01", {"name": "Same status"})
    catalog.update_location("DONA", "DONA_01", {"status": "ready"}, by_visit=True)
    assert catalog.status_history.lines == [("DONA", "DONA_01", None, "pending"), ("DONA", "DONA_01", "pending", "ready")]


def test_a_location_with_visits_or_from_trapper_is_not_removed_and_an_archived_project_changes_nothing(world):
    catalog, _, visits, _ = world
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    catalog.add_location("DONA", _madrid())
    catalog.add_location("DONA", _madrid("DONA_02", trapper_pk=5))
    visits.at["DONA_01"] = 2
    with pytest.raises(LocationHasVisits) as visited:
        catalog.delete_location("DONA", "DONA_01")
    assert "still has 2 visits: it can't be deleted — mark it as archived instead" in visited.value.message
    with pytest.raises(LocationFromTrapper):
        catalog.delete_location("DONA", "DONA_02")
    catalog.update_project("DONA", {"status": "archived"})
    with pytest.raises(ProjectArchived):
        catalog.update_location("DONA", "DONA_01", {"name": "x"})


def test_the_time_of_a_location_is_what_it_keeps(world):
    catalog, _, _, _ = world
    catalog.add_project(ResearchProject(acronym="DONA", name="Doñana"))
    catalog.add_location("DONA", _madrid())
    assert catalog.location_time("DONA", "dona_01") == {"timezone": "Europe/Madrid", "ignore_dst": True}
    assert catalog.location_time("DONA", "NOPE") == {} and catalog.location_time("DONA", None) == {}


# ── the entry points ─────────────────────────────────────────────────────────

LOCATION = {"location_id": "DONA_01", "timezone": "Europe/Madrid", "ignore_dst": False, "latitude": 37.0, "longitude": -6.4}


@pytest.fixture
def client(tmp_path: Path):
    from wildintel_uploader.web.main import app
    with patch("wildintel_uploader.core.config.collections_dir", return_value=tmp_path):
        client = TestClient(app)
        client.post("/api/catalog/projects", json={"name": "Doñana", "acronym": "DONA"})
        yield client


def test_the_web_api_of_the_locations(client):
    added = client.post("/api/catalog/projects/DONA/locations", json=LOCATION)
    assert added.status_code == 201 and added.json()["status"] == "pending"
    assert client.post("/api/catalog/projects/DONA/locations", json=LOCATION).status_code == 409
    assert client.post("/api/catalog/projects/NOPE/locations", json=LOCATION).status_code == 404
    assert [loc["location_id"] for loc in client.get("/api/catalog/projects/DONA/locations").json()] == ["DONA_01"]
    assert client.patch("/api/catalog/projects/DONA/locations/dona_01", json={"name": "One"}).json()["name"] == "One"
    assert client.patch("/api/catalog/projects/DONA/locations/DONA_01", json={"timezone": "UTC"}).status_code == 409
    assert client.patch("/api/catalog/projects/DONA/locations/NOPE", json={"name": "x"}).status_code == 404
    assert client.delete("/api/catalog/projects/DONA/locations/DONA_01").json() == {"deleted": "DONA_01"}


def test_the_addresses_of_before_answer_as_they_did(client):
    saved = client.post("/api/deployment-import/locations/save", json={"research_project_id": "DONA", "location": LOCATION})
    assert saved.status_code == 200 and saved.json()["id"]
    again = client.post("/api/deployment-import/locations/save", json={"research_project_id": "DONA", "location": LOCATION})
    assert again.status_code == 409 and "already exists" in again.json()["detail"]
    assert client.post("/api/deployment-import/locations/list", json={"research_project_id": "DONA"}).json()["results"][0]["location_id"] == "DONA_01"
    fixed = client.post("/api/deployment-import/locations/update", json={"research_project_id": "DONA", "location_id": "DONA_01", "timezone": "UTC"})
    assert fixed.status_code == 409
    assert client.post("/api/deployment-import/locations/update", json={"research_project_id": "DONA", "location_id": "NOPE"}).status_code == 404
    assert client.post("/api/deployment-import/locations/delete", json={"research_project_id": "DONA", "location_id": "dona_01"}).json() == {"deleted": "DONA_01"}


def test_the_command_line_of_the_locations(tmp_path: Path):
    from wildintel_uploader.cli.app import app as cli
    from wildintel_uploader.entrypoints.cli import injection

    injection._container = None
    with patch("wildintel_uploader.core.config.collections_dir", return_value=tmp_path):
        run = CliRunner()
        assert run.invoke(cli, ["catalog", "projects", "add", "DONA", "Doñana"]).exit_code == 0
        added = run.invoke(cli, ["catalog", "locations", "add", "DONA", "DONA_01", "--latitude", "37", "--longitude", "-6.4", "--timezone", "Europe/Madrid", "--name", "One"])
        assert added.exit_code == 0
        assert run.invoke(cli, ["catalog", "locations", "add", "DONA", "DONA_01", "--latitude", "37", "--longitude", "-6.4"]).exit_code == 1
        assert run.invoke(cli, ["catalog", "locations", "add", "DONA", "X", "--latitude", "99", "--longitude", "0"]).exit_code == 1
        listed = run.invoke(cli, ["catalog", "locations", "list", "DONA"], terminal_width=200).output
        assert "DONA_01" in listed and "Europe/Madrid" in listed and "pending" in listed and "1 location of DONA" in listed
        assert run.invoke(cli, ["catalog", "locations", "set-status", "DONA", "DONA_01", "planned"]).exit_code == 0
        refused = run.invoke(cli, ["catalog", "locations", "set-status", "DONA", "DONA_01", "active"])
        assert refused.exit_code == 1 and "active when it has a camera" in refused.output
        assert run.invoke(cli, ["catalog", "locations", "delete", "DONA", "DONA_01", "--yes"]).exit_code == 0
