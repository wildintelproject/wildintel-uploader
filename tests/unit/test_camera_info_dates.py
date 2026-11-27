"""#227: the capture dates are read with ExifTool, in one run for all the images, and with Pillow only when there is no ExifTool."""
import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from tests.support import camera_info
from wildintel_uploader.modules.fileinfo.infrastructure import exiftool as exiftool_adapter


def _jpeg(path: Path, *, original: str | None = None, digitized: str | None = None, changed: str | None = None) -> Path:
    img = Image.new("RGB", (4, 4))
    exif = img.getexif()
    if changed:
        exif[306] = changed                         # DateTime (ModifyDate for ExifTool)
    sub = exif.get_ifd(0x8769)
    if original:
        sub[36867] = original                       # DateTimeOriginal
    if digitized:
        sub[36868] = digitized                      # DateTimeDigitized (CreateDate for ExifTool)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, exif=exif)
    return path


def test_the_dates_are_read_with_exiftool_in_one_run_for_all_the_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paths = [tmp_path / f"IMG_{n}.JPG" for n in range(3)]
    runs: list[list[str]] = []
    rows = [{"SourceFile": str(paths[0]), "DateTimeOriginal": "2024:09:04 10:00:00", "CreateDate": "2024:09:04 09:00:00"},
            {"SourceFile": str(paths[1]), "CreateDate": "2024:09:05 11:00:00+02:00"},        # no DateTimeOriginal: when it was digitized
            {"SourceFile": str(paths[2]), "DateTimeOriginal": "0000:00:00 00:00:00"}]       # no date at all
    monkeypatch.setattr(exiftool_adapter, "exiftool_path", lambda: "exiftool")
    monkeypatch.setattr(exiftool_adapter.subprocess, "run", lambda args, **k: (runs.append(args), subprocess.CompletedProcess(args, 0, json.dumps(rows), ""))[1])

    dates = camera_info.read_dates(paths)

    assert len(runs) == 1 and {"-DateTimeOriginal", "-CreateDate", "-ModifyDate"} <= set(runs[0])
    assert dates == {paths[0]: datetime(2024, 9, 4, 10), paths[1]: datetime(2024, 9, 5, 11), paths[2]: None}


def test_without_exiftool_the_dates_are_read_with_pillow_in_the_same_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(exiftool_adapter, "exiftool_path", lambda: None)
    a = _jpeg(tmp_path / "a.jpg", original="2024:09:04 10:00:00", changed="2024:09:09 10:00:00")
    b = _jpeg(tmp_path / "b.jpg", digitized="2024:09:05 10:00:00", changed="2024:09:09 10:00:00")
    c = _jpeg(tmp_path / "c.jpg", changed="2024:09:09 10:00:00")
    d = _jpeg(tmp_path / "d.jpg")

    assert camera_info.read_dates([a, b, c, d]) == {a: datetime(2024, 9, 4, 10), b: datetime(2024, 9, 5, 10), c: datetime(2024, 9, 9, 10), d: None}


@pytest.mark.skipif(camera_info.exiftool_path() is None, reason="ExifTool is not installed")
def test_exiftool_and_pillow_read_the_same_dates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    paths = [_jpeg(tmp_path / "a.jpg", original="2024:09:04 10:00:00"), _jpeg(tmp_path / "b.jpg", digitized="2024:09:05 10:00:00"), _jpeg(tmp_path / "c.jpg")]
    with_exiftool = camera_info.read_dates(paths)
    monkeypatch.setattr(exiftool_adapter, "exiftool_path", lambda: None)
    assert camera_info.read_dates(paths) == with_exiftool
