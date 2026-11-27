"""#248: the use cases of the deployments (modules.deployments) over ports in memory — a deployment comes into a collection of a research project
only if it is of a visit, in the timezone of its location; one not kept has no seal."""
from pathlib import Path

import pytest

from wildintel_uploader.modules.deployments.application.use_cases import DeploymentsUseCases
from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsFailed


class Folders:
    def __init__(self, root: Path, time: dict) -> None:
        self.root_, self.time, self.copied = root, time, []

    def root(self):
        return self.root_

    def location_time(self, project_dir, location_id):
        return self.time

    def copy_as_it_is(self, *args):
        self.copied.append(args)
        return iter([{"type": "done"}])

    def kept(self, project, deployment_id):
        return None


class Visits:
    def __init__(self, known: set) -> None:
        self.known = known

    def has_deployment(self, project, deployment_id):
        return (project, deployment_id) in self.known


class Preprocessing:
    def __init__(self) -> None:
        self.asked = []

    def preprocess(self, source, collection, name, deployment, options, consolidate):
        self.asked.append(options)
        return iter([])


class Deployment:
    deployment_id, location_id = "R0001-DONA_01", "DONA_01"


def _deployments(tmp_path, known=(), time=None):
    folders, preprocessing = Folders(tmp_path, {"timezone": "Atlantic/Canary", "ignore_dst": False} if time is None else time), Preprocessing()
    service = DeploymentsUseCases(None, folders, None, None, visits=Visits(set(known)), preprocessing=preprocessing)
    return service, folders, preprocessing


def test_a_deployment_of_no_visit_is_refused_before_any_image_is_touched(tmp_path: Path):
    service, folders, _ = _deployments(tmp_path)
    with pytest.raises(DeploymentsFailed, match="is not of any visit of DONA"):
        service.import_local("src", str(tmp_path / "DONA" / "R0001"), None, Deployment(), None)
    assert folders.copied == []
    # a collection outside the collections folder has no visits to ask
    service.import_local("src", str(tmp_path.parent / "elsewhere" / "R0001"), None, Deployment(), None)
    assert len(folders.copied) == 1


def test_the_images_are_read_in_the_timezone_of_the_location_kept(tmp_path: Path):
    service, _, preprocessing = _deployments(tmp_path, {("DONA", "R0001-DONA_01")})
    service.import_local("src", str(tmp_path / "DONA" / "R0001"), None, Deployment(), {"rename": True})
    assert (preprocessing.asked[0].timezone, preprocessing.asked[0].ignore_dst) == ("Atlantic/Canary", False)
    service, _, _ = _deployments(tmp_path, {("DONA", "R0001-DONA_01")}, time={})
    with pytest.raises(DeploymentsFailed, match="has no timezone"):
        service.import_local("src", str(tmp_path / "DONA" / "R0001"), None, Deployment(), {"rename": True})


def test_a_deployment_not_kept_has_no_seal(tmp_path: Path):
    service, _, _ = _deployments(tmp_path)
    with pytest.raises(DeploymentMissing):
        service.seal_status("DONA", "R0001-DONA_01")
