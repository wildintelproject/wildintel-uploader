"""#248, #246: the prevalidation (modules.prevalidation) — the checks of the images of a folder, each a validator in domain/checks, run
in the order of its registry over one MediaFolder that asks what is known of the files once, whatever validator asks."""
from datetime import datetime
from pathlib import Path

import pytest

from tests.support.media_fakes import Info, folder_with, pmap
from wildintel_uploader.entrypoints import wiring
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.prevalidation.application.use_cases import PrevalidationUseCases
from wildintel_uploader.modules.prevalidation.domain.models import ImageOptions, PrevalidationError
from wildintel_uploader.modules.prevalidation.domain import checks as validators
from wildintel_uploader.modules.prevalidation.domain.checks.shooting_order import ShootingOrder


def _prevalidation(info) -> PrevalidationUseCases:
    return PrevalidationUseCases(info, pmap, validators.VALIDATORS)


def test_the_registry_has_each_validator_once_with_its_key_label_and_description():
    assert [v.key for v in validators.VALIDATORS] == ["corrupted", "sequence", "structure", "camera", "exif", "duplicates"]
    assert all(v.label and v.description for v in validators.VALIDATORS)


def test_the_settings_know_the_same_checks_as_the_validators():
    from wildintel_uploader.modules.prevalidation.domain import settings
    assert set(settings.IMAGE_CHECKS) == {v.key for v in validators.VALIDATORS}


def test_what_several_validators_need_is_asked_once(tmp_path: Path):
    info = Info()
    result = _prevalidation(info).validate(folder_with(tmp_path, "IMG_1.jpg", "IMG_2.jpg"))
    assert info.asked == {"cameras": 1, "dates": 1, "decode": 2}
    assert result["checked_count"] == 2 and result["exiftool"] is True and result["cameras"][0]["count"] == 2


def test_the_validators_of_the_keys_asked_for_run_in_their_order_each_told(tmp_path: Path):
    told = []
    service = _prevalidation(Info())
    service.validate(folder_with(tmp_path, "a.jpg"), service.validators(frozenset({"duplicates", "structure", "nope"})),
                     on_check=lambda check, state: told.append((check, state)))
    assert told == [("structure", "running"), ("structure", "done"), ("duplicates", "running"), ("duplicates", "done")]


def test_the_validators_given_run_in_the_order_given(tmp_path: Path):
    from wildintel_uploader.modules.prevalidation.domain.checks.corrupted import Corrupted
    from wildintel_uploader.modules.prevalidation.domain.checks.structure import Structure
    told = []
    _prevalidation(Info()).validate(folder_with(tmp_path, "a.jpg"), [Structure(), Corrupted()], on_check=lambda check, state: told.append(check))
    assert told == ["structure", "structure", "corrupted", "corrupted"]


def test_a_validator_is_tried_on_its_own(tmp_path: Path):
    folder = folder_with(tmp_path, "IMG_1.jpg", "IMG_2.jpg")
    info = Info({"IMG_1.jpg": datetime(2024, 9, 4, 11), "IMG_2.jpg": datetime(2024, 9, 4, 10)})
    issues = ShootingOrder().run(MediaFolder(folder, info, pmap), ImageOptions())["sequence_issues"]
    assert [(i["path_a"], i["path_b"]) for i in issues] == [("IMG_1.jpg", "IMG_2.jpg")]


def test_a_folder_that_is_not_one_is_refused(tmp_path: Path):
    with pytest.raises(PrevalidationError):
        _prevalidation(Info()).validate(tmp_path / "none")


def test_the_app_puts_it_together():
    from dishka import make_container
    from wildintel_uploader.modules.prevalidation.domain.ports import PrevalidationService
    service = make_container(wiring.FileInfoProvider(), wiring.ValidationProvider()).get(PrevalidationService)
    assert [v.key for v in service.validators()] == [v.key for v in validators.VALIDATORS]
