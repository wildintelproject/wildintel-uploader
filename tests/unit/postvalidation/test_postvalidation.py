"""#248, #246: the postvalidation (modules.postvalidation) — the checks of a deployment against wildintel-tools' names, its images and its visit,
each a validator in infrastructure/validators, run in the order of its registry."""
from pathlib import Path

import pytest

from tests.support.media_fakes import Info, folder_with, pmap
from wildintel_uploader.entrypoints import wiring
from wildintel_uploader.modules.fileinfo.domain.folder import MediaFolder
from wildintel_uploader.modules.postvalidation.application.use_cases import PostvalidationUseCases
from wildintel_uploader.modules.postvalidation.domain.models import Deployment, DeploymentContext, PostvalidationError
from wildintel_uploader.modules.postvalidation.infrastructure import validators
from wildintel_uploader.modules.postvalidation.infrastructure.validators.photo_count import PhotoCount


def _postvalidation(info) -> PostvalidationUseCases:
    return PostvalidationUseCases(info, pmap, validators.VALIDATORS)


def test_the_registry_has_each_validator_once_and_says_those_of_the_visit():
    keys = [v.key for v in validators.VALIDATORS]
    assert len(set(keys)) == 11 and [v.key for v in validators.VALIDATORS if v.of_the_visit] == ["sd_card", "photo_count"]
    assert keys[-3:] == ["image_count", "sequence_count", "sequence_length"] and all(v.statistical for v in validators.VALIDATORS[-3:])
    assert all(v.label and v.description for v in validators.VALIDATORS)


def test_the_settings_know_the_checks_of_the_validators():
    from wildintel_uploader.modules.postvalidation.domain import settings
    assert {v.key for v in validators.VALIDATORS} == set(settings.DEPLOYMENT_CHECKS)


def test_the_checks_asked_for_run_in_their_order(tmp_path: Path):
    told = []
    service = _postvalidation(Info())
    result = service.validate(folder_with(tmp_path, "a.jpg"), DeploymentContext(Deployment("R0001-DONA_01")),
                              service.validators(frozenset({"collection_name", "deployment_id"})), on_check=lambda c, s: told.append(c))
    assert told == ["deployment_id", "deployment_id", "collection_name", "collection_name"]
    assert result["deployment_id"]["ok"] and result["collection_name"]["ok"] and result["checked_count"] == 1


def test_a_validator_is_tried_on_its_own(tmp_path: Path):
    folder = folder_with(tmp_path, "IMG_1.jpg", "IMG_2.jpg")
    context = DeploymentContext(Deployment("R0001-DONA_01"), visit={"counted_photos": 3, "collected_session": "V1"})
    found = PhotoCount().run(MediaFolder(folder, Info(), pmap), context)["photo_count"]
    assert found == {"ok": False, "message": "The visit V1 counted 3 images on the card, and the folder has 2 images — 1 image missing."}


def test_what_cannot_be_checked_is_refused(tmp_path: Path):
    with pytest.raises(PostvalidationError):
        _postvalidation(Info()).validate(tmp_path / "none", DeploymentContext(Deployment("R0001-DONA_01")))
    with pytest.raises(PostvalidationError):
        _postvalidation(Info()).validate(tmp_path, DeploymentContext(Deployment("R0001-DONA_01"), tolerance_hours=-1))


def test_the_app_puts_it_together():
    from dishka import make_container
    from wildintel_uploader.modules.postvalidation.domain.ports import PostvalidationService
    service = make_container(wiring.FileInfoProvider(), wiring.ValidationProvider()).get(PostvalidationService)
    assert [v.key for v in service.validators()] == [v.key for v in validators.VALIDATORS]
