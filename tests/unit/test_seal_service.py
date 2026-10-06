"""The seal of a deployment: what was checked, tied to the images' content."""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit.test_preprocessing_service import DEPLOYMENT, NO_XMP, _run, _source
from wildintel_uploader.core.services import seal_service
from wildintel_uploader.core.services import preprocessing_service as pre


def _imported(tmp_path: Path, count: int = 2) -> Path:
    _run(_source(tmp_path, count), tmp_path / "out")
    return tmp_path / "out" / DEPLOYMENT.deployment_id


def test_an_import_leaves_a_seal_with_what_each_image_passed(tmp_path: Path):
    folder = _imported(tmp_path)

    body = json.loads((folder / "seal.json").read_text(encoding="utf-8"))

    assert body["deployment_id"] == DEPLOYMENT.deployment_id and len(body["images"]) == 2
    image = body["images"][0]
    assert image["name"].endswith(".JPEG") and image["original"].endswith(".JPG") and len(image["sha256"]) == 64 and len(image["source_sha1"]) == 40
    assert image["validations"]["corrupted"] == "ok" and "time_range" in image["postvalidations"]
    assert body["deployment"]["preprocessing"]["rename"] is True and "corrupted" in body["deployment"]["validated"]


def test_a_sealed_deployment_verifies_until_something_changes(tmp_path: Path):
    folder = _imported(tmp_path)
    assert seal_service.verify(folder)["status"] == "valid"

    image = sorted(folder.glob("*.JPEG"))[0]
    image.write_bytes(image.read_bytes() + b"x")
    broken = seal_service.verify(folder)

    assert broken["status"] == "broken" and broken["changed"] == [image.name]


def test_a_changed_deployment_file_an_added_image_or_an_edited_seal_break_it(tmp_path: Path):
    folder = _imported(tmp_path)
    (folder / "deployment.json").write_text("{}", encoding="utf-8")
    assert seal_service.verify(folder)["deployment_changed"] is True

    folder = _imported(tmp_path / "again")
    (folder / "extra.jpg").write_bytes((sorted(folder.glob("*.JPEG"))[0]).read_bytes())
    assert seal_service.verify(folder)["added"] == ["extra.jpg"]

    folder = _imported(tmp_path / "third")
    body = json.loads((folder / "seal.json").read_text(encoding="utf-8"))
    body["images"][0]["validations"]["corrupted"] = "tampered"
    (folder / "seal.json").write_text(json.dumps(body), encoding="utf-8")
    assert seal_service.verify(folder)["seal_changed"] is True


def test_a_deployment_never_sealed_says_so(tmp_path: Path):
    assert seal_service.verify(tmp_path)["status"] == "none"
