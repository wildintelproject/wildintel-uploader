"""#248: the use cases of the module of the settings, and the two entry points that drive them — the web API and the command line —, on settings
files of a folder of their own."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from wildintel_uploader.entrypoints.cli.app import app as cli
from wildintel_uploader.entrypoints import config
from wildintel_uploader.modules.settings.application.use_cases import SettingsUseCases
from wildintel_uploader.modules.settings.domain.models import SettingsError
from wildintel_uploader.modules.settings.domain.ports import NoLogFile, NoSettingsFile, SettingsService, UnknownConfig, UnknownSetting
from wildintel_uploader.modules.settings.infrastructure.toml_files import TomlSettingsStore


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TomlSettingsStore:
    """The settings files of a folder of their own — for the use cases, and for the entry points, which make their store from config."""
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "settings.toml")
    monkeypatch.setattr(config, "CONFIGS_DIR", tmp_path / "configs")
    monkeypatch.setattr(config, "ACTIVE_CONFIG_POINTER", tmp_path / "active-config")
    return config.settings_store()


class FakeLog:
    """The log of the app, for the use cases: a file of the test's folder, the levels applied, and a level the environment may force."""

    def __init__(self, folder: Path) -> None:
        self.path, self.applied, self.forced = folder / "app.log", [], None

    def file(self) -> Path:
        return self.path

    def level_override(self):
        return self.forced

    def apply_level(self, level: str) -> None:
        self.applied.append(level)

    def clear(self) -> int:
        existed = self.path.exists()
        self.path.unlink(missing_ok=True)
        return int(existed)


class FakeMachine:
    def cpu_count(self) -> int:
        return 12


class FakeStorage:
    """The backends of the records, for the use cases: "json" and "sqlite", and the ones put in use."""

    def __init__(self) -> None:
        self.used: list[str] = []

    def available(self):
        return ("json", "sqlite")

    def use(self, name: str) -> None:
        self.used.append(name)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def log(tmp_path: Path) -> FakeLog:
    return FakeLog(tmp_path)


@pytest.fixture
def service(store: TomlSettingsStore, tmp_path: Path, log: FakeLog, storage: FakeStorage) -> SettingsService:
    """The port in of the module, as its use cases implement it, with the log, the machine and the backends of the test."""
    return SettingsUseCases(store, tmp_path / "docs", activity_log=log, machine=FakeMachine(), record_storage=storage)


def test_the_use_cases_implement_every_operation_of_the_contract():
    offered = {name for name in vars(SettingsService) if not name.startswith("_")}
    assert offered and offered <= {name for name in vars(SettingsUseCases) if not name.startswith("_")}


# ── the use cases ────────────────────────────────────────────────────────────

def test_one_setting_is_changed_from_text_as_it_takes_it(store, service):
    service.change_setting("general.workers", "3")
    service.change_setting("GENERAL.show_welcome", "no")
    service.change_setting("POSTVALIDATION.tolerance_hours", "2.5")
    service.change_setting("TRAPPER.base_url", "https://trapper.example.org")
    service.change_setting("TRAPPER.user_name", "")                 # blank is none

    settings = store.load()
    assert (settings.general.workers, settings.general.show_welcome, settings.postvalidation.tolerance_hours) == (3, False, 2.5)
    assert settings.trapper.base_url == "https://trapper.example.org" and settings.trapper.user_name is None


@pytest.mark.parametrize("key, text, error", [
    ("GENERAL.nope", "1", UnknownSetting),
    ("NOPE.workers", "1", UnknownSetting),
    ("FIELDWORK.cameras", "x", UnknownSetting),         # not a setting: the field work of the research projects
    ("GENERAL.workers", "many", SettingsError),
    ("GENERAL.workers", "100", SettingsError),                   # the rule of the domain
    ("GENERAL.show_welcome", "perhaps", SettingsError),
    ("GENERAL.workers", "", SettingsError),                      # it can't be none
    ("VALIDATION.exif_fields", "Model", SettingsError),          # a list: the settings page, or settings.toml
])
def test_a_setting_that_cannot_be_changed_so_is_refused_and_nothing_is_saved(store, service, key, text, error):
    before = store.load()
    with pytest.raises(error):
        service.change_setting(key, text)
    assert store.load() == before


def test_the_settings_are_shown_with_the_secrets_out_of_sight(service):
    service.change_setting("TRAPPER.user_password", "s3cret")

    shown = service.shown_settings()

    assert "FIELDWORK" not in shown and list(shown)[0] == "GENERAL"
    password = next(s for s in shown["TRAPPER"] if s.key == "TRAPPER.user_password")
    assert (password.secret, password.saved, password.value) == (True, True, None)
    assert next(s for s in shown["AGOUTI"] if s.key == "AGOUTI.api_key").saved is False
    assert service.is_secret("trapper.user_password") and not service.is_secret("TRAPPER.base_url")


def test_the_data_folder_takes_the_folders_inside_it_along(store, service, tmp_path: Path):
    service.change_setting("DATA.dir", str(tmp_path / "old"))
    service.change_setting("DATA.reports_dir", str(tmp_path / "old" / "my-reports"))
    service.change_setting("DATA.packages_dir", str(tmp_path / "elsewhere"))

    assert service.set_data_dir(str(tmp_path / "new")) == tmp_path / "new"
    data = store.load().data
    assert data.reports_dir == str(tmp_path / "new" / "my-reports") and data.packages_dir == str(tmp_path / "elsewhere")
    assert service.set_data_dir(" ") == tmp_path / "docs"          # blank: the default one
    with pytest.raises(SettingsError):
        service.set_data_dir("relative")


def test_where_the_app_keeps_its_files(service, tmp_path: Path):
    places = service.places()
    assert (places.settings_file, places.data, places.collections, places.reports, places.packages) == (
        tmp_path / "settings.toml", tmp_path / "docs", tmp_path / "docs" / "collections", tmp_path / "docs" / "reports", tmp_path / "docs" / "packages")


def test_a_config_that_does_not_exist_or_has_no_file_is_said(service):
    with pytest.raises(UnknownConfig):
        service.activate_config("nope")
    with pytest.raises(UnknownConfig):
        service.config_file("nope")
    with pytest.raises(NoSettingsFile):
        service.config_file("default")             # nothing was read or saved yet


def test_the_general_section_is_shown_with_its_folders_and_what_the_system_says(service, store, log, tmp_path: Path):
    service.change_setting("DATA.reports_dir", "/mnt/reports")
    log.forced = "DEBUG"

    view = service.general()

    assert view.general == store.load().general
    assert (view.folders.reports_dir, view.folders.collections_dir) == ("/mnt/reports", None)
    assert (view.folders.default_dir, view.folders.default_collections_dir) == (tmp_path / "docs", tmp_path / "docs" / "collections")
    assert (view.system.cpu_count, view.system.max_workers, view.system.log_file, view.system.log_level_override) == (12, 64, log.path, "DEBUG")


def test_saving_the_general_section_keeps_the_rest_moves_the_folders_along_and_applies_the_level(service, store, log, tmp_path: Path):
    from wildintel_uploader.modules.settings.domain.models import DataSettings, GeneralSettings

    service.change_setting("DATA.dir", str(tmp_path / "old"))
    service.change_setting("DATA.storage", "json")
    service.change_setting("TRAPPER.base_url", "https://trapper.example.org")
    general = GeneralSettings(log_level="DEBUG", workers=6, default_research_project="DONA", show_welcome=False)

    view = service.save_general(general, DataSettings(dir=str(tmp_path / "new"), reports_dir=str(tmp_path / "old" / "reports-2026")))

    kept = store.load()
    assert kept.general == general and view.general == general and log.applied == ["DEBUG"]
    assert kept.data.dir == str(tmp_path / "new") and kept.data.reports_dir == str(tmp_path / "new" / "reports-2026")   # it was inside the old one
    assert kept.trapper.base_url == "https://trapper.example.org" and kept.data.storage == "json"                       # the rest, as it was


def test_the_log_file_is_given_once_there_is_one_and_cleared(service, log):
    with pytest.raises(NoLogFile):
        service.log_file()
    log.path.write_text("a line\n", encoding="utf-8")
    assert service.log_file() == log.path
    assert service.clear_log() == 1 and not log.path.exists()


def test_each_section_is_shown_with_its_secrets_out_of_sight_and_saved_by_the_same_rules(service, store):
    service.change_setting("TRAPPER.user_password", "s3cret")

    shown = service.section("trapper")
    assert shown.section == "TRAPPER" and "user_password" not in shown.values and shown.secrets == {"user_password": True}

    saved = service.save_section("TRAPPER", {"base_url": "  ", "user_name": "ana@example.org", "user_password": "", "max_zip_mb": 300})
    kept = store.load().trapper
    assert (kept.base_url, kept.user_name, kept.max_zip_mb) == (None, "ana@example.org", 300)   # blank is none
    assert kept.user_password == "s3cret" and saved.secrets == {"user_password": True}           # a secret left blank keeps the saved one
    service.save_section("VALIDATION", {"camera_levels": [["Make", "Model"]], "exif_fields": ["ISO", "iso"], "defaults": {"camera": "required"}})
    assert store.load().validation.camera_levels == (("Make", "Model"),) and store.load().validation.exif_fields == ("ISO",)
    assert service.save_section("EPICOLLECT5", {"mapping": {"location_id": "1_site"}}).values["mapping"] == {"location_id": "1_site"}


@pytest.mark.parametrize("section, values, error", [
    ("NOPE", {}, UnknownSetting),
    ("FIELDWORK", {"cameras": []}, UnknownSetting),
    ("TRAPPER", {"nope": 1}, UnknownSetting),
    ("TRAPPER", {"max_zip_mb": "300"}, SettingsError),        # a text where a whole number goes
    ("TRAPPER", {"enabled": "yes"}, SettingsError),
    ("TRAPPER", {"max_zip_mb": 0}, SettingsError),            # the rule of the domain
    ("VALIDATION", {"exif_fields": "Model"}, SettingsError),  # a list
    ("DATA", {"storage": "oracle"}, SettingsError),           # a storage there is not
])
def test_a_section_that_cannot_be_saved_so_is_refused_and_nothing_is_kept(service, store, section, values, error):
    before = store.load()
    with pytest.raises(error):
        service.save_section(section, values)
    assert store.load() == before


def test_saving_all_the_settings_keeps_the_secrets_follows_the_data_folder_and_puts_the_storage_and_the_level_in_use(service, store, log, storage, tmp_path: Path):
    from dataclasses import replace

    service.change_setting("AGOUTI.api_key", "k1")
    service.change_setting("DATA.dir", str(tmp_path / "old"))
    service.change_setting("DATA.reports_dir", str(tmp_path / "old" / "my-reports"))
    page = store.load()
    page = replace(page, agouti=replace(page.agouti, api_key=None), general=replace(page.general, log_level="ERROR"),
                   data=replace(page.data, dir=str(tmp_path / "new"), storage="sqlite"))

    saved = service.save_settings(page)

    assert saved.agouti.api_key == "k1" and store.load().agouti.api_key == "k1"
    assert saved.data.reports_dir == str(tmp_path / "new" / "my-reports")       # it was inside the old data folder
    assert storage.used[-1] == "sqlite" and log.applied[-1] == "ERROR"
    with pytest.raises(SettingsError) as refused:
        service.check_settings(replace(page, data=replace(page.data, storage="oracle")))
    assert refused.value.setting == "DATA.storage" and "there is no storage called 'oracle'" in refused.value.message


def test_config_set_can_clear_a_secret_on_purpose(service, store):
    service.change_setting("TRAPPER.user_password", "s3cret")
    service.change_setting("TRAPPER.user_password", "")
    assert store.load().trapper.user_password is None


# ── the command line ─────────────────────────────────────────────────────────

def test_the_command_line_lists_creates_and_switches_configs(store, tmp_path: Path):
    run = CliRunner()

    created = run.invoke(cli, ["config", "configs", "create", "Field season"], terminal_width=300)
    assert created.exit_code == 0 and "field-season" in created.output
    used = run.invoke(cli, ["config", "configs", "use", "field-season"], terminal_width=300)
    assert used.exit_code == 0 and store.active_id() == "field-season"
    assert run.invoke(cli, ["config", "configs", "use", "nope"]).exit_code == 1
    assert run.invoke(cli, ["config", "configs", "create", "!!"]).exit_code == 1

    listed = run.invoke(cli, ["config", "configs", "list"], terminal_width=300).output
    assert "default" in listed and "field-season" in listed


def test_the_command_line_sets_a_setting_and_says_why_one_cannot_be(store):
    run = CliRunner()

    assert run.invoke(cli, ["config", "set", "GENERAL.workers", "2"]).exit_code == 0 and store.load().general.workers == 2
    refused = run.invoke(cli, ["config", "set", "GENERAL.workers", "200"])
    assert refused.exit_code == 1 and "must be at least 1 and at most 64" in refused.output
    assert run.invoke(cli, ["config", "set", "GENERAL.nope", "1"]).exit_code == 1


def test_the_command_line_shows_one_section(store):
    run = CliRunner()
    shown = run.invoke(cli, ["config", "show", "trapper"], terminal_width=300).output
    assert "TRAPPER.max_zip_mb" in shown and "GENERAL" not in shown and "(not set)" in shown
    assert run.invoke(cli, ["config", "show", "nope"]).exit_code == 1


def test_the_command_line_says_where_the_files_are(store, tmp_path: Path):
    shown = CliRunner().invoke(cli, ["config", "path"], terminal_width=300)
    assert shown.exit_code == 0 and str(tmp_path / "settings.toml") in shown.output and "Packages:" in shown.output


def test_the_command_line_shows_the_general_section_and_the_log(store, tmp_path: Path):
    run = CliRunner()
    run.invoke(cli, ["config", "set", "GENERAL.workers", "3"])

    shown = run.invoke(cli, ["config", "general"], terminal_width=300)
    assert shown.exit_code == 0 and "Images at once" in shown.output and "3" in shown.output and "Collections" in shown.output
    assert run.invoke(cli, ["config", "log", "clear"], input="n\n").exit_code == 0        # asked, and not done
    assert run.invoke(cli, ["config", "log", "clear", "--yes"]).exit_code == 0


# ── the web API ──────────────────────────────────────────────────────────────

def test_the_web_api_of_the_settings_is_the_module_s(store, tmp_path: Path):
    from wildintel_uploader.web.main import app

    client = TestClient(app)
    assert [c["id"] for c in client.post("/api/settings/configs", json={"name": "B"}).json()] == ["default", "b"]
    assert client.put("/api/settings/show-welcome", json={"show": False}).json() == {"show_welcome": False}
    assert store.load().general.show_welcome is False
    assert client.put("/api/settings/data-dir", json={"dir": "relative"}).status_code == 422


# ── the wiring (dishka) ──────────────────────────────────────────────────────

def test_the_container_gives_the_contract_made_with_its_adapters(store):
    from wildintel_uploader.entrypoints import wiring

    container = wiring.make_app_container()
    with container() as request:            # a request's scope, as each request or command has
        service = request.get(SettingsService)
        assert isinstance(service, SettingsUseCases) and isinstance(service.store, TomlSettingsStore)
        assert request.get(SettingsService) is service     # one for the whole request
    container.close()


def test_the_routers_know_only_the_contract_so_another_implementation_can_be_given(tmp_path: Path):
    from dishka import Provider, Scope, make_container, provide
    from dishka.integrations.fastapi import setup_dishka
    from fastapi import FastAPI

    from wildintel_uploader.entrypoints.api import settings as router
    from wildintel_uploader.modules.settings.domain.ports import ConfigInfo

    class FakeSettings:
        def list_configs(self):
            return [ConfigInfo(id="fake", name="A fake", path="-", active=True)]

    class FakeProvider(Provider):
        @provide(scope=Scope.REQUEST)
        def service(self) -> SettingsService:
            return FakeSettings()  # type: ignore[return-value]

    app = FastAPI()
    setup_dishka(make_container(FakeProvider()), app)
    app.include_router(router.router)

    assert TestClient(app).get("/api/settings/configs").json() == [{"id": "fake", "name": "A fake", "path": "-", "active": True}]


def test_what_a_command_is_given_is_not_an_option_of_it():
    shown = CliRunner().invoke(cli, ["config", "show", "--help"], terminal_width=200).output
    assert "Show the settings" in shown and "--service" not in shown and "SERVICE" not in shown


def test_the_web_api_gives_and_saves_the_general_section(store, tmp_path: Path):
    from wildintel_uploader.web.main import app

    client = TestClient(app)
    shown = client.get("/api/settings/general").json()
    assert set(shown) == {"general", "folders", "system"} and shown["system"]["max_workers"] == 64
    assert shown["folders"]["default_collections_dir"].endswith("collections")

    saved = client.put("/api/settings/general", json={"log_level": "WARNING", "workers": 2, "default_research_project": " ", "show_welcome": False}).json()
    assert saved["general"] == {"log_level": "WARNING", "workers": 2, "default_research_project": None, "show_welcome": False}
    assert store.load().general.workers == 2

    refused = client.put("/api/settings/general", json={"log_level": "WARNING", "workers": 500})
    assert refused.status_code == 422 and refused.json()["detail"]["setting"] == "GENERAL.workers"
    assert client.put("/api/settings/general", json={"log_level": "WARNING", "workers": 2, "folders": {"dir": "relative"}}).status_code == 422
    assert store.load().general.workers == 2 and store.load().data.dir is None     # nothing of what was refused was kept


def test_the_web_api_gives_and_saves_each_section(store):
    from wildintel_uploader.web.main import app

    client = TestClient(app)
    client.put("/api/settings/sections/TRAPPER", json={"user_password": "s3cret"})
    shown = client.get("/api/settings/sections/trapper").json()
    assert shown["section"] == "TRAPPER" and shown["secrets"] == {"user_password": True} and "user_password" not in shown["values"]

    saved = client.put("/api/settings/sections/POSTVALIDATION", json={"tolerance_hours": 2.5, "similarity_method": "range"}).json()
    assert saved["values"]["tolerance_hours"] == 2.5 and store.load().postvalidation.similarity_method == "range"
    assert client.get("/api/settings/sections/NOPE").status_code == 404
    assert client.put("/api/settings/sections/TRAPPER", json={"nope": 1}).status_code == 404
    refused = client.put("/api/settings/sections/TRAPPER", json={"max_zip_mb": 0})
    assert refused.status_code == 422 and refused.json()["detail"]["setting"] == "TRAPPER.max_zip_mb"
