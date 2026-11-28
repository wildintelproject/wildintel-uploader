"""The seal of a deployment: what was checked, tied to the images' content."""
from __future__ import annotations

import json
from pathlib import Path

from tests.unit.preprocessing.test_preprocessing import DEPLOYMENT, _run, _source
from tests.support import built


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
    assert built.sealing().verify(folder)["status"] == "valid"

    image = sorted(folder.glob("*.JPEG"))[0]
    image.write_bytes(image.read_bytes() + b"x")
    broken = built.sealing().verify(folder)

    assert broken["status"] == "broken" and broken["changed"] == [image.name]


def test_a_changed_deployment_file_an_added_image_or_an_edited_seal_break_it(tmp_path: Path):
    folder = _imported(tmp_path)
    (folder / "deployment.json").write_text("{}", encoding="utf-8")
    assert built.sealing().verify(folder)["deployment_changed"] is True

    folder = _imported(tmp_path / "again")
    (folder / "extra.jpg").write_bytes((sorted(folder.glob("*.JPEG"))[0]).read_bytes())
    assert built.sealing().verify(folder)["added"] == ["extra.jpg"]

    folder = _imported(tmp_path / "third")
    body = json.loads((folder / "seal.json").read_text(encoding="utf-8"))
    body["images"][0]["validations"]["corrupted"] = "tampered"
    (folder / "seal.json").write_text(json.dumps(body), encoding="utf-8")
    assert built.sealing().verify(folder)["seal_changed"] is True


def test_a_deployment_never_sealed_says_so(tmp_path: Path):
    assert built.sealing().verify(tmp_path)["status"] == "none"


# ── what a seal says, plain Python ───────────────────────────────────────────

def test_a_seal_says_each_image_with_the_checks_of_its_original_and_knows_what_changed():
    from wildintel_uploader.modules.deployments.domain import seal as rules

    checks = rules.checked(["a.jpg", "b.jpg"], {"corrupted": [{"path": "b.jpg", "error": "broken"}]}, {}, frozenset({"corrupted"}), frozenset(), frozenset())
    body = rules.body("R0001-DONA_01", "T", "m", checks, [("A.JPEG", "h1"), ("B.JPEG", "h2")], originals={"A.JPEG": "a.jpg", "B.JPEG": "b.jpg"},
                      source_hashes=None, preprocessing=None, recovered=False)
    assert [(e["name"], e["validations"]) for e in body["images"]] == [("A.JPEG", {"corrupted": "ok"}), ("B.JPEG", {"corrupted": "broken"})]
    images, metadata, changed = rules.recorded(body)
    assert (metadata, changed) == ("m", False) and rules.recorded({**body, "deployment_id": "X"})[2] is True
    verdict = rules.verdict(images, {"A.JPEG": "h1", "B.JPEG": "other"}, ["A.JPEG", "B.JPEG", "C.JPEG"], False, False)
    assert (verdict["status"], verdict["changed"], verdict["added"]) == ("broken", ["B.JPEG"], ["C.JPEG"])
