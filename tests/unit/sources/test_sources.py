"""#248: the sources of the visits (modules.sources) — each source a class in infrastructure/sources, over a fake Epicollect5; its settings,
EPICOLLECT5 and EPICOLLECTCSV, its own and registered with the module of the settings."""
import pytest

from wildintel_uploader.modules.settings.domain import models as _settings_models
from wildintel_uploader.modules.settings.infrastructure import schema
from wildintel_uploader.modules.sources.application.use_cases import SourcesUseCases
from wildintel_uploader.modules.sources.domain.models import SourceError
from wildintel_uploader.modules.sources.domain.settings import Epicollect5Settings
from wildintel_uploader.modules.sources.infrastructure import sources
from wildintel_uploader.modules.sources.infrastructure.sources.epicollect_csv import form_columns, form_error

INPUTS = [{"ref": "r_loc", "question": "locationID", "type": "text"}, {"ref": "r_date", "question": "Date", "type": "date"},
          {"ref": "r_status", "question": "Status of the camera", "type": "radio"}, {"ref": "r_action", "question": "Action", "type": "radio"}]
PROJECT = {"data": {"project": {"name": "Field flow", "slug": "field-flow", "forms": [{"name": "Visit", "inputs": INPUTS}]}}}


class FakeEpicollect:
    def __init__(self, entries=()) -> None:
        self.read, self.given = [], list(entries)

    def project(self, slug, client_id, client_secret):
        self.read.append((slug, client_id, client_secret))
        return PROJECT

    def entries(self, slug, client_id, client_secret):
        return self.given

    def forget_tokens(self):
        pass


class Saved:
    def __init__(self, **values) -> None:
        self.values = values

    def epicollect5(self):
        return Epicollect5Settings(**self.values)


def _sources(epicollect, **saved) -> SourcesUseCases:
    return SourcesUseCases(epicollect, Saved(**saved), sources.SOURCES, form_columns=form_columns, form_error=form_error)


def test_the_sources_are_known_by_their_keys():
    assert [s.key for s in sources.SOURCES] == ["epicollect-api", "epicollect-csv"]
    with pytest.raises(SourceError, match="no source"):
        _sources(FakeEpicollect()).visits("nope")


def test_the_entries_of_the_project_become_rows_of_a_visit():
    entry = {"created_at": "2026-10-02T08:00:00Z", "r_loc": "DONA_01", "r_date": "02/10/2026", "r_status": "OK", "r_action": "Camera inspection"}
    rows = _sources(FakeEpicollect([entry]), project_slug="field-flow").visits("epicollect-api")
    assert "DONA_01,,2026-10-02" in rows.csv and ",Revision," in rows.csv and rows.time_source is None


def test_a_saved_secret_is_used_for_its_client_and_none_is_read_without_a_slug():
    epicollect = FakeEpicollect()
    service = _sources(epicollect, project_slug="field-flow", client_id="id", client_secret="s3cret")
    assert service.test_connection("field-flow", "id", None)["inputs"] == 4 and epicollect.read == [("field-flow", "id", "s3cret")]
    with pytest.raises(SourceError, match="slug first"):
        service.test_connection(" ", None, None)
    with pytest.raises(SourceError, match="no Epicollect5 project"):
        _sources(epicollect).project_form()


def test_the_entries_of_a_deployment_need_the_location_mapped():
    entries = [{"ec5_uuid": "u1", "created_at": "2026-10-01", "r_loc": "DONA_01"}, {"ec5_uuid": "u2", "created_at": "2026-10-02", "r_loc": "dona_01"}]
    service = _sources(FakeEpicollect(entries), enabled=True, project_slug="p", mapping={"location_id": "r_loc"})
    assert [e["uuid"] for e in service.deployment_entries(["DONA_01"], None)["dona_01"]] == ["u2", "u1"]
    with pytest.raises(SourceError, match="not mapped"):
        _sources(FakeEpicollect(), enabled=True, project_slug="p").deployment_entries(["DONA_01"], None)


def test_its_settings_are_its_own():
    assert _section("EPICOLLECT5").domain is Epicollect5Settings
    assert schema.SCHEMAS["EPICOLLECTCSV"].__module__ == "wildintel_uploader.modules.sources.infrastructure.settings"


def _section(name: str):
    return next(x for x in _settings_models.SECTIONS if x.name == name)
