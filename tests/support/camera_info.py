"""Which camera took an image, when, and what else its metadata say — now the module `modules.fileinfo` (#248), which reads them with ExifTool, once
while the file is the same, and remembers them. What is left here are the names the code of before calls, each asking that module."""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from wildintel_uploader.modules.fileinfo.domain.models import DATE_TAGS, CameraInfo, Tags, common_value, model_name  # noqa: F401
from wildintel_uploader.modules.fileinfo.infrastructure import exiftool as _exiftool

_model = model_name


def exiftool_path() -> str | None:
    """Where ExifTool is — the bundled one first, then the one on the PATH —; None if neither exists."""
    return _exiftool.exiftool_path()


def _service():
    from wildintel_uploader.entrypoints import wiring
    return wiring.file_info()


def read_tags(paths: list[Path], tags: list[str]) -> dict[Path, dict[str, str | None]]:
    return _service().tags(paths, tags)


def read_dates(paths: list[Path]) -> dict[Path, datetime | None]:
    return _service().dates(paths)


def read_cameras(paths: list[Path]) -> tuple[dict[Path, CameraInfo], str]:
    return _service().cameras(paths)


def _metadata(paths: list[Path], tags: list[str]) -> dict[Path, Tags] | None:
    return _service().metadata(paths, tags)


def prefetch(paths: list[Path], tags: list[str] | None = None) -> threading.Thread | None:
    return _service().prefetch(paths, tags)
