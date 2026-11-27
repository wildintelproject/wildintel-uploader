"""#248: the container of the app (Dishka) — what is made once for the app (Scope.APP) keeps no folder of the settings from when it was made: each
asks for them when it needs them, so a change to the settings while the app runs is heeded."""
import json
import types
from pathlib import Path

import pytest

from wildintel_uploader.entrypoints import config, wiring
from wildintel_uploader.modules.backup.domain.ports import BackupService
from wildintel_uploader.modules.fileinfo.domain.ports import FileInfoService
from wildintel_uploader.modules.postvalidation.domain.ports import PostvalidationService
from wildintel_uploader.modules.preprocessing.domain.ports import PreprocessingService
from wildintel_uploader.modules.prevalidation.domain.ports import PrevalidationService
from wildintel_uploader.modules.reports.domain.ports import ReportsService
from wildintel_uploader.modules.settings.domain.ports import ActivityLog, Machine, RecordStorage
from wildintel_uploader.modules.timefix.domain.ports import TimeFixService
from wildintel_uploader.modules.uploaders.domain.ports import UploadersService

MADE_ONCE = [ActivityLog, Machine, RecordStorage, FileInfoService, PrevalidationService, PostvalidationService, PreprocessingService, TimeFixService,
             UploadersService, BackupService, ReportsService]


def _paths_kept(obj, depth: int = 0, seen: set | None = None) -> list[Path]:
    """Every Path an object keeps — in its attributes, its collections and what its functions captured —, a few steps deep."""
    seen = set() if seen is None else seen
    if depth > 7 or id(obj) in seen or isinstance(obj, (type, types.ModuleType, str, bytes, int, float, bool)) or obj is None:
        return []
    seen.add(id(obj))
    if isinstance(obj, Path):
        return [obj]
    found: list[Path] = []
    if isinstance(obj, dict):
        items = list(obj.values())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        items = list(obj)
    elif isinstance(obj, types.MethodType):
        items = [obj.__self__, obj.__func__]
    elif isinstance(obj, types.FunctionType):
        items = [c.cell_contents for c in (obj.__closure__ or ()) if _filled(c)]
    else:
        items = list(getattr(obj, "__dict__", {}).values())
    for item in items:
        found += _paths_kept(item, depth + 1, seen)
    return found


def _filled(cell) -> bool:
    try:
        cell.cell_contents
    except ValueError:
        return False
    return True


@pytest.fixture
def first(tmp_path, monkeypatch) -> Path:
    """The folders of the settings when the app starts: all under one folder."""
    start = tmp_path / "start"
    monkeypatch.setattr(config, "collections_dir", lambda settings=None: start / "collections")
    monkeypatch.setattr(config, "reports_dir", lambda settings=None: start / "reports")
    monkeypatch.setattr(config, "packages_dir", lambda settings=None: start / "packages")
    monkeypatch.setattr(config, "data_dir", lambda settings=None: start)
    return start


@pytest.mark.parametrize("contract", MADE_ONCE, ids=lambda c: c.__name__)
def test_what_is_made_once_keeps_no_folder_of_the_settings(first: Path, contract):
    service = wiring.make_app_container().get(contract)
    kept = [p for p in _paths_kept(service) if p == first or first in p.parents]
    assert not kept, f"{contract.__name__} keeps {kept}: it should ask for the folder when it needs it"


def test_the_uploaders_and_the_backups_of_the_container_follow_the_collections_folder_when_it_changes(first: Path, tmp_path, monkeypatch):
    container = wiring.make_app_container()
    uploaders, backups = container.get(UploadersService), container.get(BackupService)
    then = tmp_path / "then"
    monkeypatch.setattr(config, "collections_dir", lambda settings=None: then)   # the data folder moved while the app runs

    from wildintel_uploader.modules.uploaders.infrastructure.packages import UPLOAD_LOG_FILE
    folder = then / "DONA" / "R0001" / "R0001-DONA_01"
    folder.mkdir(parents=True)
    (folder / UPLOAD_LOG_FILE).write_text(json.dumps({"uploaded_at": "2026-11-27T10:00:00Z", "parts": 1}), encoding="utf-8")
    from tests.support import built
    built.records(then).add_project({"acronym": "DONA", "name": "Doñana"})

    assert uploaders.uploads_of("DONA", "R0001-DONA_01")[0]["uploaded_at"] == "2026-11-27T10:00:00Z"
    assert [c["name"] for c in backups.describe("DONA")["collections"]] == ["R0001"]   # the research project and its collection of the folder of now
