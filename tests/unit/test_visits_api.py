"""/api/visits — the visits to the camera traps of a research project, kept in the collections folder (a temp folder)."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

PROJECT = {"name": "Doñana", "acronym": "DONA"}
VISIT = {"location_id": "DONA_01", "session": "R0013", "date": "2026-10-02", "time": "08:14:05", "actions": ["Revision"], "camera_id": "12", "num_photos": 1620, "trappers": "Ana, Luis", "setup_by": "Ana", "comments": "pilas cambiadas"}


def _client() -> TestClient:
    from wildintel_uploader.web.main import app
    return TestClient(app)


@contextmanager
def _in(tmp_path: Path):
    with patch("wildintel_uploader.web.api.routers.deployment_import.config.collections_dir", return_value=tmp_path), \
         patch("wildintel_uploader.web.api.routers.visits.config.collections_dir", return_value=tmp_path):
        yield


def _project() -> None:
    """The research project, with the locations the tests visit."""
    _client().post("/api/deployment-import/research-projects/save", json=PROJECT)
    for n in (1, 2, 3):
        _client().post("/api/deployment-import/locations/save", json={"research_project_id": "DONA", "location": {"location_id": f"DONA_0{n}", "name": f"Site {n}", "timezone": "UTC", "latitude": 37.0 + n / 100, "longitude": -6.5}})


def test_visits_are_registered_and_listed_with_those_to_one_location_apart(tmp_path: Path):
    with _in(tmp_path):
        _project()
        empty = _client().post("/api/visits/list", json={"research_project_id": "DONA"})
        saved = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": VISIT})
        _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "location_id": "DONA_02"}})
        everything = _client().post("/api/visits/list", json={"research_project_id": "DONA"}).json()["results"]
        one = _client().post("/api/visits/list", json={"research_project_id": "DONA", "location_id": "dona_01"}).json()["results"]

    assert empty.json() == {"results": []}
    assert saved.status_code == 200 and saved.json()["date"] == "2026-10-02" and saved.json()["time"] == "08:14:05"
    assert len(everything) == 2
    assert [v["location_id"] for v in one] == ["DONA_01"]


def test_how_the_card_and_the_batteries_were_is_one_of_the_codes_of_the_datasheet(tmp_path: Path):
    with _in(tmp_path):
        _project()
        for hour, code in enumerate(("OK", "CarFull", "SinPilas", "CarFullSinPilas")):
            visit = {**VISIT, "time": f"0{hour}:00:00", "card_batteries_ok": code}
            assert _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": visit}).status_code == 200
        bad = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "card_batteries_ok": "Yes"}})

    assert bad.status_code == 422


def test_a_visit_that_is_not_one_is_refused(tmp_path: Path):
    with _in(tmp_path):
        _project()
        bad_session = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "session": "trip 3"}})
        bad_action = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "actions": ["Dance"]}})
        bad_latitude = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "latitude": 91, "longitude": 3}})

    no_action = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "actions": []}})

    assert bad_session.status_code == bad_action.status_code == bad_latitude.status_code == no_action.status_code == 422


def test_a_visit_can_do_several_things_each_kept_once(tmp_path: Path):
    with _in(tmp_path):
        _project()
        saved = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "actions": ["Revision", "Desinstallation", "Revision"]}})

    assert saved.status_code == 200 and saved.json()["actions"] == ["Revision", "Desinstallation"]


def test_the_optional_details_of_a_deployment_are_kept_with_the_visit(tmp_path: Path):
    details = {"camera_model": "Reconyx-PC800", "camera_height": 1.2, "camera_tilt": -90, "bait_use": True, "feature_type": "trailHiking", "tags": ["forest edge"]}
    with _in(tmp_path):
        _project()
        saved = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, **details}})
        both = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "camera_height": 1.2, "camera_depth": 4.8}})
        bad_feature = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "feature_type": "moon"}})

    assert saved.status_code == 200 and saved.json() | details == saved.json()
    assert both.status_code == bad_feature.status_code == 422


def test_a_visit_to_a_research_project_that_is_not_kept_is_refused(tmp_path: Path):
    with _in(tmp_path):
        response = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": VISIT})

    assert response.status_code == 400


CSV = (
    "location_id,date,time,actions,trappers,card_batteries_ok,num_photos,sd,camera_id,comments\n"
    "DONA_01,2026-10-02,08:14:05,Installation,Ana,OK,,A13,P800,new camera\n"
    "dona_01,2026-11-05,09:00,Revision + Installation,Ana; Luis,CarFull,1620,B2,P800,\n"
    "DONA_02,2026-10-03,10:00:00,Stolen,,,,,X1,\n"
)


AUTO = object()  # the mapping the page starts from: the columns found by their names


def _import(tmp_path: Path, text: str, save: bool = False, fmt: str = "mapped", mapping=AUTO, **location):
    with _in(tmp_path):
        _client().post("/api/deployment-import/research-projects/save", json=PROJECT)
        for site, lat in (("DONA_01", 37.1), ("DONA_02", None), ("DONA_0001", 37.1)):
            _client().post("/api/deployment-import/locations/save", json={"research_project_id": "DONA", "location": {"location_id": site, "latitude": lat, "longitude": -6.4 if lat else None, **location}})
        if mapping is AUTO:
            mapping = _client().post("/api/visits/csv-columns", json={"csv": text}).json().get("mapping") if fmt == "mapped" else None
        return _client().post("/api/visits/import-csv", json={"research_project_id": "DONA", "csv": text, "save": save, "format": fmt, "mapping": mapping})


def test_visits_are_read_from_a_csv_and_only_kept_when_asked(tmp_path: Path):
    shown = _import(tmp_path, CSV)
    with _in(tmp_path):
        nothing = _client().post("/api/visits/list", json={"research_project_id": "DONA"}).json()["results"]

    body = shown.json()
    assert shown.status_code == 200 and body["saved"] is None and nothing == []
    assert body["problems"] == [] and body["skipped"] == 0
    first, third, second = body["visits"]  # by the day of the visit
    assert (first["location_id"], first["session"], first["actions"], first["latitude"]) == ("DONA_01", "R0001", ["Installation"], 37.1)
    assert (second["session"], second["actions"], second["card_batteries_ok"], second["num_photos"], second["time"]) == ("R0002", ["Revision", "Installation"], "CarFull", 1620, "09:00:00")
    assert (third["location_id"], third["session"], third["actions"], third["latitude"]) == ("DONA_02", "R0001", ["Stolen"], None)


def test_the_visits_of_a_csv_are_added_to_the_ones_kept_without_repeating_any(tmp_path: Path):
    _import(tmp_path, CSV, save=True)
    again = _import(tmp_path, CSV + "DONA_01,2026-12-01,08:00,Desinstallation,,,100,,P800,\n", save=True).json()
    with _in(tmp_path):
        kept = _client().post("/api/visits/list", json={"research_project_id": "DONA", "location_id": "DONA_01"}).json()["results"]

    assert again["skipped"] == 3 and again["saved"] == 1
    assert [v["session"] for v in kept] == ["R0001", "R0002", "R0003"]


def test_the_rows_that_are_not_visits_are_told_apart_from_those_that_are(tmp_path: Path):
    text = "location_id;date;time;actions;num_photos\nNOWHERE;2026-10-02;08:00;Revision;1\nDONA_01;2026-10-02;08:00;Dance;1\nDONA_01;2026/10/02;08:00;Revision;1\nDONA_01;2026-10-02;08:00;Revision;many\nDONA_01;02/10/2026;08:00;Revision;7\n"
    body = _import(tmp_path, text).json()

    assert [p["row"] for p in body["problems"]] == [3, 4, 5]
    assert "Dance" in body["problems"][0]["message"]
    assert [v["num_photos"] for v in body["visits"]] == [7]
    # a site that is not a location is no problem of the row: it is held, to be added or corrected
    assert [s["site"] for s in body["new_sites"]] == ["NOWHERE"]


def test_a_csv_without_the_columns_of_a_visit_is_refused(tmp_path: Path):
    bad = _import(tmp_path, "name,colour\nA,red\n")
    empty = _import(tmp_path, "")

    assert bad.status_code == empty.status_code == 400 and "no column for" in bad.json()["detail"]


def test_what_a_visit_has_of_a_deployment_is_read_too(tmp_path: Path):
    text = (
        "location_id,session,date,time,actions,trappers,status,card_batteries_ok,num_photos,sd,date_time_ok,camera_id,comments,longitude,latitude,"
        "camera_model,camera_interval,camera_height,camera_tilt,camera_heading,detection_distance,timestamp_issues,bait_use,feature_type,habitat,deployment_groups,tags\n"
        "DONA_01,13,2026-10-02,08:14,Revision,Ana,OK,SinPilas,1620,A13,Yes,P800,pilas cambiadas,-6.4,37.1,"
        "Reconyx-PC800,120,1.2,-90,45,9.5,no,yes,trailHiking,forest,north,forest edge|oak\n"
    )
    visit = _import(tmp_path, text).json()["visits"][0]

    assert (visit["session"], visit["actions"], visit["card_batteries_ok"], visit["num_photos"], visit["date_time_ok"], visit["comments"]) == ("R0013", ["Revision"], "SinPilas", 1620, "Yes", "pilas cambiadas")
    assert (visit["longitude"], visit["latitude"]) == (-6.4, 37.1)
    assert (visit["camera_model"], visit["camera_interval"], visit["camera_height"], visit["camera_tilt"], visit["camera_heading"], visit["detection_distance"]) == ("Reconyx-PC800", 120, 1.2, -90, 45, 9.5)
    assert (visit["timestamp_issues"], visit["bait_use"], visit["feature_type"], visit["habitat"], visit["deployment_groups"], visit["tags"]) == (False, True, "trailHiking", "forest", "north", ["forest edge", "oak"])


def test_the_dates_may_be_written_day_first(tmp_path: Path):
    body = _import(tmp_path, "location_id,date,time,actions\nDONA_01,02/10/2026,08:00,Installation\n").json()

    assert body["problems"] == [] and body["visits"][0]["date"] == "2026-10-02"


EPICOLLECT = (
    "ec5_uuid,created_at,1_Responsable,2_Collection,3_Date,4_Location,5_Camera,6_Action,7_Status_of_the_came,8_Card_Batteries,9_Number_of_pictures,10_SD,11_Date_and_hour,12_Observation,lat_13_Coordenates,long_13_Coordenates,14_Hour\n"
    "a1,2026-09-04T10:16:31.000Z,Ana,13,04/09/2026,1,5,Revision,OK,OK,1620,A13,Yes,all well,37.2,-6.5,12:16\n"
    "a2,2026-09-04T11:00:00.000Z,Ana,13,04/09/2026,DONA_02,7,Installation,,,,B2,Yes,,,,\n"
    "a3,2026-09-04T12:00:00.000Z,Ana,,04/09/2026,DONA_01,5,Revision,,,,,,,,,\n"
)


def test_an_epicollect_download_is_read_as_the_field_records_read_it(tmp_path: Path):
    body = _import(tmp_path, EPICOLLECT, fmt="epicollect").json()

    assert body["problems"] == [] and body["ignored"] == 1  # the entry of an old form, without a collection number
    first, second = body["visits"]
    assert (first["location_id"], first["session"], first["actions"], first["trappers"], first["camera_id"]) == ("DONA_0001", "R0013", ["Revision"], "Ana", "5")
    assert (first["date"], first["time"]) == ("2026-09-04", "10:16:31")  # created_at, in UTC: the location has no timezone
    assert (first["status"], first["card_batteries_ok"], first["num_photos"], first["sd"], first["date_time_ok"], first["comments"]) == ("OK", "OK", 1620, "A13", "Yes", "all well")
    assert (first["latitude"], first["longitude"]) == (37.2, -6.5)  # the coordinates of the entry, not the location's
    assert (second["location_id"], second["session"], second["actions"], second["card_batteries_ok"]) == ("DONA_02", "R0013", ["Installation"], None)


def test_the_time_of_an_entry_is_put_in_the_timezone_of_its_location(tmp_path: Path):
    summer = _import(tmp_path, EPICOLLECT, fmt="epicollect", timezone="Europe/Madrid").json()["visits"][0]
    standard = _import(tmp_path / "b", EPICOLLECT, fmt="epicollect", timezone="Europe/Madrid", ignore_dst=True).json()["visits"][0]

    assert summer["time"] == "12:16:31"
    assert standard["time"] == "11:16:31"


def test_the_donana_form_is_read_too_with_its_spanish_headers_and_codes(tmp_path: Path):
    text = (
        "created_at,1_Tramperos,2_Sesion,3_Fecha,4_Sitio,5_Camara,6_Accion,7_Estado,8_CardPilasOK,9_NumFotos,10_SD,11_FechaHoraOK,12_Observaciones,lat_13_Localizacin_actua,long_13_Localizacin_actua\n"
        "2026-09-04T10:16:31.000Z,Ana,12,04/09/2026,DONA_02,5,ROBADA,,,,,,gone,,\n"
        "2026-09-04T11:16:31.000Z,Ana,12,04/09/2026,1,6,I,,SinPilas,,A1,No,,,\n"
    )
    body = _import(tmp_path, text, fmt="epicollect").json()

    assert body["problems"] == []
    assert [(v["location_id"], v["session"], v["actions"]) for v in body["visits"]] == [("DONA_02", "R0012", ["Stolen"]), ("DONA_0001", "R0012", ["Installation"])]
    assert body["visits"][1]["card_batteries_ok"] == "SinPilas" and body["visits"][1]["date_time_ok"] == "No"


MAPPED = (
    "Lugar;Dia;Hora;Tarea;Quien;Fotos;Tarjeta;Ruido\n"
    "DONA_01;02/10/2026;08:14;Installation;Ana;;A13;x\n"
    "DONA_02;05/11/2026;09:30:15;Revision + Installation;Ana & Luis;1620;B2;y\n"
)
MAPPING = {"location_id": "Lugar", "date": "Dia", "time": "Hora", "actions": "Tarea", "trappers": "Quien", "num_photos": "Fotos", "sd": "Tarjeta"}


def test_a_csv_with_columns_of_its_own_is_read_with_the_columns_each_field_is_mapped_to(tmp_path: Path):
    body = _import(tmp_path, MAPPED, mapping=MAPPING).json()

    assert body["problems"] == []
    first, second = body["visits"]
    assert (first["location_id"], first["date"], first["time"], first["actions"], first["trappers"], first["sd"], first["num_photos"]) == ("DONA_01", "2026-10-02", "08:14:00", ["Installation"], "Ana", "A13", None)
    assert (second["location_id"], second["date"], second["actions"], second["num_photos"]) == ("DONA_02", "2026-11-05", ["Revision", "Installation"], 1620)


def test_a_mapping_that_leaves_out_what_a_visit_needs_is_refused(tmp_path: Path):
    no_actions = _import(tmp_path, MAPPED, mapping={k: v for k, v in MAPPING.items() if k != "actions"})
    no_time = _import(tmp_path, MAPPED, mapping={k: v for k, v in MAPPING.items() if k != "time"})
    nothing = _import(tmp_path, MAPPED, mapping=None)

    assert no_actions.status_code == no_time.status_code == nothing.status_code == 400
    assert "actions" in no_actions.json()["detail"] and "date and the time" in no_time.json()["detail"]


def test_the_columns_of_a_csv_are_offered_with_the_fields_and_the_column_that_most_likely_gives_each(tmp_path: Path):
    body = _client().post("/api/visits/csv-columns", json={"csv": "Site,Date,Time,Action,Sd,Whatever\nA,2026-10-02,08:00,Revision,B2,1\n"}).json()
    empty = _client().post("/api/visits/csv-columns", json={"csv": ""})

    assert body["columns"] == ["Site", "Date", "Time", "Action", "Sd", "Whatever"] and body["sample"] == [["A", "2026-10-02", "08:00", "Revision", "B2", "1"]]
    assert body["mapping"] == {"location_id": "Site", "date": "Date", "time": "Time", "actions": "Action", "sd": "Sd"}
    assert [f["field"] for f in body["fields"] if f["required"]] == ["location_id", "actions"]
    assert empty.status_code == 400


def _visit(day: str, actions: list[str], site: str = "DONA_01", **more) -> dict:
    return {**VISIT, "location_id": site, "date": day, "time": "09:00:00", "actions": actions, "num_photos": None, **more}


def _save_all(visits: list[dict]) -> None:
    """Keeps visits as they are, without the rules of a visit made by hand: these tests are about which of them are closed."""
    from wildintel_uploader.core import config
    from wildintel_uploader.core.schemas.requests import VisitRecord
    from wildintel_uploader.core.services import local_folder_service
    _project()
    local_folder_service.write_visits(config.collections_dir(), "DONA", [VisitRecord.model_validate(v).model_dump(mode="json") for v in visits])


def _closed() -> list[dict]:
    return _client().post("/api/visits/closed", json={"research_project_id": "DONA"}).json()["results"]


def test_a_visit_that_left_a_camera_is_closed_once_a_later_visit_collects_its_card(tmp_path: Path):
    with _in(tmp_path):
        _save_all([
            _visit("2026-06-10", ["Installation"]),
            _visit("2026-08-05", ["Revision"], num_photos=1620),
            _visit("2026-10-02", ["Desinstallation"], num_photos=300),
            _visit("2026-06-10", ["Installation"], site="DONA_02"),
        ])
        closed = _closed()

    # the installation and the revision left a card that was collected; the installation at DONA_02 is still out there
    assert [(c["visit"]["location_id"], c["visit"]["date"], c["end"]["date"]) for c in closed] == [("DONA_01", "2026-08-05", "2026-10-02"), ("DONA_01", "2026-06-10", "2026-08-05")]


def test_what_does_not_collect_a_card_leaves_the_visit_before_it_open(tmp_path: Path):
    with _in(tmp_path):
        _save_all([
            _visit("2026-06-10", ["Revision"], num_photos=10),                        # leaves a card; the next visit collects nothing
            _visit("2026-07-01", ["Installation"]),                                   # no card is taken
            _visit("2026-08-01", ["Revision"], num_photos=0),                         # an explicit 0 photos
            _visit("2026-09-01", ["Revision"], status="Not revised", num_photos=5),   # nothing collected
            _visit("2026-10-01", ["Stolen"]),                                         # the camera is gone
            _visit("2026-11-01", ["Revision"], num_photos=5),                         # the camera was stolen before
            _visit("2026-12-01", ["Revision"], num_photos=None),                      # the card was full, the count forgotten: still collected
        ])
        closed = _closed()

    assert [c["visit"]["date"] for c in closed] == ["2026-11-01"] and closed[0]["end"]["date"] == "2026-12-01"


def test_a_visit_linked_to_a_deployment_is_not_offered_again(tmp_path: Path):
    with _in(tmp_path):
        _save_all([_visit("2026-06-10", ["Installation"]), _visit("2026-08-05", ["Revision"], num_photos=1620)])
        linked = _client().post("/api/visits/link", json={"research_project_id": "DONA", "location_id": "dona_01", "date": "2026-06-10", "time": "09:00:00", "deployment_id": "R0001-DONA_01"})
        after = _closed()
        kept = _client().post("/api/visits/list", json={"research_project_id": "DONA"}).json()["results"]
        missing = _client().post("/api/visits/link", json={"research_project_id": "DONA", "location_id": "DONA_01", "date": "2030-01-01", "time": "09:00:00", "deployment_id": "x"})

    assert linked.status_code == 200 and after == []
    assert [v["deployment_id"] for v in kept] == ["R0001-DONA_01", None]
    assert missing.status_code == 400


# ── the rules of a visit: by hand they refuse it, in a CSV they question it ─────────────────────────────────────

def _save(visit: dict):
    return _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": visit})


def test_a_visit_by_hand_has_to_be_of_a_location_of_the_project_and_not_be_kept_already(tmp_path: Path):
    with _in(tmp_path):
        _project()
        elsewhere = _save({**VISIT, "location_id": "NOWHERE"})
        first = _save(VISIT)
        again = _save(VISIT)

    assert elsewhere.status_code == 422 and "not a location of the research project" in elsewhere.json()["detail"]
    assert first.status_code == 200
    assert again.status_code == 422 and "already a visit to DONA_01" in again.json()["detail"]


def test_a_visit_by_hand_lacks_nothing_its_actions_ask(tmp_path: Path):
    with _in(tmp_path):
        _project()
        no_camera = _save({**VISIT, "actions": ["Installation"], "camera_id": None, "sd": "A13"})
        no_card = _save({**VISIT, "actions": ["Installation"], "sd": None})
        no_photos = _save({**VISIT, "actions": ["Revision"], "num_photos": None})
        complete = _save({**VISIT, "actions": ["Installation"], "sd": "A13"})

    assert "The camera is required for Installation" in no_camera.json()["detail"]
    assert "The SD card left in the camera is required for Installation" in no_card.json()["detail"]
    assert "The photos on the card collected is required for Revision" in no_photos.json()["detail"]
    assert complete.status_code == 200


def test_a_camera_and_a_card_cannot_be_in_two_places_at_once(tmp_path: Path):
    install = {**VISIT, "actions": ["Installation"], "num_photos": None, "sd": "A13"}
    with _in(tmp_path):
        _project()
        _save(install)
        camera = _save({**install, "location_id": "DONA_02", "date": "2026-10-03", "sd": "B2"})       # the camera is at DONA_01
        card = _save({**install, "location_id": "DONA_02", "date": "2026-10-03", "camera_id": "99"})  # the card is in the camera at DONA_01
        after_collecting = _save({**VISIT, "actions": ["Desinstallation"], "date": "2026-10-05", "num_photos": 10})
        moved = _save({**install, "location_id": "DONA_02", "date": "2026-10-06"})

    assert "installed at DONA_01" in camera.json()["detail"]
    assert "is in the camera at DONA_01" in card.json()["detail"]
    assert after_collecting.status_code == 200 and moved.status_code == 200


def test_a_csv_keeps_the_visits_that_break_the_rules_and_says_what_is_odd(tmp_path: Path):
    text = (
        "location_id,date,time,actions,num_photos,sd,camera_id\n"
        "DONA_01,2026-10-02,08:00,Installation,,A13,P800\n"
        "DONA_02,2026-10-03,08:00,Installation,,B2,P800\n"      # the camera is at DONA_01
        "DONA_01,2026-10-04,08:00,Revision,,,P800\n"            # no photos counted
    )
    body = _import(tmp_path, text, save=True).json()

    assert body["saved"] == 3 and body["problems"] == []          # kept as the field wrote them
    assert any("camera P800 is at 2 sites" in w or "Camera P800 is installed at DONA_01" in w for w in body["warnings"])
    assert any("DONA_01" in w and "photos on the card collected is required" in w for w in body["warnings"])


def test_a_site_that_is_not_a_location_comes_back_as_new_or_misnamed(tmp_path: Path):
    text = (
        "location_id,date,time,actions,camera_id,latitude,longitude\n"
        "DONA_011,2026-10-02,08:00,Installation,P1,37.1001,-6.4\n"    # one character apart from DONA_01, and next to it
        "FAR_01,2026-10-03,08:00,Installation,P2,38.5,-5.0\n"         # nothing like it
    )
    body = _import(tmp_path, text, save=True).json()
    by_site = {s["site"]: s for s in body["new_sites"]}

    assert body["saved"] == 0 and body["visits"] == []             # held until the site is a location
    assert "DONA_01" in by_site["DONA_011"]["similar"] and by_site["DONA_011"]["nearest"]["location_id"] in ("DONA_01", "DONA_0001")
    assert by_site["DONA_011"]["nearest"]["distance_m"] < 50
    assert by_site["FAR_01"]["similar"] == [] and by_site["FAR_01"]["nearest"]["distance_m"] > 100000
    assert (by_site["FAR_01"]["latitude"], by_site["FAR_01"]["longitude"]) == (38.5, -5.0)


# ── the deployments the visits say, and the logs of their collections ───────────────────────────────────────────

def _field_visits() -> None:
    _save_all([
        # DONA_01: left on R0003, collected on R0004 — a closed deployment of R0003 — and a card left again, still out
        _visit("2024-09-04", ["Installation"], session="R0003", sd="A13", camera_id="P800", camera_model="Reconyx", setup_by="Ana", habitat="Pine", tags=["forest"], comments="new camera", camera_height=1.2, bait_use=True),
        _visit("2024-10-12", ["Revision"], session="R0004", sd="B2", camera_id="P800", num_photos=241, trappers="Luis", habitat="Scrub", tags=["pine", "forest"], comments="pilas", camera_height=1.5, bait_use=True),
        # DONA_02: left on R0003 and not collected yet — open
        _visit("2024-09-05", ["Installation"], site="DONA_02", session="R0003", sd="C7", camera_id="P900"),
    ])


def test_the_deployments_of_the_visits_are_closed_or_open_and_named_by_the_session_that_collects_them(tmp_path: Path):
    with _in(tmp_path):
        _field_visits()
        found = {d["deployment_id"]: d for d in _client().post("/api/visits/deployments", json={"research_project_id": "DONA"}).json()["results"]}

    closed, open_ = found["R0003-DONA_01"], found["R0004-DONA_01"]
    assert closed["status"] == "closed" and (closed["start"], closed["end"]) == ("2024-09-04T09:00:00Z", "2024-10-12T09:00:00Z")
    assert (closed["card"], closed["photos_counted"], closed["camera_id"]) == ("A13", 241, "P800")
    assert (closed["start_session"], closed["end_session"]) == ("R0003", "R0004")
    # the Revision of R0004 left a card too: still out, and the collection being completed (R0003 was the last trip's before it)
    assert open_["status"] == "open" and open_["card"] == "B2" and open_["end"] is None
    assert found["R0003-DONA_02"]["status"] == "open"                      # left on R0003, before the last trip R0004: the collection being completed


def test_what_the_two_visits_of_a_deployment_say_of_it_is_kept_beside_each_other(tmp_path: Path):
    with _in(tmp_path):
        _field_visits()
        closed = next(d for d in _client().post("/api/visits/deployments", json={"research_project_id": "DONA"}).json()["results"] if d["deployment_id"] == "R0003-DONA_01")

    assert closed["setup_by"] == "Setup: Ana | Retrieval: Luis"
    assert closed["fields"]["habitat"] == "Setup: Pine | Retrieval: Scrub"       # a text both say differently
    assert closed["fields"]["deploymentTags"] == "forest | pine"                 # the tags of both, once each
    assert closed["fields"]["cameraHeight"] == 1.2 and closed["fields"]["baitUse"] is True   # a number as the setup says it
    assert closed["comments"] == "Setup: new camera | Retrieval: pilas; cameraHeight 1.5 (setup 1.2)"


def test_the_logs_of_the_collections_are_written_with_every_deployment_closed_or_open(tmp_path: Path):
    import csv
    with _in(tmp_path):
        _field_visits()
        done = _client().post("/api/visits/field-logs", json={"research_project_id": "DONA"})

    assert done.status_code == 200
    by_collection = {c["collection"]: c for c in done.json()["collections"]}
    assert (by_collection["R0003"]["closed"], by_collection["R0003"]["open"]) == (1, 1)
    stamp = (tmp_path / "DONA" / "R0003" / "R0003_FileTimestampLog.csv").read_text(encoding="utf-8-sig").splitlines()
    assert stamp[1:] == ["r0003-dona_01,2024:09:04,09:00:00,2024:10:12,09:00:00"]            # only the closed one
    with (tmp_path / "DONA" / "R0003" / "R0003_FieldworkLog.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = {r["deploymentID"]: r for r in csv.DictReader(f)}
    assert set(rows) == {"R0003-DONA_01", "R0003-DONA_02"}                                    # the open one too
    assert rows["R0003-DONA_01"]["status"] == "closed" and rows["R0003-DONA_01"]["cardSD"] == "A13" and rows["R0003-DONA_01"]["photosCounted"] == "241"
    assert rows["R0003-DONA_02"]["status"] == "open" and rows["R0003-DONA_02"]["deploymentEnd"] == ""


# ── the folders and the logs made when a visit is registered ────────────────────────────────────────────────────

def test_the_folder_of_a_collection_and_its_logs_are_made_when_a_visit_closes_a_deployment(tmp_path: Path):
    install = {**VISIT, "actions": ["Installation"], "num_photos": None, "sd": "A13", "session": "R0003", "date": "2024-09-04", "time": "09:00:00"}
    collect = {**VISIT, "actions": ["Revision"], "sd": "B2", "num_photos": 241, "session": "R0004", "date": "2024-10-12", "time": "09:00:00"}
    with _in(tmp_path):
        _project()
        first = _save(install)
        # a camera left and not collected yet is an open deployment of the collection being completed: its folder and its FieldworkLog are made at once
        folder = tmp_path / "DONA" / "R0003"
        assert first.status_code == 200 and (folder / "collection.json").is_file() and (folder / "R0003_FieldworkLog.csv").is_file()
        assert not (folder / "R0003_FileTimestampLog.csv").exists()                  # nothing is closed yet
        second = _save(collect)

    assert second.json()["field_logs"]["collections"][0]["collection"] == "R0003"
    assert (folder / "R0003_FileTimestampLog.csv").read_text(encoding="utf-8-sig").splitlines()[1] == "r0003-dona_01,2024:09:04,09:00:00,2024:10:12,09:00:00"
    assert "closed" in (folder / "R0003_FieldworkLog.csv").read_text(encoding="utf-8-sig")


def test_the_visits_of_a_csv_make_the_folders_and_the_logs_of_their_collections_when_they_are_kept(tmp_path: Path):
    text = "location_id,date,time,actions,session,num_photos,sd,camera_id\nDONA_01,2024-09-04,09:00,Installation,R0003,,A13,P800\nDONA_01,2024-10-12,09:00,Revision,R0004,241,B2,P800\n"
    shown = _import(tmp_path, text)
    assert not (tmp_path / "DONA" / "R0003").exists()                               # only reading: nothing is made
    kept = _import(tmp_path, text, save=True).json()

    assert kept["saved"] == 2 and [c["collection"] for c in kept["field_logs"]["collections"]] == ["R0003", "R0004"]
    assert (tmp_path / "DONA" / "R0003" / "R0003_FileTimestampLog.csv").is_file() and (tmp_path / "DONA" / "R0004" / "R0004_FieldworkLog.csv").is_file()
    assert shown.status_code == 200


# ── the history of visits: an .xlsx that completes the visits kept before a file's are applied ──────────────────

def _workbook(rows: list[list]) -> str:
    import base64
    import io

    import openpyxl
    book = openpyxl.Workbook()
    for row in rows:
        book.active.append(row)
    out = io.BytesIO()
    book.save(out)
    return base64.b64encode(out.getvalue()).decode()


HISTORY = [
    ["Trappers", "Session", "Date", "Time", "Site", "Camera", "Action", "NumPhotos", "SD"],
    ["Ana", "R0003", "2024-09-04", "09:00:00", "DONA_01", "P800", "Installation", None, "A13"],
]


def test_a_history_completes_the_visits_kept_and_the_file_is_applied_on_top(tmp_path: Path):
    csv_text = "location_id,date,time,actions,session,num_photos,sd,camera_id\nDONA_01,2024-10-12,09:00,Revision,R0004,241,B2,P800\n"
    with _in(tmp_path):
        _project()
        mapping = _client().post("/api/visits/csv-columns", json={"csv": csv_text}).json()["mapping"]
        body = {"research_project_id": "DONA", "csv": csv_text, "format": "mapped", "mapping": mapping, "history_xlsx": _workbook(HISTORY)}
        shown = _client().post("/api/visits/import-csv", json=body).json()
        kept = _client().post("/api/visits/import-csv", json={**body, "save": True}).json()
        listed = _client().post("/api/visits/list", json={"research_project_id": "DONA"}).json()["results"]

    assert shown["history"] == 1 and [v["session"] for v in shown["visits"]] == ["R0003", "R0004"]      # the history first, then the file's
    assert kept["saved"] == 2 and [v["session"] for v in listed] == ["R0003", "R0004"]
    # the Revision of the file collects the deployment the history left: no warning about a card still in the camera, and the log has it
    assert not any("is in the camera at" in w for w in kept["warnings"])
    assert "closed" in (tmp_path / "DONA" / "R0003" / "R0003_FieldworkLog.csv").read_text(encoding="utf-8-sig")


def test_a_history_that_is_not_a_workbook_with_visits_is_refused(tmp_path: Path):
    import base64
    with _in(tmp_path):
        _project()
        csv_text = "location_id,date,time,actions\nDONA_01,2024-10-12,09:00,Installation\n"
        mapping = _client().post("/api/visits/csv-columns", json={"csv": csv_text}).json()["mapping"]
        base = {"research_project_id": "DONA", "csv": csv_text, "format": "mapped", "mapping": mapping}
        not_xlsx = _client().post("/api/visits/import-csv", json={**base, "history_xlsx": base64.b64encode(b"a,b\n1,2\n").decode()})
        no_visits = _client().post("/api/visits/import-csv", json={**base, "history_xlsx": _workbook([["name", "colour"], ["A", "red"]])})

    assert not_xlsx.status_code == 400 and ".xlsx" in not_xlsx.json()["detail"]
    assert no_visits.status_code == 400 and "history of visits" in no_visits.json()["detail"]


def test_a_closed_visit_comes_with_what_its_two_visits_say_of_the_deployment_mixed_as_the_log_mixes_them(tmp_path: Path):
    with _in(tmp_path):
        _field_visits()
        closed = _closed()

    details = next(c["details"] for c in closed if c["visit"]["session"] == "R0003" and c["visit"]["location_id"] == "DONA_01")
    assert details["setup_by"] == "Setup: Ana | Retrieval: Luis" and details["camera_id"] == "P800"
    assert details["habitat"] == "Setup: Pine | Retrieval: Scrub" and details["tags"] == ["forest", "pine"]
    assert details["camera_height"] == 1.2 and details["bait_use"] is True                  # the setup's number
    assert details["comments"] == "Setup: new camera | Retrieval: pilas; cameraHeight 1.5 (setup 1.2)"


# ── the settings of the field records, and what the engine of the field records also says ───────────────────────

def _parse(text: str, kept=None, options=None, fmt="epicollect", sites=("DONA_01", "DONA_02", "DONA_03")):
    from wildintel_uploader.core.services import visits_csv
    locations = [{"location_id": s, "timezone": "UTC", "ignore_dst": False, "latitude": 37.0, "longitude": -6.4} for s in sites]
    return visits_csv.parse_visits(text, locations, kept or [], "DONA_", fmt, None, options)


EPI_HEADER = "created_at,1_Responsable,2_Collection,3_Date,4_Location,5_Camera,6_Action,9_Number_of_pictures,10_SD,14_Hour\n"


def test_the_time_of_a_visit_is_when_its_entry_was_created_or_the_date_and_the_hour_typed(tmp_path: Path):
    text = EPI_HEADER + "2024-09-04T11:10:00.000Z,Ana,R0003,2024-09-04,DONA_01,P800,Installation,,A13,12:30\n"

    created = _parse(text)["visits"][0]
    typed = _parse(text, options={"time_source": "hour"})["visits"][0]

    assert (created["date"], created["time"], created["when"]) == ("2024-09-04", "11:10:00", "2024-09-04T11:10:00Z")
    assert (typed["date"], typed["time"], typed["when"]) == ("2024-09-04", "12:30:00", "2024-09-04T12:30:00Z")   # the hour typed in the form


def test_the_columns_of_a_form_named_otherwise_are_said_in_the_settings(tmp_path: Path):
    text = "created_at,Quien,Viaje,Donde,Que,Camara\n2024-09-04T11:10:00.000Z,Ana,R0003,DONA_01,Installation,P800\n"
    import pytest

    from wildintel_uploader.core.services import visits_csv
    with pytest.raises(visits_csv.VisitsCsvError, match="no column for: location_id, actions"):   # 'Donde' and 'Que' are not names it knows
        _parse(text)
    with_settings = _parse(text, options={"columns": {"trappers": "Quien", "session": "Viaje", "location_id": "Donde", "actions": "Que"}})

    assert with_settings["problems"] == []
    [visit] = with_settings["visits"]
    assert (visit["location_id"], visit["session"], visit["trappers"], visit["actions"]) == ("DONA_01", "R0003", "Ana", ["Installation"])


def test_the_date_typed_that_differs_from_the_day_of_the_entry_is_warned_of():
    text = EPI_HEADER + "2024-09-04T23:50:00.000Z,Ana,R0003,2024-09-05,DONA_01,P800,Installation,,A13,12:30\n"

    assert any("the date typed, 2024-09-05, differs from the day of the entry, 2024-09-04" in w for w in _parse(text)["warnings"])


def test_the_session_numbers_that_jump_are_warned_of_and_the_sites_not_visited_are_told_as_notes():
    kept = [{"location_id": "DONA_01", "session": "R0003", "when": "2024-09-04T09:00:00Z", "date": "2024-09-04", "time": "09:00:00", "actions": ["Installation"], "camera_id": "P800", "sd": "A13"},
            {"location_id": "DONA_02", "session": "R0003", "when": "2024-09-04T10:00:00Z", "date": "2024-09-04", "time": "10:00:00", "actions": ["Installation"], "camera_id": "P900", "sd": "B2"}]
    text = EPI_HEADER + "2024-11-05T09:00:00.000Z,Ana,R0005,2024-11-05,DONA_01,P800,Revision,50,C7,09:00\n"
    result = _parse(text, kept=kept)

    assert "Session numbers jump from R0003 to R0005." in result["warnings"]
    text = EPI_HEADER + "2024-10-12T09:00:00.000Z,Ana,R0004,2024-10-12,DONA_01,P800,Revision,50,C7,09:00\n"
    assert any(n.startswith("R0004: sites visited in R0003 and not on this trip, their cameras still out: DONA_02") for n in _parse(text, kept=kept)["notes"])


def test_a_row_that_is_a_visit_kept_already_by_its_session_site_camera_and_actions_is_left_as_it_is():
    kept = [{"location_id": "DONA_01", "session": "R0003", "when": "2024-09-04T09:00:00Z", "date": "2024-09-04", "time": "09:00:00", "actions": ["Installation"], "camera_id": "P800", "sd": "A13"}]
    # the same visit, with the time of the entry instead of the one written in the datasheet
    text = EPI_HEADER + "2024-09-04T09:07:00.000Z,Ana,R0003,2024-09-04,DONA_01,P800,Installation,,A13,12:30\n"
    result = _parse(text, kept=kept)

    assert result["visits"] == [] and result["skipped"] == 1


def test_the_seconds_are_cut_from_the_logs_unless_they_are_kept_and_an_import_leaves_its_report(tmp_path: Path):
    from unittest.mock import patch

    from wildintel_uploader.core import config
    text = ("location_id,date,time,actions,session,num_photos,sd,camera_id\nDONA_01,2024-09-04,09:00:41,Installation,R0003,,A13,P800\n"
            "DONA_01,2024-10-12,09:05:17,Revision,R0004,241,B2,P800\n")
    for keep, expected in ((False, "09:00:00,2024:10:12,09:05:00"), (True, "09:00:41,2024:10:12,09:05:17")):
        root = tmp_path / str(keep)
        root.mkdir()
        settings = config.Settings.model_validate({"FIELDLOG": {"keep_seconds": keep}})
        with patch("wildintel_uploader.web.api.routers.visits.config.load_settings", return_value=settings):
            body = _import(root, text, save=True).json()
        stamp = (root / "DONA" / "R0003" / "R0003_FileTimestampLog.csv").read_text(encoding="utf-8-sig").splitlines()[1]
        assert stamp.endswith(expected), (keep, stamp)
    report = Path(body["report"])
    assert report.parent == root / "DONA" and report.name.startswith("visits_import_") and "Visits kept to DONA: 2" in report.read_text(encoding="utf-8")


def test_a_revision_is_of_the_camera_that_is_at_the_site_unless_the_visit_also_installs_another(tmp_path: Path):
    install = {**VISIT, "actions": ["Installation"], "num_photos": None, "sd": "A13", "camera_id": "P800", "date": "2024-09-04", "session": "R0003"}
    with _in(tmp_path):
        _project()
        _save(install)
        other = _save({**VISIT, "actions": ["Revision"], "camera_id": "P999", "num_photos": 10, "sd": "B2", "date": "2024-10-12", "session": "R0004"})
        same = _save({**VISIT, "actions": ["Revision"], "camera_id": "p800", "num_photos": 10, "sd": "B2", "date": "2024-10-12", "session": "R0004"})
        swapped = _save({**VISIT, "actions": ["Revision", "Installation"], "camera_id": "P999", "num_photos": 10, "sd": "C7", "date": "2024-11-12", "session": "R0005"})

    assert other.status_code == 422 and "The camera at DONA_01 is P800" in other.json()["detail"] and "add an Installation" in other.json()["detail"]
    assert same.status_code == 200                                  # the camera that is there, whatever its case
    assert swapped.status_code == 200                               # the camera was replaced: the visit says so


def test_the_visit_book_gives_each_visit_the_deployment_it_started_closed_or_open(tmp_path: Path):
    with _in(tmp_path):
        _field_visits()
        book = _client().post("/api/visits/book", json={"research_project_id": "DONA"}).json()["results"]

    by = {(v["location_id"], v["session"]): v for v in book}
    assert (by[("DONA_01", "R0003")]["deployment"], by[("DONA_01", "R0003")]["deployment_status"]) == ("R0003-DONA_01", "closed")
    assert (by[("DONA_01", "R0004")]["deployment"], by[("DONA_01", "R0004")]["deployment_status"]) == ("R0004-DONA_01", "open")   # it left a card again: still out
    assert (by[("DONA_02", "R0003")]["deployment"], by[("DONA_02", "R0003")]["deployment_status"]) == ("R0003-DONA_02", "open")


def test_the_visit_book_has_a_row_for_each_location_that_was_not_visited_in_a_session(tmp_path: Path):
    with _in(tmp_path):
        _field_visits()   # DONA_01 and DONA_02 are visited in R0003, DONA_01 alone in R0004; the project has DONA_01, DONA_02 and DONA_03
        _client().post("/api/deployment-import/locations/save", json={"research_project_id": "DONA", "location": {"location_id": "DONA_04", "status": "retired"}})
        book = _client().post("/api/visits/book", json={"research_project_id": "DONA"}).json()["results"]

    not_done = sorted((v["session"], v["location_id"]) for v in book if v["not_done"])
    assert not_done == [("R0003", "DONA_03"), ("R0004", "DONA_02"), ("R0004", "DONA_03")]       # DONA_04 is retired: left out
    assert all(v["actions"] == [] and v["date"] == "" for v in book if v["not_done"])
    assert sum(1 for v in book if not v["not_done"]) == 3                                           # the visits are the ones made
