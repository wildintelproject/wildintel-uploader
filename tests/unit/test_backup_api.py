"""/api/backup — the backups, over HTTP: what they say as NDJSON while they are made and restored."""
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from wildintel_uploader.core.services import local_folder_service


def _client() -> TestClient:
    from wildintel_uploader.web.main import app
    return TestClient(app)


def _events(response) -> list[dict]:
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def _project(root: Path) -> None:
    local_folder_service.write_research_project(root, {"name": "Doñana", "acronym": "DONA"})
    pdir = root / "DONA"
    (pdir / "visits.json").write_text(json.dumps([{"location_id": "DONA_01", "session": "R0001", "date": "2026-06-10", "time": "09:00:00", "when": "2026-06-10T09:00:00Z", "actions": ["Installation"]}]), encoding="utf-8")
    folder = pdir / "R0001" / "R0001-DONA_01"
    folder.mkdir(parents=True)
    (folder / "deployment.json").write_text("{}", encoding="utf-8")
    (folder / "IMG_0001.JPG").write_bytes(b"jpeg")


def test_a_backup_is_made_read_and_restored_over_http(tmp_path: Path):
    source, out, target = tmp_path / "source", tmp_path / "out", tmp_path / "target"
    for folder in (source, out, target):
        folder.mkdir()
    _project(source)

    with patch("wildintel_uploader.web.api.routers.backup.config.collections_dir", return_value=source):
        info = _client().post("/api/backup/project-info", json={"research_project_id": "DONA"}).json()
        made = _events(_client().post("/api/backup/create", json={"dest_dir": str(out), "research_project_id": "DONA", "project_files": True, "visits": True, "deployments": ["R0001-DONA_01"], "images": True}))
    assert info["visits"] == 1 and info["collections"][0]["deployments"][0]["images"] == 1
    assert made[0]["type"] == "step" and made[-1]["type"] == "done" and made[-1]["path"].endswith(".zip")
    assert any(e["type"] == "file" and e["name"].endswith("IMG_0001.JPG") for e in made)

    with patch("wildintel_uploader.web.api.routers.backup.config.collections_dir", return_value=target):
        read = _client().post("/api/backup/read", json={"path": made[-1]["path"]}).json()
        restored = _events(_client().post("/api/backup/restore", json={"path": made[-1]["path"], "project_files": True, "visits": True, "deployments": ["R0001-DONA_01"], "images": True}))
    assert read["manifest"]["scope"]["research_project"] == "DONA" and read["here"]["project"] is False
    assert restored[-1]["type"] == "done" and restored[-1]["summary"]["visits"]["added"] == 1
    assert (target / "DONA" / "R0001" / "R0001-DONA_01" / "IMG_0001.JPG").read_bytes() == b"jpeg"


def test_what_cannot_be_backed_up_or_restored_is_a_plain_400_before_anything_is_touched(tmp_path: Path):
    with patch("wildintel_uploader.web.api.routers.backup.config.collections_dir", return_value=tmp_path):
        nothing = _client().post("/api/backup/create", json={"dest_dir": str(tmp_path)})
        no_folder = _client().post("/api/backup/create", json={"dest_dir": str(tmp_path / "nowhere"), "settings": True})
        not_a_backup = _client().post("/api/backup/read", json={"path": str(tmp_path / "nothing.zip")})
        no_project = _client().post("/api/backup/project-info", json={"research_project_id": "DONA"})

    assert nothing.status_code == no_folder.status_code == not_a_backup.status_code == no_project.status_code == 400
    assert "Nothing was chosen" in nothing.json()["detail"]
