"""services.local_folder_service — the "Local folder" destination's own
collection/deployment metadata, all on disk, no network."""
import json
from datetime import datetime
from pathlib import Path

import pytest

from wildintel_uploader.core.services import local_folder_service as svc


def test_check_collection_reports_a_missing_folder(tmp_path: Path):
    result = svc.check_collection(tmp_path / "nope")
    assert result == {"exists": False, "name": None}


def test_check_collection_reports_an_existing_folder_without_metadata(tmp_path: Path):
    result = svc.check_collection(tmp_path)
    assert result == {"exists": True, "name": None}


def test_write_collection_metadata_creates_the_folder_and_records_the_name(tmp_path: Path):
    collection = tmp_path / "R0001"
    svc.write_collection_metadata(collection, "Doñana 2024")

    assert collection.is_dir()
    assert svc.check_collection(collection) == {"exists": True, "name": "Doñana 2024"}


def test_write_collection_metadata_keeps_the_existing_name_when_none_is_given(tmp_path: Path):
    svc.write_collection_metadata(tmp_path, "Doñana 2024")
    svc.write_collection_metadata(tmp_path, None)

    assert svc.check_collection(tmp_path)["name"] == "Doñana 2024"


def test_write_and_list_deployment_metadata(tmp_path: Path):
    deployment_dir = tmp_path / "R0001-DONA_01"
    deployment = {"deployment_id": "R0001-DONA_01", "location_id": "DONA_01", "start_date": "2024-09-04T13:10:00"}
    svc.write_deployment_metadata(deployment_dir, deployment)

    assert (deployment_dir / "deployment.json").is_file()
    assert svc.list_deployments(tmp_path) == [deployment]


def test_list_deployments_ignores_folders_without_metadata(tmp_path: Path):
    (tmp_path / "not-a-deployment").mkdir()
    assert svc.list_deployments(tmp_path) == []


def test_list_deployments_of_a_missing_collection_is_empty(tmp_path: Path):
    assert svc.list_deployments(tmp_path / "nope") == []


# ── the collection's FileTimestampLog ───────────────────────────────────────

START = datetime(2024, 9, 4, 13, 10, 0)
END = datetime(2024, 11, 4, 14, 28, 0)


def test_the_log_is_named_after_its_collection(tmp_path: Path):
    assert svc.timestamp_log_path(tmp_path / "R0003").name == "R0003_FileTimestampLog.csv"
    assert svc.timestamp_log_path(tmp_path / "R0003_winter").name == "R0003_winter_FileTimestampLog.csv"


def test_a_deployment_is_added_with_wildintel_tools_header_and_formats(tmp_path: Path):
    collection = tmp_path / "DONA" / "R0003"

    result = svc.upsert_timestamp_log(collection, "R0003-DONA_0007_B", START, END)

    log = collection / "R0003_FileTimestampLog.csv"
    assert result == {"path": str(log), "action": "added", "rows": 1}
    # utf-8 with a BOM, as Excel and wildintel-tools write it; one row per deployment.
    assert log.read_bytes().startswith(b"\xef\xbb\xbf")
    assert log.read_text(encoding="utf-8-sig").splitlines() == [
        "Deployment,StartDate,StartTime,EndDate,EndTime",
        "r0003-dona_0007_b,2024:09:04,13:10:00,2024:11:04,14:28:00",  # in lower case, as Trapper keeps it
    ]


def test_the_collection_folder_is_created_and_named_in_its_metadata(tmp_path: Path):
    collection = tmp_path / "DONA" / "R0003"

    svc.upsert_timestamp_log(collection, "R0003-DONA_01", START, END)

    assert json.loads((collection / "collection.json").read_text())["name"] == "R0003"
    assert svc.check_collection(collection) == {"exists": True, "name": "R0003"}


def test_other_deployments_of_the_collection_keep_their_rows(tmp_path: Path):
    collection = tmp_path / "R0003"
    svc.upsert_timestamp_log(collection, "R0003-DONA_01", START, END)

    result = svc.upsert_timestamp_log(collection, "R0003-DONA_02", datetime(2024, 9, 5, 6, 0, 0), datetime(2024, 11, 5, 18, 0, 0))

    assert result["action"] == "added" and result["rows"] == 2
    assert [r["Deployment"] for r in svc.read_timestamp_log(collection / "R0003_FileTimestampLog.csv")] == ["r0003-dona_01", "r0003-dona_02"]


def test_a_deployment_that_is_there_has_its_row_replaced_not_duplicated(tmp_path: Path):
    collection = tmp_path / "R0003"
    svc.upsert_timestamp_log(collection, "R0003-DONA_01", START, END)

    updated = svc.upsert_timestamp_log(collection, "r0003-dona_01", START, datetime(2024, 12, 1, 8, 0, 0))  # compared ignoring case
    same = svc.upsert_timestamp_log(collection, "r0003-dona_01", START, datetime(2024, 12, 1, 8, 0, 0))

    assert updated["action"] == "updated" and updated["rows"] == 1
    assert same["action"] == "unchanged"
    [row] = svc.read_timestamp_log(collection / "R0003_FileTimestampLog.csv")
    assert row["Deployment"] == "r0003-dona_01" and row["EndDate"] == "2024:12:01"


def test_an_unchanged_log_is_not_rewritten(tmp_path: Path):
    collection = tmp_path / "R0003"
    svc.upsert_timestamp_log(collection, "R0003-DONA_01", START, END)
    log = collection / "R0003_FileTimestampLog.csv"
    before = log.stat().st_mtime_ns

    svc.upsert_timestamp_log(collection, "R0003-DONA_01", START, END)

    assert log.stat().st_mtime_ns == before


def test_a_log_wildintel_tools_wrote_is_read_and_kept(tmp_path: Path):
    collection = tmp_path / "R0001"
    collection.mkdir()
    (collection / "R0001_FileTimestampLog.csv").write_text(
        "Deployment,StartDate,StartTime,EndDate,EndTime\nR0001-DONA_0007_B,2024:09:04,13:10:00,2024:11:04,14:28:00\n\nR0001-DONA_0008_A,2024:09:04,06:00:00,2024:11:04,18:00:00\n",
        encoding="utf-8",
    )

    svc.upsert_timestamp_log(collection, "R0001-DONA_0009_C", START, END)

    rows = svc.read_timestamp_log(collection / "R0001_FileTimestampLog.csv")
    assert [r["Deployment"] for r in rows] == ["R0001-DONA_0007_B", "R0001-DONA_0008_A", "r0001-dona_0009_c"]  # the rows it did not write stay as they were
    assert rows[1]["StartTime"] == "06:00:00"


@pytest.mark.parametrize("content,message", [
    ("", "no header"),
    ("Deployment,StartDate,StartTime\nR0001-X,2024:09:04,13:10:00\n", "missing the columns: EndDate, EndTime"),
    ("Deployment,StartDate,StartDate,EndDate,EndTime\n", "repeats the columns: StartDate"),
])
def test_a_log_that_cannot_be_read_is_refused_and_left_as_it_is(tmp_path: Path, content: str, message: str):
    collection = tmp_path / "R0001"
    collection.mkdir()
    log = collection / "R0001_FileTimestampLog.csv"
    log.write_text(content, encoding="utf-8")

    with pytest.raises(svc.LocalFolderError, match=message):
        svc.upsert_timestamp_log(collection, "R0001-DONA_01", START, END)

    assert log.read_text(encoding="utf-8") == content


def test_a_deployment_cannot_end_before_it_starts(tmp_path: Path):
    with pytest.raises(svc.LocalFolderError, match="must start before it ends"):
        svc.upsert_timestamp_log(tmp_path / "R0003", "R0003-DONA_01", END, START)

    assert not (tmp_path / "R0003").exists()  # nothing was created


def test_a_research_project_in_two_folders_is_listed_once_from_the_one_named_by_its_acronym(tmp_path):
    for folder in ("DONA_24_", "DONA_24", "WICP_01"):  # the first renamed by hand, the second made by a sync
        (tmp_path / folder).mkdir()
        acronym = "WICP_01" if folder == "WICP_01" else "DONA_24"
        (tmp_path / folder / "research_project.json").write_text(json.dumps({"name": acronym, "acronym": acronym, "marker": folder}), encoding="utf-8")

    listed = svc.list_research_projects(tmp_path)

    assert [(p["acronym"], p["marker"]) for p in listed] == [("DONA_24", "DONA_24"), ("WICP_01", "WICP_01")]


def _project(root: Path, acronym: str = "DONA") -> None:
    svc.write_research_project(root, {"name": "Doñana", "acronym": acronym})


def test_a_research_project_starts_with_no_visits_and_gets_them_registered_in_order(tmp_path: Path):
    _project(tmp_path)
    assert svc.list_visits(tmp_path, "DONA") == []

    svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_01", "session": "R0001", "actions": ["Installation"]})
    svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_02", "session": "R0001", "actions": ["Installation"]})
    svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_01", "session": "R0002", "actions": ["Revision"]})

    assert [v["session"] for v in svc.list_visits(tmp_path, "DONA")] == ["R0001", "R0001", "R0002"]
    assert (tmp_path / "DONA" / svc.VISITS_FILE).is_file()


def test_the_visits_to_one_location_are_found_ignoring_case(tmp_path: Path):
    _project(tmp_path)
    svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_0023_B", "session": "R0001", "actions": ["Installation"]})
    svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_01", "session": "R0001", "actions": ["Installation"]})

    assert [v["location_id"] for v in svc.list_visits(tmp_path, "DONA", "dona_0023_b")] == ["DONA_0023_B"]
    assert svc.list_visits(tmp_path, "DONA", "DONA_99") == []


def test_a_visit_cannot_be_registered_to_a_research_project_that_is_not_kept(tmp_path: Path):
    with pytest.raises(svc.LocalFolderError, match="isn't in the collections folder"):
        svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_01"})


# ── the time of a visit: kept as an instant, told as the wall clock of its location ─────────────────────────────

def _location(root: Path, location_id: str = "DONA_01", **over) -> None:
    svc.write_location(root, "DONA", {"location_id": location_id, "name": location_id, **over})


def _visit_on_disk(root: Path) -> list[dict]:
    return json.loads((root / "DONA" / svc.VISITS_FILE).read_text(encoding="utf-8"))


def test_a_visit_is_kept_as_an_instant_in_iso_8601_utc_and_told_with_the_wall_clock_of_its_location(tmp_path: Path):
    _project(tmp_path)
    _location(tmp_path, "DONA_01")                                                      # UTC, following summer time: the default
    _location(tmp_path, "DONA_02", timezone="Europe/Madrid", ignore_dst=False)           # +02:00 in September
    _location(tmp_path, "DONA_03", timezone="Europe/Madrid", ignore_dst=True)            # +01:00 all the year

    for site in ("DONA_01", "DONA_02", "DONA_03"):
        told = svc.write_visit(tmp_path, "DONA", {"location_id": site, "session": "R0001", "date": "2024-09-04", "time": "13:10:00", "actions": ["Installation"]})
        assert (told["date"], told["time"]) == ("2024-09-04", "13:10:00")               # what was typed is what is told

    on_disk = _visit_on_disk(tmp_path)
    assert [v["when"] for v in on_disk] == ["2024-09-04T13:10:00Z", "2024-09-04T11:10:00Z", "2024-09-04T12:10:00Z"]
    assert all("date" not in v and "time" not in v for v in on_disk)                     # the instant is what is kept
    assert [(v["date"], v["time"]) for v in svc.list_visits(tmp_path, "DONA")] == [("2024-09-04", "13:10:00")] * 3


def test_visits_kept_with_a_day_and_a_time_are_moved_to_instants_when_read(tmp_path: Path):
    _project(tmp_path)
    _location(tmp_path, "DONA_01", timezone="Europe/Madrid")
    (tmp_path / "DONA" / svc.VISITS_FILE).write_text(json.dumps([
        {"location_id": "DONA_01", "session": "R0001", "date": "2024-01-15", "time": "09:00:00", "actions": ["Installation"]},   # +01:00 in winter
        {"location_id": "DONA_01", "session": "R0002", "date": "2024-07-15", "time": "09:00:00", "actions": ["Revision"]},       # +02:00 in summer
    ]), encoding="utf-8")

    told = svc.list_visits(tmp_path, "DONA")

    assert [(v["date"], v["time"]) for v in told] == [("2024-01-15", "09:00:00"), ("2024-07-15", "09:00:00")]
    assert [v["when"] for v in _visit_on_disk(tmp_path)] == ["2024-01-15T08:00:00Z", "2024-07-15T07:00:00Z"]   # written back as instants
    assert svc.list_visits(tmp_path, "DONA") == told                                                              # and the same when read again


def test_a_visit_is_linked_by_the_day_and_the_time_it_is_told_with(tmp_path: Path):
    _project(tmp_path)
    _location(tmp_path, "DONA_01", timezone="Europe/Madrid")
    svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_01", "session": "R0001", "date": "2024-09-04", "time": "13:10:00", "actions": ["Installation"]})

    linked = svc.link_visit(tmp_path, "DONA", "dona_01", "2024-09-04", "13:10:00", "R0001-DONA_01")

    assert linked["deployment_id"] == "R0001-DONA_01" and linked["when"] == "2024-09-04T11:10:00Z"
    assert _visit_on_disk(tmp_path)[0]["deployment_id"] == "R0001-DONA_01"


def test_a_visit_keeps_the_instant_it_was_registered_and_the_one_it_was_last_changed(tmp_path: Path):
    from unittest.mock import patch
    from wildintel_uploader.core.services import audit
    svc.write_research_project(tmp_path, {"name": "Doñana", "acronym": "DONA"})
    visit = {"location_id": "DONA_01", "session": "R0001", "date": "2024-09-04", "time": "13:10:00", "actions": ["Installation"], "created_at": "1999-01-01T00:00:00Z"}
    with patch.object(audit, "now", return_value="2026-11-01T10:00:00Z"):
        told = svc.write_visit(tmp_path, "DONA", visit)
    assert (told["created_at"], told["updated_at"]) == ("2026-11-01T10:00:00Z", "2026-11-01T10:00:00Z")      # what is sent for them is not taken

    # saved again with nothing changed: the dates stay
    with patch.object(audit, "now", return_value="2026-11-02T10:00:00Z"):
        same = svc.update_visit(tmp_path, "DONA", "DONA_01", "R0001", {k: v for k, v in told.items() if k not in ("created_at", "updated_at")})
    assert (same["created_at"], same["updated_at"]) == ("2026-11-01T10:00:00Z", "2026-11-01T10:00:00Z")

    # edited: it keeps when it was registered, and says when it was changed
    with patch.object(audit, "now", return_value="2026-11-03T10:00:00Z"):
        edited = svc.update_visit(tmp_path, "DONA", "DONA_01", "R0001", {**same, "comments": "Moved a metre", "created_at": "2000-02-02T00:00:00Z"})
    assert (edited["created_at"], edited["updated_at"]) == ("2026-11-01T10:00:00Z", "2026-11-03T10:00:00Z")

    # what the app changes by itself — the deployment it closed, its state — is a change too
    with patch.object(audit, "now", return_value="2026-11-04T10:00:00Z"):
        linked = svc.link_visit(tmp_path, "DONA", "DONA_01", "2024-09-04", "13:10:00", "R0001-DONA_01")
    assert (linked["created_at"], linked["updated_at"]) == ("2026-11-01T10:00:00Z", "2026-11-04T10:00:00Z")
    assert svc.list_visits(tmp_path, "DONA")[0]["updated_at"] == "2026-11-04T10:00:00Z"


def test_a_visit_kept_before_the_dates_existed_gets_none_made_up_until_it_changes(tmp_path: Path):
    from unittest.mock import patch
    from wildintel_uploader.core.services import audit
    svc.write_research_project(tmp_path, {"name": "Doñana", "acronym": "DONA"})
    (tmp_path / "DONA" / "visits.json").write_text(json.dumps([{"location_id": "DONA_01", "session": "R0001", "when": "2024-09-04T13:10:00Z", "actions": ["Installation"]}]), encoding="utf-8")
    assert "created_at" not in svc.list_visits(tmp_path, "DONA")[0]
    with patch.object(audit, "now", return_value="2026-11-05T10:00:00Z"):
        edited = svc.update_visit(tmp_path, "DONA", "DONA_01", "R0001", {"location_id": "DONA_01", "session": "R0001", "date": "2024-09-04", "time": "13:10:00", "actions": ["Installation"], "comments": "x"})
    assert edited["updated_at"] == "2026-11-05T10:00:00Z" and "created_at" not in edited


def test_a_location_is_deleted_logically_it_is_kept_with_its_deleted_at_and_comes_back_when_it_is_added_again(tmp_path: Path):
    from unittest.mock import patch
    from wildintel_uploader.core.services import audit
    svc.write_research_project(tmp_path, {"name": "Doñana", "acronym": "DONA"})
    with patch.object(audit, "now", return_value="2026-11-01T10:00:00Z"):
        svc.write_location(tmp_path, "DONA", {"location_id": "DONA_01", "latitude": 37.0, "longitude": -6.4, "timezone": "Europe/Madrid", "ignore_dst": False})
    with patch.object(audit, "now", return_value="2026-11-02T10:00:00Z"):
        assert svc.delete_location(tmp_path, "DONA", "dona_01") == {"deleted": "DONA_01"}

    assert svc.list_locations(tmp_path, "DONA") == []                                              # not listed…
    kept = svc.list_locations(tmp_path, "DONA", include_deleted=True)
    assert len(kept) == 1 and kept[0]["deleted_at"] == "2026-11-02T10:00:00Z" and kept[0]["created_at"] == "2026-11-01T10:00:00Z"   # …but kept
    with pytest.raises(svc.LocalFolderError):
        svc.update_location(tmp_path, "DONA", "DONA_01", {"name": "x"})                            # a location that was deleted is not changed
    with pytest.raises(svc.LocalFolderError):
        svc.delete_location(tmp_path, "DONA", "DONA_01")

    with patch.object(audit, "now", return_value="2026-11-03T10:00:00Z"):
        back = svc.write_location(tmp_path, "DONA", {"location_id": "dona_01", "latitude": 37.1, "longitude": -6.4, "timezone": "Europe/Madrid", "ignore_dst": False})
    assert "deleted_at" not in back and back["created_at"] == "2026-11-01T10:00:00Z" and back["updated_at"] == "2026-11-03T10:00:00Z" and back["latitude"] == 37.1
    assert [l["location_id"] for l in svc.list_locations(tmp_path, "DONA")] == ["dona_01"] and len(svc.list_locations(tmp_path, "DONA", include_deleted=True)) == 1


def test_a_visit_made_at_a_location_that_was_deleted_still_says_its_time_in_its_timezone(tmp_path: Path):
    svc.write_research_project(tmp_path, {"name": "Doñana", "acronym": "DONA"})
    svc.write_location(tmp_path, "DONA", {"location_id": "DONA_01", "timezone": "Europe/Madrid", "ignore_dst": False, "latitude": 37.0, "longitude": -6.4})
    svc.write_visit(tmp_path, "DONA", {"location_id": "DONA_01", "session": "R0001", "date": "2024-09-04", "time": "13:10:00", "actions": ["Installation"]})
    # with visits it is not deleted — it is archived; if it is deleted by hand in the file, the visits go on being told in its timezone
    data = json.loads((tmp_path / "DONA" / "locations.json").read_text(encoding="utf-8"))
    data[0]["deleted_at"] = "2026-11-02T10:00:00Z"
    (tmp_path / "DONA" / "locations.json").write_text(json.dumps(data), encoding="utf-8")
    assert svc.list_visits(tmp_path, "DONA")[0]["time"] == "13:10:00" and svc.list_visits(tmp_path, "DONA")[0]["when"] == "2024-09-04T11:10:00Z"


def test_a_research_project_is_deleted_logically_and_comes_back_when_it_is_added_again(tmp_path: Path):
    from unittest.mock import patch
    from wildintel_uploader.core.services import audit
    with patch.object(audit, "now", return_value="2026-11-01T10:00:00Z"):
        created = svc.write_research_project(tmp_path, {"name": "Doñana", "acronym": "DONA"})
    assert created["created_at"] == created["updated_at"] == "2026-11-01T10:00:00Z"
    svc.write_location(tmp_path, "DONA", {"location_id": "DONA_01", "latitude": 37.0, "longitude": -6.4, "timezone": "UTC", "ignore_dst": False})
    with patch.object(audit, "now", return_value="2026-11-02T10:00:00Z"):
        svc.delete_research_project(tmp_path, "DONA")

    assert svc.list_research_projects(tmp_path) == [] and not svc.has_research_project(tmp_path, "DONA")
    assert [p["acronym"] for p in svc.list_research_projects(tmp_path, include_deleted=True)] == ["DONA"]
    assert (tmp_path / "DONA" / "locations.json").is_file()                                          # what it had is kept
    with pytest.raises(svc.LocalFolderError):
        svc.write_location(tmp_path, "DONA", {"location_id": "DONA_02", "latitude": 37.0, "longitude": -6.4, "timezone": "UTC", "ignore_dst": False})   # nothing is added to a project that was deleted

    with patch.object(audit, "now", return_value="2026-11-03T10:00:00Z"):
        back = svc.write_research_project(tmp_path, {"name": "Doñana NP", "acronym": "DONA"})
    assert back["created_at"] == "2026-11-01T10:00:00Z" and back["updated_at"] == "2026-11-03T10:00:00Z" and "deleted_at" not in back
    assert [l["location_id"] for l in svc.list_locations(tmp_path, "DONA")] == ["DONA_01"]            # with the locations it had
