"""Fixing the dates and times of the images in a folder: the timeline and its segments against the period the visits give, a run of
images shifted and images removed — every fix written down, and no second copy kept."""
import json
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from wildintel_uploader.core.services import deployment_import_service as dis
from wildintel_uploader.core.services import local_folder_service as lfs
from wildintel_uploader.core.services import timefix_service as tf
from wildintel_uploader.web.main import app

needs_exiftool = pytest.mark.skipif(shutil.which("exiftool") is None, reason="ExifTool isn't installed")
LOCATION = "TATR_0001"
VISIT = ("2026-02-20", "09:30:00")  # the visit that left the camera; the next that collected the card ends the deployment
PERIOD = (datetime(2026, 2, 20, 9, 30), datetime(2026, 3, 30, 8, 15))


def _jpeg(path: Path, taken: str) -> None:
    img = Image.new("RGB", (40, 30), color="red")
    exif = img.getexif()
    exif.get_ifd(0x8769)[36867] = taken
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, exif=exif)


@pytest.fixture
def card(tmp_path):
    """A folder copied from a card: two images in the period, then the clock reset to 2020 for two more."""
    folder = tmp_path / "card"
    for i, taken in enumerate(["2026:02:21 10:00:00", "2026:02:22 10:00:00", "2020:01:01 00:00:00", "2020:01:01 06:00:00"], start=1):
        _jpeg(folder / f"IMG_{i:04d}.JPG", taken)
    return folder


@pytest.fixture
def visits(tmp_path):
    """TATRA's visits.json: an Installation, then a Revision that collected the card."""
    root = tmp_path / "collections"
    project = root / "TATRA"
    project.mkdir(parents=True)
    (project / lfs.RESEARCH_PROJECT_METADATA_FILE).write_text(json.dumps({"name": "Tatra", "acronym": "TATRA"}), encoding="utf-8")
    lfs.write_visits(root, "TATRA", [
        {"location_id": LOCATION, "session": "R0001", "date": VISIT[0], "time": VISIT[1], "actions": ["Installation"]},
        {"location_id": LOCATION, "session": "R0002", "date": "2026-03-30", "time": "08:15:00", "actions": ["Revision"], "num_photos": 4},
    ])
    with patch("wildintel_uploader.core.config.collections_dir", return_value=root):
        yield root


def _times(folder):
    return [dis._image_datetime(p).isoformat() for p in sorted(folder.glob("*.JPG"))]


def test_the_period_is_from_the_visit_that_left_the_camera_to_the_one_that_collected_its_card(visits):
    assert tf.visit_period("TATRA", LOCATION, *VISIT) == PERIOD
    with pytest.raises(tf.TimeFixError, match="There is no visit"):
        tf.visit_period("TATRA", LOCATION, "2026-01-01", "00:00:00")
    with pytest.raises(tf.TimeFixError, match="collected the card"):
        tf.visit_period("TATRA", LOCATION, "2026-03-30", "08:15:00")


def test_the_timeline_splits_where_the_time_goes_backwards(card):
    seen = tf.timeline(str(card), PERIOD)

    assert [s["state"] for s in seen["segments"]] == ["ok", "outside"]
    second = seen["segments"][1]
    assert (second["first"], second["last"], second["count"]) == ("IMG_0003.JPG", "IMG_0004.JPG", 2)
    # It should go on from where the first one ended: 2026-02-22 10:00:01.
    assert second["suggestion"]["offset_seconds"] == int((datetime(2026, 2, 22, 10, 0, 1) - datetime(2020, 1, 1)).total_seconds())
    assert seen["outside"] == 2 and not seen["ok"]
    assert seen["period"]["start"] == "2026-02-20T09:30:00"


@needs_exiftool
def test_shifting_a_run_fixes_it_and_keeps_no_second_copy(card):
    offset = tf.timeline(str(card), PERIOD)["segments"][1]["suggestion"]["offset_seconds"]

    after = tf.shift(str(card), PERIOD, "IMG_0003.JPG", None, offset, "clock reset after the batteries died")

    assert after["ok"] and len(after["segments"]) == 1
    assert _times(card) == ["2026-02-21T10:00:00", "2026-02-22T10:00:00", "2026-02-22T10:00:01", "2026-02-22T16:00:01"]
    assert sorted(p.name for p in card.iterdir()) == [f"IMG_000{i}.JPG" for i in range(1, 5)] + [tf.CORRECTIONS_FILE]
    [entry] = after["corrections"]
    assert (entry["action"], entry["first"], entry["last"], entry["count"], entry["offset_seconds"]) == ("shift", "IMG_0003.JPG", "IMG_0004.JPG", 2, offset)
    assert entry["reason"] == "clock reset after the batteries died"


def test_images_without_a_time_to_trust_are_removed(card):
    after = tf.remove(str(card), PERIOD, ["IMG_0003.JPG", "IMG_0004.JPG"], "no way to know when")

    assert after["ok"] and [i["name"] for i in after["images"]] == ["IMG_0001.JPG", "IMG_0002.JPG"]
    assert not (card / "IMG_0004.JPG").exists()
    assert json.loads((card / tf.CORRECTIONS_FILE).read_text())[0]["action"] == "remove"


def test_a_run_must_be_in_the_folder(card):
    with pytest.raises(tf.TimeFixError, match="no image"):
        tf.shift(str(card), PERIOD, "IMG_0099.JPG", None, 60)
    with pytest.raises(tf.TimeFixError, match="comes before"):
        tf.shift(str(card), PERIOD, "IMG_0003.JPG", "IMG_0001.JPG", 60)
    with pytest.raises(tf.TimeFixError, match="is not a folder"):
        tf.timeline(str(card / "nowhere"), PERIOD)


def test_the_shift_is_given_to_exiftool_in_days_hours_minutes_and_seconds():
    assert tf._shift_argument(400 * 86400 + 5 * 3600 + 30 * 60 + 15) == "-AllDates+=0:0:400 5:30:15"
    assert tf._shift_argument(-3600) == "-AllDates-=0:0:0 1:0:0"


def test_without_a_visit_the_dates_cant_be_checked_against_a_period(card):
    seen = tf.timeline(str(card), None)

    assert seen["period"] is None and seen["segments"][1]["suggestion"] is None
    assert any("No visit was chosen" in p for p in seen["problems"])


def test_the_api_reads_the_timeline_with_the_visits_period_and_refuses_a_bad_run(card, visits):
    client = TestClient(app)
    body = {"folder": str(card), "research_project_id": "TATRA", "location_id": LOCATION, "date": VISIT[0], "time": VISIT[1]}

    seen = client.post("/api/timefix/timeline", json=body).json()
    assert seen["outside"] == 2 and seen["period"]["end"] == "2026-03-30T08:15:00"
    assert client.post("/api/timefix/shift", json={**body, "first": "nope.jpg", "offset_seconds": 5}).status_code == 400
    assert client.post("/api/timefix/timeline", json={**body, "date": "2000-01-01"}).status_code == 400
    assert client.post("/api/timefix/timeline", json={"folder": str(card)}).json()["period"] is None
