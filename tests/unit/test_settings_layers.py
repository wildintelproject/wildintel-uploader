"""#248: the module of the settings — its domain (dataclasses and their rules), the mapping to the format of the files, the TOML adapter of the
SettingsStore port in a folder of its own, and the pure rules of the folders."""
from dataclasses import replace
from pathlib import Path

import pytest

from wildintel_uploader.modules.settings.domain.ports import ConfigInfo, SettingsStore
from wildintel_uploader.modules.settings.domain import folders
from wildintel_uploader.modules.settings.domain import models as domain
from wildintel_uploader.modules.settings.infrastructure import schema
from wildintel_uploader.modules.settings.infrastructure.mapping import to_domain, to_schema
from wildintel_uploader.modules.settings.infrastructure.toml_files import TomlSettingsStore


# ── the domain ───────────────────────────────────────────────────────────────

def test_the_defaults_of_the_domain_are_those_of_the_files():
    assert to_domain(schema.Settings()) == domain.Settings()


@pytest.mark.parametrize("make, setting", [
    (lambda: domain.GeneralSettings(workers=0), "GENERAL.workers"),
    (lambda: domain.GeneralSettings(workers=65), "GENERAL.workers"),
    (lambda: domain.GeneralSettings(log_level="LOUD"), "GENERAL.log_level"),
    (lambda: domain.TrapperSettings(max_zip_mb=5001), "TRAPPER.max_zip_mb"),
    (lambda: domain.DataSettings(dir="relative/folder"), "DATA.dir"),
    (lambda: domain.ValidationSettings(exif_fields=("Bad Name",)), "VALIDATION.exif_fields"),
    (lambda: domain.ValidationSettings(defaults={"nope": "warn"}), "VALIDATION.defaults"),
    (lambda: domain.ValidationSettings(defaults={"corrupted": "maybe"}), "VALIDATION.defaults.corrupted"),
    (lambda: domain.PostvalidationSettings(sequence_gap_seconds=0), "POSTVALIDATION.sequence_gap_seconds"),
    (lambda: domain.PostvalidationSettings(similarity_method="mode"), "POSTVALIDATION.similarity_method"),
    (lambda: domain.PreprocessingSettings(resize_width=50), "PREPROCESSING.resize_width"),
    (lambda: domain.FieldlogSettings(time_source="sundial"), "FIELDLOG.time_source"),
])
def test_a_setting_that_cannot_be_is_refused_naming_it(make, setting):
    with pytest.raises(domain.SettingsError) as refused:
        make()
    assert refused.value.setting == setting


def test_the_domain_tidies_what_it_only_has_to_tidy():
    assert domain.GeneralSettings(default_research_project="  ").default_research_project is None
    assert domain.DataSettings(dir="  ~/data ", reports_dir="").dir == "~/data" and domain.DataSettings(reports_dir="").reports_dir is None
    validation = domain.ValidationSettings(camera_levels=(("Model", "model", "Make"), ("MODEL", "make"), (), "SerialNumber"),
                                           exif_fields=(" ISO ", "iso", "DateTimeOriginal"), defaults={"exif": "required"})
    assert validation.camera_levels == (("Model", "Make"), ("SerialNumber",))   # each field once, each level once, the empty one left out
    assert validation.exif_fields == ("ISO",)                                   # the capture date is always expected
    assert validation.defaults == {**domain.IMAGE_CHECK_DEFAULTS, "exif": "required"}
    assert domain.PreprocessingSettings(owner="  Doñana  ").owner == "Doñana"


def test_a_change_is_a_new_value():
    general = domain.GeneralSettings(workers=2)
    with pytest.raises(AttributeError):
        general.workers = 3  # type: ignore[misc]
    assert replace(general, workers=3).workers == 3 and general.workers == 2
    with pytest.raises(domain.SettingsError):
        replace(general, workers=100)


def test_the_secrets_are_the_same_whether_the_domain_or_the_file_says_them():
    from wildintel_uploader.modules.settings.infrastructure.schema import secret_fields as of_the_file
    assert domain.secret_fields() == of_the_file() == (("TRAPPER", "user_password"), ("EPICOLLECT5", "client_secret"), ("AGOUTI", "api_key"))


# ── the mapping ──────────────────────────────────────────────────────────────

FULL = {
    "GENERAL": {"log_level": "DEBUG", "workers": 3, "default_research_project": "DONA", "show_welcome": False},
    "TRAPPER": {"base_url": "https://trapper.example.org", "user_name": "ana@example.org", "user_password": "s3cret", "max_zip_mb": 200},
    "EPICOLLECT5": {"enabled": True, "project_slug": "wildintel", "client_secret": "x", "mapping": {"location_id": "1_site"}},
    "AGOUTI": {"enabled": True, "base_url": "https://api.agouti.eu", "api_key": "k", "project_id": "p1"},
    "DATA": {"dir": "/srv/wild", "packages_dir": "/mnt/packages"},
    "VALIDATION": {"camera_levels": [["Make", "Model"]], "exif_fields": ["Model", "ISO"], "defaults": {"corrupted": "required"}},
    "POSTVALIDATION": {"photo_count": False, "similarity_method": "range", "tolerance_hours": 2.5, "defaults": {"camera": "skip"}},
    "PREPROCESSING": {"resize_width": 1920, "owner": "EBD-CSIC", "convert_to_utc": False},
    "FIELDLOG": {"time_source": "hour", "keep_seconds": True},
    "FIELDWORK": {"cameras": [{"label": "43", "research_project": "DONA", "camera_make": "RECONYX"}], "sd_cards": [{"label": "A1", "research_project": "DONA"}],
                  "trappers": [{"username": "ana", "name": "Ana Pérez"}], "roles": [{"research_project": "DONA", "trapper": "Ana Pérez", "role": "contact"}]},
}


def test_the_file_goes_to_the_domain_and_back_as_it_was():
    kept = schema.Settings.model_validate(FULL)

    settings = to_domain(kept)

    assert settings.general.workers == 3 and settings.trapper.user_password == "s3cret" and settings.data.packages_dir == "/mnt/packages"
    assert settings.validation.camera_levels == (("Make", "Model"),) and settings.postvalidation.defaults["camera"] == "skip"
    assert settings.legacy_fieldwork.cameras[0]["camera_make"] == "RECONYX"   # what is still to be moved to the research projects, as it was
    assert to_schema(settings) == kept


# ── the adapter of the port ──────────────────────────────────────────────────

def _store(tmp_path: Path) -> SettingsStore:
    return TomlSettingsStore(tmp_path / "settings.toml", tmp_path / "configs", tmp_path / "active-config")


def test_the_first_load_writes_the_defaults_and_a_save_is_read_back(tmp_path: Path):
    store = _store(tmp_path)

    assert store.load() == domain.Settings() and (tmp_path / "settings.toml").is_file()
    changed = replace(domain.Settings(), general=domain.GeneralSettings(workers=3, default_research_project="DONA"))
    store.save(changed)
    assert store.load() == changed
    assert "[GENERAL]" in (tmp_path / "settings.toml").read_text(encoding="utf-8")   # the file keeps its own format
    assert not list(tmp_path.glob(".settings.toml.*.tmp"))                            # written to a file of its own and put in place


def test_configs_are_created_named_safely_and_uniquely_and_one_is_active(tmp_path: Path):
    store = _store(tmp_path)

    assert store.create("Field season 2026") == "field-season-2026"
    assert store.create("field season 2026!") == "field-season-2026-2"
    with pytest.raises(ValueError):
        store.create("¡¡ !!")
    assert [c.id for c in store.list()] == ["default", "field-season-2026", "field-season-2026-2"]
    assert store.active_id() == "default"                 # creating one does not make it the active one

    store.set_active("field-season-2026")
    store.save(replace(domain.Settings(), general=domain.GeneralSettings(workers=2)))
    assert store.list()[1] == ConfigInfo(id="field-season-2026", name="field-season-2026", path=str(tmp_path / "configs" / "field-season-2026.toml"), active=True)
    assert store.load().general.workers == 2
    assert store.path_of("default") == tmp_path / "settings.toml"
    with pytest.raises(KeyError):
        store.set_active("nope")
    with pytest.raises(KeyError):
        store.path_of("nope")


def test_a_pointer_to_a_config_that_is_gone_means_the_default(tmp_path: Path):
    store = _store(tmp_path)
    (tmp_path / "active-config").write_text("gone", encoding="utf-8")
    assert store.active_id() == "default" and store.active_path() == tmp_path / "settings.toml"


# ── the folders ──────────────────────────────────────────────────────────────

def test_the_folders_are_their_own_when_the_settings_say_one_else_inside_the_data_folder():
    plain = domain.DataSettings()
    assert folders.data_dir(plain, Path("/docs/app")) == Path("/docs/app")
    assert folders.collections_dir(plain, Path("/data")) == Path("/data/collections")
    assert folders.reports_dir(plain, Path("/data")) == Path("/data/reports")
    assert folders.packages_dir(plain, Path("/data")) == Path("/data/packages")

    own = domain.DataSettings(dir="/srv/wild", collections_dir="/mnt/big/collections", packages_dir="~/packages")
    assert folders.data_dir(own, Path("/docs/app")) == Path("/srv/wild")
    assert folders.collections_dir(own, Path("/srv/wild")) == Path("/mnt/big/collections")
    assert folders.packages_dir(own, Path("/srv/wild")) == Path("~/packages").expanduser()
    assert folders.reports_dir(own, Path("/srv/wild")) == Path("/srv/wild/reports")
