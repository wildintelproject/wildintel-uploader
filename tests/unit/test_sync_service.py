"""Syncing the collections folder with Trapper — Trapper is faked (no network)."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from wildintel_uploader.core.services import local_folder_service, sync_service

CREDS = ("https://trapper.example.org", "alice", "s3cret")
PROJECT = {"pk": 2, "name": "Doñana", "acronym": "DONA"}
LOCATIONS = [
    {"pk": 5, "location_id": "DONA_01", "name": "Site 1", "timezone": "Europe/Madrid", "ignore_dst": True, "latitude": 37.0, "longitude": -6.5},
    {"pk": 6, "location_id": "DONA_02", "name": "Site 2", "timezone": "Europe/Madrid", "ignore_dst": False, "latitude": 37.1, "longitude": -6.4},
]


def _deployment(deployment_id: str, location_id: str, start: str, end: str) -> dict:
    return {
        "pk": 1, "deployment_id": deployment_id, "location_id": location_id, "latitude": 37.0, "longitude": -6.5,
        "start_date": start, "end_date": end,
    }


DEPLOYMENTS = [
    _deployment("R0003-DONA_01", "DONA_01", "2024-07-01T08:00:00+00:00", "2024-07-31T10:00:00+00:00"),  # summer, ignoring DST: UTC+1
    _deployment("R0003-DONA_02", "DONA_02", "2024-07-01T08:00:00+00:00", "2024-07-31T10:00:00+00:00"),  # summer, using DST: UTC+2
    _deployment("R0009-DONA_01", "DONA_01", "2024-07-01T08:00:00+00:00", "2024-07-31T10:00:00+00:00"),  # no such collection in the project
]


RESOURCES = [
    {"pk": 91, "name": "R0003-DONA_01__20240702_2.JPEG", "date_recorded": "2024-07-02T09:30:00+00:00", "mime": "image/jpeg", "date_recorded_correct": True,
     "observation_type": ["animal"], "species": ["Lynx pardinus"], "tags": []},
    {"pk": 90, "name": "R0003-DONA_01__20240701_1.JPEG", "date_recorded": "2024-07-01T08:00:00+00:00", "mime": "image/jpeg", "date_recorded_correct": True,
     "observation_type": [], "species": [], "tags": ["night"]},
]


def _run(root: Path, names=("R0003", "Other")):
    with patch("wildintel_uploader.core.services.sync_service.trapper_service.list_deployment_resources", return_value=RESOURCES), \
         patch("wildintel_uploader.core.services.sync_service.trapper_service.list_locations", return_value=LOCATIONS), \
         patch("wildintel_uploader.core.services.sync_service.trapper_service.list_deployments", return_value=DEPLOYMENTS), \
         patch("wildintel_uploader.core.services.sync_service.collection_names", return_value=[n for n in names if n.startswith("R")]):
        return sync_service.sync(CREDS, root, PROJECT, 10)


def test_wall_clock_follows_the_location_and_its_summer_time_setting():
    assert sync_service.wall_clock("2024-07-01T08:00:00+00:00", "Europe/Madrid", False).hour == 10
    assert sync_service.wall_clock("2024-07-01T08:00:00+00:00", "Europe/Madrid", True).hour == 9
    assert sync_service.wall_clock("2024-12-01T08:00:00Z", "Europe/Madrid", False).hour == 9
    assert sync_service.wall_clock("2024-07-01T08:00:00+00:00", None, False).hour == 8


def test_creates_the_expected_structure(tmp_path: Path):
    result = _run(tmp_path)

    folder = tmp_path / "DONA"
    assert json.loads((folder / "research_project.json").read_text(encoding="utf-8"))["trapper_pk"] == 2
    assert [l["location_id"] for l in json.loads((folder / "locations.json").read_text(encoding="utf-8"))] == ["DONA_01", "DONA_02"]
    assert json.loads((folder / "R0003" / "collection.json").read_text(encoding="utf-8"))["name"] == "R0003"
    assert (folder / "R0003" / "R0003-DONA_01" / "deployment.json").is_file()
    assert (folder / "R0003" / "R0003-DONA_02" / "deployment.json").is_file()
    assert not (folder / "Other").exists()  # only the collections starting with R
    log = (folder / "R0003" / "R0003_FileTimestampLog.csv").read_text(encoding="utf-8-sig")
    assert "R0003-DONA_01,2024:07:01,09:00:00,2024:07:31,11:00:00" in log
    assert "R0003-DONA_02,2024:07:01,10:00:00,2024:07:31,12:00:00" in log
    info = json.loads((folder / "R0003" / "R0003-DONA_01" / "images.json").read_text(encoding="utf-8"))
    assert (info["source"], info["image_count"], info["first"], info["last"]) == ("trapper", 2, "2024-07-01T09:00:00", "2024-07-02T10:30:00")  # DONA_01 ignores DST
    first = info["images"][0]
    assert first["name"] == "R0003-DONA_01__20240701_1.JPEG" and first["trapper_pk"] == 90 and first["timestamp"] == 1719820800.0 and first["tags"] == ["night"]
    assert info["images"][1]["species"] == ["Lynx pardinus"]
    assert result["unassigned"] == ["R0009-DONA_01"]
    assert result["created"]["deployments"] == ["R0003-DONA_01", "R0003-DONA_02"]


def test_leaves_what_is_already_there_as_it_is(tmp_path: Path):
    _run(tmp_path)
    deployment = tmp_path / "DONA" / "R0003" / "R0003-DONA_01" / "deployment.json"
    deployment.write_text('{"edited": true}', encoding="utf-8")

    again = _run(tmp_path)

    assert deployment.read_text(encoding="utf-8") == '{"edited": true}'
    assert again["created"] == {key: [] for key in again["created"]}
    assert again["kept"]["images"] == ["R0003-DONA_01", "R0003-DONA_02"]
    assert again["kept"]["deployments"] == ["R0003-DONA_01", "R0003-DONA_02"] and again["kept"]["locations"] == ["DONA_01", "DONA_02"]


def test_the_endpoint_syncs_the_collections_folder(tmp_path: Path):
    from wildintel_uploader.web.main import app
    payload = {**dict(zip(("url", "username", "password"), CREDS)), "research_project_pk": 2, "research_project_name": "Doñana", "research_project_acronym": "DONA", "classification_project_pk": 10}

    with patch("wildintel_uploader.web.api.routers.sync.config.collections_dir", return_value=tmp_path), \
         patch("wildintel_uploader.core.services.sync_service.trapper_service.list_deployment_resources", return_value=RESOURCES), \
         patch("wildintel_uploader.core.services.sync_service.trapper_service.list_locations", return_value=LOCATIONS), \
         patch("wildintel_uploader.core.services.sync_service.trapper_service.list_deployments", return_value=DEPLOYMENTS), \
         patch("wildintel_uploader.core.services.sync_service.collection_names", return_value=["R0003"]):
        response = TestClient(app).post("/api/sync/collections", json=payload)

    assert response.status_code == 200 and response.json()["research_project_id"] == "DONA"
    assert (tmp_path / "DONA" / "R0003" / "R0003-DONA_01" / "deployment.json").is_file()


def test_collection_names_keeps_those_starting_with_r_of_the_classification_project():
    client = MagicMock()
    client.classification_projects.where_project_collections.return_value = [SimpleNamespace(name=n) for n in ("R0002", "Pilot", "r0001", "R0002")]
    with patch("wildintel_uploader.core.services.sync_service.trapper_service.client", return_value=client):
        assert sync_service.collection_names(CREDS, 10) == ["r0001", "R0002"]
