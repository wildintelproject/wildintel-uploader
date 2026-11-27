"""/api/repair — looking at the deployments kept in the collections folder, and repairing them."""
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from tests.unit.deployments.test_repair import DEPLOYMENT_ID, kept  # noqa: F401 — the fixture the repair's own tests use
from wildintel_uploader.modules.deployments.infrastructure import collections as layout
from wildintel_uploader.modules.catalog.infrastructure import records as catalog_files
from wildintel_uploader.modules.preprocessing.domain.models import PREPROCESSING_LOG_FILE
from wildintel_uploader.web.main import app

PAYLOAD = {"research_project_id": "DONA", "collection": "R0003", "deployment_id": DEPLOYMENT_ID}


def _client() -> TestClient:
    return TestClient(app)


def _in(root: Path):
    return patch("wildintel_uploader.entrypoints.config.collections_dir", return_value=root)


def _events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines()]


def test_the_collections_and_their_deployment_folders_are_listed(kept):
    root, _ = kept
    with _in(root):
        response = _client().post("/api/repair/collections", json={"research_project_id": "DONA"})

    assert response.status_code == 200
    [collection] = response.json()["results"]
    assert collection["name"] == "R0003" and [d["deployment_id"] for d in collection["deployments"]] == [DEPLOYMENT_ID]


def test_inspecting_says_whether_the_deployment_is_valid(kept):
    root, dest = kept
    with _in(root):
        valid = _client().post("/api/repair/inspect", json=PAYLOAD).json()
        (dest / layout.IMAGES_FILE).unlink()
        (dest / "seal.json").unlink()
        unsealed = _client().post("/api/repair/inspect", json=PAYLOAD).json()
        missing = _client().post("/api/repair/inspect", json={**PAYLOAD, "deployment_id": "R0003-OTHER_01"})

    assert valid["status"] == "valid"
    assert unsealed["status"] == "unsealed" and unsealed["files"][layout.IMAGES_FILE] == "missing"
    assert missing.status_code == 404


def test_repairing_streams_the_steps_and_ends_with_the_deployment_valid(kept):
    root, dest = kept
    (dest / layout.DEPLOYMENT_METADATA_FILE).unlink()
    (dest / PREPROCESSING_LOG_FILE).unlink()
    with _in(root):
        response = _client().post("/api/repair/deployment", json=PAYLOAD)
        after = _client().post("/api/repair/inspect", json=PAYLOAD).json()

    assert response.status_code == 200
    events = _events(response)
    assert events[0]["type"] == "step" and events[-1]["type"] == "done" and events[-1]["status"] == "valid"
    assert after["status"] == "valid"


def test_a_repair_that_cannot_go_on_says_why_in_the_stream_and_a_deployment_that_is_not_there_is_a_400(kept):
    root, dest = kept
    (dest.parent.parent / catalog_files.LOCATIONS_FILE).write_text("[]", encoding="utf-8")
    (dest / layout.DEPLOYMENT_METADATA_FILE).unlink()
    with _in(root):
        failing = _client().post("/api/repair/deployment", json=PAYLOAD)
        absent = _client().post("/api/repair/deployment", json={**PAYLOAD, "deployment_id": "R0003-OTHER_01"})

    assert _events(failing)[-1]["type"] == "error" and "can't be rebuilt" in _events(failing)[-1]["detail"]
    assert absent.status_code == 400 and "isn't in the collection" in absent.json()["detail"]


def test_names_that_are_not_a_collection_or_a_deployment_are_a_422():
    for bad in ({"collection": "Doñana"}, {"deployment_id": "DONA-01"}):
        assert _client().post("/api/repair/inspect", json={**PAYLOAD, **bad}).status_code == 422
