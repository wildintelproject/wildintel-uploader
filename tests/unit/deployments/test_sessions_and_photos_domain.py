"""#248: the wizard's sessions and the photos of a deployment (modules.deployments) — their rules, and their use cases over ports in memory."""
import pytest

from wildintel_uploader.modules.deployments.application.photos import DeploymentPhotos
from wildintel_uploader.modules.deployments.application.sessions import WizardSessions
from wildintel_uploader.modules.deployments.domain import photos, sessions
from wildintel_uploader.modules.deployments.domain.models import DeploymentMissing, DeploymentsFailed

ID = "11111111-1111-1111-1111-111111111111"


class Kept:
    def __init__(self):
        self.kept, self.moved = {}, False

    def read(self, task_id):
        return self.kept.get(task_id)

    def write(self, task_id, manifest):
        self.kept[task_id] = manifest

    def remove(self, task_id):
        self.kept.pop(task_id, None)

    def names(self):
        return [*self.kept, "odd"]

    def move_old(self):
        self.moved = True


def test_a_session_goes_step_by_step_and_keeps_what_each_step_said():
    kept, clock = Kept(), iter(["t1", "t2", "t3"])
    wizard = WizardSessions(kept, now=lambda: next(clock))
    started = wizard.save_scan(None, "/src", {"image_count": 3})
    task_id = started["task_id"]
    assert sessions.valid_task_id(task_id) and started["phase"] == "scanned"
    wizard.save_selection(task_id, {"destination": "local"})
    ready = wizard.save_details(task_id, {"deployment_id": "R0001-X"})
    assert (ready["phase"], ready["created_at"], ready["updated_at"]) == ("ready", "t1", "t3")
    assert ready["scan"] == {"image_count": 3} and ready["selection"] == {"destination": "local"}
    assert [s["task_id"] for s in wizard.list()] == [task_id] and kept.moved   # "odd" is not a session


def test_an_id_the_app_does_not_make_names_no_session():
    wizard = WizardSessions(Kept())
    with pytest.raises(DeploymentsFailed, match="not the id of a session"):
        wizard.save_scan("../outside", "/src", {})
    with pytest.raises(DeploymentMissing):
        wizard.save_selection("../outside", {})
    with pytest.raises(DeploymentMissing):
        wizard.save_details(ID, {})
    with pytest.raises(DeploymentsFailed):
        wizard.discard("..")


class Folder:
    def names(self, *_):
        return ["b.JPG", "a.jpg", "notes.txt", "c.png"]

    def taken(self, *_):
        return {"b.JPG": "2026-01-01T08:00:00", "a.jpg": "2026-01-01T09:00:00"}

    def jpeg(self, project, collection, deployment_id, name, size):
        return f"{name}@{size}".encode()


def test_the_photos_are_in_the_order_they_were_taken_and_shown_at_their_size():
    shown = DeploymentPhotos(Folder())
    assert [p["name"] for p in shown.list("DONA", "R0001", "R0001-X")] == ["c.png", "b.JPG", "a.jpg"]   # one with no date first
    assert shown.jpeg("DONA", "R0001", "R0001-X", "a.jpg", large=True) == f"a.jpg@{photos.LARGE}".encode()
    with pytest.raises(DeploymentMissing, match="doesn't have the image"):
        shown.jpeg("DONA", "R0001", "R0001-X", "notes.txt", large=False)
    with pytest.raises(DeploymentMissing, match="not a deployment"):
        shown.list("DONA", "..", "R0001-X")
