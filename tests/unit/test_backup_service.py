"""Backups of the settings and of a research project, and their restoration (services.backup_service)."""
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from wildintel_uploader.entrypoints import config
from tests.support import built
from wildintel_uploader.modules.backup.domain.archive import FORMAT
from wildintel_uploader.modules.backup.domain.ports import BackupError, Choice


def _project(root: Path, acronym: str = "DONA") -> Path:
    built.records(root).add_project({"name": "Doñana", "acronym": acronym})
    pdir = root / acronym
    (pdir / "locations.json").write_text(json.dumps([{"location_id": "DONA_01", "status": "active"}, {"location_id": "DONA_02", "status": "archived"}]), encoding="utf-8")
    (pdir / "cameras.json").write_text(json.dumps([{"label": "CAM-1", "camera_id": "BR1", "status": "active"}]), encoding="utf-8")
    (pdir / "sd_cards.json").write_text(json.dumps([{"label": "A13", "status": "active"}]), encoding="utf-8")
    (pdir / "visits.json").write_text(json.dumps([
        {"location_id": "DONA_01", "session": "R0001", "date": "2026-06-10", "time": "09:00:00", "when": "2026-06-10T09:00:00Z", "actions": ["Installation"]},
        {"location_id": "DONA_01", "session": "R0002", "date": "2026-08-05", "time": "09:00:00", "when": "2026-08-05T09:00:00Z", "actions": ["Revision"]},
    ]), encoding="utf-8")
    folder = pdir / "R0001" / "R0001-DONA_01"
    folder.mkdir(parents=True)
    (folder / "deployment.json").write_text(json.dumps({"deployment_id": "R0001-DONA_01"}), encoding="utf-8")
    (folder / "images.json").write_text("{}", encoding="utf-8")
    (folder / "IMG_0001.JPG").write_bytes(b"jpeg-1")
    (folder / "IMG_0002.JPG").write_bytes(b"jpeg-22")
    (pdir / "R0001" / "collection.json").write_text(json.dumps({"name": "R0001"}), encoding="utf-8")
    (pdir / "R0001" / "R0001_FileTimestampLog.csv").write_text("Deployment\n", encoding="utf-8")
    return pdir


def _make(root: Path, dest: Path, **options) -> dict:
    kwargs = dict(settings=False, research_project_id="DONA", project_files=True, visits=True, deployments=["R0001-DONA_01"], images=False, app_version="9.9.9")
    o = {**kwargs, **options}
    events = list(built.backup(root, o["app_version"]).create(dest, o["research_project_id"], Choice(o["settings"], o["project_files"], o["visits"], list(o["deployments"]), o["images"])))
    assert events[-1]["type"] == "done"
    return events[-1]


def test_a_project_says_what_can_be_put_in_a_backup(tmp_path: Path):
    _project(tmp_path)

    info = built.backup(tmp_path).describe("DONA")

    assert (info["locations"], info["cameras"], info["sd_cards"], info["visits"]) == (2, 1, 1, 2)
    [collection] = info["collections"]
    [deployment] = collection["deployments"]
    assert collection["name"] == "R0001"
    assert (deployment["id"], deployment["images"], deployment["image_bytes"], deployment["files"]) == ("R0001-DONA_01", 2, len(b"jpeg-1") + len(b"jpeg-22"), 4)


def test_a_backup_holds_what_was_chosen_and_says_so_and_the_images_only_when_asked(tmp_path: Path):
    _project(tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()

    without = _make(tmp_path, dest)
    with zipfile.ZipFile(without["path"]) as zf:
        names = set(zf.namelist())
    assert {"manifest.json", "project/locations.json", "project/visits.json", "deployments/R0001/R0001-DONA_01/deployment.json", "deployments/R0001/collection.json",
            "deployments/R0001/R0001_FileTimestampLog.csv"} <= names
    assert not any(n.endswith(".JPG") for n in names)
    assert without["manifest"]["scope"]["images"] is False and without["manifest"]["secrets_included"] is False
    assert without["manifest"]["counts"] == {"locations": 2, "cameras": 1, "sd_cards": 1, "visits": 2} and without["manifest"]["app_version"] == "9.9.9"

    with_images = _make(tmp_path, dest, images=True)
    with zipfile.ZipFile(with_images["path"]) as zf:
        assert "deployments/R0001/R0001-DONA_01/IMG_0001.JPG" in zf.namelist()
    assert with_images["bytes"] > without["bytes"]


def test_the_settings_go_with_no_passwords_nor_the_folders_of_this_computer(tmp_path: Path):
    settings = config.Settings()
    settings.TRAPPER.user_password = "trapper-secret"
    settings.TRAPPER.user_name = "ana@x.org"
    settings.EPICOLLECT5.client_secret = "epi-secret"
    settings.AGOUTI.api_key = "agouti-key"
    settings.DATA.dir = "/home/me/data"
    dest = tmp_path / "out"
    dest.mkdir()

    with patch.object(config, "load_settings", return_value=settings):
        done = _make(tmp_path, dest, settings=True, research_project_id=None, project_files=False, visits=False, deployments=[])

    with zipfile.ZipFile(done["path"]) as zf:
        text = zf.read("settings.json").decode()
        data = json.loads(text)
    assert "trapper-secret" not in text and "epi-secret" not in text and "agouti-key" not in text and "/home/me/data" not in text
    assert data["TRAPPER"]["user_name"] == "ana@x.org" and data["TRAPPER"]["user_password"] is None and "DATA" not in data
    assert done["manifest"]["scope"]["research_project"] is None


def test_a_backup_of_nothing_is_refused(tmp_path: Path):
    _project(tmp_path)
    with pytest.raises(BackupError, match="Nothing was chosen"):
        list(built.backup(tmp_path, "1").create(tmp_path, "DONA", Choice(False, False, False, list([]), False)))
    with pytest.raises(BackupError, match="is not there"):
        list(built.backup(tmp_path, "1").create(tmp_path / "nowhere", None, Choice(True, False, False, list([]), False)))


def test_a_backup_says_what_it_holds_and_what_of_it_is_already_here(tmp_path: Path):
    _project(tmp_path)
    dest = tmp_path / "out"
    dest.mkdir()
    done = _make(tmp_path, dest, images=True)

    read = built.backup(tmp_path).read(Path(done["path"]))
    assert read["manifest"]["scope"]["research_project"] == "DONA" and read["has_images"] == {"R0001-DONA_01": True}
    assert read["here"] == {"project": True, "deployments": {"R0001-DONA_01": True}, "visits": {"in_backup": 2, "already": 2}}

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    assert built.backup(elsewhere).read(Path(done["path"]))["here"] == {"project": False, "deployments": {"R0001-DONA_01": False}, "visits": {"in_backup": 2, "already": 0}}


def test_a_file_that_is_not_a_backup_is_refused(tmp_path: Path):
    plain = tmp_path / "plain.zip"
    with zipfile.ZipFile(plain, "w") as zf:
        zf.writestr("notes.txt", "hello")
    with pytest.raises(BackupError, match="no manifest"):
        built.backup(tmp_path).read(plain)
    text = tmp_path / "text.zip"
    text.write_text("not a zip")
    with pytest.raises(BackupError, match="not a .zip"):
        built.backup(tmp_path).read(text)
    newer = tmp_path / "newer.zip"
    with zipfile.ZipFile(newer, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format": FORMAT, "version": 99, "scope": {}}))
    with pytest.raises(BackupError, match="newer version"):
        built.backup(tmp_path).read(newer)


def test_a_backup_with_a_path_that_leaves_it_is_not_restored(tmp_path: Path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format": FORMAT, "version": 1, "scope": {}}))
        zf.writestr("../outside.txt", "x")
    with pytest.raises(BackupError, match="goes out of it"):
        built.backup(tmp_path).read(evil)


def _crafted(path: Path, collection: str, entries: dict[str, str], deployment: str = "D1") -> Path:
    """A backup made by hand: its manifest names a deployment of `collection`, and it holds `entries`."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"format": FORMAT, "version": 1, "scope": {"research_project": "DONA", "deployments": [{"collection": collection, "id": deployment}]}}))
        for name, text in entries.items():
            zf.writestr(name, text)
    return path


@pytest.mark.parametrize("collection", ["{outside}", "../../outside", "..", "a/b", "a\\b", "C:outside", ""])
def test_a_backup_whose_manifest_names_a_collection_that_is_not_a_folder_of_the_project_is_neither_read_nor_restored(tmp_path: Path, collection: str):
    _project(tmp_path / "root")
    outside = tmp_path / "outside"
    collection = collection.format(outside=outside)
    evil = _crafted(tmp_path / "evil.zip", collection, {f"deployments/{collection}/D1/file.txt": "x"})

    refused = "not the name of a folder|goes out of it"   # a name with `..` is refused already for the files of the .zip that go with it
    with pytest.raises(BackupError, match=refused):
        built.backup(tmp_path / "root").read(evil)
    with pytest.raises(BackupError, match=refused):
        list(built.backup(tmp_path / "root").restore(evil, Choice(False, False, False, list(["D1"]), True), True))
    assert not outside.exists()


def test_a_backup_whose_manifest_names_a_deployment_that_is_not_a_folder_is_refused(tmp_path: Path):
    _project(tmp_path / "root")
    evil = _crafted(tmp_path / "evil.zip", "R0001", {}, deployment="../../D1")

    with pytest.raises(BackupError, match="not the name of a folder"):
        built.backup(tmp_path / "root").read(evil)


@pytest.mark.parametrize("name", ["deployments/R0001/D1/x\\..\\..\\..\\..\\outside.txt", "deployments/R0001/..\\..\\outside.txt", "\\outside.txt", "C:\\outside.txt"])
def test_a_backslash_in_the_name_of_a_file_of_the_backup_is_a_separator_as_on_windows(tmp_path: Path, name: str):
    _project(tmp_path / "root")
    evil = _crafted(tmp_path / "evil.zip", "R0001", {name: "x"})

    with pytest.raises(BackupError, match="goes out of it"):
        built.backup(tmp_path / "root").read(evil)


def test_no_file_of_a_backup_is_written_out_of_the_research_project(tmp_path: Path):
    _project(tmp_path / "root")
    (tmp_path / "root" / "DONA" / "R0001" / "link").symlink_to(tmp_path)   # a folder of the project that leads out of it
    evil = _crafted(tmp_path / "evil.zip", "R0001", {"deployments/R0001/link/escaped.txt": "x", "deployments/R0001/D1/fine.txt": "y"}, deployment="link")

    with pytest.raises(BackupError, match="goes out of it"):
        list(built.backup(tmp_path / "root").restore(evil, Choice(False, False, False, list(["link"]), True), True))
    assert not (tmp_path / "escaped.txt").exists() and not (tmp_path / "root" / "DONA" / "R0001" / "D1" / "fine.txt").exists()   # none is written


def _restore(root: Path, path: str, **options) -> dict:
    kwargs = dict(settings=False, project_files=True, visits=True, deployments=["R0001-DONA_01"], images=True, replace=False)
    o = {**kwargs, **options}
    events = list(built.backup(root).restore(Path(path), Choice(o["settings"], o["project_files"], o["visits"], list(o["deployments"]), o["images"]), o["replace"]))
    assert events[-1]["type"] == "done"
    return events[-1]["summary"]


def test_a_backup_restores_into_a_folder_where_nothing_is(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    _project(source)
    dest = tmp_path / "out"
    dest.mkdir()
    done = _make(source, dest, images=True)
    target = tmp_path / "target"
    target.mkdir()

    summary = _restore(target, done["path"])

    pdir = target / "DONA"
    assert (pdir / "research_project.json").is_file()
    assert summary["project_files"]["locations"] == {"added": 2, "replaced": 0, "kept": 0} and summary["visits"] == {"added": 2, "replaced": 0, "kept": 0}
    assert summary["deployments"] == {"restored": ["R0001-DONA_01"], "skipped": []}
    assert (pdir / "R0001" / "R0001-DONA_01" / "IMG_0001.JPG").read_bytes() == b"jpeg-1"
    assert (pdir / "R0001" / "collection.json").is_file() and (pdir / "R0001" / "R0001_FileTimestampLog.csv").is_file()
    assert len(json.loads((pdir / "visits.json").read_text(encoding="utf-8"))) == 2


def test_the_history_of_the_status_goes_in_the_backup_and_comes_back_without_repeating_what_is_there(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    pdir = _project(source)
    lines = [{"kind": "locations", "name": "DONA_01", "before": None, "after": "active", "at": "2026-06-10T09:00:00Z", "day": "2026-06-10", "reason": "Created."},
             {"kind": "cameras", "name": "CAM-1", "before": "ready", "after": "active", "at": "2026-06-10T09:01:00Z", "day": "2026-06-10", "reason": "The visit R0001 to DONA_01."}]
    (pdir / "status_history.json").write_text(json.dumps(lines), encoding="utf-8")
    dest = tmp_path / "out"
    dest.mkdir()
    done = _make(source, dest)
    target = tmp_path / "target"
    target.mkdir()

    first = _restore(target, done["path"])
    again = _restore(target, done["path"])

    assert "project/status_history.json" in zipfile.ZipFile(done["path"]).namelist()
    assert first["project_files"]["status_history"] == {"added": 2, "replaced": 0, "kept": 0}
    assert again["project_files"]["status_history"] == {"added": 0, "replaced": 0, "kept": 2}
    assert json.loads((target / "DONA" / "status_history.json").read_text(encoding="utf-8")) == lines


def test_the_images_are_restored_only_when_asked_and_when_the_backup_has_them(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    _project(source)
    dest = tmp_path / "out"
    dest.mkdir()
    done = _make(source, dest, images=True)
    target = tmp_path / "target"
    target.mkdir()

    _restore(target, done["path"], images=False)

    folder = target / "DONA" / "R0001" / "R0001-DONA_01"
    assert (folder / "deployment.json").is_file() and not (folder / "IMG_0001.JPG").exists()


def test_what_is_there_is_not_overwritten_unless_it_is_asked_and_what_is_archived_stays_archived(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    pdir = _project(source)
    dest = tmp_path / "out"
    dest.mkdir()
    done = _make(source, dest, images=True)

    # the same project, a little later: a location changed, one is archived for good, a deployment has other files, a visit was added
    (pdir / "locations.json").write_text(json.dumps([{"location_id": "DONA_01", "status": "archived"}, {"location_id": "DONA_02", "status": "active", "name": "later"}, {"location_id": "DONA_03"}]), encoding="utf-8")
    (pdir / "R0001" / "R0001-DONA_01" / "IMG_0001.JPG").write_bytes(b"changed")
    visits = json.loads((pdir / "visits.json").read_text(encoding="utf-8"))
    (pdir / "visits.json").write_text(json.dumps(visits + [{"location_id": "DONA_03", "session": "R0001", "date": "2026-06-11", "time": "10:00:00", "when": "2026-06-11T10:00:00Z", "actions": ["Installation"]}]), encoding="utf-8")

    kept = _restore(source, done["path"])
    assert kept["project_files"]["locations"] == {"added": 0, "replaced": 0, "kept": 2} and kept["visits"] == {"added": 0, "replaced": 0, "kept": 2}
    assert kept["deployments"]["skipped"] == ["R0001-DONA_01"] and kept["deployments"]["restored"] == []
    assert (pdir / "R0001" / "R0001-DONA_01" / "IMG_0001.JPG").read_bytes() == b"changed"

    replaced = _restore(source, done["path"], replace=True)
    locations = {l["location_id"]: l for l in json.loads((pdir / "locations.json").read_text(encoding="utf-8"))}
    assert locations["DONA_01"]["status"] == "archived"                      # archived in the backup's own copy of it as in what is here: it stays
    assert locations["DONA_02"]["status"] == "archived"                      # what is here was active, the backup says archived: the backup wins
    assert "DONA_03" in locations                                           # what the backup does not have is kept
    assert replaced["project_files"]["locations"]["replaced"] == 1 and replaced["project_files"]["locations"]["kept"] == 1
    assert replaced["deployments"]["restored"] == ["R0001-DONA_01"]
    assert (pdir / "R0001" / "R0001-DONA_01" / "IMG_0001.JPG").read_bytes() == b"jpeg-1"
    assert len(json.loads((pdir / "visits.json").read_text(encoding="utf-8"))) == 3   # the visit made after the backup is not lost


def test_a_project_that_is_not_here_needs_its_data_restored_too(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    _project(source)
    dest = tmp_path / "out"
    dest.mkdir()
    done = _make(source, dest)
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(BackupError, match="not here: restore its data too"):
        _restore(target, done["path"], project_files=False)


def test_the_settings_are_restored_keeping_the_passwords_and_the_folders_here(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    saved = config.Settings()
    saved.TRAPPER.user_name = "ana@x.org"
    saved.TRAPPER.user_password = "old-secret"
    saved.DATA.dir = "/there"
    dest = tmp_path / "out"
    dest.mkdir()
    with patch.object(config, "load_settings", return_value=saved):
        done = _make(source, dest, settings=True, research_project_id=None, project_files=False, visits=False, deployments=[])

    here = config.Settings()
    here.TRAPPER.user_name = "bob@x.org"
    here.TRAPPER.user_password = "my-secret"
    here.DATA.dir = "/here"
    written = {}
    with patch.object(config, "load_settings", return_value=here), patch.object(config, "save_settings", side_effect=lambda s, *a, **k: written.update(s=s)):
        summary = _restore(source, done["path"], settings=True, project_files=False, visits=False, deployments=[])

    assert summary["settings"] is True
    new = written["s"]
    assert new.TRAPPER.user_name == "ana@x.org"          # what the backup says
    assert new.TRAPPER.user_password == "my-secret"      # the password of this computer stays
    assert new.DATA.dir == "/here"                       # so does its folder


# ── the rules of a backup, plain Python ──────────────────────────────────────

def test_restoring_adds_what_is_not_here_replaces_only_when_asked_and_never_what_is_archived():
    from wildintel_uploader.modules.backup.domain import archive

    here = [{"id": "a", "label": "A", "status": "active"}, {"id": "b", "label": "B", "status": "archived"}]
    backed = [{"label": "A", "status": "retired"}, {"label": "B", "status": "active"}, {"label": "C"}]
    key = archive.RECORD_KEYS["sd_cards"]

    assert archive.merge(here, backed, key, replace=False)[1:] == (1, 0, 2)
    merged, added, replaced, kept = archive.merge(here, backed, key, replace=True)
    assert (added, replaced, kept) == (1, 1, 1) and merged[0] == {"id": "a", "label": "A", "status": "retired"} and merged[1]["status"] == "archived"


def test_a_name_that_leaves_the_backup_or_is_not_a_folder_is_known_as_such():
    from wildintel_uploader.modules.backup.domain import archive

    assert [archive.leaves_the_backup(n) for n in ("a/b.txt", "../x", "/x", "C:\\x", "a\\..\\..\\x")] == [False, True, True, True, True]
    for bad in ("..", "a/b", "C:", ""):
        with pytest.raises(BackupError, match="not the name of a folder"):
            archive.folder_name(bad, "a deployment")
    with pytest.raises(BackupError, match="newer version"):
        archive.checked_manifest({"format": archive.FORMAT, "version": archive.VERSION + 1})


def test_the_settings_of_a_backup_have_no_secrets_nor_folders_and_restoring_keeps_those_here():
    from wildintel_uploader.modules.backup.domain import archive

    here = {"DATA": {"dir": "/mine"}, "TRAPPER": {"base_url": "https://a", "password": "secret"}, "FIELDWORK": {"cameras": [1]}}
    snapshot = archive.settings_for_a_backup(here, [("TRAPPER", "password")], [{"username": "ana"}])
    assert "DATA" not in snapshot and snapshot["TRAPPER"]["password"] is None and snapshot["FIELDWORK"]["trappers"] == [{"username": "ana"}]
    assert here["TRAPPER"]["password"] == "secret"                                          # what is here is not touched
    restored = archive.settings_restored(here, {"TRAPPER": {"base_url": "https://b", "password": None}, "DATA": {"dir": "/theirs"}}, [("TRAPPER", "password")])
    assert restored["TRAPPER"] == {"base_url": "https://b", "password": "secret"} and restored["DATA"] == {"dir": "/mine"}
