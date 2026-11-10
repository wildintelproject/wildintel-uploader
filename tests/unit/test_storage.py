"""core/storage — where the records are kept: the JSON files of the collections folder, and the promise that another place is a backend to add, not a change to the app."""
import json
from pathlib import Path

import pytest

from wildintel_uploader.core import storage
from wildintel_uploader.core.services import local_folder_service as svc
from wildintel_uploader.core.storage import ProjectStore, StorageError


@pytest.fixture(autouse=True)
def json_again():
    """Whatever a test chose, the next one starts from the JSON files."""
    yield
    storage.configure("json")


# ── the JSON files ─────────────────────────────────────────────────────────────────────────────────────────────

def test_the_records_are_json_files_in_the_folder_of_the_research_project(tmp_path: Path):
    store = storage.open_store(tmp_path)
    store.add_project({"name": "Doñana", "acronym": "DONA"})
    store.write_records("DONA", "visits", [{"location_id": "DONA_01", "session": "R0001"}])

    assert json.loads((tmp_path / "DONA" / "research_project.json").read_text(encoding="utf-8"))["acronym"] == "DONA"
    assert json.loads((tmp_path / "DONA" / "visits.json").read_text(encoding="utf-8")) == [{"location_id": "DONA_01", "session": "R0001"}]
    assert store.read_records("DONA", "visits") == [{"location_id": "DONA_01", "session": "R0001"}]
    assert store.read_records("DONA", "cameras") == []                    # nothing kept yet
    assert [p["acronym"] for p in store.list_projects()] == ["DONA"]


def test_what_is_not_a_project_or_a_kind_of_record_is_refused(tmp_path: Path):
    store = storage.open_store(tmp_path)
    with pytest.raises(StorageError):
        store.has_project("../outside")                                    # an id names a folder
    store.add_project({"name": "Doñana", "acronym": "DONA"})
    with pytest.raises(StorageError):
        store.add_project({"name": "Doñana", "acronym": "DONA"})           # already kept
    with pytest.raises(StorageError):
        store.read_records("DONA", "photos")                               # not a kind of record
    with pytest.raises(StorageError):
        store.write_records("TATR", "visits", [])                          # a research project that is not kept


def test_nothing_is_left_half_written(tmp_path: Path):
    store = storage.open_store(tmp_path)
    store.add_project({"name": "Doñana", "acronym": "DONA"})
    store.write_records("DONA", "visits", [{"a": 1}])
    assert [p.name for p in (tmp_path / "DONA").iterdir() if p.name.endswith(".tmp")] == []


def test_the_backend_is_chosen_by_its_name():
    assert "json" in storage.available() and storage.selected() == "json"
    with pytest.raises(StorageError):
        storage.configure("oracle")


# ── another place for the records ──────────────────────────────────────────────────────────────────────────────

class MemoryStore(ProjectStore):
    """A backend written for this test, the way a database one would be: it keeps the records in memory. Nothing else of the app is told of it."""
    DATA: dict[str, dict] = {}

    def __init__(self, root: Path):
        self.root = root

    def list_projects(self): return [d["project"] for d in self.DATA.values()]
    def has_project(self, research_project_id): return storage.valid_project_id(research_project_id) in self.DATA
    def get_project(self, research_project_id): return self.DATA.get(research_project_id, {}).get("project")

    def add_project(self, project):
        if project["acronym"] in self.DATA:
            raise StorageError(f"The research project '{project['acronym']}' already exists.")
        self.DATA[project["acronym"]] = {"project": project, "records": {}}

    def save_project(self, research_project_id, project):
        if research_project_id not in self.DATA:
            raise StorageError(f"The research project '{research_project_id}' isn't in the collections folder.")
        self.DATA[research_project_id]["project"] = project

    def delete_project(self, research_project_id): self.DATA.pop(research_project_id, None)

    def read_records(self, research_project_id, kind):
        return [dict(r) for r in self.DATA.get(storage.valid_project_id(research_project_id), {}).get("records", {}).get(kind, [])]

    def write_records(self, research_project_id, kind, records):
        if research_project_id not in self.DATA:
            raise StorageError(f"The research project '{research_project_id}' isn't in the collections folder.")
        self.DATA[research_project_id]["records"][kind] = [dict(r) for r in records]

    def delete_records(self, research_project_id, kind): self.DATA.get(research_project_id, {}).get("records", {}).pop(kind, None)


def test_keeping_the_records_somewhere_else_is_adding_a_backend_and_the_app_goes_on_as_it_was(tmp_path: Path):
    MemoryStore.DATA = {}
    storage.register("memory", MemoryStore)
    try:
        _on_memory(tmp_path)
    finally:
        storage._FACTORIES.pop("memory", None)


def _on_memory(tmp_path: Path):
    storage.configure("memory")
    assert "memory" in storage.available()

    # the same functions the app uses, now on the other backend: projects, locations, visits, cameras
    svc.write_research_project(tmp_path, {"name": "Doñana", "acronym": "DONA"})
    svc.write_location(tmp_path, "DONA", {"location_id": "DONA_01", "latitude": 37.0, "longitude": -6.4, "timezone": "Europe/Madrid", "ignore_dst": False})
    svc.write_field_items(tmp_path, "DONA", "cameras", [{"label": "CAM-1", "camera_id": "BR1", "research_project": "DONA"}])
    told = svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_01", "session": "R0001", "date": "2024-09-04", "time": "13:10:00", "actions": ["Installation"]})

    assert not (tmp_path / "DONA" / "visits.json").exists()                           # none of it went to the JSON files
    assert [p["acronym"] for p in svc.list_research_projects(tmp_path)] == ["DONA"]
    assert svc.list_visits(tmp_path, "DONA")[0]["when"] == "2024-09-04T11:10:00Z"      # the rules are the services', whatever keeps the records
    assert told["created_at"] and told["created_at"] == told["updated_at"]
    assert svc.list_field_items(tmp_path, "DONA", "cameras")[0]["created_at"]

    # the rules of the services hold: a location with visits is not deleted, and the dates follow the changes
    with pytest.raises(svc.LocalFolderError):
        svc.delete_location(tmp_path, "DONA", "DONA_01")
    edited = svc.update_visit(tmp_path, "DONA", "DONA_01", "R0001", {**told, "comments": "x"})
    assert edited["created_at"] == told["created_at"]
    assert svc.delete_research_project(tmp_path, "DONA") == {"deleted": "DONA"}
    assert svc.list_research_projects(tmp_path) == []
