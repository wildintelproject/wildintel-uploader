"""#248: the uploaders (modules.uploaders) — what TRAPPER and the network refuse, as the module's errors with the words the pages have always shown;
an upload that fails is written down, and one that works clears it; TRAPPER and AGOUTI are its settings."""
from pathlib import Path

import httpx
import pytest
from trapper_client import err

from wildintel_uploader.modules.settings.domain.registry import settings_registry
from wildintel_uploader.modules.uploaders.application.use_cases import UploadersUseCases
from wildintel_uploader.modules.uploaders.domain.models import Account, NotThere, UploaderError
from wildintel_uploader.modules.uploaders.domain.settings import TrapperSettings
from wildintel_uploader.modules.uploaders.infrastructure.trapper import as_uploader_error


@pytest.mark.parametrize("exc, status, words", [
    (err.UnauthorizedError("x"), 401, "Incorrect TRAPPER username or password."),
    (httpx.ConnectError("refused"), 502, "Could not connect to the TRAPPER server: refused"),
    (httpx.ReadTimeout("slow"), 504, "Timed out connecting to the TRAPPER server: slow"),
    (ValueError("anything else"), 400, "anything else"),
])
def test_what_trapper_refuses_is_told_with_its_status(exc, status, words):
    found = as_uploader_error(exc)
    assert (found.status, found.message) == (status, words)


class Trapper:
    def __init__(self, events) -> None:
        self.events = events

    def credentials(self, account):
        return ("u", "n", "p")

    def upload(self, *args):
        return iter(self.events)

    def describe(self, exc):
        return str(exc)


class Kept:
    def __init__(self, root: Path) -> None:
        self.root, self.notes = root, []

    def project(self, project):
        return {"acronym": project} if project == "DONA" else None

    def collection_dir(self, project, collection):
        return self.root / collection

    def note_failure(self, project, deployment_id, destination, note):
        self.notes.append(note)


def _failing():
    yield {"type": "start"}
    raise RuntimeError("the network went away")


def test_an_upload_that_fails_is_written_down_and_one_that_works_clears_it(tmp_path: Path):
    (tmp_path / "R0001" / "R0001-DONA_01").mkdir(parents=True)
    kept = Kept(tmp_path)
    done = UploadersUseCases(Trapper([{"type": "done"}]), kept, None).upload(Account(), "DONA", "R0001", "R0001-DONA_01", "upload", None, False)
    assert list(done) == [{"type": "done"}] and kept.notes == [None]
    failed = UploadersUseCases(Trapper(_failing()), kept, None).upload(Account(), "DONA", "R0001", "R0001-DONA_01", "upload", None, False)
    with pytest.raises(UploaderError, match="the network went away"):
        list(failed)
    assert kept.notes == [None, "the network went away"]
    with pytest.raises(NotThere, match="isn't in the collections folder"):
        UploadersUseCases(Trapper([]), kept, None).upload(Account(), "NOPE", "R0001", "R0001-DONA_01", "upload", None, False)


def test_its_settings_are_its_own():
    from wildintel_uploader.modules.settings.infrastructure import schema  # noqa: F401 — the format of the sections is registered when the file is read
    assert settings_registry.get("TRAPPER").domain is TrapperSettings
    assert settings_registry.get("AGOUTI").schema.__module__ == "wildintel_uploader.modules.uploaders.infrastructure.settings"
