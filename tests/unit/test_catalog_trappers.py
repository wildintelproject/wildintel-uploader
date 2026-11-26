"""#248: the people of the catalog (modules.catalog) — their rules in the domain, the use cases over a repository in memory, taking those versions
before left in the settings, and the two entry points."""
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from wildintel_uploader.modules.catalog.application.use_cases import CatalogUseCases
from wildintel_uploader.modules.catalog.domain import rules
from wildintel_uploader.modules.catalog.domain.models import Audit, CatalogError, Trapper
from wildintel_uploader.modules.catalog.domain.ports import CatalogService


# ── the domain ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("make, field", [
    (lambda: Trapper(username="", name="Ana"), "username"),
    (lambda: Trapper(username="ana perez", name="Ana"), "username"),
    (lambda: Trapper(username="ana", name="   "), "name"),
    (lambda: Trapper(username="ana", name="Ana", email="not-an-email"), "email"),
    (lambda: Trapper(username="ana", name="Ana", status="retired"), "status"),
])
def test_a_trapper_that_cannot_be_is_refused_naming_what(make, field):
    with pytest.raises(CatalogError) as refused:
        make()
    assert refused.value.field == field


def test_a_trapper_is_tidied():
    t = Trapper(username=" ana ", name="  Ana   Pérez ", affiliation="  ", email=" ana@example.org ")
    assert (t.username, t.name, t.affiliation, t.email) == ("ana", "Ana Pérez", None, "ana@example.org")


def test_a_list_of_people_has_each_name_once_and_each_username_once_whatever_its_case():
    ana, again = Trapper(username="ana", name="Ana"), Trapper(username="ana2", name="Ana")
    gone = Trapper(username="old", name="Ana", audit=Audit(id="x", deleted_at="2026-01-01T00:00:00Z"))
    assert rules.checked_trappers([ana, again, gone]) == [ana, gone]          # the name once among those not removed; a removed one stays
    with pytest.raises(CatalogError) as refused:
        rules.checked_trappers([ana, Trapper(username="ANA", name="Other")])
    assert "is used by more than one trapper" in refused.value.message


def test_saving_a_list_of_people_knows_who_is_who_keeps_the_archived_removes_and_brings_back():
    ids = iter(f"id-{n}" for n in range(10))
    kept = rules.saved_trappers([], [Trapper(username="ana", name="Ana"), Trapper(username="luis", name="Luis"),
                                     Trapper(username="eva", name="Eva", status="archived")], "T1", lambda: next(ids))
    ana, luis, eva = kept
    assert (ana.audit.id, ana.audit.created_at, ana.audit.updated_at) == ("id-0", "T1", "T1")

    # renamed, by its id; Luis no longer listed; Eva archived: as she was
    second = rules.saved_trappers(kept, [replace(ana, username="ana.perez", name="Ana Pérez"), replace(eva, name="Changed")], "T2", lambda: next(ids))
    by_id = {t.audit.id: t for t in second}
    assert by_id["id-0"].username == "ana.perez" and by_id["id-0"].audit.updated_at == "T2" and by_id["id-0"].audit.created_at == "T1"
    assert by_id["id-1"].audit.deleted_at == "T2" and by_id["id-2"].name == "Eva"

    # Luis listed again, by his username: he comes back, as he was created; unchanged Ana keeps her date
    third = rules.saved_trappers(second, [by_id["id-0"], Trapper(username="luis", name="Luis")], "T3", lambda: next(ids))
    luis_back = next(t for t in third if t.username == "luis")
    assert (luis_back.audit.id, luis_back.deleted, luis_back.audit.created_at, luis_back.audit.updated_at) == ("id-1", False, "T1", "T3")
    assert next(t for t in third if t.audit.id == "id-0").audit.updated_at == "T2"


# ── the use cases, over a repository in memory ───────────────────────────────

class MemoryRepository:
    def __init__(self, trappers=None) -> None:
        self.kept, self.writes = list(trappers or []), 0

    def read_trappers(self):
        return list(self.kept)

    def write_trappers(self, trappers) -> None:
        self.kept, self.writes = list(trappers), self.writes + 1


class Legacy:
    def __init__(self, trappers=None) -> None:
        self.left = list(trappers or [])

    def take(self):
        taken, self.left = self.left, []
        return taken


class Clock:
    def now(self) -> str:
        return "2026-11-27T10:00:00Z"


def _catalog(repository=None, legacy=None) -> CatalogService:
    ids = iter(f"new-{n}" for n in range(100))
    return CatalogUseCases(repository or MemoryRepository(), legacy_trappers=legacy or Legacy(), clock=Clock(), new_id=lambda: next(ids))


def test_the_people_versions_before_left_in_the_settings_come_in_as_they_were_kept():
    old = Trapper(username="ana", name="Ana", audit=Audit(id="legacy-ana"))
    legacy, repository = Legacy([old]), MemoryRepository()
    catalog = _catalog(repository, legacy)

    assert catalog.trappers() == [old]                         # with the id the roles and the visits point to — not a new one
    assert legacy.left == [] and repository.kept == [old]
    assert catalog.trappers() == [old] and repository.writes == 1


def test_people_are_added_unless_their_username_is_taken_and_listed_without_the_removed():
    catalog = _catalog(MemoryRepository([Trapper(username="ana", name="Ana", audit=Audit(id="a")),
                                         Trapper(username="old", name="Old", audit=Audit(id="o", deleted_at="T0"))]))

    added = catalog.add_trappers([Trapper(username="ANA", name="Another"), Trapper(username="luis", name="Luis", status="inactive")])

    assert (added.added, added.skipped) == (["luis"], ["ANA"])
    assert [(t.username, t.status) for t in catalog.trappers()] == [("ana", "active"), ("luis", "active")]   # added as active
    assert [t.username for t in catalog.trappers(include_deleted=True)] == ["ana", "luis", "old"]


# ── the entry points ─────────────────────────────────────────────────────────

def test_the_web_api_lists_and_saves_the_people(tmp_path: Path):
    from unittest.mock import patch

    from wildintel_uploader.web.main import app

    with patch("wildintel_uploader.core.config.collections_dir", return_value=tmp_path):
        client = TestClient(app)
        assert client.post("/api/setup/trappers", json={"trappers": [{"username": "ana", "name": "Ana"}]}).json() == {"added": ["ana"], "skipped": []}
        listed = client.get("/api/catalog/trappers").json()
        assert [(t["username"], t["status"]) for t in listed] == [("ana", "active")] and listed[0]["id"]

        saved = client.put("/api/catalog/trappers", json=[{**listed[0], "name": "Ana Pérez"}, {"username": "luis", "name": "Luis"}]).json()
        assert [(t["username"], t["name"]) for t in saved] == [("ana", "Ana Pérez"), ("luis", "Luis")] and saved[0]["id"] == listed[0]["id"]
        refused = client.put("/api/catalog/trappers", json=[{"username": "a b", "name": "A"}])
        assert refused.status_code == 422 and refused.json()["detail"]["field"] == "username"
        assert len(client.get("/api/catalog/trappers", params={"include_deleted": True}).json()) == 2


def test_the_command_line_lists_and_adds_people(tmp_path: Path):
    from unittest.mock import patch

    from wildintel_uploader.cli.app import app as cli
    from wildintel_uploader.entrypoints.cli import injection

    injection._container = None      # a container of its own: made with the patched collections folder
    with patch("wildintel_uploader.core.config.collections_dir", return_value=tmp_path):
        run = CliRunner()
        assert run.invoke(cli, ["catalog", "trappers", "add", "ana", "Ana Pérez", "--email", "ana@example.org"]).exit_code == 0
        again = run.invoke(cli, ["catalog", "trappers", "add", "ANA", "Other"])
        assert again.exit_code == 1 and "already a trapper" in again.output
        assert run.invoke(cli, ["catalog", "trappers", "add", "a b", "X"]).exit_code == 1
        listed = run.invoke(cli, ["catalog", "trappers", "list"], terminal_width=300).output
        assert "Ana Pérez" in listed and "ana@example.org" in listed and "1 person" in listed
