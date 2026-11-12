"""The photos of a created deployment, to look at them: the list and each one as a JPEG."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from wildintel_uploader.web.main import app


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / "DONA" / "R0003" / "R0003-DONA_01"
    folder.mkdir(parents=True)
    for n, when in (("b.JPEG", "2026-10-25T00:09:00"), ("a.JPEG", "2026-10-25T00:08:00")):
        Image.new("RGB", (640, 480), "green").save(folder / n)
    (folder / "images.json").write_text(json.dumps({"images": [{"name": "b.JPEG", "local_time": "2026-10-25T00:09:00"}, {"name": "a.JPEG", "local_time": "2026-10-25T00:08:00"}]}))
    (folder / "deployment.json").write_text("{}")
    return tmp_path


Q = {"research_project_id": "DONA", "collection": "R0003", "deployment_id": "R0003-DONA_01"}


def _get(root: Path, path: str, **extra):
    with patch("wildintel_uploader.core.config.collections_dir", return_value=root):
        return TestClient(app).get(f"/api/deployment-import/{path}", params={**Q, **extra})


def test_the_photos_are_listed_in_the_order_they_were_taken(root):
    response = _get(root, "photos")
    assert response.status_code == 200
    assert [p["name"] for p in response.json()["photos"]] == ["a.JPEG", "b.JPEG"]
    assert response.json()["photos"][0]["taken"] == "2026-10-25T00:08:00"


def test_a_photo_is_served_as_a_jpeg_that_fits(root):
    response = _get(root, "photo", name="a.JPEG")
    assert response.status_code == 200 and response.headers["content-type"] == "image/jpeg"
    assert max(Image.open(__import__("io").BytesIO(response.content)).size) <= 320


def test_nothing_outside_the_folder_or_that_is_not_a_photo_is_served(root):
    assert _get(root, "photo", name="../../DONA/other.JPEG").status_code == 404
    assert _get(root, "photo", name="deployment.json").status_code == 404
    assert _get(root, "photos", deployment_id="..").status_code == 404
