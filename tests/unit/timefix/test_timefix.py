"""Fixing the dates and times of the images in a folder (modules.timefix): the period the visits give and the segments — the rules of its
domain —, and through its use cases the timeline, a run of images shifted and images removed — every fix written down, and no second copy kept."""
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.support import built
from wildintel_uploader.modules.catalog.infrastructure import records as catalog_files
from wildintel_uploader.entrypoints.wiring import build_timefix
from wildintel_uploader.modules.timefix.domain import rules
from wildintel_uploader.modules.timefix.domain.ports import TimeFixError, VisitOfTheImages
from wildintel_uploader.modules.timefix.infrastructure.corrections import CORRECTIONS_FILE
from wildintel_uploader.modules.timefix.infrastructure.images import shift_argument
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
    (project / catalog_files.RESEARCH_PROJECT_METADATA_FILE).write_text(json.dumps({"name": "Tatra", "acronym": "TATRA"}), encoding="utf-8")
    built.kept_visits(root).add_many("TATRA", [
        {"location_id": LOCATION, "session": "R0001", "date": VISIT[0], "time": VISIT[1], "actions": ["Installation"]},
        {"location_id": LOCATION, "session": "R0002", "date": "2026-03-30", "time": "08:15:00", "actions": ["Revision"], "num_photos": 4},
    ])
    with patch("wildintel_uploader.entrypoints.config.collections_dir", return_value=root):
        yield root


VISIT_OF = VisitOfTheImages("TATRA", LOCATION, *VISIT)


def _timefix():
    """The fixes of the dates as the app puts them together, with the visits of the test told by the period they give."""
    timefix = build_timefix()
    timefix.period = lambda visit: PERIOD
    return timefix


def _times(folder):
    return [built.file_info().dates([p]).get(p).isoformat() for p in sorted(folder.glob("*.JPG"))]


KEPT = [{"location_id": LOCATION, "date": VISIT[0], "time": VISIT[1], "actions": ["Installation"]},
        {"location_id": LOCATION, "date": "2026-03-30", "time": "08:15:00", "actions": ["Revision"], "num_photos": 4}]


def test_the_period_is_from_the_visit_that_left_the_camera_to_the_one_that_collected_its_card():
    assert rules.deployment_period(KEPT, "TATRA", LOCATION, *VISIT) == PERIOD
    with pytest.raises(TimeFixError, match="There is no visit"):
        rules.deployment_period(KEPT, "TATRA", LOCATION, "2026-01-01", "00:00:00")
    with pytest.raises(TimeFixError, match="collected the card"):
        rules.deployment_period(KEPT, "TATRA", LOCATION, "2026-03-30", "08:15:00")


def test_the_period_comes_from_the_visits_kept(visits):
    assert build_timefix().period(VisitOfTheImages("TATRA", LOCATION, *VISIT)) == PERIOD


def test_segments_are_split_where_the_time_goes_backwards_and_checked_against_the_period():
    t = [datetime(2026, 2, 21, 10), datetime(2026, 2, 22, 10), None, datetime(2020, 1, 1), datetime(2026, 2, 25)]
    found = rules.segments(["a", "b", "c", "d", "e"], t, PERIOD, timedelta(hours=0))
    assert [(s["first"], s["last"], s["count"], s["state"]) for s in found] == [("a", "b", 2, "ok"), ("d", "e", 2, "partly")]
    assert found[1]["suggestion"]["why"] == "so that it goes on from where the one before ended"
    assert rules.run_of(["a", "b", "c"], "b", None) == (1, 2)


def test_the_timeline_splits_where_the_time_goes_backwards(card):
    seen = _timefix().timeline(str(card), VISIT_OF)

    assert [s["state"] for s in seen["segments"]] == ["ok", "outside"]
    second = seen["segments"][1]
    assert (second["first"], second["last"], second["count"]) == ("IMG_0003.JPG", "IMG_0004.JPG", 2)
    # It should go on from where the first one ended: 2026-02-22 10:00:01.
    assert second["suggestion"]["offset_seconds"] == int((datetime(2026, 2, 22, 10, 0, 1) - datetime(2020, 1, 1)).total_seconds())
    assert seen["outside"] == 2 and not seen["ok"]
    assert seen["period"]["start"] == "2026-02-20T09:30:00"


@needs_exiftool
def test_shifting_a_run_fixes_it_and_keeps_no_second_copy(card):
    offset = _timefix().timeline(str(card), VISIT_OF)["segments"][1]["suggestion"]["offset_seconds"]

    after = _timefix().shift(str(card), VISIT_OF, "IMG_0003.JPG", None, offset, "clock reset after the batteries died")

    assert after["ok"] and len(after["segments"]) == 1
    assert _times(card) == ["2026-02-21T10:00:00", "2026-02-22T10:00:00", "2026-02-22T10:00:01", "2026-02-22T16:00:01"]
    assert sorted(p.name for p in card.iterdir()) == [f"IMG_000{i}.JPG" for i in range(1, 5)] + [CORRECTIONS_FILE]
    [entry] = after["corrections"]
    assert (entry["action"], entry["first"], entry["last"], entry["count"], entry["offset_seconds"]) == ("shift", "IMG_0003.JPG", "IMG_0004.JPG", 2, offset)
    assert entry["reason"] == "clock reset after the batteries died"


def test_images_without_a_time_to_trust_are_removed(card):
    after = _timefix().remove(str(card), VISIT_OF, ["IMG_0003.JPG", "IMG_0004.JPG"], "no way to know when")

    assert after["ok"] and [i["name"] for i in after["images"]] == ["IMG_0001.JPG", "IMG_0002.JPG"]
    assert not (card / "IMG_0004.JPG").exists()
    assert json.loads((card / CORRECTIONS_FILE).read_text())[0]["action"] == "remove"


def test_a_run_must_be_in_the_folder(card):
    with pytest.raises(TimeFixError, match="no image"):
        _timefix().shift(str(card), VISIT_OF, "IMG_0099.JPG", None, 60)
    with pytest.raises(TimeFixError, match="comes before"):
        _timefix().shift(str(card), VISIT_OF, "IMG_0003.JPG", "IMG_0001.JPG", 60)
    with pytest.raises(TimeFixError, match="is not a folder"):
        _timefix().timeline(str(card / "nowhere"), VISIT_OF)


def test_the_shift_is_given_to_exiftool_in_days_hours_minutes_and_seconds():
    assert shift_argument(400 * 86400 + 5 * 3600 + 30 * 60 + 15) == "-AllDates+=0:0:400 5:30:15"
    assert shift_argument(-3600) == "-AllDates-=0:0:0 1:0:0"


def test_without_a_visit_the_dates_cant_be_checked_against_a_period(card):
    seen = _timefix().timeline(str(card), None)

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


# ── the use cases, over ports in memory: no disk, no ExifTool ──

class _Folder:
    def __init__(self, times):
        self.times = dict(times)

    def open(self, folder):
        return Path(folder)

    def images(self, folder):
        return [folder / n for n in self.times]

    def delete(self, images):
        for p in images:
            del self.times[p.name]


class _Shifter:
    def __init__(self, folder):
        self.folder = folder

    def shift(self, folder, images, offset):
        for p in images:
            self.folder.times[p.name] += timedelta(seconds=offset)


class _Log:
    def __init__(self):
        self.entries = []

    def read(self, folder):
        return list(self.entries)

    def write(self, folder, entry):
        self.entries.append(entry)


def test_the_use_cases_shift_a_run_and_write_it_down_over_any_ports():
    from wildintel_uploader.modules.timefix.application.use_cases import TimeFixUseCases

    folder = _Folder({"a.jpg": datetime(2026, 2, 21, 10), "b.jpg": datetime(2020, 1, 1), "c.jpg": datetime(2020, 1, 1, 6)})
    dates = type("Dates", (), {"dates": lambda self, paths: {p: folder.times[p.name] for p in paths}})()
    visits = type("Visits", (), {"visits": lambda self, project, location: KEPT})()
    tolerance = type("Tolerance", (), {"hours": lambda self: 0})()
    log = _Log()
    timefix = TimeFixUseCases(visits, folder, dates, _Shifter(folder), log, tolerance)

    before = timefix.timeline("/card", VISIT_OF)
    offset = before["segments"][1]["suggestion"]["offset_seconds"]
    after = timefix.shift("/card", VISIT_OF, "b.jpg", None, offset, " reset ")

    assert after["ok"] and log.entries == [{"action": "shift", "first": "b.jpg", "last": "c.jpg", "count": 2, "offset_seconds": offset, "reason": "reset"}]
    with pytest.raises(TimeFixError, match="An offset of 0"):
        timefix.shift("/card", VISIT_OF, "b.jpg", None, 0)
    assert [i["name"] for i in timefix.remove("/card", None, ["c.jpg"])["images"]] == ["a.jpg", "b.jpg"]
