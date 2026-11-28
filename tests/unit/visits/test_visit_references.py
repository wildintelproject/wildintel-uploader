"""#248: what a visit points to is a rule of the visits' domain (domain.references) — kept by id, told by what it is called — plain Python."""
from wildintel_uploader.modules.visits.domain import references


def _refs():
    return references.Refs([{"id": "L1", "location_id": "DONA_01", "timezone": "UTC"}], [{"id": "C1", "label": "CAM-1", "camera_id": "SN9"}],
                           [{"id": "S1", "label": "A13"}], [{"id": "T1", "name": "Ana", "username": "ana"}])


def test_a_visit_is_kept_by_the_ids_of_what_it_points_to_and_told_by_what_it_is_called():
    told = {"location_id": "dona_01", "date": "2026-01-02", "time": "10:00:00", "camera_id": "SN9", "sd": "A13", "trappers": "Ana, Someone"}
    kept = references.as_kept(told, _refs())
    assert (kept["location_ref"], kept["camera_ref"], kept["sd_ref"], kept["trapper_refs"], kept["trappers"]) == ("L1", "C1", "S1", ["T1"], "Someone")
    assert kept["when"] == "2026-01-02T10:00:00Z" and "location_id" not in kept and "date" not in kept
    again = references.as_told(kept, _refs())
    assert (again["location_id"], again["camera_id"], again["sd"], again["trappers"], again["date"]) == ("DONA_01", "CAM-1", "A13", "Ana, Someone", "2026-01-02")


def test_the_unknown_visits_point_to_their_location_by_id_when_it_is_there():
    locations = [{"id": "L1", "location_id": "DONA_01"}]
    kept = references.unknown_kept([{"location_id": "dona_01", "session": "R0002"}, {"location_id": "X", "session": "R0002"}], locations)
    assert kept == [{"location_ref": "L1", "session": "R0002"}, {"location_id": "X", "session": "R0002"}]
    assert references.unknown_told(kept, locations) == [{"location_id": "DONA_01", "session": "R0002"}, {"location_id": "X", "session": "R0002"}]
