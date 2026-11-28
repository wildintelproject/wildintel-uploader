"""#248: the uploaders (modules.uploaders) — what TRAPPER and the network refuse, as the module's errors with the words the pages have always shown;
an upload that fails is written down, and one that works clears it; TRAPPER and AGOUTI are its settings."""
from pathlib import Path

import httpx
import pytest

from tests.support.unused import unused
from trapper_client import err

from wildintel_uploader.modules.settings.domain import models as _settings_models
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

    def has_deployment(self, collection_dir, deployment_id):
        return (collection_dir / deployment_id).is_dir()

    def note_failure(self, project, deployment_id, destination, note):
        self.notes.append(note)


class Sending:
    """The upload itself: what it tells."""

    def __init__(self, events) -> None:
        self.events = events

    def upload(self, *args, **kwargs):
        return iter(self.events)


class Places:
    def packages_dir(self, project):
        return Path("/packages") / project

    def max_zip_bytes(self):
        return 1


def _uploaders(events, kept):
    return UploadersUseCases(Trapper(events), kept, unused("reports"), unused("uploads"), sending=Sending(events), places=Places(),
                             deployments=unused("deployments"), syncing=unused("syncing"))


def _failing():
    yield {"type": "start"}
    raise RuntimeError("the network went away")


def test_an_upload_that_fails_is_written_down_and_one_that_works_clears_it(tmp_path: Path):
    (tmp_path / "R0001" / "R0001-DONA_01").mkdir(parents=True)
    kept = Kept(tmp_path)
    done = _uploaders([{"type": "done"}], kept).upload(Account(), "DONA", "R0001", "R0001-DONA_01", "upload", None, False)
    assert list(done) == [{"type": "done"}] and kept.notes == [None]
    failed = _uploaders(_failing(), kept).upload(Account(), "DONA", "R0001", "R0001-DONA_01", "upload", None, False)
    with pytest.raises(UploaderError, match="the network went away"):
        list(failed)
    assert kept.notes == [None, "the network went away"]
    with pytest.raises(NotThere, match="isn't in the collections folder"):
        _uploaders([], kept).upload(Account(), "NOPE", "R0001", "R0001-DONA_01", "upload", None, False)


def test_its_settings_are_its_own():
    from wildintel_uploader.modules.settings.infrastructure import schema  # noqa: F401 — the format of the sections is registered when the file is read
    assert _section("TRAPPER").domain is TrapperSettings
    assert schema.SCHEMAS["AGOUTI"].__module__ == "wildintel_uploader.modules.uploaders.infrastructure.settings"


class Organizer:
    def organize(self, research_project_id, source_dir, deployment):
        return Path("/collections/DONA/R0001/R0001-DONA_01"), iter([{"type": "copy", "index": 1, "total": 1, "name": "a.jpg"}])


class Deployment:
    deployment_id, location_id = "R0001-DONA_01", "DONA_01"


class Registering(Trapper):
    def __init__(self) -> None:
        super().__init__([])
        self.registered = []

    def register(self, credentials, rp, cp, deployment, timezone, ignore_dst):
        self.registered.append((timezone, ignore_dst))


class NoTime:
    def location_time(self, project, location_id):
        return {}


def test_a_deployment_is_organized_by_the_deployments_and_then_registered():
    trapper = Registering()
    service = UploadersUseCases(trapper, NoTime(), unused("reports"), unused("uploads"), deployments=Organizer, sending=unused("sending"),
                                places=unused("places"), syncing=unused("syncing"))
    events = list(service.import_deployment(Account(), 2, None, "src", Deployment(), "DONA", True, timezone="Europe/Madrid"))
    assert [e["type"] for e in events] == ["copy", "registering", "done"] and trapper.registered == [("Europe/Madrid", False)]
    with pytest.raises(UploaderError, match="A timezone is required"):
        service.import_deployment(Account(), 2, None, "src", Deployment(), "DONA", True)


# ── an upload, over ports in memory: no SDK, no disk ─────────────────────────

class Site:
    def __init__(self) -> None:
        self.made, self.sent, self.processed = [], [], []

    def research_projects(self, c):
        return [{"pk": 2, "acronym": "DONA", "name": "Doñana"}]

    def classification_projects(self, c, pk):
        return [{"pk": 7, "name": "Doñana classification"}]

    def locations(self, c, pk):
        return [{"pk": 1, "location_id": "dona_01", "timezone": "Europe/Madrid", "ignore_dst": False}] if "location" in self.made else []

    def deployments(self, c, pk):
        return [{"pk": 3, "deployment_id": "r0001-dona_01"}] if "deployment" in self.made else []

    def create_location(self, c, pk, deployment, timezone, ignore_dst):
        self.made.append("location")

    def create_deployment(self, c, pk, deployment, timezone, ignore_dst, location_id):
        self.made.append("deployment")
        assert location_id == "dona_01"                     # named as TRAPPER has it

    def log_in_to_uploader(self, c):
        pass

    def upload_file(self, c, path, report):
        self.sent.append(path.name)

    def process(self, c, yaml_name, zip_name, remove_zip):
        self.processed.append((yaml_name, zip_name))

    def collection(self, c, pk, name):
        return {"pk": 26, "name": name}


class KeptHere:
    def __init__(self) -> None:
        self.marked = None

    def metadata(self, d):
        return {"deployment_id": "R0001-DONA_01", "location_id": "DONA_01"}

    def preprocessing(self, d):
        return {"images": [{"name": "a.jpg", "date": "2026-01-01T10:00:00+00:00"}, {"name": "b.jpg", "date": "2026-01-01T11:00:00+00:00"}],
                "options": {"timezone": "UTC", "ignore_dst": True}}

    def as_deployment(self, metadata):
        from types import SimpleNamespace
        return SimpleNamespace(camera_model="X", longitude=1, latitude=2, start_date=None, end_date=None, **metadata)

    def missing(self, d, names):
        return []

    def sizes(self, d, names):
        return [10 for _ in names]

    def mark_uploaded(self, d, record):
        self.marked = record


class PackagesHere:
    def __init__(self) -> None:
        self.parts, self.rows, self.removed = [], [], []

    def build(self, output_dir, parts, progress):
        from wildintel_uploader.modules.uploaders.domain.ports import Package
        self.parts = parts
        return [Package(output_dir / f"{p.base}.yaml", output_dir / f"{p.base}.zip", len(p.entries)) for p in parts]

    def size(self, paths):
        return 100

    def file_sizes(self, paths):
        return {}

    def upsert_csv(self, path, row):
        self.rows.append(row)
        return {"path": str(path), "action": "added", "rows": 1}

    def remove_from_csv(self, path, deployment_id):
        pass

    def remove(self, packages, output_dir):
        self.removed += packages


def test_an_upload_creates_what_trapper_lacks_declares_the_locations_time_and_marks_the_deployment_over_any_ports():
    from wildintel_uploader.modules.uploaders.application.upload import TrapperUploads

    site, kept, packages = Site(), KeptHere(), PackagesHere()
    uploads = TrapperUploads(site, kept, packages, sleep=lambda s: None)
    events = list(uploads.upload(("https://t.org", "ana", "pw"), {"acronym": "DONA"}, Path("/c/R0001"), "R0001-DONA_01", Path("/packages"),
                                 max_zip_bytes=10))

    assert site.made == ["location", "deployment"] and len(site.processed) == 2              # two parts: 10 bytes each, at most 10 a zip
    assert [(p.timezone, p.ignore_dst, p.named, p.collection) for p in packages.parts][0] == ("Europe/Madrid", False, "r0001-dona_01", "DONA-R0001")
    assert kept.marked["collection_url"] == "https://t.org/storage/collection/detail/26/" and events[-1]["files_deleted"] is True
    dry = list(TrapperUploads(Site(), KeptHere(), PackagesHere()).upload(("https://t.org", "ana", "pw"), {"acronym": "DONA"}, Path("/c/R0001"),
                                                                           "R0001-DONA_01", Path("/p"), mode="dry_run"))
    assert dry[-1] == {"type": "done", "mode": "dry_run", "collection": "R0001", "deployment_id": "R0001-DONA_01", "would_create_location": True,
                       "would_create_deployment": True, "parts": 1}


def test_the_uploaders_made_once_follow_the_collections_folder_when_it_changes(tmp_path, monkeypatch):
    """The uploaders are made once for the app (Scope.APP): the collections folder is asked each time, not kept from when they were made."""
    import json

    from wildintel_uploader.entrypoints import config, wiring
    from wildintel_uploader.modules.uploaders.infrastructure.packages import UPLOAD_LOG_FILE
    first, then = tmp_path / "first", tmp_path / "then"
    monkeypatch.setattr(config, "collections_dir", lambda settings=None: first)
    uploaders = wiring.build_uploaders()
    monkeypatch.setattr(config, "collections_dir", lambda settings=None: then)   # the data folder moved while the app runs
    folder = then / "DONA" / "R0001" / "R0001-DONA_01"
    folder.mkdir(parents=True)
    (folder / UPLOAD_LOG_FILE).write_text(json.dumps({"uploaded_at": "2026-11-27T10:00:00Z", "parts": 1}), encoding="utf-8")

    [upload] = uploaders.uploads_of("DONA", "R0001-DONA_01")
    assert upload["kind"] == "uploaded" and upload["uploaded_at"] == "2026-11-27T10:00:00Z"


def _section(name: str):
    return next(x for x in _settings_models.SECTIONS if x.name == name)
