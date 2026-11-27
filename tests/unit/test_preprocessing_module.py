"""#248, #246: the preprocessing (modules.preprocessing) — each step a class in infrastructure/steps, in the order of its registry; one tried on its
own; what can't be done said before anything is written."""
from datetime import datetime
from pathlib import Path

import pytest

from tests.unit._media_fakes import Info
from wildintel_uploader.entrypoints import wiring
from wildintel_uploader.modules.preprocessing.domain.models import ImageWork, PreprocessingError, PreprocessOptions, public_record
from wildintel_uploader.modules.preprocessing.domain.steps import Job
from wildintel_uploader.modules.preprocessing.infrastructure import steps
from wildintel_uploader.modules.preprocessing.infrastructure.steps.capture_date import CaptureDate
from wildintel_uploader.modules.preprocessing.infrastructure.steps.metadata import XmpMetadata
from wildintel_uploader.modules.preprocessing.infrastructure.steps.rename import Rename


class Deployment:
    deployment_id, location_id, location_name = "R0001-DONA_01", "DONA_01", None


def test_the_registry_has_the_steps_in_their_order():
    assert [s.key for s in steps.IMAGE_STEPS] == ["date", "rename", "resize", "hashes", "camera"]
    assert [s.key for s in steps.FOLDER_STEPS] == ["metadata", "final_hash"]


def test_the_date_and_the_name_are_steps_tried_on_their_own(tmp_path: Path):
    image = tmp_path / "IMG_7.JPG"
    image.write_bytes(b"x")
    job = Job(options=PreprocessOptions(timezone="Europe/Madrid", ignore_dst=False), deployment=Deployment(), info=Info(),
              dates={image: datetime(2024, 7, 1, 12)})
    work = ImageWork(3, image, tmp_path, tmp_path / "work")
    CaptureDate().run(work, job)
    Rename().run(work, job)
    assert public_record(work.record) == {"original": "IMG_7.JPG", "name": "R0001-DONA_01__20240701_3.JPEG", "date": "2024-07-01T10:00:00+00:00",
                                          "date_source": "exif"}


def test_metadata_without_exiftool_is_refused_before_anything_is_written():
    with pytest.raises(PreprocessingError, match="needs ExifTool"):
        XmpMetadata().check(Job(options=PreprocessOptions(), deployment=Deployment(), info=Info(), exiftool=None))


def test_the_app_puts_it_together():
    from dishka import make_container
    from wildintel_uploader.modules.preprocessing.domain.ports import PreprocessingService
    assert isinstance(make_container(wiring.FileInfoProvider(), wiring.PreprocessingProvider()).get(PreprocessingService), PreprocessingService)
