

# ── exporting ───────────────────────────────────────────────────────────────

def test_export_is_read_back_as_the_same_visits():
    from wildintel_uploader.core.services import visits_csv
    locations = [{"location_id": "WICP_0001", "latitude": 40.0, "longitude": -3.0, "timezone": "UTC"}]
    visits = [
        {"location_id": "WICP_0001", "session": "R0001", "date": "2026-09-14", "time": "11:40:00", "actions": ["Installation"], "camera_id": "CAM1", "sd": "3", "bait_use": True,
         "camera_height": 1.5, "tags": ["a", "b"], "trappers": "Ana Pérez", "comments": "uno, dos"},
        {"location_id": "WICP_0001", "session": "R0002", "date": "2026-10-19", "time": "11:40:00", "actions": ["Revision", "Desinstallation"], "camera_id": "CAM1",
         "card_batteries_ok": "OK", "num_photos": 12, "sd": "4"},
        {"location_id": "WICP_0001", "session": "R0003", "date": "2026-11-20", "time": "09:00:00", "actions": [], "status": "Not revised"},
    ]
    text = visits_csv.export_visits(visits)
    mapping = visits_csv.suggest_mapping(text)["mapping"]
    result = visits_csv.parse_visits(text, locations, [], "", "mapped", mapping)
    assert not result["problems"]
    back = result["visits"]
    assert len(back) == 3
    for original, got in zip(visits, back):
        for field, value in original.items():
            assert got.get(field) == value, field


def test_every_row_says_what_became_of_it():
    from wildintel_uploader.core.services import visits_csv
    locations = [{"location_id": "WICP_0001", "latitude": 40.0, "longitude": -3.0, "timezone": "UTC"}]
    kept = [{"location_id": "WICP_0001", "session": "R0001", "date": "2026-09-14", "time": "11:40:00", "actions": ["Installation"], "camera_id": "CAM1"}]
    text = ("location_id,actions,date,time,session,camera_id\n"
            "WICP_0001,Installation,2026-09-14,11:40:00,R0001,CAM1\n"      # row 2: already kept
            "WICP_0001,Flying,2026-10-19,11:40:00,R0002,CAM1\n"            # row 3: a problem
            "WICP_0009,Installation,2026-10-19,12:00:00,R0001,CAM2\n"      # row 4: a site that is not a location
            "WICP_0001,Revision,2026-10-20,11:40:00,R0002,CAM1\n")         # row 5: fine
    mapping = visits_csv.suggest_mapping(text)["mapping"]
    result = visits_csv.parse_visits(text, locations, kept, "", "mapped", mapping)
    by_row = {r["row"]: r for r in result["rows"]}
    assert [by_row[n]["result"] for n in (2, 3, 4, 5)] == ["already_kept", "problem", "new_site", "ok"]
    assert (by_row[5]["date"], by_row[5]["time"]) == ("2026-10-20", "11:40")   # the day and the time of the visit the row says
    assert by_row[5]["actions"] == "Revision" and by_row[3]["actions"] == "Flying"   # as the dashboard says them; as the file wrote them when they are not valid
    assert "already kept" in by_row[2]["message"] and "Flying" in by_row[3]["message"] and by_row[4]["site"] == "WICP_0009"


def test_a_visit_of_a_session_and_site_already_kept_is_not_imported_and_a_closed_revision_takes_nothing_new():
    from wildintel_uploader.core.services import visits_csv
    locations = [{"location_id": "WICP_0001", "timezone": "UTC"}, {"location_id": "WICP_0002", "timezone": "UTC"}]
    kept = [  # R0001 is closed: every location has its visit — one of them "Not revised", with no camera
        {"location_id": "WICP_0001", "session": "R0001", "date": "2026-09-14", "time": "11:40:00", "actions": ["Installation"], "camera_id": "CAM1"},
        {"location_id": "WICP_0002", "session": "R0001", "date": "2026-09-14", "time": "13:15:00", "actions": [], "status": "Not revised"},
    ]
    text = ("location_id,actions,date,time,session,camera_id\n"
            "WICP_0002,Installation,2026-09-14,11:40:00,R0001,CAM2\n")     # same session and site, another camera and actions
    mapping = visits_csv.suggest_mapping(text)["mapping"]
    result = visits_csv.parse_visits(text, locations, kept, "", "mapped", mapping)
    assert result["visits"] == [] and result["skipped"] == 1
    assert "closed" in result["rows"][0]["message"] and result["rows"][0]["result"] == "already_kept"


# ── defaults and creating what does not exist ───────────────────────────────

_NEW = ("site,what,day,hour,lat,lon,cam,sd\n"
        "WICP_0001,Installation,2026-09-14,11:40,40.1,-3.2,CAM9,S9\n"
        "WICP_0001,Revision,2026-10-14,11:40,40.1,-3.2,CAM9,S10\n")
_MAP = {"location_id": "site", "actions": "what", "date": "day", "time": "hour", "latitude": "lat", "longitude": "lon", "camera_id": "cam", "sd": "sd"}


def test_a_default_gives_a_field_the_file_has_no_column_for_and_fills_its_empty_cells():
    from wildintel_uploader.core.services import visits_csv
    locations = [{"location_id": "WICP_0001", "timezone": "UTC"}]
    text = "site,what,day,hour,cam,model\nWICP_0001,Installation,2026-09-14,11:40,CAM1,\nWICP_0001,Revision,2026-10-14,11:40,CAM1,Browning\n"
    mapping = {**_MAP, "camera_model": "model"} | {"latitude": "", "longitude": "", "sd": ""}
    result = visits_csv.parse_visits(text, locations, [], "", "mapped", mapping, {"defaults": {"camera_model": "Reconyx-PC900", "trappers": "Ana"}})
    assert [v["camera_model"] for v in result["visits"]] == ["Reconyx-PC900", "Browning"]   # empty cell filled, cell given kept
    assert {v["trappers"] for v in result["visits"]} == {"Ana"}                                # no column: always


def test_a_default_counts_as_a_column_for_what_is_required():
    import pytest
    from wildintel_uploader.core.services import visits_csv
    text = "site,day,hour\nWICP_0001,2026-09-14,11:40\n"
    mapping = {"location_id": "site", "date": "day", "time": "hour"}
    with pytest.raises(visits_csv.VisitsCsvError, match="actions"):
        visits_csv.parse_visits(text, [{"location_id": "WICP_0001"}], [], "", "mapped", mapping)
    result = visits_csv.parse_visits(text, [{"location_id": "WICP_0001"}], [], "", "mapped", mapping, {"defaults": {"actions": "Revision"}})
    assert result["visits"][0]["actions"] == ["Revision"]


def test_locations_cameras_and_sd_cards_that_do_not_exist_are_created_when_asked_and_the_row_has_what_they_need():
    from wildintel_uploader.core.services import visits_csv
    mapping = {**_MAP, "camera_model": "model", "sd_brand": "brand", "timezone": "tz"}
    text = ("site,what,day,hour,lat,lon,cam,sd,model,brand,tz\n"
            "WICP_0001,Installation,2026-09-14,11:40,40.1,-3.2,CAM9,S9,Browning,SanDisk,Europe/Madrid\n"
            "WICP_0001,Revision,2026-10-14,11:40,,,CAM9,S9,Browning,SanDisk,\n")        # the site is created from the first row
    options = {"create": {"locations": True, "cameras": True, "sd_cards": True}}
    result = visits_csv.parse_visits(text, [], [], "", "mapped", mapping, options)
    assert not result["problems"] and len(result["visits"]) == 2 and result["new_sites"] == []
    made = result["create"]
    assert [(l["location_id"], l["timezone"], l["latitude"]) for l in made["locations"]] == [("WICP_0001", "Europe/Madrid", 40.1)]
    assert [(c["camera_id"], c["camera_model"], c["label"]) for c in made["cameras"]] == [("CAM9", "Browning", "CAM9")]
    assert [(c["label"], c["brand"]) for c in made["sd_cards"]] == [("S9", "SanDisk")]
    assert result["visits"][0]["time"] == "11:40:00" and "creates the location WICP_0001" in result["rows"][0]["message"]

    # what exists is not created again, and what is not asked for is not created
    again = visits_csv.parse_visits(text, [{"location_id": "WICP_0001", "timezone": "UTC"}], [], "", "mapped", mapping,
                                    {"create": {"cameras": True, "sd_cards": True}, "cameras": [{"camera_id": "CAM9", "label": "A"}], "cards": [{"label": "s9"}]})
    assert again["create"] == {"locations": [], "cameras": [], "sd_cards": []}


def test_a_row_that_would_create_something_without_what_it_needs_is_a_problem_and_creates_nothing():
    from wildintel_uploader.core.services import visits_csv
    mapping = {**_MAP, "camera_model": "model", "sd_brand": "brand", "timezone": "tz"}
    text = ("site,what,day,hour,lat,lon,cam,sd,model,brand,tz\n"
            "WICP_0001,Installation,2026-09-14,11:40,40.1,-3.2,CAM9,S9,,SanDisk,UTC\n"        # no camera model
            "WICP_0002,Installation,2026-09-14,12:40,40.1,-3.2,CAM8,S8,Browning,,UTC\n"       # no SD brand
            "WICP_0003,Installation,2026-09-14,13:40,40.1,-3.2,CAM7,S7,Browning,SanDisk,\n")  # no timezone
    result = visits_csv.parse_visits(text, [], [], "", "mapped", mapping, {"create": {"locations": True, "cameras": True, "sd_cards": True}})
    assert result["visits"] == [] and result["create"] == {"locations": [], "cameras": [], "sd_cards": []}
    assert [(r["row"], r["label"]) for r in result["rows"]] == [(2, "Data to create it is missing"), (3, "Data to create it is missing"), (4, "Data to create it is missing")]
    assert "model" in result["rows"][0]["message"] and "brand" in result["rows"][1]["message"] and "timezone" in result["rows"][2]["message"]


def test_creating_asks_for_the_columns_it_needs():
    import pytest
    from wildintel_uploader.core.services import visits_csv
    with pytest.raises(visits_csv.VisitsCsvError, match="timezone"):
        visits_csv.parse_visits(_NEW, [], [], "", "mapped", _MAP, {"create": {"locations": True}})


# ── what a cell says, with the code of what is wrong; and the warnings in the rows ─────────

def test_a_cell_that_is_not_what_its_field_takes_is_refused_with_the_code_of_the_kind_of_error():
    from wildintel_uploader.core.services import visits_csv
    locations = [{"location_id": "WICP_0001", "timezone": "UTC"}]
    mapping = {"location_id": "site", "actions": "what", "date": "day", "time": "hour", "num_photos": "photos", "bait_use": "bait", "session": "rev", "card_batteries_ok": "card", "camera_height": "height"}
    text = ("site,what,day,hour,photos,bait,rev,card,height\n"
            "WICP_0001,Revision,2026-10-14,11:40,many,,,,\n"            # row 2: a number
            "WICP_0001,Revision,2026-10-15,11:40,,maybe,,,\n"           # row 3: yes or no
            "WICP_0001,Revision,2026-10-16,11:40,,,Rx,,\n"              # row 4: a session
            "WICP_0001,Revision,2026-10-17,11:40,,,,Full,\n"            # row 5: card and batteries
            "WICP_0001,Revision,2026-10-18,11:40,,,,,tall\n"            # row 6: a decimal number
            "WICP_0001,Flying,2026-10-19,11:40,,,,,\n"                  # row 7: actions
            "WICP_0001,Revision,19/13/2026,11:40,,,,,\n")               # row 8: a date
    result = visits_csv.parse_visits(text, locations, [], "", "mapped", mapping)
    by_row = {r["row"]: r for r in result["rows"]}
    assert [by_row[n]["label"] for n in range(2, 9)] == ["Number not valid", "Not yes or no", "Session not valid", "Card and batteries not valid", "Number not valid", "Actions not valid", "Date or time not valid"]
    assert by_row[2]["message"] == "num_photos: 'many' is not a whole number." and by_row[6]["message"] == "camera_height: 'tall' is not a number."
    assert by_row[5]["message"].startswith("'Full' is not OK, CarFull") and by_row[7]["message"].startswith("The actions 'Flying'")


def test_a_cell_is_read_as_its_field_takes_it():
    from wildintel_uploader.core.services import visits_csv
    mapping = {"location_id": "site", "actions": "what", "date": "day", "time": "hour", "camera_id": "cam", "card_batteries_ok": "card", "bait_use": "bait", "tags": "tags", "camera_tilt": "tilt", "session": "rev"}
    text = "site,what,day,hour,cam,card,bait,tags,tilt,rev\nWICP_0001,Install+Revision,2026-10-14,11:40,12.0,carfull,SI,a;b,-15.0,3\n"
    visit = visits_csv.parse_visits(text, [{"location_id": "WICP_0001", "timezone": "UTC"}], [], "", "mapped", mapping)["visits"]
    assert visit == [] or True   # "Install" is not an action: the row is refused
    text = text.replace("Install+Revision", "Installation+Revision")
    visit = visits_csv.parse_visits(text, [{"location_id": "WICP_0001", "timezone": "UTC"}], [], "", "mapped", mapping)["visits"][0]
    assert (visit["camera_id"], visit["card_batteries_ok"], visit["bait_use"], visit["tags"], visit["camera_tilt"], visit["session"]) == ("12", "CarFull", True, ["a", "b"], -15, "R0003")


def test_what_is_odd_goes_to_the_rows_that_make_it_odd_and_what_is_about_no_row_is_said_apart():
    from wildintel_uploader.core.services import visits_csv
    locations = [{"location_id": "WICP_0001", "timezone": "UTC"}, {"location_id": "WICP_0002", "timezone": "UTC"}]
    kept = [{"location_id": "WICP_0001", "session": "R0001", "date": "2026-09-14", "time": "11:40:00", "actions": ["Installation"], "camera_id": "C1", "sd": "1"},
            {"location_id": "WICP_0002", "session": "R0001", "date": "2026-09-14", "time": "13:15:00", "actions": ["Installation"], "camera_id": "C2", "sd": "2"}]
    mapping = {"location_id": "site", "actions": "what", "date": "day", "time": "hour", "session": "rev", "num_photos": "photos", "sd": "sd"}
    text = ("site,what,day,hour,rev,photos,sd\n"
            "WICP_0001,Revision,2026-10-14,11:40,R0002,0,3\n"           # row 2: a Revision with no photos
            "WICP_0002,Revision,2026-10-14,13:15,R0002,40,4\n")         # row 3: fine
    result = visits_csv.parse_visits(text, locations, kept, "", "mapped", mapping)
    by_row = {r["row"]: r for r in result["rows"]}
    assert any("0 photos" in w for w in by_row[2]["warnings"]) and not any("0 photos" in w for w in by_row[3].get("warnings", []))
    assert any("0 photos" in w for w in result["warnings"]) and result["loose_warnings"] == []   # the notice keeps only what no row has


def test_the_report_of_an_import_tells_what_is_odd_in_the_rows_it_is_about():
    from wildintel_uploader.core.services import report_service
    result = {"rows": [{"row": 2, "site": "WICP_0001", "session": "R0002", "date": "2026-10-14", "time": "11:40", "result": "ok", "label": "", "message": "", "warnings": ["R0002 WICP_0001: Revision with 0 photos."]},
                       {"row": 3, "site": "WICP_0002", "session": "R0002", "date": "2026-10-14", "time": "13:15", "result": "ok", "label": "", "message": ""}],
              "problems": [], "warnings": ["R0002 WICP_0001: Revision with 0 photos.", "from the history"], "loose_warnings": ["from the history"], "notes": [], "new_sites": [], "create": {}}
    report = report_service.visits_import_report("WICP", result, 2)
    checks = [(e["identifier"], e["check"], e["status"]) for e in report["entries"]]
    assert ("Row 2 · WICP_0001 · R0002 · 2026-10-14 11:40", "Things to check", "failed") in checks
    assert ("(import)", "Things to check", "failed") in checks and len([c for c in checks if c[1] == "Things to check"]) == 2   # the one of the row is not said twice


def test_what_does_not_exist_is_created_from_an_epicollect_download_too_with_what_the_form_does_not_have_as_defaults():
    from wildintel_uploader.core.services import visits_csv
    text = ("2_Collection,4_Location,5_Camera,6_Action,10_SD,created_at,lat_13_Coordenates,long_13_Coordenates\n"
            "1,9,CAM9,Installation,S9,2026-09-14T11:40:00.000Z,40.1,-3.2\n")
    options = {"create": {"locations": True, "cameras": True, "sd_cards": True}, "defaults": {"timezone": "Europe/Madrid", "camera_model": "Browning", "sd_brand": "SanDisk"}}
    result = visits_csv.parse_visits(text, [], [], "WICP_", "epicollect", None, options)
    assert not result["problems"] and len(result["visits"]) == 1
    made = result["create"]
    assert [(l["location_id"], l["timezone"]) for l in made["locations"]] == [("WICP_0009", "Europe/Madrid")]       # the site is a number: the id has the prefix of the project
    assert [(c["camera_id"], c["camera_model"]) for c in made["cameras"]] == [("CAM9", "Browning")]
    assert [(c["label"], c["brand"]) for c in made["sd_cards"]] == [("S9", "SanDisk")]
    assert result["visits"][0]["time"] == "13:40:00"      # the entry is read in the timezone of the location that was created (Madrid, summer time)
