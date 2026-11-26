"""#248: the use cases of the module of the settings, and the two entry points that drive them — the web API and the command line —, on settings
files of a folder of their own."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from wildintel_uploader.cli.app import app as cli
from wildintel_uploader.core import config
from wildintel_uploader.modules.settings.application.use_cases import SettingsUseCases
from wildintel_uploader.modules.settings.domain.models import SettingsError
from wildintel_uploader.modules.settings.domain.ports import NoSettingsFile, SettingsService, UnknownConfig, UnknownSetting
from wildintel_uploader.modules.settings.infrastructure.toml_files import TomlSettingsStore


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TomlSettingsStore:
    """The settings files of a folder of their own — for the use cases, and for the entry points, which make their store from config."""
    monkeypatch.setattr(config, "DEFAULT_CONFIG_FILE", tmp_path / "settings.toml")
    monkeypatch.setattr(config, "CONFIGS_DIR", tmp_path / "configs")
    monkeypatch.setattr(config, "ACTIVE_CONFIG_POINTER", tmp_path / "active-config")
    return config.settings_store()


@pytest.fixture
def service(store: TomlSettingsStore, tmp_path: Path) -> SettingsService:
    """The port in of the module, as its use cases implement it."""
    return SettingsUseCases(store, tmp_path / "docs")


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


def test_the_command_line_says_where_the_files_are(store, tmp_path: Path):
    shown = CliRunner().invoke(cli, ["config", "path"], terminal_width=300)
    assert shown.exit_code == 0 and str(tmp_path / "settings.toml") in shown.output and "Packages:" in shown.output


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
    assert "Show every setting" in shown and "--service" not in shown and "SERVICE" not in shown
