"""services.file_memo — what the steps of an import remember of a file while it is the same one: what ExifTool read of an image (kept on disk too), its camera, and that it decoded in full (#140)."""
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from tests.support import camera_info
from wildintel_uploader.modules.fileinfo.infrastructure import store as exif_store
from wildintel_uploader.modules.fileinfo.infrastructure import memory as file_memo
from tests.support import deployment_import_service as svc
from tests.support import checks as old_checks
from tests.support import preprocessing_service as pre
from wildintel_uploader.modules.fileinfo.infrastructure import exiftool as exiftool_adapter, pillow as pillow_adapter


def _jpeg(path: Path, size=(4, 4), make="Reconyx", model="HC600", color="red") -> Path:
    img = Image.new("RGB", size, color=color)
    exif = img.getexif()
    exif[271], exif[272] = make, model
    exif[306] = "2024:09:01 10:00:00"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, exif=exif)
    return path


# ── the memory itself ────────────────────────────────────────────────────────

def test_a_memory_is_bounded_and_forgets_the_oldest_first():
    memo = file_memo.FileMemo(limit=2)
    for n in range(3):
        memo.put(("f", n, n), n)
    assert memo.get(("f", 0, 0)) is None and memo.get(("f", 1, 1)) == 1 and memo.get(("f", 2, 2)) == 2


def test_a_memory_keeps_what_was_asked_for_last():
    memo = file_memo.FileMemo(limit=2)
    memo.put(("f", 0, 0), 0)
    memo.put(("f", 1, 1), 1)
    memo.get(("f", 0, 0))
    memo.put(("f", 2, 2), 2)
    assert memo.get(("f", 0, 0)) == 0 and memo.get(("f", 1, 1)) is None


def test_a_file_that_cannot_be_looked_at_has_no_stamp_and_nothing_is_kept_of_it(tmp_path: Path):
    assert file_memo.stamp(tmp_path / "nothing.jpg") is None
    memo = file_memo.FileMemo()
    memo.put(None, 1)
    assert memo.get(None) is None and len(memo) == 0


def test_a_file_changed_in_size_or_in_time_has_another_stamp(tmp_path: Path):
    path = tmp_path / "a.bin"
    path.write_bytes(b"one")
    before = file_memo.stamp(path)
    path.write_bytes(b"three")
    assert file_memo.stamp(path) != before
    again = file_memo.stamp(path)
    os.utime(path, ns=(1, 1))
    assert file_memo.stamp(path) != again


# ── the camera ───────────────────────────────────────────────────────────────

@pytest.fixture
def no_exiftool(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(exiftool_adapter, "exiftool_path", lambda: None)


def _count(monkeypatch: pytest.MonkeyPatch, name: str) -> list:
    calls: list = []
    real = getattr(pillow_adapter, name)
    monkeypatch.setattr(pillow_adapter, name, lambda *a, **k: calls.append(a) or real(*a, **k))
    return calls


def test_the_camera_of_an_image_is_read_once_while_the_image_is_the_same(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_exiftool):
    images = [_jpeg(tmp_path / f"IMG_{n}.jpg", model=f"M{n}") for n in range(3)]
    calls = _count(monkeypatch, "_read_with_pillow")

    first, reader = camera_info.read_cameras(images)
    second, again = camera_info.read_cameras(images)

    assert len(calls) == 3 and first == second and reader == again == "pillow"
    assert [info.model for info in second.values()] == ["Reconyx M0", "Reconyx M1", "Reconyx M2"]


def test_only_the_images_that_changed_are_read_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_exiftool):
    images = [_jpeg(tmp_path / f"IMG_{n}.jpg") for n in range(3)]
    camera_info.read_cameras(images)
    calls = _count(monkeypatch, "_read_with_pillow")

    _jpeg(images[1], size=(8, 8), model="Another")   # replaced by another image
    cameras, _ = camera_info.read_cameras(images)

    assert [c[0].name for c in calls] == ["IMG_1.jpg"]
    assert cameras[images[1]].model == "Reconyx Another" and cameras[images[0]].model == "Reconyx HC600"


def _fake_exiftool(monkeypatch: pytest.MonkeyPatch, tags_of: dict[Path, dict[str, str]] | None = None) -> list[tuple[list[Path], list[str]]]:
    """ExifTool, as far as camera_info is concerned: each run is recorded (the images and the tags asked for), and gives what tags_of says of each image (a
    camera "Reconyx HC600", serial "S1", taken 2024-09-04 10:00 when it is not said); an image not in tags_of, when it is given, cannot be read."""
    runs: list[tuple[list[Path], list[str]]] = []
    monkeypatch.setattr(exiftool_adapter, "exiftool_path", lambda: "exiftool")

    def read(tool, paths, tags):
        runs.append((list(paths), list(tags)))
        base = {"Make": "Reconyx", "Model": "HC600", "SerialNumber": "S1", "DateTimeOriginal": "2024:09:04 10:00:00"}
        return {p: {t: {**base, **(tags_of or {}).get(p, {})}.get(t) for t in tags} for p in paths if tags_of is None or p in tags_of}
    monkeypatch.setattr(exiftool_adapter, "_tags_with_exiftool", read)
    return runs


def test_one_exiftool_run_gives_the_camera_the_dates_and_the_fields_of_every_step(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    images = [_jpeg(tmp_path / f"IMG_{n}.jpg") for n in range(3)]
    runs = _fake_exiftool(monkeypatch)

    cameras, reader = camera_info.read_cameras(images)
    dates = camera_info.read_dates(images)
    models = camera_info.read_tags(images, ["Model", "SerialNumber"])

    assert len(runs) == 1 and {"Make", "Model", "SerialNumber", "DateTimeOriginal", "CreateDate", "ModifyDate"} <= set(runs[0][1])
    assert reader == "exiftool" and cameras[images[0]] == camera_info.CameraInfo(model="Reconyx HC600", camera_id="S1")
    assert set(dates.values()) == {datetime(2024, 9, 4, 10)} and models[images[2]] == {"Model": "HC600", "SerialNumber": "S1"}


def test_a_field_not_read_before_is_read_with_the_rest_and_then_remembered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    images = [_jpeg(tmp_path / "a.jpg")]
    runs = _fake_exiftool(monkeypatch, {images[0]: {"ISO": "400"}})
    camera_info.read_dates(images)

    assert camera_info.read_tags(images, ["ISO"]) == {images[0]: {"ISO": "400"}}
    camera_info.read_tags(images, ["ISO"])
    camera_info.read_cameras(images)

    assert [r[1][-1] for r in runs] == ["ModifyDate", "ISO"]   # the second run asked for ISO, besides the camera and the dates; nothing after it


def test_only_the_images_that_changed_are_read_again_by_exiftool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    images = [_jpeg(tmp_path / f"IMG_{n}.jpg") for n in range(3)]
    runs = _fake_exiftool(monkeypatch)
    camera_info.read_dates(images)

    _jpeg(images[1], size=(8, 8))   # replaced by another image
    camera_info.read_dates(images)

    assert [r[0] for r in runs] == [images, [images[1]]]


def test_what_exiftool_read_is_kept_on_disk_for_after_a_restart(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    images = [_jpeg(tmp_path / f"IMG_{n}.jpg") for n in range(2)]
    runs = _fake_exiftool(monkeypatch)
    first = camera_info.read_cameras(images)

    file_memo.forget_all()   # the app restarted: its memory is empty
    assert camera_info.read_cameras(images) == first and camera_info.read_dates(images)[images[0]] == datetime(2024, 9, 4, 10)
    assert len(runs) == 1 and exif_store.path().is_file()

    _jpeg(images[0], size=(8, 8))   # but not what an earlier file said
    file_memo.forget_all()
    camera_info.read_cameras(images)
    assert runs[1][0] == [images[0]]


def test_an_image_exiftool_could_not_read_is_looked_at_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    good, bad = _jpeg(tmp_path / "good.jpg"), _jpeg(tmp_path / "bad.jpg")
    runs = _fake_exiftool(monkeypatch, {good: {}})

    assert camera_info.read_dates([good, bad]) == {good: datetime(2024, 9, 4, 10), bad: None}
    camera_info.read_dates([good, bad])

    assert [r[0] for r in runs] == [[good, bad], [bad]]


def test_a_store_on_disk_that_cannot_be_read_is_as_if_it_were_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    images = [_jpeg(tmp_path / "a.jpg")]
    runs = _fake_exiftool(monkeypatch)
    camera_info.read_dates(images)
    monkeypatch.setattr(exif_store, "_open", lambda: (_ for _ in ()).throw(sqlite3.OperationalError("disk I/O error")))
    file_memo.forget_all()

    assert camera_info.read_dates(images)[images[0]] == datetime(2024, 9, 4, 10)
    assert len(runs) == 2


def test_the_store_on_disk_keeps_at_most_its_limit_the_oldest_forgotten_first(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(exif_store, "LIMIT", 2)
    for n in range(3):
        exif_store.put_many({(f"/img/{n}.jpg", 1, 1): {"model": str(n)}})

    assert exif_store.get_many([(f"/img/{n}.jpg", 1, 1) for n in range(3)]) == {("/img/1.jpg", 1, 1): {"model": "1"}, ("/img/2.jpg", 1, 1): {"model": "2"}}


def test_the_exif_read_ahead_is_what_the_steps_find_even_when_they_ask_while_it_is_being_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    images = [_jpeg(tmp_path / f"IMG_{n}.jpg") for n in range(3)]
    runs = _fake_exiftool(monkeypatch, {p: {"ISO": "100"} for p in images})
    reading, slow, real = threading.Event(), threading.Event(), exiftool_adapter._tags_with_exiftool
    monkeypatch.setattr(exiftool_adapter, "_tags_with_exiftool", lambda *a: (reading.set(), slow.wait(5), real(*a))[2])
    monkeypatch.setattr("wildintel_uploader.modules.fileinfo.application.use_cases.PREFETCH", True)

    ahead = camera_info.prefetch(images, ["ISO"])
    assert reading.wait(5)   # ExifTool is reading them
    asked: dict = {}
    step = threading.Thread(target=lambda: asked.update(camera_info.read_dates(images)))
    step.start()          # the checks are run while it is still reading
    slow.set()
    ahead.join(5); step.join(5)

    assert len(runs) == 1 and "ISO" in runs[0][1]            # one reading, with the fields of the settings
    assert asked == dict.fromkeys(images, datetime(2024, 9, 4, 10))
    assert camera_info.read_tags(images, ["ISO"])[images[0]] == {"ISO": "100"} and len(runs) == 1


def test_nothing_is_read_ahead_without_exiftool_or_without_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("wildintel_uploader.modules.fileinfo.application.use_cases.PREFETCH", True)
    monkeypatch.setattr(exiftool_adapter, "exiftool_path", lambda: None)
    assert camera_info.prefetch([_jpeg(tmp_path / "a.jpg")]) is None
    monkeypatch.setattr(exiftool_adapter, "exiftool_path", lambda: "exiftool")
    assert camera_info.prefetch([]) is None


def test_a_reading_by_pillow_is_made_again_when_exiftool_is_there_now(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    images = [_jpeg(tmp_path / "a.jpg")]
    monkeypatch.setattr(exiftool_adapter, "exiftool_path", lambda: None)
    camera_info.read_cameras(images)

    runs = _fake_exiftool(monkeypatch)
    cameras, reader = camera_info.read_cameras(images)

    assert len(runs) == 1 and reader == "exiftool" and cameras[images[0]].camera_id == "S1"
    camera_info.read_cameras(images)
    assert len(runs) == 1   # and now it is remembered


def test_the_reader_is_pillow_when_exiftool_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    a, b = _jpeg(tmp_path / "a.jpg"), _jpeg(tmp_path / "b.jpg")
    _fake_exiftool(monkeypatch)
    assert camera_info.read_cameras([a])[1] == "exiftool"
    monkeypatch.setattr(exiftool_adapter, "_tags_with_exiftool", lambda tool, paths, tags: (_ for _ in ()).throw(OSError("gone")))
    assert camera_info.read_cameras([a, b])[1] == "pillow"


# ── the images that decode ───────────────────────────────────────────────────

def _opens(monkeypatch: pytest.MonkeyPatch) -> list:
    opened: list = []
    real = svc.Image.open
    monkeypatch.setattr(svc.Image, "open", lambda path, *a, **k: opened.append(Path(path).name) or real(path, *a, **k))
    return opened


def test_an_image_that_decoded_is_not_decoded_again_while_it_is_the_same(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _jpeg(tmp_path / "a.jpg")
    _jpeg(tmp_path / "b.jpg")
    opened = _opens(monkeypatch)

    assert old_checks.validate_images(tmp_path, frozenset({"corrupted"}))["corrupted"] == []
    assert sorted(opened) == ["a.jpg", "b.jpg"]
    opened.clear()
    assert old_checks.validate_images(tmp_path, frozenset({"corrupted"}))["corrupted"] == []
    assert opened == []


def test_a_corrupted_image_is_looked_at_every_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    _jpeg(tmp_path / "good.jpg")
    bad = _jpeg(tmp_path / "bad.jpg", size=(64, 64))
    bad.write_bytes(bad.read_bytes()[:-40])   # cut short
    opened = _opens(monkeypatch)

    for _ in range(2):
        assert [c["path"] for c in old_checks.validate_images(tmp_path, frozenset({"corrupted"}))["corrupted"]] == ["bad.jpg"]
    assert opened.count("bad.jpg") == 2 and opened.count("good.jpg") == 1


def test_an_image_that_decoded_and_was_then_cut_short_is_found_corrupted(tmp_path: Path):
    path = _jpeg(tmp_path / "a.jpg", size=(64, 64))
    assert old_checks.validate_images(tmp_path, frozenset({"corrupted"}))["corrupted"] == []

    path.write_bytes(path.read_bytes()[:-40])

    assert [c["path"] for c in old_checks.validate_images(tmp_path, frozenset({"corrupted"}))["corrupted"]] == ["a.jpg"]


def test_resizing_an_image_says_it_decoded_and_the_check_does_not_decode_it_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    big = _jpeg(tmp_path / "src" / "big.jpg", size=(3000, 2000))
    pre.resize_to_width(big, tmp_path / "out.jpg", 2400)
    opened = _opens(monkeypatch)

    assert old_checks.validate_images(big.parent, frozenset({"corrupted"}))["corrupted"] == []
    assert opened == []


def test_an_image_that_is_only_copied_is_not_said_to_have_decoded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    small = _jpeg(tmp_path / "src" / "small.jpg", size=(1000, 800))
    assert pre.resize_to_width(small, tmp_path / "out.jpg", 2400) is False
    opened = _opens(monkeypatch)

    old_checks.validate_images(small.parent, frozenset({"corrupted"}))

    assert opened == ["small.jpg"]


def test_an_image_that_failed_to_resize_is_not_said_to_have_decoded(tmp_path: Path):
    bad = _jpeg(tmp_path / "src" / "bad.jpg", size=(3000, 2000))
    bad.write_bytes(bad.read_bytes()[:-2000])
    with pytest.raises(Exception):
        pre.resize_to_width(bad, tmp_path / "out.jpg", 2400)

    assert [c["path"] for c in old_checks.validate_images(bad.parent, frozenset({"corrupted"}))["corrupted"]] == ["bad.jpg"]
