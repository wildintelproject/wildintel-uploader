"""What is known of the files, told by a test — and how many times each thing was asked: for the prevalidation and the postvalidation."""
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import CameraInfo


class Info:
    def __init__(self, dates=None) -> None:
        self.given_dates, self.asked = dates or {}, {"cameras": 0, "dates": 0, "decode": 0}

    def cameras(self, paths):
        self.asked["cameras"] += 1
        return {p: CameraInfo(model="Reconyx HC600", camera_id="S1") for p in paths}, "exiftool"

    def dates(self, paths):
        self.asked["dates"] += 1
        return {p: self.given_dates.get(p.name) for p in paths}

    def tags(self, paths, tags):
        return {p: {t: None for t in tags} for p in paths}

    def decode_error(self, path):
        self.asked["decode"] += 1
        return None

    def hash(self, path, algorithm):
        return path.read_bytes().hex()


def pmap(function, items, progress=None):
    return [function(i) for i in items]


def folder_with(tmp_path: Path, *names: str) -> Path:
    for name in names:
        (tmp_path / name).write_bytes(name.encode())
    return tmp_path
