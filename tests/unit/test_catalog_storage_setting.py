"""#248: where the catalog is kept is a setting of the module of the settings (DATA.catalog_storage, DATA.catalog_database), which the catalog asks
for through its contract; and moving it — the people and the research projects, as they are kept — from the JSON files to a SQLite database and
back."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from wildintel_uploader.entrypoints import config
from wildintel_uploader.modules.catalog.application.migration import TargetNotEmpty, copy_catalog
from wildintel_uploader.modules.catalog.domain.models import ResearchProject, Trapper
from wildintel_uploader.modules.settings.domain import folders
from wildintel_uploader.modules.settings.domain.models import DataSettings, SettingsError


# ── the settings ─────────────────────────────────────────────────────────────

def test_where_the_catalog_is_kept_is_a_setting_with_its_rules():
    assert (DataSettings().catalog_storage, DataSettings().catalog_database) == ("json", None)
    with pytest.raises(SettingsError) as refused:
        DataSettings(catalog_storage="oracle")
    assert refused.value.setting == "DATA.catalog_storage"
    with pytest.raises(SettingsError):
        DataSettings(catalog_database="relative/catalog.sqlite3")
    assert folders.catalog_database(DataSettings(), Path("/data")) == Path("/data/catalog.sqlite3")
    assert folders.catalog_database(DataSettings(catalog_database="/srv/c.db"), Path("/data")) == Path("/srv/c.db")


def test_the_database_of_the_catalog_follows_the_data_folder_like_the_folders():
    before = DataSettings(dir="/old", catalog_database="/old/db/catalog.sqlite3")
    assert folders.follow_data_dir(before, DataSettings(dir="/new", catalog_database="/old/db/catalog.sqlite3"), Path("/docs")).catalog_database == "/new/db/catalog.sqlite3"
    assert folders.follow_data_dir(before, DataSettings(dir="/new", catalog_database="/old/catalog.sqlite3"), Path("/docs")).catalog_database is None


# ── the copy, between any two repositories ───────────────────────────────────

class Memory:
    def __init__(self, trappers=(), projects=()) -> None:
        self.trappers, self.projects, self.locations = list(trappers), {p.acronym: p for p in projects}, {}

    def read_trappers(self):
        return list(self.trappers)

    def write_trappers(self, trappers) -> None:
        self.trappers = list(trappers)

    def read_projects(self):
        return list(self.projects.values())

    def read_project(self, acronym):
        return self.projects.get(acronym)

    def add_project(self, project) -> None:
        self.projects[project.acronym] = project

    def save_project(self, project) -> None:
        self.projects[project.acronym] = project

    def held_by_project(self, acronym):
        return []

    def read_locations(self, project):
        return list(self.locations.get(project, []))

    def write_locations(self, project, locations) -> None:
        self.locations[project] = list(locations)


def test_the_catalog_is_copied_as_it_is_kept_and_not_over_another_unless_asked():
    source = Memory([Trapper(username="ana", name="Ana")], [ResearchProject(acronym="DONA", name="Doñana")])
    target = Memory()
    copied = copy_catalog(source, target)
    assert (copied.trappers, copied.projects) == (1, 1) and target.read_trappers() == source.read_trappers()
    with pytest.raises(TargetNotEmpty):
        copy_catalog(source, target)
    assert copy_catalog(source, target, replace=True).projects == 1


# ── moving it, end to end ────────────────────────────────────────────────────

@pytest.fixture
def app_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The settings files and the data folder of the test."""
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "config" / "settings.toml")
    monkeypatch.setattr(config, "CONFIGS_DIR", tmp_path / "config" / "configs")
    monkeypatch.setattr(config, "ACTIVE_CONFIG_POINTER", tmp_path / "config" / "active-config")
    from wildintel_uploader.entrypoints.cli import injection
    injection._container = None
    assert CliRunner().invoke(_cli(), ["config", "set", "DATA.dir", str(tmp_path / "data")]).exit_code == 0
    return tmp_path / "data"


def _cli():
    from wildintel_uploader.entrypoints.cli.app import app
    return app


def test_the_catalog_is_moved_to_a_database_and_back(app_folders: Path):
    run, cli = CliRunner(), _cli()
    collections = app_folders / "collections"
    assert run.invoke(cli, ["catalog", "trappers", "add", "ana", "Ana"]).exit_code == 0
    assert run.invoke(cli, ["catalog", "projects", "add", "DONA", "Doñana"]).exit_code == 0
    assert "JSON files" in run.invoke(cli, ["catalog", "where"]).output

    moved = run.invoke(cli, ["catalog", "migrate", "--to", "sqlite"])
    assert moved.exit_code == 0 and "1 people and 1 research projects moved to sqlite" in moved.output
    assert config.load_settings().DATA.catalog_storage == "sqlite" and (app_folders / "catalog.sqlite3").is_file()
    assert str(app_folders / "catalog.sqlite3") in run.invoke(cli, ["catalog", "where"], terminal_width=300).output
    assert run.invoke(cli, ["catalog", "migrate", "--to", "sqlite"]).exit_code == 1           # there already

    # it is read from the database now: the JSON files left where they were are not
    (collections / "trappers.json").unlink()
    (collections / "DONA" / "research_project.json").unlink()
    assert "Ana" in run.invoke(cli, ["catalog", "trappers", "list"]).output
    assert run.invoke(cli, ["catalog", "projects", "add", "ALBA", "Albacete"]).exit_code == 0
    assert not (collections / "ALBA" / "research_project.json").exists() and (collections / "ALBA").is_dir()

    # and back: the place holds what was left there — written again here — so it is replaced only when asked
    (collections / "trappers.json").write_text('[{"username": "old", "name": "Old"}]', encoding="utf-8")
    refused = run.invoke(cli, ["catalog", "migrate", "--to", "json"])
    assert refused.exit_code == 1 and "already holds one" in refused.output
    assert run.invoke(cli, ["catalog", "migrate", "--to", "json", "--replace"]).exit_code == 0
    assert config.load_settings().DATA.catalog_storage == "json"
    listed = run.invoke(cli, ["catalog", "projects", "list"]).output
    assert "ALBA" in listed and "DONA" in listed and (collections / "ALBA" / "research_project.json").is_file()


def test_the_web_api_moves_the_catalog_and_the_settings_page_does_not_undo_it(app_folders: Path):
    from wildintel_uploader.web.main import app

    client = TestClient(app)
    assert client.post("/api/catalog/migrate", json={"to": "sqlite"}).json() == {"trappers": 0, "projects": 0}
    assert client.post("/api/catalog/migrate", json={"to": "sqlite"}).status_code == 422

    # the settings page sends its folders without saying where the catalog is: it is not its to change
    page = client.get("/api/settings").json()
    for name in ("catalog_storage", "catalog_database", "storage"):
        page["DATA"].pop(name, None)
    assert client.put("/api/settings", json=page).status_code == 200
    assert config.load_settings().DATA.catalog_storage == "sqlite"
