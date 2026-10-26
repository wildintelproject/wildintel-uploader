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


def test_visits_are_registered_and_listed_with_those_to_one_location_apart(tmp_path: Path):
    with _in(tmp_path):
        _client().post("/api/deployment-import/research-projects/save", json=PROJECT)
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
        _client().post("/api/deployment-import/research-projects/save", json=PROJECT)
        for code in ("OK", "CarFull", "SinPilas", "CarFullSinPilas"):
            assert _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "card_batteries_ok": code}}).status_code == 200
        bad = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "card_batteries_ok": "Yes"}})

    assert bad.status_code == 422


def test_a_visit_that_is_not_one_is_refused(tmp_path: Path):
    with _in(tmp_path):
        _client().post("/api/deployment-import/research-projects/save", json=PROJECT)
        bad_session = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "session": "trip 3"}})
        bad_action = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "actions": ["Dance"]}})
        bad_latitude = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "latitude": 91, "longitude": 3}})

    no_action = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "actions": []}})

    assert bad_session.status_code == bad_action.status_code == bad_latitude.status_code == no_action.status_code == 422


def test_a_visit_can_do_several_things_each_kept_once(tmp_path: Path):
    with _in(tmp_path):
        _client().post("/api/deployment-import/research-projects/save", json=PROJECT)
        saved = _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": {**VISIT, "actions": ["Revision", "Desinstallation", "Revision"]}})

    assert saved.status_code == 200 and saved.json()["actions"] == ["Revision", "Desinstallation"]


def test_the_optional_details_of_a_deployment_are_kept_with_the_visit(tmp_path: Path):
    details = {"camera_model": "Reconyx-PC800", "camera_height": 1.2, "camera_tilt": -90, "bait_use": True, "feature_type": "trailHiking", "tags": ["forest edge"]}
    with _in(tmp_path):
        _client().post("/api/deployment-import/research-projects/save", json=PROJECT)
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

    assert [p["row"] for p in body["problems"]] == [2, 3, 4, 5]
    assert "not a location" in body["problems"][0]["message"] and "Dance" in body["problems"][1]["message"]
    assert [v["num_photos"] for v in body["visits"]] == [7]


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
    _client().post("/api/deployment-import/research-projects/save", json=PROJECT)
    for visit in visits:
        assert _client().post("/api/visits/save", json={"research_project_id": "DONA", "visit": visit}).status_code == 200


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
