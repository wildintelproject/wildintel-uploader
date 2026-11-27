"""#248: the rules of bringing a folder of images into a collection (modules.deployments.domain.imports) — plain Python, no disk."""
from datetime import datetime
from pathlib import PurePath

import pytest

from wildintel_uploader.modules.deployments.domain import imports as rules
from wildintel_uploader.modules.deployments.domain.models import DeploymentImportError


def test_the_timestamp_log_is_the_one_named_after_the_folder_else_the_only_one():
    assert rules.timestamp_log_of("R0033", ["R0033_FileTimestampLog.csv", "x_FileTimestampLog.csv"]) == ("R0033_FileTimestampLog.csv", [])
    assert rules.timestamp_log_of("R0033", ["old_FileTimestampLog.csv", "notes.txt"]) == ("old_FileTimestampLog.csv", [])
    name, warnings = rules.timestamp_log_of("R0033", ["a_FileTimestampLog.csv", "b_FileTimestampLog.csv"])
    assert name is None and "none is named after the folder" in warnings[0]
    name, warnings = rules.timestamp_log_of("R0033", [])
    assert name is None and "No timestamp log (R0033_FileTimestampLog.csv)" in warnings[0]


def test_the_log_gives_its_period_to_the_subfolders_it_names():
    rows = [{"Deployment": "R0033-DONA_01", "StartDate": "2024:09:04", "StartTime": "13:10:00", "EndDate": "2024:10:01", "EndTime": "09:00:00"},
            {"Deployment": "R0033-DONA_09", "StartDate": "2024:09:04", "StartTime": "13:10:00", "EndDate": "2024:10:01", "EndTime": "09:00:00"},
            {"Deployment": "R0033-BAD", "StartDate": "4/9/2024", "StartTime": "", "EndDate": "", "EndTime": ""}]
    found, warnings = rules.periods("R0033_FileTimestampLog.csv", rows)
    assert set(found) == {"r0033-dona_01", "r0033-dona_09"} and "R0033-BAD" in warnings[0]
    deployments = [rules.session_deployment("DONA_01", "/s/DONA_01", {}), rules.session_deployment("DONA_02", "/s/DONA_02", {})]
    matched = rules.match_log(deployments, found)
    assert matched == {"rows": 2, "matched": 1, "revision": 33, "unmatched": ["R0033-DONA_09"]}
    assert deployments[0]["start_date"] == "2024-09-04T13:10:00" and deployments[0]["log_deployment_id"] == "R0033-DONA_01"
    assert deployments[1]["from_timestamp_log"] is False


def test_the_details_suggest_a_camera_only_when_every_image_agrees():
    taken = [datetime(2024, 9, 4, 13), None, datetime(2024, 9, 1, 8)]
    details = rules.guess(taken, ["TC1", "TC1", "TC1"], ["A", "B", "A"], "exiftool")
    assert (details["start_date"], details["end_date"]) == ("2024-09-01T08:00:00", "2024-09-04T13:00:00")
    assert details["camera_model"] == "TC1" and details["camera_id"] is None
    assert any("1 of 3 image(s)" in w for w in details["warnings"]) and any("2 different camera ids" in w for w in details["warnings"])
    assert rules.guess([], [], [], "pillow")["warnings"] == ["There are no images to read — the dates must be entered by hand."]


def test_where_a_deployment_is_kept_and_what_is_refused():
    assert rules.collection_of(PurePath("/c"), "DONA", "R0003-DONA_01") == PurePath("/c/DONA/R0003")
    with pytest.raises(DeploymentImportError, match="folder name"):
        rules.collection_of(PurePath("/c"), "../x", "R0003-DONA_01")
    with pytest.raises(DeploymentImportError, match="cannot be the deployment folder"):
        rules.check_nesting(PurePath("/a"), PurePath("/a/b"))
    with pytest.raises(DeploymentImportError, match="synced from TRAPPER"):
        rules.check_not_kept(PurePath("/a/R0003-X"), synced=True, has_content=False)
    assert rules.is_pending(True, False) and not rules.is_pending(True, True)


def test_the_logs_say_of_a_deployment_its_period_and_its_fieldwork():
    entry = rules.log_entry("R0003", "r0003-dona_01",
                            [{"Deployment": "R0003-DONA_01", "StartDate": "2024:09:04", "StartTime": "", "EndDate": "2024:10:01", "EndTime": "09:00:00"}],
                            [{"deploymentID": "R0003-DONA_01", "cameraHeight": "1.2", "cameraTilt": "x", "baitUse": "TRUE", "deploymentTags": "a| b|"}])
    assert entry["timestamps"] == {"start": "2024-09-04T00:00:00", "end": "2024-10-01T09:00:00"}
    assert entry["fieldwork"]["details"] == {"camera_height": 1.2, "bait_use": True, "tags": ["a", "b"]}
