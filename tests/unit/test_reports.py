"""The reports of the validations, postvalidations and preprocessings — built, kept, listed, downloaded."""
import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from wildintel_uploader.core import config
from wildintel_uploader.core.schemas.requests import DeploymentFields
from wildintel_uploader.core.services import deployment_import_service as dis
from wildintel_uploader.core.services import report_service as rs


def _jpeg(path: Path, taken: str | None) -> None:
    img = Image.new("RGB", (8, 8), color=(len(path.name) * 7 % 255, 20, 30))
    exif = img.getexif()
    if taken:
        exif[306] = taken
    img.save(path, exif=exif)


@pytest.fixture
def source(tmp_path: Path) -> Path:
    folder = tmp_path / "R0003-DONA_01"
    folder.mkdir()
    _jpeg(folder / "IMG_0001.JPG", "2024:09:04 10:00:00")
    _jpeg(folder / "IMG_0002.JPG", "2024:09:04 09:00:00")  # earlier than the one before it: out of order
    _jpeg(folder / "IMG_0003.JPG", None)  # no date
    (folder / "IMG_0004.JPG").write_bytes(b"not an image")  # corrupted
    return folder


@pytest.fixture
def reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "reports"
    monkeypatch.setattr(config, "reports_dir", lambda settings=None: root)
    return root


def _entry(report: dict, identifier: str, check: str) -> dict:
    return next(e for e in report["entries"] if e["identifier"] == identifier and e["check"] == check)


def test_a_validation_report_says_which_image_failed_which_check(source: Path):
    found = dis.validate_images(source, None, detail=True)

    report = rs.validation_report(found, source)

    assert report["kind"] == "validation" and report["checked"] == 4
    assert _entry(report, "IMG_0004.JPG", "corrupted")["status"] == "failed"
    assert _entry(report, "IMG_0001.JPG", "corrupted")["status"] == "ok"  # what passed is written down too
    assert "dated before IMG_0001.JPG" in _entry(report, "IMG_0002.JPG", "sequence")["message"]
    assert _entry(report, "IMG_0003.JPG", "exif")["message"] == "no date, no camera model, no camera id" or "no date" in _entry(report, "IMG_0003.JPG", "exif")["message"]
    assert report["checks"]["corrupted"] == {"label": "Corrupted images", "scope": "images", "ok": 3, "failed": 1}
    assert report["checks"]["structure"]["scope"] == "deployment"
    assert report["totals"]["failed"] == sum(c["failed"] for c in report["checks"].values())


def test_only_the_checks_that_ran_are_in_the_report(source: Path):
    found = dis.validate_images(source, frozenset({"corrupted"}), detail=True)

    report = rs.validation_report(found, source, ["corrupted"])

    assert list(report["checks"]) == ["corrupted"]
    assert report["parameters"] == {"checks": ["corrupted"]}


def test_a_postvalidation_report_has_the_deployment_checks_and_the_images_out_of_range(source: Path):
    deployment = DeploymentFields(deployment_id="R0003-DONA_01", location_id="DONA_01", latitude=37, longitude=-6,
                                  start_date="2024-09-04T10:00:00+02:00", end_date="2024-09-05T10:00:00+02:00", camera_model="X")
    result = dis.validate_deployment_consistency(source, deployment, None, collection_name="R0003", expected_location_id="DONA_01")

    report = rs.postvalidation_report(result, "R0003-DONA_01", source)

    assert report["kind"] == "postvalidation" and report["deployment_id"] == "R0003-DONA_01"
    assert _entry(report, rs.DEPLOYMENT, "deployment_id")["status"] == "ok"
    assert report["checks"]["time_range"]["scope"] == "images"
    assert report["checks"]["time_range"]["ok"] + report["checks"]["time_range"]["failed"] == 4


def test_a_preprocessing_report_lists_what_was_done_and_what_was_skipped(source: Path, tmp_path: Path):
    records = [{"original": "IMG_0001.JPG", "name": "R0003-DONA_01__20240904_1.JPEG", "date": "2024-09-04T08:00:00+00:00", "date_source": "exif", "resized": True}]
    skipped = [{"name": "IMG_0004.JPG", "detail": "cannot identify image file"}]

    report = rs.preprocessing_report(records, skipped, "R0003-DONA_01", source, tmp_path / "out", {"resize": True})

    done = _entry(report, "IMG_0001.JPG", "preprocessing")
    assert done["status"] == "ok" and "→ R0003-DONA_01__20240904_1.JPEG" in done["message"] and "resized" in done["message"]
    assert _entry(report, "IMG_0004.JPG", "preprocessing") == {"identifier": "IMG_0004.JPG", "check": "preprocessing", "status": "failed", "message": "cannot identify image file"}
    assert report["totals"] == {"entries": 2, "ok": 1, "failed": 1, "images_with_issues": 1}


def test_a_report_is_kept_read_listed_and_deleted(source: Path, reports: Path):
    report = rs.validation_report(dis.validate_images(source, None, detail=True), source)

    report_id = rs.save(report)

    assert report_id.endswith("_validation_R0003-DONA_01") and (reports / f"{report_id}.json").is_file()
    assert rs.read(report_id)["entries"] == report["entries"]
    listed = rs.list_reports()
    assert [r["id"] for r in listed] == [report_id] and "entries" not in listed[0]
    rs.delete(report_id)
    assert rs.list_reports() == []
    with pytest.raises(rs.ReportError, match="no report"):
        rs.read(report_id)


def test_two_reports_in_the_same_second_do_not_overwrite_each_other(source: Path, reports: Path):
    report = rs.validation_report(dis.validate_images(source, None, detail=True), source)
    assert rs.save(dict(report)) != rs.save(dict(report))


def test_only_a_reports_id_is_taken_for_a_path(reports: Path):
    for bad in ("../settings", "20240101-000000_validation_x/../../y", "anything"):
        with pytest.raises(rs.ReportError, match="isn't a report"):
            rs.read(bad)


def test_the_csv_has_a_row_per_entry(source: Path):
    report = rs.validation_report(dis.validate_images(source, frozenset({"corrupted"}), detail=True), source, ["corrupted"])

    rows = list(csv.DictReader(io.StringIO(rs.to_csv(report))))

    assert len(rows) == 4 and set(rows[0]) == {"identifier", "check", "status", "message"}
    assert [r["identifier"] for r in rows if r["status"] == "failed"] == ["IMG_0004.JPG"]


def test_reports_older_than_some_days_are_deleted(source: Path, reports: Path):
    old = rs.validation_report(dis.validate_images(source, None, detail=True), source)
    old["created_at"] = "2020-01-01T00:00:00+00:00"
    old_id = rs.save(old)
    new_id = rs.save(rs.validation_report(dis.validate_images(source, None, detail=True), source))

    assert rs.delete_older_than(30) == 1
    assert [r["id"] for r in rs.list_reports()] == [new_id] and old_id not in [r["id"] for r in rs.list_reports()]


# ── the API ──────────────────────────────────────────────────────────────────

def _client() -> TestClient:
    from wildintel_uploader.web.main import app
    return TestClient(app)


def test_validating_answers_with_the_id_of_its_report_which_can_be_downloaded(source: Path, reports: Path):
    client = _client()

    answer = client.post("/api/deployment-import/validate-images", json={"path": str(source)}).json()

    report_id = answer["report_id"]
    assert answer["checked_count"] == 4 and report_id
    as_json = client.get(f"/api/reports/{report_id}")
    assert as_json.status_code == 200 and as_json.json()["kind"] == "validation"
    csv_file = client.get(f"/api/reports/{report_id}/download", params={"format": "csv"})
    assert csv_file.headers["content-disposition"] == f'attachment; filename="{report_id}.csv"'
    assert csv_file.text.splitlines()[0] == "identifier,check,status,message"
    assert client.get(f"/api/reports/{report_id}/download", params={"format": "pdf"}).status_code == 400
    assert [r["id"] for r in client.get("/api/reports").json()] == [report_id]
    assert client.delete(f"/api/reports/{report_id}").json() == {"status": "ok"}
    assert client.get(f"/api/reports/{report_id}").status_code == 404


def test_postvalidating_answers_with_the_id_of_its_report(source: Path, reports: Path):
    body = {
        "path": str(source), "research_project_id": "DONA", "collection_name": "R0003", "expected_location_id": "DONA_01",
        "deployment": {"deployment_id": "R0003-DONA_01", "location_id": "DONA_01", "latitude": 37, "longitude": -6,
                       "start_date": "2024-09-04T10:00:00+02:00", "end_date": "2024-09-05T10:00:00+02:00", "tags": []},
    }

    answer = _client().post("/api/deployment-import/validate-deployment", json=body).json()

    assert answer["report_id"].endswith("_postvalidation_R0003-DONA_01")
    assert rs.read(answer["report_id"])["kind"] == "postvalidation"


# ── what the dashboard shows of each failure ─────────────────────────────────

def test_a_failed_image_has_a_short_tag_and_its_capture_date(source: Path):
    report = rs.validation_report(dis.validate_images(source, None, detail=True), source)

    out_of_order = _entry(report, "IMG_0002.JPG", "sequence")
    assert out_of_order["tag"] == "Out of order" and out_of_order["taken"] == "2024-09-04T09:00:00"
    assert _entry(report, "IMG_0003.JPG", "exif")["tag"].startswith("No date")
    assert _entry(report, "IMG_0004.JPG", "corrupted")["tag"] == "Corrupted" and "taken" not in _entry(report, "IMG_0004.JPG", "corrupted")  # no date to read
    assert "tag" not in _entry(report, "IMG_0001.JPG", "corrupted") and "taken" not in _entry(report, "IMG_0001.JPG", "corrupted")  # what passed has neither


def test_the_totals_count_the_images_with_issues(source: Path):
    checks = frozenset({"corrupted", "sequence", "duplicates", "structure"})
    report = rs.validation_report(dis.validate_images(source, checks, detail=True), source, checks)

    # IMG_0002 is out of order and IMG_0004 is corrupted; a check of the whole folder has no image to count.
    assert report["totals"]["images_with_issues"] == 2


def test_the_images_of_a_report_are_served_as_thumbnails_and_only_those(source: Path, reports: Path):
    (source / "other.txt").write_text("secret")
    report_id = rs.save(rs.validation_report(dis.validate_images(source, None, detail=True), source))

    jpeg = rs.image_jpeg(report_id, "IMG_0001.JPG")

    assert jpeg[:2] == b"\xff\xd8"  # a JPEG
    for bad in ("other.txt", "../R0003-DONA_01/IMG_0001.JPG", "/etc/passwd", "IMG_9999.JPG"):
        with pytest.raises(rs.ReportError, match="doesn't have the image"):
            rs.image_jpeg(report_id, bad)
    with pytest.raises(rs.ReportError, match="can't be shown"):  # listed, but it isn't an image
        rs.image_jpeg(report_id, "IMG_0004.JPG")


def test_the_api_serves_a_reports_image(source: Path, reports: Path):
    client = _client()
    report_id = client.post("/api/deployment-import/validate-images", json={"path": str(source)}).json()["report_id"]

    ok = client.get(f"/api/reports/{report_id}/image", params={"path": "IMG_0001.JPG"})
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/reports/{report_id}/image", params={"path": "IMG_0001.JPG", "size": "large"}).status_code == 200
    assert client.get(f"/api/reports/{report_id}/image", params={"path": "IMG_0004.JPG"}).status_code == 404
    assert client.get(f"/api/reports/{report_id}/image", params={"path": "../x.jpg"}).status_code == 404
