"""Preprocessing the images as they are imported into their collection — now the module `modules.preprocessing` (#248, #246), each step a class in
its infrastructure/steps. What is left here are the names of before, for those that call them; what the module refuses is a DeploymentImportError,
with its words, as it was."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import TypeVar

from wildintel_uploader.shared.camtrap import DeploymentFields
from wildintel_uploader.modules.deployments.domain.models import DeploymentImportError
from wildintel_uploader.modules.preprocessing.domain import models as _models
from wildintel_uploader.modules.preprocessing.domain.models import (  # noqa: F401 — the names of before
    PREPROCESSING_LOG_FILE, STAGING_DIR, ImageWork, PreprocessOptions, localize, new_name, resize_summary, xmp_tags,
)
from wildintel_uploader.modules.preprocessing.domain.steps import Job
from wildintel_uploader.modules.preprocessing.infrastructure import folders as _folders
from wildintel_uploader.modules.preprocessing.infrastructure.steps import capture_date as _capture_date, metadata as _metadata
from wildintel_uploader.modules.preprocessing.infrastructure.steps import resize as _resize
from wildintel_uploader.modules.preprocessing.infrastructure.steps.metadata import EXIFTOOL_TMP_SUFFIX  # noqa: F401
from wildintel_uploader.modules.preprocessing.infrastructure.folders import PUBLISH_TRIES, PUBLISH_WAIT, staging_dir  # noqa: F401
from wildintel_uploader.modules.preprocessing.infrastructure.images import sha1 as _sha1  # noqa: F401

T = TypeVar("T")


def _wiring():
    from wildintel_uploader.entrypoints import wiring
    return wiring


def _ours(call: Callable[[], T]) -> T:
    try:
        return call()
    except _models.PreprocessingError as exc:
        raise DeploymentImportError(str(exc)) from exc


def _events(events: Iterator[dict]) -> Iterator[dict]:
    try:
        yield from events
    except _models.PreprocessingError as exc:
        raise DeploymentImportError(str(exc)) from exc


def zone_of(name: str):
    return _ours(lambda: _models.zone_of(name))


def _camera_time(path: Path, options: PreprocessOptions, dates: dict[Path, datetime | None] | None = None) -> tuple[datetime, datetime, str]:
    """The capture time as the camera's wall clock, the same in its timezone, and where it came from: "exif", or "file"."""
    job = Job(options=options, deployment=None, info=_wiring().file_info(), dates=dates or {})  # type: ignore[arg-type]
    return _ours(lambda: _capture_date.camera_time(ImageWork(0, path, path.parent, path.parent), job))


def capture_datetime(path: Path, options: PreprocessOptions) -> tuple[datetime, str]:
    """The image's capture date — in UTC if asked — and where it came from: "exif", or "file" when the image has no date."""
    _, aware, source = _camera_time(path, options)
    return _models.as_kept(aware, options), source


def resize_to_width(source: Path, dest: Path, width: int) -> bool:
    return _resize.resize_to_width(source, dest, width, _wiring().file_info().mark_decoded)


def write_xmp_batches(exiftool: str, items: list[tuple[Path, dict[str, str]]]) -> Iterator[int]:
    return _events(_metadata.write_xmp_batches(exiftool, items))


def write_xmp(exiftool: str, items: list[tuple[Path, dict[str, str]]]) -> None:
    for _ in write_xmp_batches(exiftool, items):
        pass


def publish(work: Path, dest: Path) -> None:
    _ours(lambda: _folders.publish(work, dest))


def preprocess_stream(source_dir: str, collection_dir: str, collection_name: str | None, deployment: DeploymentFields, options: PreprocessOptions,
                      consolidate: bool = True) -> Iterator[dict]:
    """See PreprocessingService.preprocess."""
    events = _ours(lambda: _wiring().build_preprocessing().preprocess(Path(source_dir), Path(collection_dir), collection_name, deployment, options,
                                                                      consolidate))
    return _events(events)


def consolidate_stream(source_dir: str, collection_dir: str, deployment: DeploymentFields) -> Iterator[dict]:
    """See PreprocessingService.consolidate."""
    return _events(_ours(lambda: _wiring().build_preprocessing().consolidate(Path(source_dir), Path(collection_dir), deployment)))
